# -*- coding: utf-8 -*-
import datetime
import io
import os
import sys
import time
import traceback
import uuid
from decimal import Decimal

from environs import Env
from flask import Flask, g, request, Response
# 禁用 Flask 写入 session cookie 的机制
from flask.sessions import SecureCookieSessionInterface
from flask_cors import CORS
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError

import views
from config import Config, get_env
from controllers import init_app
from core import log
from core.admin_bootstrap import ensure_admin, initialize_bootstrap_state
from core.admin_collection import ensure_account_collection
from core.readiness import ReadinessProbe
from core.request_logging import redact_mapping, redact_url
from extensions import ext_database, ext_migrate, ext_login
from extensions.ext_database import db

# ===== 修复 Windows 控制台中文乱码问题 =====
if sys.platform == 'win32':
    # 1. 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 2. 设置控制台代码页为 UTF-8 (65001)
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    
    # 3. 包装 sys.stdout 和 sys.stderr，处理编码错误
    class SafeStreamWrapper(io.TextIOWrapper):
        """安全的流包装器，自动处理编码问题"""
        def write(self, text):
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='replace')
            try:
                # 尝试直接写入
                return super().write(text)
            except UnicodeEncodeError:
                # 如果失败，尝试使用 GBK 编码（Windows 默认）
                try:
                    encoded = text.encode('gbk', errors='replace').decode('gbk', errors='replace')
                    return super().write(encoded)
                except Exception:
                    # 最后的兜底：替换所有无法编码的字符
                    safe_text = text.encode('ascii', errors='replace').decode('ascii')
                    return super().write(safe_text)
    
    # 4. 替换标准输出流
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = SafeStreamWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = SafeStreamWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )
    except Exception:
        pass

class DisabledSessionInterface(SecureCookieSessionInterface):
    def save_session(self, *args, **kwargs):
        pass

