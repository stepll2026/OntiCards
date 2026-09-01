"""
 @File: prompt_config_api.py
 @Description: 提示词配置管理 API - 提供提示词的 CRUD 操作接口
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-05-06

 接口列表:
 - GET    /console/api/prompt_config/list       - 获取提示词列表（支持分页、搜索）
 - GET    /console/api/prompt_config/<id>      - 获取单个提示词详情
 - GET    /console/api/prompt_config/file/<file_name> - 通过文件名获取提示词
 - POST   /console/api/prompt_config/list       - 创建新提示词
 - PUT    /console/api/prompt_config/<id>      - 更新提示词
 - DELETE /console/api/prompt_config/<id>       - 删除提示词
 - POST   /console/api/prompt_config/sync       - 同步提示词（单个或全部）
 - GET    /console/api/prompt_config/categories - 获取提示词分类列表
"""

from typing import Any, Dict, Tuple
from flask import Blueprint, request
from flask_restful import Api, Resource
from sqlalchemy import or_

from extensions.ext_database import db
from models.prompt_config import PromptConfig, prompt_manager

prompt_config_api = Blueprint("prompt_config_api",__name__)
api = Api(prompt_config_api)


def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    """统一响应格式"""
    return {  # type: ignore[return]
        "code": code,
        "msg": msg,
        "data": data
    }, http_status


# ==================== 辅助函数 ====================

def _validate_file_name(file_name: str) -> tuple:
    """
    验证文件名格式

    Returns:
        (is_valid, error_message)
    """
    if not file_name:
        return False, "文件名不能为空"

    # 检查文件扩展名
    if not file_name.endswith('.txt'):
        return False, "文件名必须以 .txt 结尾"

    # 检查文件名是否包含非法字符
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    for char in invalid_chars:
        if char in file_name:
            return False, f"文件名不能包含特殊字符: {char}"

    return True, None


def _get_category_from_file_name(file_name: str) -> str:
    """
    根据文件名推断分类

    分类规则:
    - data_audit_*.txt -> 数据基础质检
    - *_multi_table.txt -> 聚合检索相关
    - strategy_detect.txt -> 查询融合策略
    - result_fusion.txt -> 跨源结果融合
    - sql_with_relationship.txt -> 联表查询相关
    - table_relationship*.txt -> 表关系分析
    - fill_field*.txt -> 字段填充
    - retry*.txt -> 重试提示
    - report_summary_prompt.txt / dialect_adaptation_prompt.txt / report_dynamic_prompt.txt / rule_parsing_prompt.txt -> 数据治理
    - report_*_chunk.txt -> 报告生成
    - datacard_generate_prompt.txt -> 数据卡片生成
    """
    if file_name.startswith('data_audit_'):
        return '数据基础质检'
    elif '_multi_table.txt' in file_name:
        return '聚合检索相关'
    elif file_name == 'strategy_detect.txt':
        return '查询融合策略'
    elif file_name == 'result_fusion.txt':
        return '跨源结果融合'
    elif file_name == 'sql_with_relationship.txt':
        return '联表查询相关'
    elif 'table_relationship' in file_name:
        return '表关系分析'
    elif 'fill_field' in file_name:
        return '字段填充'
    elif 'retry' in file_name:
        return '重试提示'
    elif file_name in ('report_summary_prompt.txt', 'dialect_adaptation_prompt.txt',
                       'report_dynamic_prompt.txt', 'rule_parsing_prompt.txt'):
        return '数据治理'
    elif file_name in ('report_basic_audit_chunk.txt', 'report_relation_chunk.txt',
                       'report_quality_chunk.txt', 'report_overall_summary_chunk.txt',
                       'report_chunk_prompt.txt'):
        return '报告生成'
    elif file_name in ('datacard_generate_prompt.txt', 'datacard_sample_prompt.txt'):
        return '数据卡片生成'
    else:
        return '其他'


