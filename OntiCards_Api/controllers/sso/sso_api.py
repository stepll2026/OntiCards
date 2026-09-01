"""
 @File: sso_api.py
 @Description: SSO单点登录控制器
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-04-13
"""

from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, redirect
import jwt
import flask_login
import threading
import time
import os

from extensions.ext_database import db
from models.users import User
from controllers.weaviate_db_tool.weaviate_api import ensure_user_collection_exists

sso_bp = Blueprint('sso', __name__, url_prefix='/sso')

# 获取flask_login的login_user函数
login_user = flask_login.login_user


def get_sso_secret_key():
    """获取SSO共享密钥

    ⚠️ 配置说明：
    - 生产环境：请设置环境变量 SSO_SECRET_KEY
    - 本地开发：使用默认值 'my_jwt_secret_key_123'（仅用于测试）
    """
    import os
    from environs import Env
    env = Env()
    # 生产环境务必设置此环境变量
    return env.str('SSO_SECRET_KEY', 'onticards_sso_secret_key_for_step2')


# ============================================================
# SSO 限流（防滥用 / 防容器 OOM）
#
# 背景：合作方通过 SSO 入口图标调用 /sso/login 时，如果接入姿势异常
#       （iframe 反复加载、定时轮询、路由拦截误触），请求量会被放大
#       数十~数百倍，导致日志磁盘快速增长，最终触发容器层 OOM。
#
# 设计：内存版滑动窗口（不引入第三方依赖）
#   - 每个 gunicorn worker 进程独立计数（单容器部署，按当前配置 2 worker）
#   - IP 维度：防止单个客户端打爆
#   - 全局维度：防止多客户端汇聚打爆
#   - 滑动窗口 60 秒
#   - 线程安全（gthread 模式下同进程内多线程共享）
#
# 调优环境变量：
#   SSO_RATE_LIMIT_PER_IP       每 IP 每分钟最大请求数（默认 60）
#   SSO_RATE_LIMIT_GLOBAL       每 worker 每分钟最大请求数（默认 600）
#   SSO_RATE_LIMIT_ENABLED      0 关闭；1 启用（默认 1）
# ============================================================
_rate_limit_lock = threading.Lock()
_rate_limit_ip = {}        # ip -> [timestamps]
_rate_limit_global = []    # [timestamps]


def _rate_limit_check():
    """返回 (allowed: bool, retry_after: int)。"""
    if os.getenv('SSO_RATE_LIMIT_ENABLED', '1') == '0':
        return True, 0

    now = time.time()
    window_start = now - 60
    per_ip_limit = int(os.getenv('SSO_RATE_LIMIT_PER_IP', '60') or '60')
    global_limit = int(os.getenv('SSO_RATE_LIMIT_GLOBAL', '600') or '600')

    with _rate_limit_lock:
        # 1. 全局窗口
        _rate_limit_global[:] = [t for t in _rate_limit_global if t >= window_start]
        if len(_rate_limit_global) >= global_limit:
            return False, 60

        # 2. IP 窗口
        # 兼容反向代理：优先取 X-Forwarded-For 的第一个
        ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
              or request.remote_addr or 'unknown')
        arr = _rate_limit_ip.setdefault(ip, [])
        arr[:] = [t for t in arr if t >= window_start]
        if len(arr) >= per_ip_limit:
            return False, 60

        arr.append(now)
        _rate_limit_global.append(now)
        return True, 0


def _client_ip():
    ip = (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
          or request.remote_addr or 'unknown')
    return ip


