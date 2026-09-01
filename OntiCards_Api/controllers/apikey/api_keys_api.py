"""
 @File: api_keys_api.py
 @Description: api_keys 管理
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-12-29 13:48
"""

from datetime import datetime, timezone
from typing import Any, Dict, Tuple
import secrets
from uuid import UUID

from flask import Blueprint, request
from flask_restful import Api, Resource

from extensions.ext_database import db
from models.api_keys import ApiKey   # 按你项目实际路径调整

api_keys_api = Blueprint("api_keys_api", __name__)
api = Api(api_keys_api)

def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    return {  # type: ignore[return]
        "code": code,
        "msg": msg,
        "data": data
    }, http_status

# 校验是否过期
def _parse_expires_at(value):
    """
    解析 expires_at，支持 ISO8601 / None
    """
    if value in (None, ""):
        return None
    return datetime.fromisoformat(value)

# 根据id查询单条ApiKey的uuid校验
def _is_uuid(v: str) -> bool:
    try:
        UUID(str(v))
        return True
    except Exception:
        return False

class ApiKeysAPI(Resource):
    """
    API Key 资源类
    GET    : 查询 API Key（列表 / 单条）
    POST   : 创建 API Key
    PUT    : 修改 API Key（name / status / expires_at）
    DELETE : 删除 API Key
    """

    def get(self):
        """
        查询 API Key
        Query 参数（必须二选一）：
          - id: 查询单条 API Key（UUID）
          - user_id: 查询该用户下的所有 API Keys
        """
        try:
            key_id = request.args.get("id")
            user_id = request.args.get("user_id")

            if not key_id and not user_id:
                return resp(400, "缺少查询参数，必须提供 id 或 user_id", None, 400)

            # 1) 按 id 查单条（UUID 校验）
            if key_id:
                if not _is_uuid(key_id):
                    return resp(400, "id 格式错误，必须为 UUID", None, 400)

                obj = ApiKey.query.filter_by(id=key_id).first()
                if not obj:
                    return resp(404, "API Key 不存在", None, 404)

                return resp(200, "success", {
                    "id": str(obj.id),
                    "user_id": str(obj.user_id),
                    "name": obj.name,
                    "api_key": obj.api_key,
                    "status": obj.status,
                    "expires_at": obj.expires_at.isoformat() if obj.expires_at else None,
                    "last_used_at": obj.last_used_at.isoformat() if obj.last_used_at else None,
                    "created_at": obj.created_at.isoformat() if obj.created_at else None,
                    "updated_at": obj.updated_at.isoformat() if obj.updated_at else None,
                })

            # 2) 按 user_id 查列表
            records = (
                ApiKey.query
                .filter_by(user_id=user_id)
                .order_by(ApiKey.created_at.desc())
                .all()
            )

            data = []
            for r in records:
                data.append({
                    "id": str(r.id),
                    "user_id": str(r.user_id),
                    "name": r.name,
                    "api_key": r.api_key,
                    "status": r.status,
                    "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                    "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                })

            return resp(200, "success", data)

        except Exception as e:
            return resp(500, f"查询失败: {e}", None, 500)

    def post(self):
        """
        创建 API Key
        Body:
          - user_id: 必填
          - name: 必填
          - api_key: 可选（不传则系统生成）
          - expires_at: 可选（ISO8601）
        """
        try:
            payload = request.get_json(force=True) or {}

            user_id = payload.get("user_id")
            name = payload.get("name")
            api_key_plain = payload.get("api_key")
            expires_at_raw = payload.get("expires_at")

            if not user_id:
                return resp(400, "user_id 不能为空", None, 400)
            if not name:
                return resp(400, "name 不能为空", None, 400)

            expires_at = None
            if "expires_at" in payload:
                try:
                    expires_at = _parse_expires_at(expires_at_raw)
                except Exception:
                    return resp(400, "expires_at 格式错误，需为 ISO8601", None, 400)

            if not api_key_plain:
                api_key_plain = "ak_" + secrets.token_urlsafe(32)

            # 明文唯一校验
            exists = ApiKey.query.filter_by(api_key=api_key_plain).first()
            if exists:
                return resp(409, "api_key 已存在", None, 409)

            obj = ApiKey(
                user_id=user_id,
                name=name,
                api_key=api_key_plain,
                status="active",
                expires_at=expires_at
            )

            db.session.add(obj)
            db.session.commit()

            # 创建时返回明文 api_key
            return resp(200, "success", {
                "id": str(obj.id),
                "api_key": api_key_plain
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"创建失败: {e}", None, 500)

    def put(self):
        """
        修改 API Key
        规则：
        - 允许修改 name / status / expires_at
        - expires_at 只允许延长，或清空（null = 永不过期）
        """
        try:
            payload = request.get_json(force=True) or {}
            key_id = payload.get("id")

            if not key_id:
                return resp(400, "id 不能为空", None, 400)

            obj = ApiKey.query.filter_by(id=key_id).first()
            if not obj:
                return resp(404, "API Key 不存在", None, 404)

            # 1️⃣ 修改 name
            if "name" in payload:
                if not payload["name"]:
                    return resp(400, "name 不能为空", None, 400)
                obj.name = payload["name"]

            # 2️⃣ 修改 status
            if "status" in payload:
                status = payload["status"]
                if status not in ("active", "disabled"):
                    return resp(400, "status 仅支持 active / disabled", None, 400)
                obj.status = status

            # 3️⃣ 修改 expires_at（重点逻辑）
            if "expires_at" in payload:
                raw_exp = payload.get("expires_at")

                # 3.1 设为永不过期（允许）
                if raw_exp in (None, ""):
                    obj.expires_at = None

                else:
                    try:
                        new_exp = _parse_expires_at(raw_exp)
                    except Exception:
                        return resp(400, "expires_at 格式错误，需为 ISO8601 或 null", None, 400)

                    # ---- 统一 new_exp 为 aware UTC ----
                    if new_exp.tzinfo is None:
                        new_exp = new_exp.replace(tzinfo=timezone.utc)

                    # ---- 如果原本就有 expires_at，只允许延长 ----
                    if obj.expires_at:
                        old_exp = obj.expires_at
                        if old_exp.tzinfo is None:
                            old_exp = old_exp.replace(tzinfo=timezone.utc)

                        if new_exp < old_exp:
                            return resp(
                                400,
                                "expires_at 只能延长，不能缩短",
                                None,
                                400
                            )

                    obj.expires_at = new_exp

            obj.updated_at = datetime.utcnow()
            db.session.commit()

            return resp(200, "success", {"id": str(obj.id)})

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新失败: {e}", None, 500)

    def delete(self):
        """
        删除 API Key
        Body:
          - id: 必填
        """
        try:
            payload = request.get_json(force=True) or {}
            key_id = payload.get("id")

            if not key_id:
                return resp(400, "id 不能为空", None, 400)

            obj = ApiKey.query.filter_by(id=key_id).first()
            if not obj:
                return resp(404, "API Key 不存在", None, 404)

            db.session.delete(obj)
            db.session.commit()

            return resp(200, "success", {"id": key_id})

        except Exception as e:
            db.session.rollback()
            return resp(500, f"删除失败: {e}", None, 500)


# 路由注册
api.add_resource(ApiKeysAPI, "/api_keys")
