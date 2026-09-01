"""
 @File: version_update_log_api.py
 @Description: 版本更新日志控制类
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-11-05 10:20
"""
from typing import Any, Dict, Tuple
import flask_login
from flask import Blueprint, jsonify, request
from flask_login import login_required
from flask_restful import Api, Resource

from extensions.ext_database import db
from models.change_logs import Changelog

# === 注册 Flask Blueprint 和 API ===
version_update_log_api= Blueprint('version_update_log_api', __name__)
api = Api(version_update_log_api)

ALLOWED_STATUS = {"public", "hidden"}

def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    return {"code": code, "msg": msg, "data": data if data is not None else []}, http_status  # type: ignore[return]

def validate_status(value: str) -> str:
    if value is None:
        return "hidden"
    value = str(value).lower()
    if value not in ALLOWED_STATUS:
        raise ValueError(f"status 仅支持 {sorted(ALLOWED_STATUS)}")
    return value


class VersionUpdateLogResource(Resource):
    """
    支持：
      - GET /api/changelog            → 列表（全部日志，含公开与隐藏）
      - GET /api/changelog/<id>       → 单条详情（如需要）
      - POST /api/changelog           → 新增
      - PUT /api/changelog/<id>       → 修改
      - DELETE /api/changelog/<id>    → 删除
    说明：按你之前需求，前台展示可以只用 public；这里的 GET 列表返回全部，方便后台管理。
    如需只返回 public，可在下方 GET 列表里加筛选。
    """

    # LIST / DETAIL
    @login_required
    def get(self, cid: int = None):
        try:
            if cid is not None:
                r = Changelog.query.get_or_404(cid)
                data = {
                    "id": r.id,
                    "version": r.version,
                    "title": r.title,
                    "content_md": r.content_md,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
                return resp(200, "success", data, 200)

            # 列表：如仅想返回 public，把下一行改为 .filter(Changelog.status == "public")
            q = Changelog.query.order_by(Changelog.created_at.desc())
            records = q.all()
            data = [{
                "id": r.id,
                "version": r.version,
                "title": r.title,
                "content_md": r.content_md,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            } for r in records]
            return resp(200, "success", data, 200)

        except Exception as e:
            db.session.rollback()
            return resp(500, f"获取失败: {e}", [], 500)

    # CREATE
    @login_required
    def post(self):
        try:
            payload = request.get_json(force=True) or {}
            version = payload.get("version")
            title = payload.get("title")
            content_md = payload.get("content_md")
            status = validate_status(payload.get("status"))

            if not version or not title or not content_md:
                return resp(400, "缺少必填字段：version / title / content_md", [], 400)

            # 版本唯一
            exists = Changelog.query.filter_by(version=version).first()
            if exists:
                return resp(409, f"版本号已存在：{version}", [], 409)

            obj = Changelog(
                version=version,
                title=title,
                content_md=content_md,
                status=status
            )
            db.session.add(obj)
            db.session.commit()

            data = {"id": obj.id}
            return resp(200, "created", data, 200)

        except ValueError as ve:
            db.session.rollback()
            return resp(400, str(ve), [], 400)
        except Exception as e:
            db.session.rollback()
            return resp(500, f"新增失败: {e}", [], 500)

    # UPDATE
    @login_required
    def put(self, cid: int):
        try:
            obj = Changelog.query.get_or_404(cid)
            payload = request.get_json(force=True) or {}

            if "version" in payload:
                new_version = payload["version"]
                if not new_version:
                    return resp(400, "version 不能为空", [], 400)
                # 保证唯一（排除自身）
                dup = Changelog.query.filter(Changelog.id != cid, Changelog.version == new_version).first()
                if dup:
                    return resp(409, f"版本号已存在：{new_version}", [], 409)
                obj.version = new_version

            if "title" in payload:
                if not payload["title"]:
                    return resp(400, "title 不能为空", [], 400)
                obj.title = payload["title"]

            if "content_md" in payload:
                if not payload["content_md"]:
                    return resp(400, "content_md 不能为空", [], 400)
                obj.content_md = payload["content_md"]

            if "status" in payload:
                obj.status = validate_status(payload["status"])

            db.session.commit()
            return resp(200, "updated", {"id": obj.id}, 200)

        except ValueError as ve:
            db.session.rollback()
            return resp(400, str(ve), [], 400)
        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新失败: {e}", [], 500)

    # DELETE
    @login_required
    def delete(self, cid: int):
        try:
            obj = Changelog.query.get_or_404(cid)
            db.session.delete(obj)
            db.session.commit()
            return resp(200, "deleted", {"id": cid}, 200)
        except Exception as e:
            db.session.rollback()
            return resp(500, f"删除失败: {e}", [], 500)

api.add_resource(VersionUpdateLogResource,
                 '/changelog',              # GET 列表 / POST 新增
                 '/changelog/<int:cid>')    # GET 详情 / PUT 修改 / DELETE 删除

'''
列表：GET /changelog

详情：GET /changelog/123

新增：POST /changelog

修改：PUT /changelog/123

删除：DELETE /changelog/123
'''