@sso_bp.route('/login', methods=['GET'])
def sso_login():
    """
    SSO登录入口（供第三方系统跳转调用）

    URL示例: /sso/login?token=xxx
    """
    # ============================================================
    # 限流检查：放在最前面，避免消耗 JWT 解码 / DB 查询 / Weaviate
    # ============================================================
    allowed, retry_after = _rate_limit_check()
    if not allowed:
        from flask import make_response
        resp = make_response(jsonify({
            "error": "请求过于频繁，请稍后重试",
            "client_ip": _client_ip(),
            "retry_after": retry_after,
        }), 429)
        resp.headers['Retry-After'] = str(retry_after)
        return resp

    token = request.args.get('token')

    if not token:
        return jsonify({"error": "缺少token参数"}), 400

    try:
        # 验证JWT token
        secret_key = get_sso_secret_key()
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])

        # 提取用户信息
        username = payload.get('username')
        idp_user_id = payload.get('user_id')  # 对方系统的用户ID
        idp_source = payload.get('source', 'default')  # 来源标识，默认default
        nickname = payload.get('nickname', username)
        email = payload.get('email')

        if not username or not idp_user_id:
            return jsonify({"error": "token中缺少必要的用户信息"}), 400

        # 查询或创建用户
        user = _get_or_create_user(
            idp_user_id=idp_user_id,
            idp_source=idp_source,
            username=username,
            nickname=nickname,
            email=email
        )

        # 更新登录时间
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # 执行本地登录（flask_login）
        login_user(user)

        # 生成返回给前端的token（与普通登录接口格式一致）
        from core.passport import PassportService
        user_token = PassportService.get_account_jwt_token(user)

        # 返回JSON格式（前端可以直接使用）
        # 同时支持 redirect_url 参数，实现重定向跳转
        redirect_url = request.args.get('redirect_url')
        
        if redirect_url:
            # 重定向到前端页面，把我们的token放在URL参数中
            # 参数名用 access_token 明确区分
            separator = '&' if '?' in redirect_url else '?'
            redirect_url_with_token = f"{redirect_url}{separator}access_token={user_token}"
            return redirect(redirect_url_with_token)
        else:
            return jsonify({
                "data": {
                    "token": user_token,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "nickname": user.nickname,
                        "role": user.role
                    }
                }
            })

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "token已过期"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "token无效"}), 401
    except Exception as e:
        return jsonify({"error": f"登录失败: {str(e)}"}), 500


def _get_or_create_user(idp_user_id: str, idp_source: str, username: str, nickname: str, email: str = None):
    """
    根据第三方用户信息，查询或创建本地用户

    Args:
        idp_user_id: 第三方系统用户ID
        idp_source: 第三方来源标识
        username: 用户名
        nickname: 昵称
        email: 邮箱

    Returns:
        User: 本地用户对象
    """
    # 1. 尝试通过SSO标识查找已存在用户
    user = User.query.filter_by(
        idp_user_id=idp_user_id,
        idp_source=idp_source
    ).first()

    if user:
        return user

    # 2. 检查username是否已被本地用户使用（SSO用户不使用本地密码）
    existing_by_username = User.query.filter_by(username=username).first()
    if existing_by_username and existing_by_username.idp_user_id is None:
        # 如果存在一个非SSO的本地用户，重命名为 username_sso 以避免冲突
        new_username = f"{username}_sso"
        counter = 1
        while User.query.filter_by(username=new_username).first():
            counter += 1
            new_username = f"{username}_sso_{counter}"

        existing_by_username.username = new_username
        db.session.commit()

    # 3. 创建新的SSO用户
    user = User(
        username=username,
        nickname=nickname,
        email=email,
        password='',  # SSO用户不需要本地密码
        password_salt='',
        status='normal',
        role='normal',  # 默认普通用户，可手动调整为admin
        idp_user_id=idp_user_id,
        idp_source=idp_source,
    )
    db.session.add(user)
    db.session.flush()  # 获取user.id

    # 4. 为用户创建独立的Weaviate向量空间
    user.weaviate_class_name = User.build_weaviate_class_name(user.id)
    db.session.commit()

    # 5. 创建Weaviate collection
    ensure_user_collection_exists(user.weaviate_class_name)

    return user


@sso_bp.route('/config', methods=['GET'])
def sso_config():
    """
    获取SSO配置信息（供调试和接入使用）
    返回示例：
    {
        "callback_url": "https://your-domain/sso/login",
        "token_format": {...},
        "required_fields": ["username", "user_id"]
    }
    """
    from flask import url_for, request as flask_request
    callback_url = url_for('sso.sso_login', _external=True)

    config = {
        "callback_url": callback_url,
        "required_fields": {
            "username": "string - 必填，用户唯一标识",
            "user_id": "string - 必填，第三方系统用户ID",
            "nickname": "string - 可选，用户昵称",
            "email": "string - 可选，用户邮箱",
            "source": "string - 可选，来源标识，默认default"
        },
        "token_expiry": "建议5分钟",
        "algorithm": "HS256"
    }

    return jsonify(config)