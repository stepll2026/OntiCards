"""
 @File: business_term_api.py
 @Description: 业务术语库 API - 提供业务术语库和术语的 CRUD 操作及模板导入接口
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-14
 @Update: 2026-05-14 重构：新增术语库管理，支持一个库包含多个术语
 @Update: 2026-05-14 新增：数据源-术语库关联管理，支持在数据源工作空间中管理术语库

 接口列表:
 业务术语库管理:
 - GET    /console/api/business_term/libraries              - 获取术语库列表
 - GET    /console/api/business_term/libraries/<id>         - 获取术语库详情（含术语列表）
 - POST   /console/api/business_term/libraries               - 创建术语库
 - PUT    /console/api/business_term/libraries/<id>         - 更新术语库
 - DELETE /console/api/business_term/libraries/<id>          - 删除术语库

 业务术语管理:
 - GET    /console/api/business_term/list                    - 获取术语列表（支持按库、搜索）
 - GET    /console/api/business_term/<id>                   - 获取术语详情
 - POST   /console/api/business_term/list                    - 创建术语
 - PUT    /console/api/business_term/<id>                    - 更新术语
 - DELETE /console/api/business_term/<id>                    - 删除术语

 术语模板:
 - GET    /console/api/business_term/templates/categories    - 获取模板分类列表
 - GET    /console/api/business_term/templates               - 获取模板列表
 - POST   /console/api/business_term/templates/import         - 从模板导入术语

 数据源-术语库关联管理:
 - GET    /console/api/business_term/datasource/<datasource_id>/libraries       - 获取数据源已添加的术语库列表
 - POST   /console/api/business_term/datasource/<datasource_id>/libraries      - 为数据源添加术语库
 - PUT    /console/api/business_term/datasource/<datasource_id>/libraries/<id> - 更新数据源的术语库状态（启用/禁用）
 - DELETE /console/api/business_term/datasource/<datasource_id>/libraries/<id>  - 从数据源移除术语库
 - GET    /console/api/business_term/datasource/<datasource_id>/available      - 获取数据源可添加的术语库列表（未添加的）
"""

from typing import Any, Dict, Tuple
import json
import uuid
import flask_login
from flask import Blueprint, request
from flask_restful import Api, Resource
from sqlalchemy import or_

from extensions.ext_database import db
from models.business_terms import BusinessTerm
from models.business_term_libraries import BusinessTermLibrary
from models.business_term_templates import BusinessTermTemplate
from models.datasource_term_library import DatasourceTermLibrary

business_term_api = Blueprint("business_term_api", __name__)
api = Api(business_term_api)


def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    """统一响应格式"""
    return {  # type: ignore[return]
        "code": code,
        "msg": msg,
        "data": data
    }, http_status


# ==================== 辅助函数 ====================


def _validate_name(name: str, max_length: int = 100) -> tuple:
    """验证名称格式"""
    if not name or not name.strip():
        return False, "名称不能为空"
    if len(name) > max_length:
        return False, f"名称不能超过{max_length}个字符"
    return True, None


def _validate_term_name(term_name: str) -> tuple:
    """验证术语名称格式"""
    if not term_name or not term_name.strip():
        return False, "术语名称不能为空"
    if len(term_name) > 255:
        return False, "术语名称不能超过255个字符"
    return True, None


# ==================== 业务术语库 CRUD ====================

