"""
 @File: model_config_api.py
 @Description: 模型配置接口实现
 @Author: 韩小豪 849631113@qq.com
 @Create: 2025-11-28 12:49
"""
from typing import Any, Dict, Tuple
from flask import Blueprint, request
from flask_restful import Api, Resource
from flask_login import current_user, login_required

from extensions.ext_database import db
from models.model_config import Model_configuration
from controllers.model_config.model_endpoints import discover_models, ModelDiscoveryError, validate_model_options
from controllers.model_config.model_protocols import probe_model, ModelServiceError

# -----------------------------
# Blueprint & API
# -----------------------------
model_config_api = Blueprint("model_config_api", __name__)
api = Api(model_config_api)


def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    """统一响应格式"""
    return {"code": code, "msg": msg, "data": data if data is not None else []}, http_status  # type: ignore[return]


# 资源类
class ModelConfigAPI(Resource):
    """
    模型配置资源类
    GET: 查询模型配置（列表或单个）
    POST: 新增模型配置
    PUT: 修改模型配置
    DELETE: 删除模型配置
    """
    
    def get(self):
        """
        查询模型配置
        查询参数: id (可选，如果提供则返回单个，否则返回列表)
        """
        try:
            model_id = request.args.get("id")
            
            if model_id:
                # 查询单个记录
                obj = Model_configuration.query.filter_by(id=model_id).first()
                if not obj:
                    return resp(404, "模型配置不存在", [], 404)
                
                data = {
                    "id": str(obj.id),
                    "model_name": obj.model_name,
                    "model_type": obj.model_type,
                    "model_api_key": obj.model_api_key,
                    "model_class": obj.model_class,
                    "url": obj.url,
                    "api_protocol": obj.api_protocol,
                    "embedding_dimensions": obj.embedding_dimensions,
                    "api_options": obj.api_options or {},
                    "created_at": obj.created_at.isoformat() if obj.created_at else None,
                    "updated_at": obj.updated_at.isoformat() if obj.updated_at else None
                }
                return resp(200, "success", data, 200)
            else:
                # 查询列表
                records = Model_configuration.query.order_by(Model_configuration.created_at.desc()).all()
                data = [{
                    "id": str(r.id),
                    "model_name": r.model_name,
                    "model_type": r.model_type,
                    "model_api_key": r.model_api_key,
                    "model_class": r.model_class,
                    "url": r.url,
                    "api_protocol": r.api_protocol,
                    "embedding_dimensions": r.embedding_dimensions,
                    "api_options": r.api_options or {},
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None
                } for r in records]
                return resp(200, "success", data, 200)
                
        except Exception as e:
            return resp(500, f"查询失败: {e}", [], 500)
    
    def post(self):
        """
        新增模型配置
        必填参数: model_name, model_type, model_api_key, model_class, url
        """
        try:
            payload = request.get_json(force=True) or {}
            model_name = payload.get("model_name")
            model_type = payload.get("model_type")
            model_api_key = payload.get("model_api_key")
            model_class = payload.get("model_class")
            url = payload.get("url")
            api_protocol = payload.get("api_protocol", "auto")
            embedding_dimensions = payload.get("embedding_dimensions")
            api_options = payload.get("api_options")
            try:
                validate_model_options(api_protocol, embedding_dimensions, api_options)
            except ValueError as exc:
                return resp(400, str(exc), [], 400)
            
            # 验证必填字段
            if not model_name:
                return resp(400, "model_name 不能为空", [], 400)
            if not model_type:
                return resp(400, "model_type 不能为空", [], 400)
            if not model_class:
                return resp(400, "model_class 不能为空", [], 400)
            if not url:
                return resp(400, "url 不能为空", [], 400)
            
            # 检查模型名称是否已存在
            exists = Model_configuration.query.filter_by(model_name=model_name).first()
            if exists:
                return resp(409, f"该类型模型已存在：{model_class}", [], 409)
            
            # 创建新记录
            obj = Model_configuration(
                model_name=model_name,
                model_type=model_type,
                model_api_key=model_api_key,
                model_class=model_class,
                url=url,
                api_protocol=api_protocol,
                embedding_dimensions=embedding_dimensions,
                api_options=api_options,
            )
            db.session.add(obj)
            db.session.commit()
            
            data = {"id": str(obj.id)}
            return resp(200, "success", data, 200)
            
        except Exception as e:
            db.session.rollback()
            return resp(500, f"新增失败: {e}", [], 500)
    
    def put(self):
        """
        修改模型配置
        必填参数: id
        可选参数: model_name, model_type, model_api_key, model_class, url
        """
        try:
            payload = request.get_json(force=True) or {}
            model_id = payload.get("id")
            
            if not model_id:
                return resp(400, "id 不能为空", [], 400)
            
            # 查找记录
            obj = Model_configuration.query.filter_by(id=model_id).first()
            if not obj:
                return resp(404, "模型配置不存在", [], 404)
            
            # 更新字段
            try:
                validate_model_options(payload.get("api_protocol", obj.api_protocol),
                                       payload.get("embedding_dimensions", obj.embedding_dimensions),
                                       payload.get("api_options", obj.api_options))
            except ValueError as exc:
                return resp(400, str(exc), [], 400)
            if "api_protocol" in payload:
                obj.api_protocol = payload["api_protocol"]
            if "embedding_dimensions" in payload:
                obj.embedding_dimensions = payload["embedding_dimensions"]
            if "api_options" in payload:
                obj.api_options = payload["api_options"]
            if "model_name" in payload:
                new_model_name = payload["model_name"]
                if not new_model_name:
                    return resp(400, "model_name 不能为空", [], 400)
                # 检查名称是否已被其他记录使用
                dup = Model_configuration.query.filter(
                    Model_configuration.id != model_id,
                    Model_configuration.model_name == new_model_name
                ).first()
                if dup:
                    return resp(409, f"模型名称已存在：{new_model_name}", [], 409)
                obj.model_name = new_model_name
            
            if "model_type" in payload:
                if not payload["model_type"]:
                    return resp(400, "model_type 不能为空", [], 400)
                obj.model_type = payload["model_type"]
            
            if "model_api_key" in payload:
                obj.model_api_key = payload["model_api_key"]
            
            if "model_class" in payload:
                if not payload["model_class"]:
                    return resp(400, "model_class 不能为空", [], 400)
                obj.model_class = payload["model_class"]
            
            if "url" in payload:
                if not payload["url"]:
                    return resp(400, "url 不能为空", [], 400)
                obj.url = payload["url"]
            
            db.session.commit()
            return resp(200, "success", {"id": str(obj.id)}, 200)
            
        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新失败: {e}", [], 500)
    
    def delete(self):
        """
        删除模型配置
        必填参数: id
        """
        try:
            payload = request.get_json(force=True) or {}
            model_id = payload.get("id")
            
            if not model_id:
                return resp(400, "id 不能为空", [], 400)
            
            # 查找记录
            obj = Model_configuration.query.filter_by(id=model_id).first()
            if not obj:
                return resp(404, "模型配置不存在", [], 404)
            
            # 删除记录
            db.session.delete(obj)
            db.session.commit()
            
            return resp(200, "deleted", {"id": model_id}, 200)
            
        except Exception as e:
            db.session.rollback()
            return resp(500, f"删除失败: {e}", [], 500)


class ModelCatalogAPI(Resource):
    @login_required
    def post(self):
        if current_user.role != "admin":
            return resp(403, "仅管理员可读取模型列表", [], 403)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return resp(400, "请提供接口地址和 API Key", [], 400)
        try:
            result = discover_models(payload.get("url"), payload.get("model_api_key") or "", payload.get("api_protocol", "auto"))
            return resp(200, "success", result)
        except ValueError as exc:
            return resp(400, str(exc), [], 400)
        except ModelDiscoveryError as exc:
            return resp(502, str(exc), [], 502)


class ModelProbeAPI(Resource):
    @login_required
    def post(self):
        if current_user.role != "admin":
            return resp(403, "仅管理员可测试模型", [], 403)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return resp(400, "请提供模型配置", [], 400)
        try:
            return resp(200, "测试通过", probe_model(payload))
        except ModelServiceError as exc:
            # A provider authentication failure must not log the user out of this app.
            return resp(502, str(exc), [], 502)
        except ValueError as exc:
            return resp(400, str(exc), [], 400)


# 路由注册
api.add_resource(ModelConfigAPI, "/model_config")
api.add_resource(ModelCatalogAPI, "/model_config/models")
api.add_resource(ModelProbeAPI, "/model_config/test")
