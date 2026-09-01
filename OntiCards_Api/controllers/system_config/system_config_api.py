"""
 @File: system_config_api.py
 @Description: 系统配置模块 API
 @Author: 韩小豪 849631113@qq.com
 @Create: 2026-03-30
 @Update: 2026-04-08 - 新增手动数据清理接口 /cleanup
"""

from datetime import datetime, timezone, timedelta as td
from typing import Any, Dict, Tuple
from flask import Blueprint, request
from flask import g as flask_g
from flask_restful import Api, Resource
from flask_login import login_required, current_user

from extensions.ext_database import db
from models.system_configs import SystemConfig, get_config, set_config

system_config_api = Blueprint("system_config_api", __name__)
api = Api(system_config_api)


def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    return {  # type: ignore[return]
        "code": code,
        "msg": msg,
        "data": data
    }, http_status


class SystemConfigResource(Resource):
    """
    系统配置资源
    GET    : 获取配置（列表/单条）
    PUT    : 更新配置
    DELETE : 删除配置
    """

    def get(self):
        """
        获取系统配置

        Query参数:
            - key: 配置键名（可选，不传则返回全部配置）
            - scope: 范围，system=只看系统级，user=只看用户级，all=全部（默认）
            - include_system: 是否包含系统级配置（默认True，配合scope=user使用）

        返回示例:
            {
                "code": 200,
                "data": {
                    "configs": [
                        {
                            "id": "uuid",
                            "config_key": "token_price_embedding",
                            "config_value": "0.0007",
                            "description": "Embedding Token 单价（元/千token）",
                            "user_id": null,
                            "scope": "system"
                        }
                    ]
                }
            }
        """
        try:
            key = request.args.get('key', '').strip()
            scope = request.args.get('scope', 'all').strip().lower()
            include_system = request.args.get('include_system', 'true').lower() == 'true'

            if key:
                # 查询单个配置（支持用户级覆盖）
                config = SystemConfig.query.filter_by(config_key=key).first()
                if not config:
                    return resp(404, f"配置项 '{key}' 不存在", None, 404)

                config_dict = config.to_dict()
                config_dict['scope'] = 'system' if config.user_id is None else 'user'
                return resp(200, "success", config_dict)

            else:
                # 查询全部配置
                query = SystemConfig.query

                if scope == 'system':
                    query = query.filter(SystemConfig.user_id.is_(None))
                elif scope == 'user':
                    if not include_system:
                        query = query.filter(SystemConfig.user_id.isnot(None))
                # scope == 'all': 返回全部

                configs = query.order_by(
                    SystemConfig.user_id,
                    SystemConfig.config_key
                ).all()

                result = []
                for c in configs:
                    config_dict = c.to_dict()
                    config_dict['scope'] = 'system' if c.user_id is None else 'user'
                    result.append(config_dict)

                return resp(200, "success", {
                    "configs": result
                })

        except Exception as e:
            return resp(500, f"查询配置失败: {str(e)}", None, 500)

    def put(self):
        """
        更新或创建系统配置

        Body参数:
            - key: 配置键名，必填
            - value: 配置值，必填
            - description: 配置描述，可选
            - user_id: 目标用户ID（可选，为空或null表示系统级配置）

        返回示例:
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "config_key": "token_price_embedding",
                    "config_value": "0.0008",
                    "user_id": null,
                    "scope": "system",
                    "message": "配置更新成功"
                }
            }
        """
        try:
            payload = request.get_json(force=True) or {}
            key = payload.get('key', '').strip()
            value = payload.get('value')
            description = payload.get('description')
            target_user_id = payload.get('user_id')

            if not key:
                return resp(400, "配置键名(key)不能为空", None, 400)

            if value is None:
                return resp(400, "配置值(value)不能为空", None, 400)

            # 处理 user_id：None表示系统级，其他表示用户级
            config_user_id = None
            if target_user_id and str(target_user_id).lower() != 'null':
                config_user_id = target_user_id

            # 价格配置校验（仅对系统级配置）
            if config_user_id is None:
                try:
                    set_config(key, value, description, validate_price=True, user_id=config_user_id)
                except ValueError as e:
                    return resp(400, str(e), None, 400)
            else:
                set_config(key, value, description, validate_price=False, user_id=config_user_id)

            scope = 'system' if config_user_id is None else 'user'
            return resp(200, "success", {
                "config_key": key,
                "config_value": str(value),
                "user_id": str(config_user_id) if config_user_id else None,
                "scope": scope,
                "message": "配置更新成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新配置失败: {str(e)}", None, 500)

    def delete(self):
        """
        删除系统配置

        Body参数:
            - key: 配置键名，必填
            - user_id: 目标用户ID（可选，为空或null表示系统级配置）

        注意：系统关键配置不建议删除
        """
        try:
            payload = request.get_json(force=True) or {}
            key = payload.get('key', '').strip()
            target_user_id = payload.get('user_id')

            if not key:
                return resp(400, "配置键名(key)不能为空", None, 400)

            # 处理 user_id
            config_user_id = None
            if target_user_id and str(target_user_id).lower() != 'null':
                config_user_id = target_user_id

            # 禁止删除系统级关键配置
            if config_user_id is None:
                protected_keys = [
                    'query_logs_retention_days',
                    'stats_retention_days',
                    'token_price_embedding',
                    'token_price_rerank',
                    'token_price_llm_input',
                    'token_price_llm_output'
                ]

                if key in protected_keys:
                    return resp(403, f"关键配置 '{key}' 禁止删除", None, 403)

            config = SystemConfig.query.filter_by(
                config_key=key,
                user_id=config_user_id
            ).first()
            if not config:
                return resp(404, f"配置项 '{key}' 不存在", None, 404)

            db.session.delete(config)
            db.session.commit()

            scope = 'system' if config_user_id is None else 'user'
            return resp(200, "success", {
                "config_key": key,
                "user_id": str(config_user_id) if config_user_id else None,
                "scope": scope,
                "message": "配置删除成功"
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"删除配置失败: {str(e)}", None, 500)


class TokenPriceConfigResource(Resource):
    """
    Token价格配置专项接口
    GET /console/api/system_config/token_prices
    PUT /console/api/system_config/token_prices

    Query参数(GET):
        - user_id: 用户ID（可选，为空则查系统级配置）
    """

    def get(self):
        """
        获取当前Token价格配置

        Query参数:
            - user_id: 用户ID（可选）

        返回示例:
            {
                "code": 200,
                "data": {
                    "scope": "system",  // "system" 或 "user"
                    "user_id": null,
                    "embedding": {
                        "key": "token_price_embedding",
                        "value": "0.0007",
                        "description": "Embedding Token 单价（元/千token）"
                    },
                    "rerank": {...},
                    "llm_input": {...},
                    "llm_output": {...}
                }
            }
        """
        try:
            user_id = request.args.get('user_id') or None

            # 构建查询条件：先查用户级，找不到再查系统级
            def _get_price(key, default_value):
                if user_id:
                    config = SystemConfig.query.filter_by(
                        config_key=key,
                        user_id=user_id
                    ).first()
                    if config:
                        return config.config_value, config.description
                    config = SystemConfig.query.filter_by(
                        config_key=key,
                        user_id=None
                    ).first()
                else:
                    config = SystemConfig.query.filter_by(
                        config_key=key,
                        user_id=None
                    ).first()
                if config:
                    return config.config_value, config.description
                return default_value, ''

            embedding_val, embedding_desc = _get_price('token_price_embedding', '0.0007')
            rerank_val, rerank_desc = _get_price('token_price_rerank', '0.002')
            llm_input_val, llm_input_desc = _get_price('token_price_llm_input', '0.002')
            llm_output_val, llm_output_desc = _get_price('token_price_llm_output', '0.006')

            config_key_map = {
                'embedding': 'token_price_embedding',
                'rerank': 'token_price_rerank',
                'llm_input': 'token_price_llm_input',
                'llm_output': 'token_price_llm_output'
            }

            result = {
                "scope": "user" if user_id else "system",
                "user_id": str(user_id) if user_id else None,
                "embedding": {
                    "key": config_key_map['embedding'],
                    "value": embedding_val,
                    "description": embedding_desc
                },
                "rerank": {
                    "key": config_key_map['rerank'],
                    "value": rerank_val,
                    "description": rerank_desc
                },
                "llm_input": {
                    "key": config_key_map['llm_input'],
                    "value": llm_input_val,
                    "description": llm_input_desc
                },
                "llm_output": {
                    "key": config_key_map['llm_output'],
                    "value": llm_output_val,
                    "description": llm_output_desc
                }
            }

            return resp(200, "success", result)

        except Exception as e:
            return resp(500, f"获取价格配置失败: {str(e)}", None, 500)

    def put(self):
        """
        批量更新Token价格配置

        Body参数:
            - embedding: Embedding 价格（元/千token）
            - rerank: Rerank 价格（元/千token）
            - llm_input: LLM 输入价格（元/千token）
            - llm_output: LLM 输出价格（元/千token）
            - user_id: 目标用户ID（可选，为空或null表示系统级配置）

        注意：系统级价格会进行合理性校验，用户级价格不校验
        """
        try:
            payload = request.get_json(force=True) or {}
            target_user_id = payload.get('user_id')

            # 处理 user_id
            config_user_id = None
            if target_user_id and str(target_user_id).lower() != 'null':
                config_user_id = target_user_id

            is_system_level = (config_user_id is None)
            validate_price = is_system_level

            updates = []
            errors = []

            price_keys = {
                'embedding': 'token_price_embedding',
                'rerank': 'token_price_rerank',
                'llm_input': 'token_price_llm_input',
                'llm_output': 'token_price_llm_output'
            }

            descriptions = {
                'token_price_embedding': 'Embedding Token 单价（元/千token）',
                'token_price_rerank': 'Rerank Token 单价（元/千token）',
                'token_price_llm_input': 'LLM 输入 Token 单价（元/千token）',
                'token_price_llm_output': 'LLM 输出 Token 单价（元/千token）'
            }

            for short_key, full_key in price_keys.items():
                if short_key in payload:
                    value = payload[short_key]
                    try:
                        set_config(full_key, value, descriptions[full_key],
                                   validate_price=validate_price, user_id=config_user_id)
                        updates.append({
                            "key": full_key,
                            "value": str(value)
                        })
                    except ValueError as e:
                        errors.append(str(e))

            if errors:
                return resp(400, "; ".join(errors), {"updated": updates}, 400)

            scope = "system" if is_system_level else "user"
            return resp(200, "success", {
                "message": f"{'系统级' if is_system_level else '用户级'}价格配置更新成功",
                "scope": scope,
                "user_id": str(config_user_id) if config_user_id else None,
                "updated": updates
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新价格配置失败: {str(e)}", None, 500)


class DataRetentionConfigResource(Resource):
    """
    数据保留配置专项接口
    GET /console/api/system_config/data_retention
    PUT /console/api/system_config/data_retention

    Query参数(GET):
        - user_id: 用户ID（可选，为空则查系统级配置）
    """

    def get(self):
        """
        获取数据保留配置

        Query参数:
            - user_id: 用户ID（可选）
        """
        try:
            user_id = request.args.get('user_id') or None

            def _get_retention(key, default_value):
                if user_id:
                    config = SystemConfig.query.filter_by(
                        config_key=key,
                        user_id=user_id
                    ).first()
                    if config:
                        return config.config_value, config.description
                    config = SystemConfig.query.filter_by(
                        config_key=key,
                        user_id=None
                    ).first()
                else:
                    config = SystemConfig.query.filter_by(
                        config_key=key,
                        user_id=None
                    ).first()
                if config:
                    return config.config_value, config.description
                return default_value, ''

            query_logs_val, query_logs_desc = _get_retention('query_logs_retention_days', '180')
            stats_val, stats_desc = _get_retention('stats_retention_days', '365')

            result = {
                "scope": "user" if user_id else "system",
                "user_id": str(user_id) if user_id else None,
                "query_logs_retention_days": {
                    "value": query_logs_val,
                    "description": query_logs_desc,
                    "unit": "天"
                },
                "stats_retention_days": {
                    "value": stats_val,
                    "description": stats_desc,
                    "unit": "天"
                }
            }

            return resp(200, "success", result)

        except Exception as e:
            return resp(500, f"获取保留配置失败: {str(e)}", None, 500)

    def put(self):
        """
        更新数据保留配置

        Body参数:
            - query_logs_retention_days: 查询日志保留天数
            - stats_retention_days: 聚合统计保留天数
            - user_id: 目标用户ID（可选，为空或null表示系统级配置）
        """
        try:
            payload = request.get_json(force=True) or {}
            target_user_id = payload.get('user_id')

            # 处理 user_id
            config_user_id = None
            if target_user_id and str(target_user_id).lower() != 'null':
                config_user_id = target_user_id

            updates = []
            errors = []

            retention_keys = {
                'query_logs_retention_days': '查询日志保留天数',
                'stats_retention_days': '聚合统计保留天数'
            }

            for key, desc in retention_keys.items():
                if key in payload:
                    value = payload[key]
                    try:
                        int_value = int(value)
                        if int_value < 1 or int_value > 3650:
                            errors.append(f"{desc}必须在1-3650之间")
                            continue
                        set_config(key, str(int_value), desc, validate_price=False, user_id=config_user_id)
                        updates.append({
                            "key": key,
                            "value": str(int_value)
                        })
                    except ValueError:
                        errors.append(f"{desc}必须是有效整数")

            if errors:
                return resp(400, "; ".join(errors), {"updated": updates}, 400)

            scope = "system" if config_user_id is None else "user"
            return resp(200, "success", {
                "message": f"{'系统级' if config_user_id is None else '用户级'}保留配置更新成功",
                "scope": scope,
                "user_id": str(config_user_id) if config_user_id else None,
                "updated": updates
            })

        except Exception as e:
            db.session.rollback()
            return resp(500, f"更新保留配置失败: {str(e)}", None, 500)


class DataCleanupResource(Resource):
    """
    数据清理手动触发接口
    POST /console/api/system_config/cleanup

    用于手动触发数据清理任务（管理员使用）。
    正常情况下，数据清理由定时任务自动执行，此接口仅用于特殊情况。
    """

    def post(self):
        """
        手动触发数据清理

        请求参数（可选）：
            - type: 清理类型，可选值：
                - "logs"：只清理查询日志
                - "stats"：只清理聚合统计
                - "all" 或不传：清理所有（默认）

        注意：此操作可能需要较长时间，返回前会等待清理完成。
        """
        try:
            payload = request.get_json(force=True) or {}
            cleanup_type = payload.get('type', 'all').strip().lower()

            # 导入清理函数
            from task import cleanup_expired_logs, cleanup_expired_stats, cleanup_all

            results = {}
            start_time = datetime.now(tz=timezone(timedelta(hours=8)))

            if cleanup_type == 'logs':
                results = {"query_logs": cleanup_expired_logs()}
            elif cleanup_type == 'stats':
                results = {"query_stats_daily": cleanup_expired_stats()}
            else:
                results = cleanup_all()

            end_time = datetime.now(tz=timezone(timedelta(hours=8)))
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            total_deleted = sum(r.get("deleted", 0) for r in results.values())

            return resp(200, "数据清理完成", {
                "type": cleanup_type,
                "results": results,
                "total_deleted": total_deleted,
                "duration_ms": duration_ms,
                "executed_at": start_time.isoformat()
            })

        except Exception as e:
            import traceback
            return resp(500, f"数据清理失败: {str(e)}\n{traceback.format_exc()}", None, 500)


# 路由注册
api.add_resource(SystemConfigResource, '/config')
api.add_resource(TokenPriceConfigResource, '/token_prices')
api.add_resource(DataRetentionConfigResource, '/data_retention')
api.add_resource(DataCleanupResource, '/cleanup')
