from datetime import datetime, timezone  # ← 增加 timezone

import flask_login
from flask import request
from werkzeug.exceptions import Unauthorized

from core.passport import PassportService
from models.users import User

login_manager = flask_login.LoginManager()


def init_app(app):
    login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return None  # 强制不通过 session 恢复用户


def _to_aware_utc(dt):
    """
    把任意 datetime 转为 UTC aware：
    - 如果是 None，直接返回 None
    - 如果是 naive，假定它代表 UTC 并补上 tzinfo
    - 如果是带时区，统一转到 UTC
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@login_manager.request_loader
def load_user_from_request(request_from_flask_login):
    """Load user based on Authorization header with raw token (no Bearer)."""
    import logging
    logger = logging.getLogger(__name__)

    auth_token = request.headers.get('Authorization', '')
    if not auth_token:
        auth_token = request.args.get('_token')
        if not auth_token:
            raise Unauthorized('Missing Authorization token.')

    try:
        decoded = PassportService().verify(auth_token)
    except Exception as e:
        raise Unauthorized(f'Token verification failed: {e}')

    user_id = decoded.get('user_id')
    iat = decoded.get('iat', None)

    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        logger.error(f"Failed to query user {user_id}: {e}")
        # 如果是连接问题，尝试使用新连接重试一次
        from extensions.ext_database import db
        try:
            db.session.rollback()  # 重置会话状态
            user = User.query.filter_by(id=user_id).first()
        except Exception as retry_error:
            logger.error(f"Retry failed for user {user_id}: {retry_error}")
            raise Unauthorized(f'User query failed after retry: {retry_error}')
        if user is None:
            raise Unauthorized(f'User not found in database.')

    if not user:
        raise Unauthorized('User not found.')
    if user.status == 'disabled':
        raise Unauthorized('User is disabled.')

    # 统一用 UTC aware 比较
    if user.password_reset_at:
        if iat is None:
            raise Unauthorized('Token missing iat.')
        iat_dt = datetime.fromtimestamp(iat, timezone.utc)           # ← aware UTC
        pwd_reset_dt = _to_aware_utc(user.password_reset_at)         # ← aware UTC

        if iat_dt < pwd_reset_dt:
            raise Unauthorized('Token issued before password reset.')

    return user