def create_app():
    env = Env()
    env.read_env()
    app_path = os.path.dirname(os.path.abspath(__file__))

    app = Flask(
        __name__,
        template_folder=f'{app_path}/templates',
        static_folder=f'{app_path}/static'
    )

    def decimal_default(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (bytes, bytearray, memoryview)):
            try:
                return bytes(obj).decode("utf-8", "ignore")
            except Exception:
                return str(obj)
        # 最后兜底，避免 TypeError 把整个响应打爆
        return str(obj)

    app.config['RESTFUL_JSON'] = {
        'ensure_ascii': False,
        'default': decimal_default,
    }

    # ============================================================
    # PR-F: 请求体大小硬上限（防任意接口被恶意上传大文件导致 OOM）
    #
    # 背景：Flask/Werkzeug 默认不限制请求体大小。若攻击者 POST 一个
    # 几 GB 的 body，Werkzeug 会尝试完整读入内存才报错，单 worker 瞬间
    # 内存爆满 → 触发 worker_memory_limit SIGKILL → 接口 5xx 抖动。
    #
    # 修复：设 MAX_CONTENT_LENGTH=50MB。超过直接返回 413，不读内存。
    # 为什么是 50MB：
    #   - 业务最大合法请求体（数据卡片导入、字典上传）实测 < 10MB
    #   - 留 5x 余量，防止业务小幅增长撞线
    #   - 不会误伤正常请求
    # ============================================================
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

    # 禁用写入 session cookie
    app.session_interface = DisabledSessionInterface()

    app.config.from_object(Config())
    log.init(app)
    init_app(app)
    ext_migrate.init(app, db)
    ext_database.init_app(app)
    ext_login.init_app(app)
    # ext_weaviate.init_app(app)
    views.init(app)

    @app.cli.command("initialize-schema")
    def initialize_schema_command():
        """Initialize a new database before running online migrations."""
        ensure_database_initialized(app)

    from models.users import User
    with app.app_context():
        readiness = ReadinessProbe(db.engine.url, User.__table__, get_env("WEAVIATE_URL"))
    app.add_url_rule("/readyz", view_func=readiness, endpoint="readiness", methods=["GET"])

    # 删除了旧的 cookie 相关配置（不再需要）

    app.add_url_rule('/favicon.ico', '', redirect_to='/static/favicon.ico')

    # --------------- CORS 配置 ---------------
    origins = env.list("ALLOWED_ORIGINS", ["http://localhost:3000"])  # 允许的域名列表
    CORS(app, resources={r"/*": {"origins": origins}}, supports_credentials=True)

    @app.before_request
    def beforeRequest():
        g.env = env
        g.app_path = app_path
        g.root_path = app_path
        app.logger.info("%s %s", request.method, redact_url(request.url))
        if request.form:
            app.logger.info("form=%s", redact_mapping(request.form))

    @app.after_request
    def afterRequest(resp: Response):
        # 跳过文件下载等非 JSON 响应的内容日志输出
        content_type = resp.content_type or ''
        content_disposition = resp.headers.get('Content-Disposition', '')

        # 如果是文件下载（包含 Content-Disposition: attachment）或非文本响应，不输出内容日志
        if 'attachment' in content_disposition.lower() or not content_type.startswith(('application/json', 'text/')):
            pass  # 跳过内容日志输出
        elif not resp.is_streamed:
            try:
                # 使用 UTF-8 解码响应数据，限制日志长度避免过大
                resp_text = resp.data.decode("utf-8", errors='replace')

                # ============================================================
                # 安全/资源防护：脱敏敏感字段，避免日志膨胀触发磁盘满→OOM
                #
                # 背景：合作方通过 SSO 入口图标调用 /sso/login，响应体中包含
                #       access_token（明文 JWT）。当接入姿势异常（例如定时轮询、
                #       iframe 重载、路由拦截误触）时，请求量会被放大数十~数百倍，
                #       access_token 全文落盘会使日志文件快速增长，最终磁盘满
                #       → 数据库写入失败 → 内存累积 → OOM Killer 杀容器。
                #
                # 措施：
                #   1. 命中敏感字段（access_token / password / token / secret）
                #      时，整条响应体只输出状态码+长度，不打印正文。
                #   2. 响应体过大（> 500 字符）时已截断；这里对 SSO 路径额外压缩。
                # ============================================================
                _sensitive_markers = ('"access_token"', '"password"', '"token"', '"secret"')
                if any(marker in resp_text for marker in _sensitive_markers):
                    app.logger.info(f"[redacted: sensitive response, status={resp.status_code}, len={len(resp_text)}]")
                elif len(resp_text) > 500:
                    app.logger.info(resp_text[:500] + f"... [truncated, total {len(resp_text)} chars]")
                else:
                    app.logger.info(resp_text)
            except Exception as e:
                app.logger.debug(f"Failed to decode response data: {e}")

        # **动态设置 Access-Control-Allow-Origin**，以防止 CORS 失效
        origin = request.headers.get('Origin')
        if origin and origin in origins:
            resp.headers['Access-Control-Allow-Origin'] = origin
            resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
            resp.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
            resp.headers['Access-Control-Allow-Credentials'] = 'true'  # 允许携带 Cookie
            # 暴露 Content-Disposition 等 headers，让前端 JavaScript 可以访问
            resp.headers['Access-Control-Expose-Headers'] = 'Content-Disposition, Content-Length, Content-Type'
        return resp

    # ============================================================
    # /health 健康检查端点（单容器场景下的诊断接口）
    #
    # 作用：
    #   提供一个轻量 HTTP 接口，可在容器内或宿主机通过 curl 实时查看
    #   进程内存占用、线程数、worker 数，用于排查"周期性关停"问题。
    #
    # 设计：
    #   - 始终返回 200（单容器场景下没有流量摘除机制）
    #   - 只读 /proc/self/status，不引入新依赖
    #   - 不影响任何业务接口
    # ============================================================
    @app.route('/health', methods=['GET'])
    @app.route('/healthz', methods=['GET'])
    def health_check():
        import os as _os
        import threading as _threading

        try:
            rss_mb = 0
            try:
                with open('/proc/self/status', 'r', encoding='utf-8') as _f:
                    for _line in _f:
                        if _line.startswith('VmRSS:'):
                            rss_mb = int(_line.split()[1]) // 1024  # KB -> MB
                            break
            except Exception:
                # 非 Linux 环境（如 macOS 开发）忽略
                rss_mb = -1

            return {
                'status': 'ok',
                'rss_mb': rss_mb,
                'threads': _threading.active_count(),
                'workers': int(_os.getenv('GUNICORN_WORKERS', '2')),
            }, 200
        except Exception as e:
            app.logger.warning(f"[health] 异常: {e}")
            return {'status': 'degraded', 'error': str(e)}, 200

    @app.errorhandler(Exception)
    def internalError(e):
        app.logger.error(traceback.format_exc())

        # 根据异常类型返回更友好的错误信息
        error_message = str(e)

        # 如果是 SQLAlchemy 相关错误，返回更友好的提示
        if 'tuple index out of range' in error_message or 'IndexError' in str(type(e).__name__):
            # 这通常是连接池问题，不暴露内部细节
            app.logger.error(f"数据库连接异常，可能是连接池问题: {e}")
            return {'code': 500, 'message': '数据库连接异常，请稍后重试'}, 500

        if 'sqlalchemy' in error_message.lower() or 'psycopg2' in error_message.lower():
            app.logger.error(f"数据库操作异常: {e}")
            return {'code': 500, 'message': '数据库操作异常，请稍后重试'}, 500

        return {'code': 500, 'message': error_message}, 500

    return app