def _get_db_type_from_file_name(file_name: str) -> str:
    """
    根据文件名推断数据库类型
    """
    if 'postgresql' in file_name or file_name.startswith('data_audit_postgre'):
        return 'PostgreSQL'
    elif 'mysql' in file_name:
        return 'MySQL'
    elif 'mssql' in file_name or 'sqlserver' in file_name:
        return 'SQL Server'
    elif 'oracle' in file_name:
        return 'Oracle'
    elif 'sqlite' in file_name:
        return 'SQLite'
    elif 'trino' in file_name:
        return 'Trino'
    elif 'kingbase' in file_name:
        return 'KingBase'
    elif 'oceanbase' in file_name:
        return 'OceanBase'
    elif 'dm' in file_name:
        return '达梦 DM'
    else:
        return '通用'


# ==================== 资源类 ====================

class PromptConfigListResource(Resource):
    """
    提示词列表资源

    GET: 获取提示词列表（支持分页、搜索、分类筛选）
    POST: 创建新提示词
    """

    def get(self):
        """
        获取提示词列表

        Query参数:
            - page: 页码（默认1）
            - page_size: 每页数量（默认20，最大100）
            - search: 搜索关键词（搜索 file_name 和 description）
            - category: 分类筛选（可选）
            - db_type: 数据库类型筛选（可选）
            - include_prompt: 是否包含提示词内容（默认false，仅列表展示时可设为false提升性能）

        返回示例:
            {
                "code": 200,
                "data": {
                    "items": [
                        {
                            "id": "uuid",
                            "file_name": "data_audit_postgre.txt",
                            "description": "PostgreSQL 数据盘查 DDL SQL",
                            "category": "数据盘查",
                            "db_type": "PostgreSQL",
                            "prompt_length": 1234
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "page_size": 20,
                        "total": 15,
                        "total_pages": 1
                    }
                }
            }
        """
        try:
            # 获取查询参数
            page = max(1, int(request.args.get('page', 1)))
            page_size = min(100, max(1, int(request.args.get('page_size', 20))))
            search = request.args.get('search', '').strip()
            category = request.args.get('category', '').strip()
            db_type = request.args.get('db_type', '').strip()
            include_prompt = request.args.get('include_prompt', 'false').lower() == 'true'

            # 构建查询
            query = PromptConfig.query

            # 搜索过滤
            if search:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        PromptConfig.file_name.ilike(search_pattern),
                        PromptConfig.description.ilike(search_pattern)
                    )
                )

            # 分类过滤（通过文件名推断）
            if category:
                # 获取该分类下的所有文件名
                all_configs = PromptConfig.query.all()
                category_file_names = [
                    c.file_name for c in all_configs
                    if _get_category_from_file_name(c.file_name) == category
                ]
                if category_file_names:
                    query = query.filter(PromptConfig.file_name.in_(category_file_names))
                else:
                    return resp(200, "success", {
                        "items": [],
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total": 0,
                            "total_pages": 0
                        }
                    })

            # 数据库类型过滤
            if db_type:
                all_configs = PromptConfig.query.all()
                db_type_file_names = [
                    c.file_name for c in all_configs
                    if _get_db_type_from_file_name(c.file_name) == db_type
                ]
                if db_type_file_names:
                    query = query.filter(PromptConfig.file_name.in_(db_type_file_names))
                else:
                    return resp(200, "success", {
                        "items": [],
                        "pagination": {
                            "page": page,
                            "page_size": page_size,
                            "total": 0,
                            "total_pages": 0
                        }
                    })

            # 获取总数
            total = query.count()

            # 分页
            pagination = query.order_by(PromptConfig.file_name).paginate(
                page=page, per_page=page_size, error_out=False
            )

            # 构建返回数据
            items = []
            for config in pagination.items:
                item = {
                    "id": str(config.id),
                    "file_name": config.file_name,
                    "description": config.description,
                    "category": _get_category_from_file_name(config.file_name),
                    "db_type": _get_db_type_from_file_name(config.file_name),
                    "prompt_length": len(config.prompt) if config.prompt else 0,
                    "created_at": config.created_at.isoformat() if config.created_at else None,
                    "updated_at": config.updated_at.isoformat() if config.updated_at else None,
                }
                if include_prompt:
                    item["prompt"] = config.prompt
                items.append(item)

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
            return resp(500, f"获取提示词列表失败: {str(e)}", None, 500)

    def post(self):
        """
        创建新提示词

        Body参数:
            - file_name: 文件名（必填，格式：xxx.txt）
            - prompt: 提示词内容（必填）
            - description: 描述（可选）

        返回示例:
            {
                "code": 200,
                "data": {
                    "id": "uuid",
                    "file_name": "custom_prompt.txt",
                    "description": "自定义提示词",
                    "message": "创建成功"
                }
            }
        """
        try:
            payload = request.get_json(force=True) or {}
            file_name = payload.get('file_name', '').strip()
            prompt_content = payload.get('prompt', '').strip()
            description = payload.get('description', '').strip()

            # 验证必填参数
            if not file_name:
                return resp(400, "文件名(file_name)不能为空", None, 400)

            if not prompt_content:
                return resp(400, "提示词内容(prompt)不能为空", None, 400)

            # 验证文件名格式
            is_valid, error_msg = _validate_file_name(file_name)
            if not is_valid:
                return resp(400, error_msg, None, 400)

            # 检查是否已存在同名文件
            existing = PromptConfig.query.filter_by(file_name=file_name).first()
            if existing:
                return resp(409, f"文件名 '{file_name}' 已存在，如需更新请使用 PUT 接口", None, 409)

            # 创建新记录
            config = PromptConfig(
                file_name=file_name,
                prompt=prompt_content,
                description=description
            )
            db.session.add(config)
            db.session.commit()

            # 清除相关缓存
            prompt_manager.invalidate_cache(file_name)

            return resp(200, "创建成功", {
                "id": str(config.id),
                "file_name": config.file_name,
                "description": config.description,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "message": "创建成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"创建提示词失败: {str(e)}", None, 500)


class PromptConfigDetailResource(Resource):
    """
    提示词详情资源

    GET: 获取单个提示词详情
    PUT: 更新提示词
    DELETE: 删除提示词
    """

    def get(self, config_id):
        """
        获取单个提示词详情

        Path参数:
            - config_id: 提示词ID (UUID)

        返回示例:
            {
                "code": 200,
                "data": {
                    "id": "uuid",
                    "file_name": "data_audit_postgre.txt",
                    "prompt": "提示词内容...",
                    "description": "PostgreSQL 数据盘查 DDL SQL",
                    "category": "数据盘查",
                    "db_type": "PostgreSQL",
                    "prompt_length": 1234
                }
            }
        """
        try:
            config = PromptConfig.query.get(config_id)
            if not config:
                return resp(404, f"提示词不存在: {config_id}", None, 404)

            return resp(200, "success", {
                "id": str(config.id),
                "file_name": config.file_name,
                "prompt": config.prompt,
                "description": config.description,
                "category": _get_category_from_file_name(config.file_name),
                "db_type": _get_db_type_from_file_name(config.file_name),
                "prompt_length": len(config.prompt) if config.prompt else 0,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            })

        except Exception as e:
            return resp(500, f"获取提示词详情失败: {str(e)}", None, 500)

    def put(self, config_id):
        """
        更新提示词

        Path参数:
            - config_id: 提示词ID (UUID)

        Body参数:
            - prompt: 提示词内容（可选）
            - description: 描述（可选）

        注意：不支持修改 file_name，如需修改请删除后重新创建

        返回示例:
            {
                "code": 200,
                "data": {
                    "id": "uuid",
                    "file_name": "data_audit_postgre.txt",
                    "message": "更新成功"
                }
            }
        """
        try:
            config = PromptConfig.query.get(config_id)
            if not config:
                return resp(404, f"提示词不存在: {config_id}", None, 404)

            payload = request.get_json(force=True) or {}
            prompt_content = payload.get('prompt')
            description = payload.get('description')
            updated_fields = []

            # 更新提示词内容
            if prompt_content is not None:
                if not isinstance(prompt_content, str):
                    return resp(400, "prompt 必须是字符串", None, 400)
                if not prompt_content.strip():
                    return resp(400, "prompt 不能为空字符串", None, 400)
                config.prompt = prompt_content
                updated_fields.append("prompt")

            # 更新描述
            if description is not None:
                config.description = description
                updated_fields.append("description")

            if not updated_fields:
                return resp(400, "没有需要更新的字段", None, 400)

            # 更新 updated_at
            from datetime import datetime
            config.updated_at = datetime.utcnow()

            db.session.commit()

            # 清除相关缓存
            prompt_manager.invalidate_cache(config.file_name)

            return resp(200, "更新成功", {
                "id": str(config.id),
                "file_name": config.file_name,
                "updated_fields": updated_fields,
                "message": "更新成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新提示词失败: {str(e)}", None, 500)

    def delete(self, config_id):
        """
        删除提示词

        Path参数:
            - config_id: 提示词ID (UUID)

        返回示例:
            {
                "code": 200,
                "data": {
                    "file_name": "data_audit_postgre.txt",
                    "message": "删除成功"
                }
            }
        """
        try:
            config = PromptConfig.query.get(config_id)
            if not config:
                return resp(404, f"提示词不存在: {config_id}", None, 404)

            file_name = config.file_name
            db.session.delete(config)
            db.session.commit()

            # 清除相关缓存
            prompt_manager.invalidate_cache(file_name)

            return resp(200, "删除成功", {
                "file_name": file_name,
                "message": "删除成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"删除提示词失败: {str(e)}", None, 500)


class PromptConfigByFileNameResource(Resource):
    """
    通过文件名获取提示词

    GET: 通过文件名获取提示词内容
    """

    def get(self, file_name):
        """
        通过文件名获取提示词

        Path参数:
            - file_name: 文件名（如 data_audit_postgre.txt）

        Query参数:
            - use_cache: 是否使用缓存（默认true）

        返回示例:
            {
                "code": 200,
                "data": {
                    "id": "uuid",
                    "file_name": "data_audit_postgre.txt",
                    "prompt": "提示词内容...",
                    "description": "PostgreSQL 数据盘查 DDL SQL",
                    "category": "数据盘查",
                    "db_type": "PostgreSQL",
                    "from_cache": true
                }
            }
        """
        try:
            # URL 解码文件名
            import urllib.parse
            file_name_decoded = urllib.parse.unquote(file_name)

            use_cache = request.args.get('use_cache', 'true').lower() == 'true'

            config = PromptConfig.query.filter_by(file_name=file_name_decoded).first()
            if not config:
                return resp(404, f"未找到提示词: {file_name_decoded}", None, 404)

            return resp(200, "success", {
                "id": str(config.id),
                "file_name": config.file_name,
                "prompt": config.prompt,
                "description": config.description,
                "category": _get_category_from_file_name(config.file_name),
                "db_type": _get_db_type_from_file_name(config.file_name),
                "from_cache": use_cache,
                "created_at": config.created_at.isoformat() if config.created_at else None,
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            })

        except Exception as e:
            return resp(500, f"获取提示词失败: {str(e)}", None, 500)


class PromptConfigSyncResource(Resource):
    """
    提示词同步资源

    POST /sync_from_file: 从文件同步单个提示词到数据库
    POST /sync_all: 同步所有提示词到数据库
    """

    def post(self):
        """
        同步提示词（单个或全部）

        Body参数:
            - file_name: 文件名（可选，不传则同步全部）
            - file_path: 文件路径（可选，用于指定非默认路径的文件）

        返回示例（单个）:
            {
                "code": 200,
                "data": {
                    "file_name": "data_audit_postgre.txt",
                    "message": "同步成功",
                    "prompt_length": 1234
                }
            }

        返回示例（全部）:
            {
                "code": 200,
                "data": {
                    "success": ["file1.txt", "file2.txt"],
                    "failed": ["file3.txt"],
                    "total": 10,
                    "message": "同步完成"
                }
            }
        """
        try:
            payload = request.get_json(force=True) or {}
            file_name = payload.get('file_name', '').strip()
            file_path = payload.get('file_path', '').strip()

            if file_name:
                # 同步单个文件
                if prompt_manager.sync_from_file(file_name, file_path or None):
                    config = PromptConfig.query.filter_by(file_name=file_name).first()
                    return resp(200, "同步成功", {
                        "file_name": file_name,
                        "message": "同步成功",
                        "prompt_length": len(config.prompt) if config and config.prompt else 0
                    })
                else:
                    return resp(404, f"同步失败：文件不存在或读取失败: {file_name}", None, 404)
            else:
                # 同步全部
                results = prompt_manager.sync_all_from_files()

                return resp(200, "同步完成", {
                    "success": results.get("success", []),
                    "failed": results.get("failed", []),
                    "total": results.get("success", []) + results.get("failed", []),
                    "message": f"同步完成，成功 {len(results.get('success', []))} 个，失败 {len(results.get('failed', []))} 个"
                })

        except Exception as e:
            return resp(500, f"同步提示词失败: {str(e)}", None, 500)


class PromptConfigCategoriesResource(Resource):
    """
    提示词分类资源

    GET: 获取提示词分类列表和统计
    """

    def get(self):
        """
        获取提示词分类列表

        返回示例:
            {
                "code": 200,
                "data": {
                    "categories": [
                        {
                            "name": "数据盘查",
                            "count": 6,
                            "db_types": ["PostgreSQL", "MySQL", "SQL Server", "Oracle", "SQLite", "Trino"]
                        },
                        {
                            "name": "多表查询",
                            "count": 6,
                            "db_types": ["PostgreSQL", "MySQL", "SQL Server", "Oracle", "SQLite", "Trino"]
                        }
                    ],
                    "db_types": ["PostgreSQL", "MySQL", "SQL Server", "Oracle", "SQLite", "Trino"]
                }
            }
        """
        try:
            configs = PromptConfig.query.all()

            # 统计分类
            category_stats = {}
            db_type_stats = {}

            for config in configs:
                category = _get_category_from_file_name(config.file_name)
                db_type = _get_db_type_from_file_name(config.file_name)

                if category not in category_stats:
                    category_stats[category] = {
                        "name": category,
                        "count": 0,
                        "db_types": []
                    }
                category_stats[category]["count"] += 1

                if db_type not in db_type_stats:
                    db_type_stats[db_type] = 0
                db_type_stats[db_type] += 1

                if db_type not in category_stats[category]["db_types"]:
                    category_stats[category]["db_types"].append(db_type)

            # 排序：数据基础质检 > 聚合检索相关 > 查询融合策略 > 跨源结果融合 > 联表查询相关 > 表关系分析 > 字段填充 > 重试提示 > 数据治理 > 报告生成 > 数据卡片生成 > 其他
            category_order = ['数据基础质检', '聚合检索相关', '查询融合策略', '跨源结果融合', '联表查询相关', '表关系分析', '字段填充', '重试提示', '数据治理', '报告生成', '数据卡片生成', '其他']
            sorted_categories = sorted(
                category_stats.values(),
                key=lambda x: category_order.index(x["name"]) if x["name"] in category_order else 999
            )

            return resp(200, "success", {
                "categories": sorted_categories,
                "db_types": sorted(db_type_stats.keys())
            })

        except Exception as e:
            return resp(500, f"获取分类列表失败: {str(e)}", None, 500)


# ==================== 路由注册 ====================
# 注意：更具体的路由必须放在前面，否则会被通配符路由拦截

api.add_resource(PromptConfigListResource, '/list')
api.add_resource(PromptConfigByFileNameResource, '/file/<path:file_name>')
api.add_resource(PromptConfigSyncResource, '/sync')
api.add_resource(PromptConfigCategoriesResource, '/categories')
api.add_resource(PromptConfigDetailResource, '/<string:config_id>')