class BusinessTermLibraryListResource(Resource):
    """
    业务术语库列表资源

    GET: 获取术语库列表（支持分页、搜索、分类筛选）
    POST: 创建新术语库
    """

    @flask_login.login_required
    def get(self):
        """获取术语库列表"""
        try:
            page = max(1, int(request.args.get("page", 1)))
            page_size = min(100, max(1, int(request.args.get("page_size", 20))))
            search = request.args.get("search", "").strip()
            category = request.args.get("category", "").strip()
            status = request.args.get("status", "").strip()

            # 自动获取当前用户创建的术语库
            current_user_id = flask_login.current_user.id

            query = BusinessTermLibrary.query.filter_by(created_by=current_user_id)

            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        BusinessTermLibrary.name.ilike(search_pattern),
                        BusinessTermLibrary.description.ilike(search_pattern)
                    )
                )

            if category:
                query = query.filter_by(category=category)

            if status:
                query = query.filter_by(status=status)

            total = query.count()
            pagination = query.order_by(BusinessTermLibrary.created_at.desc()).paginate(
                page=page, per_page=page_size, error_out=False
            )

            items = [lib.to_simple_dict() for lib in pagination.items]

            return resp(200, "success", {
                "items": items,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
                }
            })

        except Exception as e:
            return resp(500, f"获取术语库列表失败: {str(e)}", None, 500)

    @flask_login.login_required
    def post(self):
        """创建术语库"""
        try:
            payload = request.get_json(force=True) or {}
            name = payload.get("name", "").strip()
            description = payload.get("description", "").strip()
            category = payload.get("category", "").strip()

            # 验证必填参数
            if not name:
                return resp(400, "name 不能为空", None, 400)

            # 验证名称格式
            is_valid, error_msg = _validate_name(name)
            if not is_valid:
                return resp(400, error_msg, None, 400)

            # 检查当前用户是否已存在同名库
            current_user_id = flask_login.current_user.id
            existing = BusinessTermLibrary.query.filter_by(
                name=name, created_by=current_user_id
            ).first()
            if existing:
                return resp(409, f"术语库 '{name}' 已存在", None, 409)

            # 创建库
            library = BusinessTermLibrary(
                name=name,
                description=description if description else None,
                category=category if category else None,
                created_by=flask_login.current_user.id
            )
            db.session.add(library)
            db.session.flush()  # 强制刷新以获取生成的 id
            db.session.commit()

            return resp(200, "创建成功", {
                "id": str(library.id),
                "name": library.name,
                "message": "创建成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"创建术语库失败: {str(e)}", None, 500)


class BusinessTermLibraryDetailResource(Resource):
    """
    业务术语库详情资源

    GET: 获取术语库详情（含术语列表）
    PUT: 更新术语库
    DELETE: 删除术语库
    """

    @flask_login.login_required
    def get(self, library_id):
        """获取术语库详情"""
        try:
            library = BusinessTermLibrary.query.get(library_id)
            if not library:
                return resp(404, f"术语库不存在: {library_id}", None, 404)

            # 获取关联术语
            terms_page = request.args.get("terms_page", "1")
            terms_page_size = request.args.get("terms_page_size", "100")
            terms_search = request.args.get("terms_search", "").strip()
            terms_status = request.args.get("terms_status", "").strip()

            term_query = library.terms
            if terms_search:
                pattern = f"%{terms_search}%"
                term_query = term_query.filter(
                    or_(
                        BusinessTerm.term_name.ilike(pattern),
                        BusinessTerm.term_definition.ilike(pattern)
                    )
                )
            if terms_status:
                term_query = term_query.filter_by(status=terms_status)

            terms_total = term_query.count()
            terms_pagination = term_query.order_by(BusinessTerm.created_at.desc()).paginate(
                page=max(1, int(terms_page)),
                per_page=min(100, max(1, int(terms_page_size))),
                error_out=False
            )

            result = library.to_dict()
            result["terms"] = [t.to_simple_dict() for t in terms_pagination.items]
            result["terms_pagination"] = {
                "page": int(terms_page),
                "page_size": int(terms_page_size),
                "total": terms_total,
                "total_pages": (terms_total + int(terms_page_size) - 1) // int(terms_page_size) if terms_total > 0 else 0
            }

            return resp(200, "success", result)

        except Exception as e:
            return resp(500, f"获取术语库详情失败: {str(e)}", None, 500)

    @flask_login.login_required
    def put(self, library_id):
        """更新术语库"""
        try:
            library = BusinessTermLibrary.query.get(library_id)
            if not library:
                return resp(404, f"术语库不存在: {library_id}", None, 404)

            payload = request.get_json(force=True) or {}
            updated_fields = []

            if "name" in payload:
                new_name = payload["name"].strip()
                if new_name != library.name:
                    existing = BusinessTermLibrary.query.filter_by(
                        name=new_name, created_by=library.created_by
                    ).first()
                    if existing and str(existing.id) != str(library_id):
                        return resp(409, f"术语库名称 '{new_name}' 已存在", None, 409)
                    is_valid, error_msg = _validate_name(new_name)
                    if not is_valid:
                        return resp(400, error_msg, None, 400)
                    library.name = new_name
                    updated_fields.append("name")

            if "description" in payload:
                library.description = payload["description"]
                updated_fields.append("description")

            if "category" in payload:
                library.category = payload["category"]
                updated_fields.append("category")

            if "status" in payload:
                library.status = payload["status"]
                updated_fields.append("status")

            if not updated_fields:
                return resp(400, "没有需要更新的字段", None, 400)

            db.session.commit()

            return resp(200, "更新成功", {
                "id": str(library.id),
                "updated_fields": updated_fields,
                "message": "更新成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新术语库失败: {str(e)}", None, 500)

    @flask_login.login_required
    def delete(self, library_id):
        """删除术语库"""
        try:
            library = BusinessTermLibrary.query.get(library_id)
            if not library:
                return resp(404, f"术语库不存在: {library_id}", None, 404)

            # 先删除关联的数据源-术语库记录
            DatasourceTermLibrary.query.filter_by(library_id=library_id).delete()

            # 删除关联的术语
            BusinessTerm.query.filter_by(library_id=library_id).delete()

            # 最后删除术语库本身
            db.session.delete(library)
            db.session.commit()

            return resp(200, "删除成功", {
                "id": library_id,
                "message": "删除成功，关联术语和数据源绑定一并删除"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"删除术语库失败: {str(e)}", None, 500)


# ==================== 业务术语 CRUD ====================

class BusinessTermListResource(Resource):
    """
    业务术语列表资源

    GET: 获取术语列表（支持按库、搜索、状态筛选）
    POST: 创建新术语
    """

    @flask_login.login_required
    def get(self):
        """获取术语列表"""
        try:
            library_id = request.args.get("library_id", "").strip()
            page = max(1, int(request.args.get("page", 1)))
            page_size = min(100, max(1, int(request.args.get("page_size", 20))))
            search = request.args.get("search", "").strip()
            status = request.args.get("status", "").strip()

            if not library_id:
                return resp(400, "library_id 不能为空", None, 400)

            # 验证库是否存在
            library = BusinessTermLibrary.query.get(library_id)
            if not library:
                return resp(404, f"术语库不存在: {library_id}", None, 404)

            query = BusinessTerm.query.filter_by(library_id=library_id)

            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        BusinessTerm.term_name.ilike(search_pattern),
                        BusinessTerm.term_definition.ilike(search_pattern)
                    )
                )

            if status:
                query = query.filter_by(status=status)

            total = query.count()
            pagination = query.order_by(BusinessTerm.created_at.desc()).paginate(
                page=page, per_page=page_size, error_out=False
            )

            items = [term.to_simple_dict() for term in pagination.items]

            return resp(200, "success", {
                "items": items,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
                }
            })

        except Exception as e:
            return resp(500, f"获取术语列表失败: {str(e)}", None, 500)

    @flask_login.login_required
    def post(self):
        """创建术语"""
        try:
            payload = request.get_json(force=True) or {}
            library_id = payload.get("library_id", "").strip()
            term_name = payload.get("term_name", "").strip()
            term_alias = payload.get("term_alias")
            term_definition = payload.get("term_definition", "").strip()
            applicable_conditions = payload.get("applicable_conditions")
            remarks = payload.get("remarks")
            related_datacards = payload.get("related_datacards")
            related_fields = payload.get("related_fields")
            related_terms = payload.get("related_terms")

            # 验证必填参数
            if not library_id:
                return resp(400, "library_id 不能为空", None, 400)
            if not term_name:
                return resp(400, "term_name 不能为空", None, 400)
            if not term_definition:
                return resp(400, "term_definition 不能为空", None, 400)

            # 验证库存在
            library = BusinessTermLibrary.query.get(library_id)
            if not library:
                return resp(404, f"术语库不存在: {library_id}", None, 404)

            # 验证术语名称格式
            is_valid, error_msg = _validate_term_name(term_name)
            if not is_valid:
                return resp(400, error_msg, None, 400)

            # 检查是否已存在同名术语（同一库内）
            existing = BusinessTerm.query.filter_by(
                library_id=uuid.UUID(library_id),
                term_name=term_name
            ).first()
            if existing:
                return resp(409, f"术语 '{term_name}' 已存在", None, 409)

            # 处理 JSON 字段
            term_alias_json = json.dumps(term_alias) if term_alias else None
            related_datacards_json = json.dumps(related_datacards) if related_datacards else None
            related_fields_json = json.dumps(related_fields) if related_fields else None
            related_terms_json = json.dumps(related_terms) if related_terms else None

            # 创建术语
            term = BusinessTerm(
                library_id=uuid.UUID(library_id),
                term_name=term_name,
                term_alias=term_alias_json,
                term_definition=term_definition,
                applicable_conditions=applicable_conditions,
                remarks=remarks,
                related_datacards=related_datacards_json,
                related_fields=related_fields_json,
                related_terms=related_terms_json,
                created_by=flask_login.current_user.id
            )
            db.session.add(term)
            db.session.commit()

            return resp(200, "创建成功", {
                "id": str(term.id),
                "term_name": term.term_name,
                "message": "创建成功"
            })

        except ValueError:
            return resp(400, "library_id 格式错误，应为有效的 UUID", None, 400)
        except Exception as e:
            db.session.rollback()
            return resp(500, f"创建术语失败: {str(e)}", None, 500)


class BusinessTermDetailResource(Resource):
    """
    业务术语详情资源

    GET: 获取术语详情
    PUT: 更新术语
    DELETE: 删除术语
    """

    @flask_login.login_required
    def get(self, term_id):
        """获取术语详情"""
        try:
            term = BusinessTerm.query.get(term_id)
            if not term:
                return resp(404, f"术语不存在: {term_id}", None, 404)

            return resp(200, "success", term.to_dict())

        except Exception as e:
            return resp(500, f"获取术语详情失败: {str(e)}", None, 500)

    @flask_login.login_required
    def put(self, term_id):
        """更新术语"""
        try:
            term = BusinessTerm.query.get(term_id)
            if not term:
                return resp(404, f"术语不存在: {term_id}", None, 404)

            payload = request.get_json(force=True) or {}
            updated_fields = []

            if "term_name" in payload:
                new_name = payload["term_name"].strip()
                if new_name != term.term_name:
                    existing = BusinessTerm.query.filter_by(
                        library_id=term.library_id,
                        term_name=new_name
                    ).first()
                    if existing and str(existing.id) != str(term_id):
                        return resp(409, f"术语名称 '{new_name}' 已存在", None, 409)
                    is_valid, error_msg = _validate_term_name(new_name)
                    if not is_valid:
                        return resp(400, error_msg, None, 400)
                    term.term_name = new_name
                    updated_fields.append("term_name")

            if "term_alias" in payload:
                term.term_alias = json.dumps(payload["term_alias"]) if payload["term_alias"] else None
                updated_fields.append("term_alias")

            if "term_definition" in payload:
                term.term_definition = payload["term_definition"].strip()
                updated_fields.append("term_definition")

            if "applicable_conditions" in payload:
                term.applicable_conditions = payload["applicable_conditions"]
                updated_fields.append("applicable_conditions")

            if "remarks" in payload:
                term.remarks = payload["remarks"]
                updated_fields.append("remarks")

            if "related_datacards" in payload:
                term.related_datacards = json.dumps(payload["related_datacards"]) if payload["related_datacards"] else None
                updated_fields.append("related_datacards")

            if "related_fields" in payload:
                term.related_fields = json.dumps(payload["related_fields"]) if payload["related_fields"] else None
                updated_fields.append("related_fields")

            if "related_terms" in payload:
                term.related_terms = json.dumps(payload["related_terms"]) if payload["related_terms"] else None
                updated_fields.append("related_terms")

            if "status" in payload:
                term.status = payload["status"]
                updated_fields.append("status")

            if not updated_fields:
                return resp(400, "没有需要更新的字段", None, 400)

            db.session.commit()

            return resp(200, "更新成功", {
                "id": str(term.id),
                "updated_fields": updated_fields,
                "message": "更新成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新术语失败: {str(e)}", None, 500)

    @flask_login.login_required
    def delete(self, term_id):
        """删除术语"""
        try:
            term = BusinessTerm.query.get(term_id)
            if not term:
                return resp(404, f"术语不存在: {term_id}", None, 404)

            db.session.delete(term)
            db.session.commit()

            return resp(200, "删除成功", {
                "id": term_id,
                "message": "删除成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"删除术语失败: {str(e)}", None, 500)


# ==================== 术语模板 ====================

class BusinessTermTemplateCategoriesResource(Resource):
    """获取模板分类列表"""

    @flask_login.login_required
    def get(self):
        try:
            from sqlalchemy import func

            stats = db.session.query(
                BusinessTermTemplate.category,
                BusinessTermTemplate.template_name,
                func.count(BusinessTermTemplate.id).label("count")
            ).group_by(
                BusinessTermTemplate.category,
                BusinessTermTemplate.template_name
            ).order_by(
                BusinessTermTemplate.category,
                BusinessTermTemplate.template_name
            ).all()

            categories = {}
            for stat in stats:
                cat = stat.category
                if cat not in categories:
                    categories[cat] = {
                        "category": cat,
                        "templates": []
                    }
                categories[cat]["templates"].append({
                    "template_name": stat.template_name,
                    "count": stat.count
                })

            return resp(200, "success", {
                "categories": list(categories.values())
            })

        except Exception as e:
            return resp(500, f"获取模板分类失败: {str(e)}", None, 500)


class BusinessTermTemplateListResource(Resource):
    """获取模板列表"""

    @flask_login.login_required
    def get(self):
        try:
            category = request.args.get("category", "").strip()
            template_name = request.args.get("template_name", "").strip()

            query = BusinessTermTemplate.query
            if category:
                query = query.filter_by(category=category)
            if template_name:
                query = query.filter_by(template_name=template_name)

            templates = query.order_by(
                BusinessTermTemplate.category,
                BusinessTermTemplate.template_name,
                BusinessTermTemplate.term_name
            ).all()

            items = [t.to_simple_dict() for t in templates]

            return resp(200, "success", {
                "items": items,
                "total": len(items)
            })

        except Exception as e:
            return resp(500, f"获取模板列表失败: {str(e)}", None, 500)


class BusinessTermTemplateImportResource(Resource):
    """从模板导入术语"""

    @flask_login.login_required
    def post(self):
        try:
            payload = request.get_json(force=True) or {}
            library_id = payload.get("library_id", "").strip()
            template_ids = payload.get("template_ids")
            category = payload.get("category")
            template_name = payload.get("template_name")

            if not library_id:
                return resp(400, "library_id 不能为空", None, 400)

            # 验证库存在
            library = BusinessTermLibrary.query.get(library_id)
            if not library:
                return resp(404, f"术语库不存在: {library_id}", None, 404)

            # 确定要导入的模板
            query = BusinessTermTemplate.query
            if template_ids:
                if isinstance(template_ids, list) and template_ids:
                    query = query.filter(BusinessTermTemplate.id.in_(template_ids))
                else:
                    return resp(400, "template_ids 必须是有效的ID列表", None, 400)
            elif category:
                query = query.filter_by(category=category)
            elif template_name:
                query = query.filter_by(template_name=template_name)
            else:
                return resp(400, "template_ids、category、template_name 至少需要指定一个", None, 400)

            source_templates = query.all()
            if not source_templates:
                return resp(404, "未找到匹配的模板", None, 404)

            imported_count = 0
            skipped_count = 0
            skipped_items = []

            for tmpl in source_templates:
                existing = BusinessTerm.query.filter_by(
                    library_id=uuid.UUID(library_id),
                    term_name=tmpl.term_name
                ).first()
                if existing:
                    skipped_count += 1
                    skipped_items.append(tmpl.term_name)
                    continue

                term = BusinessTerm(
                    library_id=uuid.UUID(library_id),
                    term_name=tmpl.term_name,
                    term_alias=tmpl.term_alias,
                    term_definition=tmpl.term_definition,
                    applicable_conditions=tmpl.applicable_conditions,
                    remarks=tmpl.remarks,
                    related_datacards=None,
                    related_fields=None,
                    related_terms=None,
                    created_by=flask_login.current_user.id
                )
                db.session.add(term)
                imported_count += 1

            db.session.commit()

            result = {
                "imported_count": imported_count,
                "skipped_count": skipped_count,
                "message": f"导入成功 {imported_count} 个，跳过 {skipped_count} 个（已存在）"
            }
            if skipped_items:
                result["skipped_items"] = skipped_items

            return resp(200, "导入完成", result)

        except ValueError:
            return resp(400, "library_id 格式错误，应为有效的 UUID", None, 400)
        except Exception as e:
            db.session.rollback()
            return resp(500, f"导入模板失败: {str(e)}", None, 500)


# ==================== 数据源-术语库关联管理 ====================

class DatasourceLibraryListResource(Resource):
    """
    数据源已添加的术语库列表

    GET: 获取数据源已添加的术语库列表
    POST: 为数据源添加术语库
    """

    @flask_login.login_required
    def get(self, datasource_id):
        """获取数据源已添加的术语库列表"""
        try:
            page = max(1, int(request.args.get("page", 1)))
            page_size = min(100, max(1, int(request.args.get("page_size", 20))))
            is_enabled = request.args.get("is_enabled", "").strip()

            query = DatasourceTermLibrary.query.filter_by(datasource_id=datasource_id)

            if is_enabled:
                query = query.filter_by(is_enabled=is_enabled.lower() == "true")

            total = query.count()
            pagination = query.order_by(DatasourceTermLibrary.added_at.desc()).paginate(
                page=page, per_page=page_size, error_out=False
            )

            items = [item.to_simple_dict() for item in pagination.items]

            return resp(200, "success", {
                "items": items,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
                }
            })

        except Exception as e:
            return resp(500, f"获取数据源术语库列表失败: {str(e)}", None, 500)

    @flask_login.login_required
    def post(self, datasource_id):
        """为数据源添加术语库"""
        try:
            payload = request.get_json(force=True) or {}
            library_id = payload.get("library_id", "").strip()
            is_enabled = payload.get("is_enabled", True)

            if not library_id:
                return resp(400, "library_id 不能为空", None, 400)

            # 验证术语库存在
            library = BusinessTermLibrary.query.get(library_id)
            if not library:
                return resp(404, f"术语库不存在: {library_id}", None, 404)

            # 检查是否已添加
            existing = DatasourceTermLibrary.query.filter_by(
                datasource_id=datasource_id,
                library_id=library_id
            ).first()
            if existing:
                return resp(409, f"术语库 '{library.name}' 已添加到此数据源", None, 409)

            # 创建关联
            ds_library = DatasourceTermLibrary(
                datasource_id=datasource_id,
                library_id=library_id,
                is_enabled=is_enabled,
                added_by=flask_login.current_user.id
            )
            db.session.add(ds_library)
            db.session.commit()

            return resp(200, "添加成功", {
                "id": str(ds_library.id),
                "datasource_id": str(datasource_id),
                "library_id": str(library_id),
                "library_name": library.name,
                "is_enabled": ds_library.is_enabled,
                "message": "术语库添加成功"
            })

        except ValueError:
            return resp(400, "library_id 格式错误，应为有效的 UUID", None, 400)
        except Exception as e:
            db.session.rollback()
            return resp(500, f"添加术语库失败: {str(e)}", None, 500)


class DatasourceLibraryDetailResource(Resource):
    """
    数据源术语库详情/操作

    GET: 获取数据源术语库详情
    PUT: 更新数据源术语库状态（启用/禁用）
    DELETE: 从数据源移除术语库
    """

    @flask_login.login_required
    def get(self, datasource_id, ds_library_id):
        """获取数据源术语库详情"""
        try:
            ds_library = DatasourceTermLibrary.query.get(ds_library_id)
            if not ds_library:
                return resp(404, f"关联不存在: {ds_library_id}", None, 404)

            if str(ds_library.datasource_id) != str(datasource_id):
                return resp(404, "该术语库不属于指定的数据源", None, 404)

            return resp(200, "success", ds_library.to_dict())

        except Exception as e:
            return resp(500, f"获取术语库详情失败: {str(e)}", None, 500)

    @flask_login.login_required
    def put(self, datasource_id, ds_library_id):
        """更新数据源术语库状态"""
        try:
            ds_library = DatasourceTermLibrary.query.get(ds_library_id)
            if not ds_library:
                return resp(404, f"关联不存在: {ds_library_id}", None, 404)

            if str(ds_library.datasource_id) != str(datasource_id):
                return resp(404, "该术语库不属于指定的数据源", None, 404)

            payload = request.get_json(force=True) or {}

            if "is_enabled" in payload:
                ds_library.is_enabled = bool(payload["is_enabled"])

            db.session.commit()

            return resp(200, "更新成功", {
                "id": str(ds_library.id),
                "is_enabled": ds_library.is_enabled,
                "message": "状态更新成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新术语库状态失败: {str(e)}", None, 500)

    @flask_login.login_required
    def delete(self, datasource_id, ds_library_id):
        """从数据源移除术语库"""
        try:
            ds_library = DatasourceTermLibrary.query.get(ds_library_id)
            if not ds_library:
                return resp(404, f"关联不存在: {ds_library_id}", None, 404)

            if str(ds_library.datasource_id) != str(datasource_id):
                return resp(404, "该术语库不属于指定的数据源", None, 404)

            library_name = ds_library.library.name if ds_library.library else "术语库"
            db.session.delete(ds_library)
            db.session.commit()

            return resp(200, "移除成功", {
                "id": ds_library_id,
                "message": f"术语库 '{library_name}' 已从数据源移除"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"移除术语库失败: {str(e)}", None, 500)


class DatasourceAvailableLibrariesResource(Resource):
    """
    获取数据源可添加的术语库列表（未添加的）

    GET: 获取数据源可添加的术语库列表
    """

    @flask_login.login_required
    def get(self, datasource_id):
        """获取数据源可添加的术语库列表"""
        try:
            search = request.args.get("search", "").strip()
            category = request.args.get("category", "").strip()
            status = request.args.get("status", "").strip()

            # 获取已添加的术语库ID
            added_ids = db.session.query(DatasourceTermLibrary.library_id).filter_by(
                datasource_id=datasource_id
            ).subquery()

            # 查询未添加的术语库（仅当前用户创建的）
            current_user_id = flask_login.current_user.id
            query = BusinessTermLibrary.query.filter(
                ~BusinessTermLibrary.id.in_(added_ids),
                BusinessTermLibrary.created_by == current_user_id
            )

            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        BusinessTermLibrary.name.ilike(search_pattern),
                        BusinessTermLibrary.description.ilike(search_pattern)
                    )
                )

            if category:
                query = query.filter_by(category=category)

            if status:
                query = query.filter_by(status=status)

            # 只返回启用状态的术语库
            query = query.filter_by(status="active")

            libraries = query.order_by(BusinessTermLibrary.created_at.desc()).all()

            items = [lib.to_simple_dict() for lib in libraries]

            return resp(200, "success", {
                "items": items,
                "total": len(items)
            })

        except Exception as e:
            return resp(500, f"获取可用术语库列表失败: {str(e)}", None, 500)


# ==================== 路由注册 ====================

api.add_resource(BusinessTermLibraryListResource, '/libraries')
api.add_resource(BusinessTermLibraryDetailResource, '/libraries/<string:library_id>')
api.add_resource(BusinessTermListResource, '/list')
api.add_resource(BusinessTermDetailResource, '/<string:term_id>')
api.add_resource(BusinessTermTemplateCategoriesResource, '/templates/categories')
api.add_resource(BusinessTermTemplateListResource, '/templates')
api.add_resource(BusinessTermTemplateImportResource, '/templates/import')
api.add_resource(DatasourceLibraryListResource, '/datasource/<string:datasource_id>/libraries')
api.add_resource(DatasourceLibraryDetailResource, '/datasource/<string:datasource_id>/libraries/<string:ds_library_id>')
api.add_resource(DatasourceAvailableLibrariesResource, '/datasource/<string:datasource_id>/available')