def check_database_has_tables(connection):
    return bool(connection.scalar(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        )
    """)))


def execute_init_sql(app, connection):
    """执行 init.sql 脚本"""
    app_path = os.path.dirname(os.path.abspath(__file__))
    init_sql_path = os.path.join(app_path, 'init.sql')
    
    if not os.path.exists(init_sql_path):
        app.logger.warning(f"未找到 init.sql 文件: {init_sql_path}")
        return False
    
    try:
        with open(init_sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 处理 SQL 内容：移除 # 注释（PostgreSQL 不支持 # 作为注释）
        lines = sql_content.split('\n')
        cleaned_lines = []
        for line in lines:
            # 如果整行是 # 开头的注释，则跳过
            stripped = line.strip()
            if stripped.startswith('#'):
                # 检查是否是行内注释（# 后面有内容，且不在字符串中）
                # 简单处理：如果整行以 # 开头，则跳过
                continue
            # 移除行尾的 # 注释（简单处理：如果行中包含 # 且不在引号中）
            # 为了安全，这里只处理整行注释的情况
            cleaned_lines.append(line)
        
        sql_content = '\n'.join(cleaned_lines)
        
        # 使用更简单可靠的方式分割 SQL 语句
        # 按分号分割，但需要处理多行语句和字符串中的分号
        statements = []
        current_statement = []
        
        # 简单的状态机：跟踪是否在字符串中
        in_single_quote = False
        in_double_quote = False
        
        for line in sql_content.split('\n'):
            # 检查行中是否有分号（不在字符串中）
            line_chars = list(line)
            semicolon_pos = -1
            
            for i, char in enumerate(line_chars):
                if char == "'" and (i == 0 or line_chars[i-1] != '\\'):
                    in_single_quote = not in_single_quote
                elif char == '"' and (i == 0 or line_chars[i-1] != '\\'):
                    in_double_quote = not in_double_quote
                elif char == ';' and not in_single_quote and not in_double_quote:
                    semicolon_pos = i
                    break
            
            current_statement.append(line)
            
            # 如果找到分号且不在字符串中，说明语句结束
            if semicolon_pos >= 0:
                statement = '\n'.join(current_statement).strip()
                if statement:
                    statements.append(statement)
                current_statement = []
                # 重置字符串状态（新语句开始）
                in_single_quote = False
                in_double_quote = False
        
        # 处理最后一个语句（可能没有分号结尾）
        if current_statement:
            statement = '\n'.join(current_statement).strip()
            if statement:
                statements.append(statement)
        
        # 过滤空语句和纯注释语句
        filtered_statements = []
        for stmt in statements:
            # 移除注释和空行后检查
            lines = [l for l in stmt.split('\n') 
                    if l.strip() and not l.strip().startswith('--')]
            if lines:
                filtered_statements.append(stmt)
        
        if not filtered_statements:
            app.logger.warning("init.sql 文件中没有找到可执行的 SQL 语句")
            return False
        
        app.logger.info(f"准备执行 {len(filtered_statements)} 条 SQL 语句")
        
        for statement in filtered_statements:
            connection.execute(text(statement))

        app.logger.info("init.sql 脚本执行完成")
        return True
        
    except Exception as e:
        app.logger.error(f"执行 init.sql 脚本时出错: {e}", exc_info=True)
        return False


def ensure_database_initialized(app):
    with app.app_context(), db.engine.begin() as connection:
        standard_schema = connection.scalar(text("""
            SELECT current_schema() = 'public'
               AND to_regclass('users') IS NOT DISTINCT FROM to_regclass('public.users')
               AND to_regclass('user_groups') IS NOT DISTINCT FROM to_regclass('public.user_groups')
        """))
        if not standard_schema:
            raise RuntimeError("OntiCards requires the standard PostgreSQL public schema.")
        # Serialize the schema check and DDL across workers starting against the same database.
        connection.execute(text("SELECT pg_advisory_xact_lock(410731, 1)"))
        if check_database_has_tables(connection):
            return
        if not execute_init_sql(app, connection):
            raise RuntimeError("Database schema initialization failed.")
        from models.users import User
        initialize_bootstrap_state(connection, User.__table__, os.environ)


def ensure_admin_initialized(app):
    from models.users import User

    with app.app_context():
        created = ensure_admin(
            db.engine, User.__table__, User.build_weaviate_class_name,
            lambda namespace, owner, claim: ensure_account_collection(get_env("WEAVIATE_URL"), namespace, owner, claim),
            os.environ,
        )
    if created:
        app.logger.info("First administrator initialized.")


def ensure_prompt_configs_initialized(app):
    """检查 prompt_config 表是否为空，为空则从文件同步初始数据"""
    from models.prompt_config import PromptConfig

    with app.app_context():
        existing = db.session.query(func.count(PromptConfig.id)).scalar() or 0
        if existing > 0:
            app.logger.info(f"Skip prompt config seeding, found {existing} config(s).")
            return

        app.logger.info("prompt_config 表为空，开始同步提示词配置...")
        try:
            from models.prompt_config import prompt_manager
            # 使用自动检测：优先查找项目根目录下的 libs/，找不到则查找项目父目录下的 libs/
            results = prompt_manager.sync_all_from_files()

            success_count = len(results.get("success", []))
            failed_count = len(results.get("failed", []))

            if success_count > 0:
                app.logger.info(f"提示词配置同步成功: {success_count} 个，失败: {failed_count} 个")
            if failed_count > 0:
                app.logger.warning(f"提示词配置同步失败: {results.get('failed', [])}")
        except Exception as e:
            app.logger.error(f"提示词配置同步失败: {e}", exc_info=True)

app = create_app()
app.json.ensure_ascii = False

def create_runtime_app():
    """Provision the first administrator only when starting an API process."""
    with app.app_context():
        try:
            ensure_admin_initialized(app)
            ensure_prompt_configs_initialized(app)
        finally:
            db.session.remove()
            db.engine.dispose()
    if os.getenv("LOG_ROTATION_ENABLED", "1") == "1":
        _start_log_rotation_thread()
    return app


# ============================================================
# SSO 入口加固：轻量日志巡检（防"日志膨胀→磁盘满→OOM"链路）
#
# 在 Flask app 启动时启动一个后台 daemon 线程，每天定时检查 logs 目录大小。
# 超过阈值时仅保留最新 N MB + 压缩归档最老的。
#
# 这个线程是 daemon=True，不会阻塞主进程退出。
# 不影响 gunicorn 启动 / 重启行为，不影响其他任何模块。
# ============================================================
def _start_log_rotation_thread():
    import threading
    import glob as _glob

    def _rotate():
        while True:
            try:
                # 每 6 小时检查一次
                time.sleep(6 * 3600)
                logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
                if not os.path.isdir(logs_dir):
                    continue
                # 阈值：单文件 > 200MB 或目录 > 2GB 触发清理
                total_size = 0
                big_files = []
                for f in _glob.glob(os.path.join(logs_dir, '*.log*')):
                    try:
                        sz = os.path.getsize(f)
                        total_size += sz
                        if sz > 200 * 1024 * 1024:
                            big_files.append((f, sz))
                    except Exception:
                        pass
                if total_size > 2 * 1024 * 1024 * 1024 or big_files:
                    app.logger.warning(
                        f"[log-rotate] 日志目录 {logs_dir} 总大小={total_size // 1024 // 1024}MB，"
                        f"大文件={[f for f, _ in big_files]}"
                    )
                    # 仅截断最大的 access log（保守做法，不删文件）
                    for f, _ in big_files:
                        try:
                            if 'access' in os.path.basename(f).lower():
                                # 截断为最新 50MB
                                with open(f, 'rb') as _fr:
                                    _fr.seek(-50 * 1024 * 1024, os.SEEK_END)
                                    tail = _fr.read()
                                with open(f, 'wb') as _fw:
                                    _fw.write(tail)
                                app.logger.warning(f"[log-rotate] 已截断 {f}")
                        except Exception as _e:
                            app.logger.debug(f"[log-rotate] 截断 {f} 失败: {_e}")
            except Exception:
                pass

    t = threading.Thread(target=_rotate, daemon=True, name='log-rotate')
    t.start()
    app.logger.info("[log-rotate] 后台日志巡检线程已启动")


if __name__ == '__main__':
    env = Env()
    env.read_env()
    port = env.int('PORT', 9000)
    create_runtime_app().run(port=port, host='0.0.0.0', debug=False)
