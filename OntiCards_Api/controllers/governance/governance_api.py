"""
@File: governance_api.py
@Description: 数据治理 API - 规则库、规则、报告 CRUD 接口
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
"""
import json

"""
接口列表:

规则库管理:
- GET    /console/api/governance/libraries              - 获取规则库列表
- GET    /console/api/governance/libraries/<id>         - 获取规则库详情（含规则列表）
- POST   /console/api/governance/libraries               - 创建规则库
- PUT    /console/api/governance/libraries/<id>         - 更新规则库
- DELETE /console/api/governance/libraries/<id>          - 删除规则库

规则管理:
- GET    /console/api/governance/rules                  - 获取规则列表（支持按规则库、类型筛选）
- GET    /console/api/governance/rules/<id>            - 获取规则详情
- POST   /console/api/governance/rules                  - 创建规则
- PUT    /console/api/governance/rules/<id>            - 更新规则
- DELETE /console/api/governance/rules/<id>             - 删除规则
- PUT    /console/api/governance/rules/<id>/toggle     - 启用/禁用规则

规则模板:
- GET    /console/api/governance/templates              - 获取系统模板列表
- POST   /console/api/governance/templates/import        - 从模板导入规则

盘点报告:
- GET    /console/api/governance/reports                          - 获取报告列表
- GET    /console/api/governance/reports/<id>                    - 获取报告详情
- DELETE /console/api/governance/reports/<id>                     - 删除报告
- POST   /governance/report                                      - 生成报告文档（替代旧的 /reports/<id>/export，由 GovernanceReportGenerateApi 提供）
- GET    /console/api/governance/reports/<id>/download           - 下载报告文件（支持 ?file_id=xxx 下载历史文件）
- DELETE /console/api/governance/reports/<id>/file               - 删除报告文件
- DELETE /console/api/governance/files/<file_id>                   - 删除单个导出文件记录

数据源元数据:
- GET    /console/api/governance/datasources/<id>/tables                        - 获取数据源下的所有表
- GET    /console/api/governance/datasources/<id>/tables/<table>/columns        - 获取指定表的字段列表
"""

import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Tuple, Union, List, Optional
from flask import Blueprint, request
from flask_restful import Api, Resource

from extensions.ext_database import db
from models.governance_rule_library import GovernanceRuleLibrary
from models.governance_rule import GovernanceRule
from models.governance_rule_template import GovernanceRuleTemplate
from models.governance_report import GovernanceReport
from models.rule_execution_result import RuleExecutionResult
from models.datasource_infos import DatasourceInfo
from models.user_datasource_schema import UserDatasourceSchema

governance_api = Blueprint("governance_api", __name__)
api = Api(governance_api)


def resp(code: int = 200, msg: str = "success", data: Any = None,
         http_status: int = 200) -> Tuple[Dict[str, Any], int]:
    """统一响应格式"""
    return {  # type: ignore[return-value]
        "code": code,
        "msg": msg,
        "data": data
    }, http_status


def _validate_name(name: str, max_length: int = 100) -> tuple:
    """验证名称格式"""
    if not name or not name.strip():
        return False, "名称不能为空"
    if len(name) > max_length:
        return False, f"名称不能超过{max_length}个字符"
    return True, None


# ==================== 规则库 API ====================

class LibraryListApi(Resource):
    """规则库列表"""

    def get(self):
        """获取规则库列表"""
        from flask_login import current_user
        from models.datasource_infos import DatasourceInfo

        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        search = request.args.get('search', '')
        datasource_id = request.args.get('datasource_id')

        query = GovernanceRuleLibrary.query

        if search:
            query = query.filter(
                GovernanceRuleLibrary.name.ilike(f'%{search}%')
            )

        # 支持按数据源筛选
        if datasource_id:
            query = query.filter(GovernanceRuleLibrary.datasource_id == datasource_id)

        query = query.filter_by(created_by=current_user.id)
        query = query.order_by(GovernanceRuleLibrary.created_at.desc())

        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        items = []
        for lib in pagination.items:
            lib_dict = lib.to_dict()
            # 添加数据源信息
            if lib.datasource_id:
                datasource = DatasourceInfo.query.get(lib.datasource_id)
                if datasource:
                    lib_dict['connect_name'] = datasource.connect_name
                    lib_dict['database_name'] = datasource.database_name
                    lib_dict['datasource_db_type'] = datasource.db_type
            items.append(lib_dict)

        return resp(data={
            'items': items,
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'pages': pagination.pages
        })

    def post(self):
        """创建规则库（必须关联数据源）"""
        from flask_login import current_user
        from models.datasource_infos import DatasourceInfo

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        # 验证 datasource_id（必须）
        datasource_id = data.get('datasource_id')
        if not datasource_id:
            return resp(code=400, msg="datasource_id 不能为空，创建规则库必须关联数据源", http_status=400)

        # 验证数据源存在且属于当前用户
        datasource = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()
        if not datasource:
            return resp(code=404, msg="数据源不存在或无权访问", http_status=404)

        name = data.get('name', '').strip()
        valid, err_msg = _validate_name(name)
        if not valid:
            return resp(code=400, msg=err_msg, http_status=400)

        description = data.get('description', '')

        library = GovernanceRuleLibrary(
            name=name,
            description=description,
            status='active',
            created_by=current_user.id,
            datasource_id=datasource_id
        )

        db.session.add(library)
        db.session.commit()

        # 返回包含数据源信息的规则库
        result = library.to_dict()
        result['datasource_name'] = datasource.connect_name
        return resp(data=result)


class LibraryDetailApi(Resource):
    """规则库详情"""

    def get(self, library_id):
        """获取规则库详情（含规则列表和数据源信息）"""
        from flask_login import current_user
        from models.datasource_infos import DatasourceInfo

        library = GovernanceRuleLibrary.query.filter_by(
            id=library_id,
            created_by=current_user.id
        ).first()

        if not library:
            return resp(code=404, msg="规则库不存在", http_status=404)

        library_dict = library.to_dict()

        # 获取数据源信息
        if library.datasource_id:
            datasource = DatasourceInfo.query.get(library.datasource_id)
            if datasource:
                library_dict['datasource_name'] = datasource.connect_name
                library_dict['datasource'] = {
                    'id': str(datasource.id),
                    'name': datasource.connect_name,
                    'db_type': datasource.db_type
                }

        library_dict['rules'] = [r.to_dict() for r in library.rules.all()]

        return resp(data=library_dict)

    def put(self, library_id):
        """更新规则库"""
        from flask_login import current_user

        library = GovernanceRuleLibrary.query.filter_by(
            id=library_id,
            created_by=current_user.id
        ).first()

        if not library:
            return resp(code=404, msg="规则库不存在", http_status=404)

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        if 'name' in data:
            name = data['name'].strip()
            valid, err_msg = _validate_name(name)
            if not valid:
                return resp(code=400, msg=err_msg, http_status=400)
            library.name = name

        if 'description' in data:
            library.description = data['description']

        if 'status' in data:
            library.status = data['status']

        db.session.commit()

        return resp(data=library.to_dict())

    def delete(self, library_id):
        """删除规则库"""
        from flask_login import current_user

        library = GovernanceRuleLibrary.query.filter_by(
            id=library_id,
            created_by=current_user.id
        ).first()

        if not library:
            return resp(code=404, msg="规则库不存在", http_status=404)

        db.session.delete(library)
        db.session.commit()

        return resp(msg="删除成功")


# ==================== 规则 API ====================

class RuleListApi(Resource):
    """规则列表"""

    def get(self):
        """获取规则列表"""
        from flask_login import current_user

        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        library_id = request.args.get('library_id')
        rule_type = request.args.get('rule_type')
        enabled = request.args.get('enabled')
        create_source = request.args.get('create_source')
        search = request.args.get('search', '')

        query = GovernanceRule.query.join(
            GovernanceRuleLibrary,
            GovernanceRule.library_id == GovernanceRuleLibrary.id
        ).filter(
            GovernanceRuleLibrary.created_by == current_user.id
        )

        if library_id:
            query = query.filter(GovernanceRule.library_id == library_id)

        if rule_type:
            query = query.filter(GovernanceRule.rule_type == rule_type)

        if enabled is not None:
            query = query.filter(GovernanceRule.enabled == (enabled.lower() == 'true'))

        if create_source and create_source in GovernanceRule.CREATE_SOURCES:
            query = query.filter(GovernanceRule.create_source == create_source)

        if search:
            query = query.filter(
                GovernanceRule.rule_name.ilike(f'%{search}%')
            )

        query = query.order_by(GovernanceRule.created_at.desc())

        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        items = []
        for rule in pagination.items:
            rule_dict = rule.to_dict()
            # 添加数据源信息
            if rule.library and rule.library.datasource_id:
                rule_dict['datasource_id'] = str(rule.library.datasource_id)
                datasource = DatasourceInfo.query.get(rule.library.datasource_id)
                if datasource:
                    rule_dict['connect_name'] = datasource.connect_name
                    rule_dict['datasource_name'] = datasource.database_name
                    rule_dict['datasource_db_type'] = datasource.db_type
            items.append(rule_dict)

        return resp(data={
            'items': items,
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'pages': pagination.pages
        })

    def post(self):
        """创建规则"""
        from flask_login import current_user

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        # 创建来源
        create_source = data.get('create_source', 'manual')
        if create_source not in GovernanceRule.CREATE_SOURCES:
            create_source = 'manual'

        library_id = data.get('library_id')
        library = None
        db_type = None
        schema_name = None
        if library_id:
            library = GovernanceRuleLibrary.query.filter_by(
                id=library_id,
                created_by=current_user.id
            ).first()
            if not library:
                return resp(code=400, msg="规则库不存在", http_status=400)
            # 从规则库关联的数据源继承 db_type 和 schema_name
            ds = DatasourceInfo.query.get(library.datasource_id)
            if ds:
                db_type = ds.db_type
                schema_name = ds.schema_name
        else:
            return resp(code=400, msg="library_id 不能为空", http_status=400)

        # ============================================
        # 手动专家模式（提前验证，避免后续重复代码）
        # ============================================
        if create_source == 'manual':
            rule_name = data.get('rule_name', '').strip()
            valid, err_msg = _validate_name(rule_name, max_length=255)
            if not valid:
                return resp(code=400, msg=err_msg, http_status=400)

            # 检查同一规则库下是否已存在同名规则
            if library_id:
                existing_rule = GovernanceRule.query.filter_by(
                    library_id=library_id, rule_name=rule_name
                ).first()
                if existing_rule:
                    return resp(
                        code=400,
                        msg=f"规则库中已存在同名规则「{rule_name}」",
                        http_status=400
                    )

            target_table = (data.get('target_table') or '').strip()
            if not target_table:
                return resp(code=400, msg="手动模式下目标表（target_table）不能为空", http_status=400)

            rule_type_input = data.get('rule_type', 'custom_sql')
            rule_type = rule_type_input if rule_type_input in GovernanceRule.RULE_TYPES else 'custom_sql'

            conditions = data.get('conditions', [])
            is_composite = (rule_type == 'composite' and conditions)

            # 单条件模式下才需要 target_column 和 condition_expr
            if not is_composite:
                target_column = (data.get('target_column') or '').strip()
                condition_expr = (data.get('condition_expr') or '').strip()
                if not target_column:
                    return resp(code=400, msg="单条件模式下目标列（target_column）不能为空", http_status=400)
                if not condition_expr:
                    return resp(code=400, msg="单条件模式下条件表达式（condition_expr）不能为空", http_status=400)
                if condition_expr and 'column' in condition_expr and target_column:
                    condition_expr = condition_expr.replace('column', f'"{target_column}"')
            else:
                target_column = None
                condition_expr = None

            severity = data.get('severity', 'warning')
            if severity not in GovernanceRule.SEVERITIES:
                severity = 'warning'

            # 生成 sql_text
            sql_text = data.get('sql_text')
            if not sql_text and condition_expr:
                sql_text = self._generate_preview_sql(
                    target_table, target_column, condition_expr, rule_type,
                    schema=schema_name, db_type=db_type
                )

            rule = GovernanceRule(
                library_id=library_id,
                rule_name=rule_name,
                rule_type=rule_type,
                target_table=target_table,
                target_column=target_column,
                condition_expr=condition_expr,
                sql_text=sql_text,
                severity=severity,
                description=data.get('description'),
                enabled=data.get('enabled', True),
                create_source='manual',
                db_type=db_type
            )

            # 复合条件支持
            if conditions:
                processed_conditions = []
                for cond in conditions:
                    processed_cond = dict(cond)
                    cond_expr = processed_cond.get('condition', '')
                    cond_column = processed_cond.get('column', '')
                    if cond_expr and 'column' in cond_expr and cond_column:
                        processed_cond['condition'] = cond_expr.replace('column', f'"{cond_column}"')
                    processed_conditions.append(processed_cond)

                rule.set_conditions(processed_conditions, data.get('condition_mode', 'AND'))
                if not sql_text:
                    sql_text = self._generate_composite_preview_sql(
                        target_table, processed_conditions, data.get('condition_mode', 'AND'),
                        schema=schema_name, db_type=db_type
                    )
                    rule.sql_text = sql_text

        # ============================================
        # AI 自然语言模式
        # ============================================
        elif create_source == 'ai':
            rule_name = data.get('rule_name', '').strip()
            valid, err_msg = _validate_name(rule_name, max_length=255)
            if not valid:
                return resp(code=400, msg=err_msg, http_status=400)

            if library_id:
                existing_rule = GovernanceRule.query.filter_by(
                    library_id=library_id, rule_name=rule_name
                ).first()
                if existing_rule:
                    return resp(
                        code=400,
                        msg=f"规则库中已存在同名规则「{rule_name}」",
                        http_status=400
                    )

            rule_config = data.get('rule_config')
            if not rule_config:
                return resp(code=400, msg="AI模式下 rule_config 不能为空", http_status=400)

            rule_type = rule_config.get('rule_type', 'threshold')
            if rule_type not in GovernanceRule.RULE_TYPES:
                rule_type = 'custom_sql'

            ai_conditions = rule_config.get('conditions', [])
            ai_condition_mode = rule_config.get('condition_mode', 'AND')

            if not rule_config.get('target_table'):
                return resp(code=400, msg="AI模式下 target_table 不能为空", http_status=400)

            severity = data.get('severity', 'warning')
            if severity not in GovernanceRule.SEVERITIES:
                severity = 'warning'

            ai_description = data.get('user_input') or data.get('description') or ''
            ai_sql_text = (data.get('sql_preview') or
                           rule_config.get('sql_preview') or
                           data.get('sql_text') or '')

            if not ai_sql_text:
                ai_sql_text = self._generate_ai_preview_sql(
                    target_table=rule_config.get('target_table'),
                    target_column=rule_config.get('target_column'),
                    condition_expr=rule_config.get('condition_expr'),
                    conditions=ai_conditions,
                    condition_mode=ai_condition_mode,
                    rule_type=rule_type,
                    schema=schema_name,
                    db_type=db_type
                )

            is_ai_composite = (rule_type == 'composite' and ai_conditions)
            ai_condition_expr = None if is_ai_composite else rule_config.get('condition_expr')

            rule = GovernanceRule(
                library_id=library_id,
                rule_name=rule_name,
                rule_type=rule_type,
                target_table=rule_config.get('target_table'),
                target_column=rule_config.get('target_column'),
                condition_expr=ai_condition_expr,
                sql_text=ai_sql_text,
                severity=rule_config.get('severity', severity),
                description=ai_description,
                enabled=data.get('enabled', True),
                create_source='ai',
                db_type=db_type
            )
            if ai_conditions:
                rule.set_conditions(ai_conditions, ai_condition_mode)

        # ============================================
        # 模板模式
        # ============================================
        else:
            template_id = data.get('template_id')
            if not template_id:
                return resp(code=400, msg="模板模式下必须传入 template_id", http_status=400)

            template = GovernanceRuleTemplate.query.get(template_id)
            if not template:
                return resp(code=404, msg=f"模板「{template_id}」不存在", http_status=404)

            # 规则名：优先用户输入，否则自动生成
            tmpl_rule_name = data.get('rule_name', '').strip()
            if not tmpl_rule_name:
                t_table = data.get('target_table', '') or ''
                t_col = data.get('target_column', '') or ''
                if t_table and t_col:
                    tmpl_rule_name = f"{template.template_name}({t_table}.{t_col})"
                elif t_table:
                    tmpl_rule_name = f"{template.template_name}({t_table})"
                else:
                    tmpl_rule_name = template.template_name

            # 规则名不能为空
            valid, err_msg = _validate_name(tmpl_rule_name, max_length=255)
            if not valid:
                return resp(code=400, msg=err_msg, http_status=400)

            # 重复规则名检查
            if library_id:
                existing_rule = GovernanceRule.query.filter_by(
                    library_id=library_id, rule_name=tmpl_rule_name
                ).first()
                if existing_rule:
                    return resp(
                        code=400,
                        msg=f"规则库中已存在同名规则「{tmpl_rule_name}」",
                        http_status=400
                    )

            tmpl_target_table = (data.get('target_table') or '').strip()
            if not tmpl_target_table:
                return resp(code=400, msg="模板模式下目标表（target_table）不能为空", http_status=400)

            tmpl_target_column = (data.get('target_column') or '').strip()

            tmpl_rule_type = data.get('rule_type') or template.rule_type
            if tmpl_rule_type not in GovernanceRule.RULE_TYPES:
                tmpl_rule_type = 'custom_sql'

            tmpl_severity = data.get('severity') or template.default_severity
            if tmpl_severity not in GovernanceRule.SEVERITIES:
                tmpl_severity = 'warning'

            tmpl_description = data.get('description') or template.description or ''

            # 条件表达式
            tmpl_condition_expr = (data.get('condition_expr') or '').strip()
            if not tmpl_condition_expr:
                tmpl_condition_expr = template.default_condition or ''
            if tmpl_condition_expr and 'column' in tmpl_condition_expr and tmpl_target_column:
                tmpl_condition_expr = tmpl_condition_expr.replace(
                    'column', f'"{tmpl_target_column}"'
                )

            # SQL 预览
            tmpl_sql_text = data.get('sql_text') or ''
            if not tmpl_sql_text and tmpl_condition_expr:
                tmpl_sql_text = self._generate_preview_sql(
                    tmpl_target_table, tmpl_target_column,
                    tmpl_condition_expr, tmpl_rule_type,
                    schema=schema_name, db_type=db_type
                )

            rule = GovernanceRule(
                library_id=library_id,
                rule_name=tmpl_rule_name,
                rule_type=tmpl_rule_type,
                target_table=tmpl_target_table,
                target_column=tmpl_target_column,
                condition_expr=tmpl_condition_expr,
                sql_text=tmpl_sql_text,
                severity=tmpl_severity,
                description=tmpl_description,
                enabled=data.get('enabled', True),
                create_source='template',
                db_type=db_type
            )

        db.session.add(rule)
        db.session.commit()

        return resp(data=rule.to_dict())

    def _generate_preview_sql(
        self,
        table_name: str,
        column_name: str,
        condition_expr: str,
        rule_type: str,
        schema: str = None,
        db_type: str = 'postgresql'
    ) -> str:
        """
        生成预览SQL（用于手动模式和模板模式）

        核心逻辑（按优先级）：
        1. rule_type == 'unique' → 唯一性检测专用模板（优先级最高）
        2. rule_type == 'consistency_check' → 一致性检测专用模板
        3. 有 condition_expr → 专家/模板模式：NOT(业务条件) = 违规条件
        4. 无 condition_expr → 自动模式：根据 rule_type 生成默认条件

        Args:
            table_name: 表名
            column_name: 列名
            condition_expr: 业务条件表达式
            rule_type: 规则类型
            schema: Schema 名（可选）
            db_type: 数据库类型（默认 postgresql）

        Returns:
            预览SQL字符串
        """
        if not table_name:
            return ""

        from controllers.governance.dialect_adapter import DialectAdapter
        adapter = DialectAdapter(db_type)
        quoted_table = adapter.quote_table_reference(table_name, schema)
        quoted_col = adapter.quote_identifier(column_name) if column_name else None

        # ============================================================
        # 优先级 1：唯一性检测（优先级最高）
        # ============================================================
        if rule_type == 'unique':
            # 唯一性检测：COUNT(DISTINCT) != COUNT 表示出现重复
            return f"""SELECT COUNT(*) as total_count, COUNT({quoted_col}) as non_null_count, COUNT(DISTINCT {quoted_col}) as unique_count, COUNT(*) - COUNT(DISTINCT {quoted_col}) as duplicate_count FROM {quoted_table} WHERE {quoted_col} IS NOT NULL AND {quoted_col} != ''"""

        # ============================================================
        # 优先级 2：一致性检测（NULL 值会导致 NOT() 失效）
        # ============================================================
        if rule_type == 'consistency_check' and condition_expr:
            match = re.search(r'(\w+)\s*=\s*(\w+)', condition_expr)
            if match:
                col1, col2 = match.group(1), match.group(2)
                violation_condition = f"({col1} <> {col2}) OR ({col1} IS NULL) <> ({col2} IS NULL)"
                return f'SELECT COUNT(*) as total_count, SUM(CASE WHEN {violation_condition} THEN 1 ELSE 0 END) as failed_count FROM {quoted_table}'

        # ============================================================
        # 优先级 3：有 condition_expr → 专家/模板模式
        # ============================================================
        if column_name and condition_expr:
            # 只在 condition_expr 包含 column 占位符时才替换
            if 'column' in condition_expr.lower():
                sql_condition = re.sub(
                    r'\bcolumn\b',
                    quoted_col,
                    condition_expr,
                    flags=re.IGNORECASE
                )
            else:
                # 已处理的条件表达式
                sql_condition = condition_expr

            return f'SELECT COUNT(*) as total_count, SUM(CASE WHEN NOT ({sql_condition}) THEN 1 ELSE 0 END) as failed_count FROM {quoted_table}'

        # ============================================================
        # 优先级 4：自动模式
        # ============================================================
        if rule_type == 'null_check':
            return f'SELECT COUNT(*) as total_count, SUM(CASE WHEN NOT ({quoted_col} IS NOT NULL AND {quoted_col} != \'\') THEN 1 ELSE 0 END) as failed_count FROM {quoted_table}'

        return f'SELECT COUNT(*) as total_count FROM {quoted_table}'

    def _generate_composite_preview_sql(
        self,
        table_name: str,
        conditions: list,
        condition_mode: str = 'AND',
        schema: str = None,
        db_type: str = 'postgresql'
    ) -> str:
        """
        生成复合条件的预览SQL（用于手动模式的多条件规则）

        语义：conditions 中存储的是【业务条件】（business conditions），
        即"必须满足的条件"。SQL 中每个条件取反后，根据德摩根定律反向连接：
          - 业务 AND → 违规用 OR （任一不满足即为违规）
          - 业务 OR  → 违规用 AND （全部不满足才为违规）
        注意：必须先取反，再切换连接符，否则会双重否定，导致与执行SQL语义不一致。

        Args:
            table_name: 表名
            conditions: 条件数组，每个条件格式如 {"column": "xxx", "rule_type": "xxx", "condition": "xxx"}
                        condition 为业务条件（如 "> 0"、"IS NOT NULL"）
            condition_mode: 业务条件组合方式，AND 或 OR
            schema: Schema 名（可选）
            db_type: 数据库类型（默认 postgresql）

        Returns:
            预览SQL字符串
        """
        if not table_name:
            return ""

        from controllers.governance.dialect_adapter import DialectAdapter
        adapter = DialectAdapter(db_type)
        quoted_table = adapter.quote_table_reference(table_name, schema)

        if not conditions:
            return f'SELECT COUNT(*) as total_count FROM {quoted_table}'

        # 构建组合条件：业务条件取反后得到违规条件
        condition_parts = []
        for cond in conditions:
            column = cond.get('column', '')
            rule_type = cond.get('rule_type', '')
            condition = cond.get('condition', '')

            if column and condition:
                # 替换 column 占位符为实际列名
                sql_cond = condition.replace('column', f'"{column}"')
                # 业务条件取反，得到违规条件
                condition_parts.append(f'(NOT ({sql_cond}))')

        if not condition_parts:
            return f'SELECT COUNT(*) as total_count FROM {quoted_table}'

        # De Morgan：业务 AND → 违规用 OR，业务 OR → 违规用 AND
        sql_mode = 'OR' if condition_mode == 'AND' else 'AND'
        separator = f' {sql_mode} '
        combined_condition = separator.join(condition_parts)

        return f'SELECT COUNT(*) as total_count, SUM(CASE WHEN {combined_condition} THEN 1 ELSE 0 END) as failed_count FROM {quoted_table}'

    def _generate_ai_preview_sql(
        self,
        target_table: str,
        target_column: str,
        condition_expr: str,
        conditions: list,
        condition_mode: str,
        rule_type: str,
        schema: str = None,
        db_type: str = 'postgresql'
    ) -> str:
        """
        生成AI模式下的预览SQL（用于自然语言模式创建规则时自动生成sql_text）

        核心逻辑（按优先级）：
        1. rule_type == 'unique' → 唯一性检测专用模板（优先级最高）
        2. 有 conditions（多条件）→ 复合规则
        3. 有 condition_expr（单条件）→ NOT(业务条件)
        4. 无条件 → 基础计数

        Args:
            target_table: 表名
            target_column: 列名（单条件规则）
            condition_expr: 条件表达式（已替换列名）
            conditions: 条件数组（多条件规则）
            condition_mode: 条件组合方式
            rule_type: 规则类型
            schema: Schema 名（可选）
            db_type: 数据库类型（默认 postgresql）

        Returns:
            预览SQL字符串
        """
        if not target_table:
            return ""

        from controllers.governance.dialect_adapter import DialectAdapter
        adapter = DialectAdapter(db_type)
        quoted_table = adapter.quote_table_reference(target_table, schema)
        quoted_col = adapter.quote_identifier(target_column) if target_column else None

        # ============================================================
        # 优先级 1：唯一性检测
        # ============================================================
        if rule_type == 'unique' and quoted_col:
            return f"""SELECT COUNT(*) as total_count, COUNT({quoted_col}) as non_null_count, COUNT(DISTINCT {quoted_col}) as unique_count, COUNT(*) - COUNT(DISTINCT {quoted_col}) as duplicate_count FROM {quoted_table} WHERE {quoted_col} IS NOT NULL AND {quoted_col} != ''"""

        # ============================================================
        # 优先级 2：多条件规则（composite）
        # ============================================================
        if conditions:
            condition_parts = []
            for cond in conditions:
                column = cond.get('column', '')
                condition = cond.get('condition', '')

                if column and condition:
                    # AI模式的条件已替换列名，直接包装 NOT()
                    condition_parts.append(f'(NOT ({condition}))')

            if condition_parts:
                # De Morgan：业务 AND → 违规用 OR，业务 OR → 违规用 AND
                sql_mode = 'OR' if condition_mode == 'AND' else 'AND'
                separator = f' {sql_mode} '
                combined_condition = separator.join(condition_parts)
                return f'SELECT COUNT(*) as total_count, SUM(CASE WHEN {combined_condition} THEN 1 ELSE 0 END) as failed_count FROM {quoted_table}'

        # ============================================================
        # 优先级 3：单条件规则
        # ============================================================
        if target_column and condition_expr:
            return f'SELECT COUNT(*) as total_count, SUM(CASE WHEN NOT ({condition_expr}) THEN 1 ELSE 0 END) as failed_count FROM {quoted_table}'

        # ============================================================
        # 兜底：只返回总行数
        # ============================================================
        return f'SELECT COUNT(*) as total_count FROM {quoted_table}'


class RuleDetailApi(Resource):
    """规则详情"""

    def get(self, rule_id):
        """获取规则详情"""
        from flask_login import current_user

        datasource_id = request.args.get('datasource_id')

        query = GovernanceRule.query.join(
            GovernanceRuleLibrary
        ).filter(
            GovernanceRule.id == rule_id,
            GovernanceRuleLibrary.created_by == current_user.id
        )
        if datasource_id:
            query = query.filter(GovernanceRuleLibrary.datasource_id == datasource_id)
        rule = query.first()

        if not rule:
            return resp(code=404, msg="规则不存在", http_status=404)

        return resp(data=rule.to_dict())

    def put(self, rule_id):
        """更新规则"""
        from flask_login import current_user

        datasource_id = request.args.get('datasource_id')

        query = GovernanceRule.query.join(
            GovernanceRuleLibrary
        ).filter(
            GovernanceRule.id == rule_id,
            GovernanceRuleLibrary.created_by == current_user.id
        )
        if datasource_id:
            query = query.filter(GovernanceRuleLibrary.datasource_id == datasource_id)
        rule = query.first()

        if not rule:
            return resp(code=404, msg="规则不存在", http_status=404)

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        if 'rule_name' in data:
            name = data['rule_name'].strip()
            valid, err_msg = _validate_name(name, max_length=255)
            if not valid:
                return resp(code=400, msg=err_msg, http_status=400)

            # 检查同一规则库下是否已存在同名规则（排除自身）
            check_library_id = data.get('library_id', rule.library_id)
            if check_library_id:
                existing_rule = GovernanceRule.query.filter(
                    GovernanceRule.library_id == check_library_id,
                    GovernanceRule.rule_name == name,
                    GovernanceRule.id != rule_id
                ).first()
                if existing_rule:
                    return resp(
                        code=400,
                        msg=f"规则库中已存在同名规则「{name}」",
                        http_status=400
                    )
            rule.rule_name = name

        if 'rule_type' in data:
            if data['rule_type'] not in GovernanceRule.RULE_TYPES:
                return resp(code=400, msg="无效的规则类型", http_status=400)
            old_rule_type = rule.rule_type
            new_rule_type = data['rule_type']
            rule.rule_type = new_rule_type

            # 当 rule_type 在复合条件和非复合类型之间切换时，同步相关字段
            is_new_composite = (new_rule_type == 'composite' and data.get('conditions'))
            is_old_composite = (old_rule_type == 'composite')

            if is_new_composite and not is_old_composite:
                # 非复合 → 复合：清空 target_column / condition_expr，保留 conditions_config
                rule.target_column = None
                rule.condition_expr = None
            elif not is_new_composite and is_old_composite:
                # 复合 → 非复合：清空 conditions_config
                rule.conditions_config = None

        if 'severity' in data:
            if data['severity'] in GovernanceRule.SEVERITIES:
                rule.severity = data['severity']

        # 只更新前端显式传入的字段（None 也视为显式传值，会清空字段）
        for field in ['target_table', 'condition_expr', 'sql_text', 'description']:
            if field in data:
                setattr(rule, field, data[field])

        # target_column 需要特殊处理：复合条件模式下不更新
        if 'target_column' in data:
            if rule.rule_type != 'composite':
                rule.target_column = data['target_column']
            # composite 模式下不更新 target_column

        if 'enabled' in data:
            rule.enabled = data['enabled']

        if 'library_id' in data:
            library_id = data['library_id']
            if library_id:
                library = GovernanceRuleLibrary.query.filter_by(
                    id=library_id,
                    created_by=current_user.id
                ).first()
                if not library:
                    return resp(code=400, msg="规则库不存在", http_status=400)
            rule.library_id = library_id

        # 处理多条件配置
        if 'conditions' in data:
            conditions = data['conditions']
            condition_mode = data.get('condition_mode', 'AND')
            if conditions:
                # 统一替换 column 占位符为实际列名
                processed_conditions = []
                for cond in conditions:
                    processed_cond = dict(cond)
                    cond_expr = processed_cond.get('condition', '')
                    cond_column = processed_cond.get('column', '')
                    if cond_expr and 'column' in cond_expr and cond_column:
                        processed_cond['condition'] = cond_expr.replace('column', f'"{cond_column}"')
                    processed_conditions.append(processed_cond)
                rule.set_conditions(processed_conditions, condition_mode)
            else:
                rule.conditions_config = None

        db.session.commit()

        return resp(data=rule.to_dict())

    def delete(self, rule_id):
        """删除规则"""
        from flask_login import current_user

        datasource_id = request.args.get('datasource_id')

        query = GovernanceRule.query.join(
            GovernanceRuleLibrary
        ).filter(
            GovernanceRule.id == rule_id,
            GovernanceRuleLibrary.created_by == current_user.id
        )
        if datasource_id:
            query = query.filter(GovernanceRuleLibrary.datasource_id == datasource_id)
        rule = query.first()

        if not rule:
            return resp(code=404, msg="规则不存在", http_status=404)

        db.session.delete(rule)
        db.session.commit()

        return resp(msg="删除成功")


class RuleToggleApi(Resource):
    """规则启用/禁用"""

    def put(self, rule_id):
        """切换规则启用状态"""
        from flask_login import current_user

        datasource_id = request.args.get('datasource_id')

        query = GovernanceRule.query.join(
            GovernanceRuleLibrary
        ).filter(
            GovernanceRule.id == rule_id,
            GovernanceRuleLibrary.created_by == current_user.id
        )
        if datasource_id:
            query = query.filter(GovernanceRuleLibrary.datasource_id == datasource_id)
        rule = query.first()

        if not rule:
            return resp(code=404, msg="规则不存在", http_status=404)

        rule.enabled = not rule.enabled
        db.session.commit()

        return resp(data={
            'id': str(rule.id),
            'enabled': rule.enabled,
            'msg': '启用成功' if rule.enabled else '禁用成功'
        })


# ==================== 规则模板 API ====================

class TemplateListApi(Resource):
    """规则模板列表 / 分组模板列表"""

    def get(self):
        """获取系统模板列表

        Query 参数:
            - rule_type:     可选，按规则类型过滤（如 null_check）
            - group_by:      可选，值为 'rule_type' 时按规则类型分组返回
            - keyword:       可选，关键字模糊搜索（匹配模板名称和描述）
            - library_id:    可选，关联规则库ID，用于返回"已在该规则库中的模板"标记
            - datasource_id: 可选，数据源ID，用于返回"该数据源下建议应用的模板"标记

        返回（group_by 不为 'rule_type'）:
            { "code": 200, "data": [模板字典, ...] }

        返回（group_by='rule_type'）:
            { "code": 200, "data": {
                "groups": [
                    { "rule_type": "null_check", "rule_type_name": "空值检测", "templates": [...] },
                    ...
                ],
                "total": 27
            }}
        """
        rule_type = request.args.get('rule_type')
        group_by = request.args.get('group_by')
        keyword = request.args.get('keyword', '').strip()
        library_id = request.args.get('library_id')
        datasource_id = request.args.get('datasource_id')

        query = GovernanceRuleTemplate.query

        if rule_type:
            query = query.filter(GovernanceRuleTemplate.rule_type == rule_type)

        if keyword:
            query = query.filter(
                db.or_(
                    GovernanceRuleTemplate.template_name.ilike(f'%{keyword}%'),
                    GovernanceRuleTemplate.description.ilike(f'%{keyword}%')
                )
            )

        templates = query.order_by(GovernanceRuleTemplate.rule_type).all()

        # ---- 分组返回模式 ----
        if group_by == 'rule_type':
            from collections import defaultdict
            groups_dict = defaultdict(list)
            for t in templates:
                groups_dict[t.rule_type].append(t.to_dict())

            groups = []
            for rt, tpls in sorted(groups_dict.items()):
                from models.governance_rule_template import RULE_TYPE_NAMES
                groups.append({
                    'rule_type': rt,
                    'rule_type_name': RULE_TYPE_NAMES.get(rt, rt),
                    'templates': tpls
                })

            # 标记已导入到指定规则库的模板
            if library_id:
                imported_tmpl_ids = set(
                    row[0] for row in db.session.query(GovernanceRule.rule_type)
                    .filter(GovernanceRule.library_id == library_id, GovernanceRule.create_source == 'template')
                    .distinct().all()
                )
                for g in groups:
                    for t in g['templates']:
                        t['is_imported'] = t['id'] in imported_tmpl_ids

            return resp(data={
                'groups': groups,
                'total': len(templates)
            })

        # ---- 普通列表返回模式 ----
        template_list = [t.to_dict() for t in templates]

        # 标记已导入到指定规则库的模板
        if library_id:
            imported_tmpl_ids = set(
                str(row[0]) for row in
                db.session.query(GovernanceRule.id)
                .filter(GovernanceRule.library_id == library_id, GovernanceRule.create_source == 'template')
                .distinct().all()
            )
            for t in template_list:
                t['is_imported'] = t['id'] in imported_tmpl_ids

        return resp(data=template_list)


class TemplateDetailApi(Resource):
    """规则模板详情"""

    def get(self, template_id):
        """获取指定模板的完整信息

        路径参数:
            template_id: 模板ID（如 'tmpl-null-check'）

        返回:
            { "code": 200, "data": { 模板完整字典 } }
            { "code": 404, "msg": "模板不存在" }
        """
        template = GovernanceRuleTemplate.query.get(template_id)
        if not template:
            return resp(code=404, msg="模板不存在", http_status=404)

        result = template.to_dict(include_details=True)

        # 可选：返回已关联该模板的数据源列表（最近使用过的前5个）
        # 这里可以扩展：返回哪些规则库已导入过该模板
        related_rules = GovernanceRule.query.filter_by(
            rule_type=template.rule_type,
            create_source='template'
        ).limit(10).all()
        result['related_rules_count'] = len(related_rules)

        return resp(data=result)


class TemplateImportApi(Resource):
    """从模板导入规则"""

    def post(self):
        """从模板导入规则

        请求参数:
        {
            "template_ids": ["template_id1", "template_id2"],  // 必填，模板ID列表
            "library_id": "xxx",                               // 必填，目标规则库ID
            "target_table": "orders",                          // 可选，指定目标表
            "target_column": "total_amount",                   // 可选，指定目标列
            "override_name": true                              // 可选，是否追加表/列名到规则名称后缀，默认 true
        }

        说明:
        - 不指定 target_table/target_column: 导入通用规则模板
        - 指定 target_table: 导入针对指定表的规则
        - 同时指定 target_table + target_column: 导入针对具体表+列的规则
        - override_name=true 时，规则名称会追加 "(表名.列名)" 后缀
        """
        from flask_login import current_user

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        template_ids = data.get('template_ids', [])
        library_id = data.get('library_id')
        target_table = data.get('target_table')
        target_column = data.get('target_column')
        override_name = data.get('override_name', True)

        if not library_id:
            return resp(code=400, msg="请选择目标规则库", http_status=400)

        library = GovernanceRuleLibrary.query.filter_by(
            id=library_id,
            created_by=current_user.id
        ).first()

        if not library:
            return resp(code=404, msg="规则库不存在", http_status=404)

        if not template_ids:
            return resp(code=400, msg="请选择要导入的模板", http_status=400)

        templates = GovernanceRuleTemplate.query.filter(
            GovernanceRuleTemplate.id.in_(template_ids)
        ).all()

        if not templates:
            return resp(code=404, msg="未找到指定的模板", http_status=404)

        imported_rules = []
        for template in templates:
            # 生成规则名称
            rule_name = template.template_name
            if override_name and target_table:
                if target_column:
                    rule_name = f"{template.template_name}({target_table}.{target_column})"
                else:
                    rule_name = f"{template.template_name}({target_table})"

            rule = GovernanceRule(
                library_id=library_id,
                rule_name=rule_name,
                rule_type=template.rule_type,
                target_table=target_table,
                target_column=target_column,
                condition_expr=template.default_condition,
                severity='warning',
                description=template.description,
                enabled=True,
                create_source='template'  # 模板导入来源
            )
            db.session.add(rule)
            imported_rules.append(rule)

        db.session.commit()

        return resp(data={
            'imported_count': len(imported_rules),
            'target_table': target_table,
            'target_column': target_column,
            'rules': [r.to_dict() for r in imported_rules]
        })


# ==================== 报告 API ====================

class ReportListApi(Resource):
    """报告列表"""

    def get(self):
        """获取报告列表"""
        from flask_login import current_user
        from models.datasource_infos import DatasourceInfo

        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        datasource_id = request.args.get('datasource_id')

        query = GovernanceReport.query.filter_by(user_id=current_user.id)

        if datasource_id:
            query = query.filter_by(datasource_id=datasource_id)

        query = query.order_by(GovernanceReport.created_at.desc())

        pagination = query.paginate(page=page, per_page=page_size, error_out=False)

        # 一次性查出所有涉及的数据源，O(1) 次查询
        ds_ids = list({r.datasource_id for r in pagination.items if r.datasource_id})
        datasource_dict = {}
        if ds_ids:
            for ds in DatasourceInfo.query.filter(DatasourceInfo.id.in_(ds_ids)).all():
                datasource_dict[ds.id] = ds

        items = [report.to_summary_dict(datasource_dict) for report in pagination.items]

        return resp(data={
            'items': items,
            'total': pagination.total,
            'page': page,
            'page_size': page_size,
            'pages': pagination.pages
        })


class ReportDetailApi(Resource):
    """报告详情"""

    def get(self, report_id):
        """获取报告详情"""
        from flask_login import current_user

        report = GovernanceReport.query.filter_by(
            id=report_id,
            user_id=current_user.id
        ).first()

        if not report:
            return resp(code=404, msg="报告不存在", http_status=404)

        report_dict = report.to_dict(include_details=True)

        return resp(data=report_dict)

    def delete(self, report_id):
        """删除报告（同时删除关联的所有导出文件）"""
        from flask_login import current_user
        from models.global_inventory import TableRelationship, TableRelationshipCard
        from models.governance_report_file import GovernanceReportFile

        report = GovernanceReport.query.filter_by(
            id=report_id,
            user_id=current_user.id
        ).first()

        if not report:
            return resp(code=404, msg="报告不存在", http_status=404)

        # 1. 查询并删除该报告产生的所有导出文件（物理文件）
        report_files = GovernanceReportFile.query.filter_by(report_id=report.id).all()
        files_deleted_count = 0
        files_not_found = []
        for rf in report_files:
            try:
                # 统一处理路径分隔符，确保跨平台兼容
                import os as os_module
                file_path = rf.file_path.replace('/', os_module.sep)
                if os_module.path.exists(file_path):
                    os_module.remove(file_path)
                    files_deleted_count += 1
                else:
                    files_not_found.append(rf.file_path)
            except Exception as e:
                print(f"[删除报告] 删除文件失败: {rf.file_path}, error={e}")

        # 2. 删除本报告在关系盘点阶段产生的 table_relationship /
        # table_relationship_card 记录
        rel_deleted = db.session.query(TableRelationship).filter(
            TableRelationship.governance_report_id == report.id
        ).delete(synchronize_session=False)

        card_deleted = db.session.query(TableRelationshipCard).filter(
            TableRelationshipCard.governance_report_id == report.id
        ).delete(synchronize_session=False)

        # 3. 删除报告（governance_report_files 表通过 CASCADE 自动清理记录）
        db.session.delete(report)
        db.session.commit()

        return resp(msg="删除成功", data={
            'report_id': str(report.id),
            'files_deleted': files_deleted_count,
            'files_not_found': files_not_found,  # 文件不存在的原因可能是已手动删除
            'rule_execution_results_cleared': 'cascade',
            'table_relationships_deleted': rel_deleted,
            'table_relationship_cards_deleted': card_deleted,
        })

    def put(self, report_id):
        """修改报告名称"""
        from flask_login import current_user
        from flask import request

        # 获取请求数据
        data = request.get_json(silent=True) or {}

        # 验证必填参数
        new_report_name = data.get('report_name')
        if new_report_name is None:
            return resp(code=400, msg="report_name 不能为空", http_status=400)

        # 限制名称长度
        if len(new_report_name) > 255:
            return resp(code=400, msg="报告名称不能超过255个字符", http_status=400)

        # 查询报告
        report = GovernanceReport.query.filter_by(
            id=report_id,
            user_id=current_user.id
        ).first()

        if not report:
            return resp(code=404, msg="报告不存在", http_status=404)

        # 1. 更新主报告表（governance_reports.report_name）
        report.report_name = new_report_name

        # 2. 同步更新文件关联表（governance_report_files.report_name）
        # 该字段为冗余存储，前端 history_files 列表会展示，因此必须保持一致
        from models.governance_report_file import GovernanceReportFile
        files_updated = db.session.query(GovernanceReportFile).filter(
            GovernanceReportFile.report_id == report.id
        ).update(
            {GovernanceReportFile.report_name: new_report_name},
            synchronize_session=False
        )

        db.session.commit()

        return resp(msg="修改成功", data={
            'report_id': str(report.id),
            'report_name': report.report_name,
            'files_updated': files_updated,
            'updated_at': report.created_at.isoformat() if report.created_at else None,
        })


# ==================== 注册路由 ====================

api.add_resource(LibraryListApi, '/libraries')
api.add_resource(LibraryDetailApi, '/libraries/<string:library_id>')
api.add_resource(RuleListApi, '/rules')
api.add_resource(RuleDetailApi, '/rules/<string:rule_id>')
api.add_resource(RuleToggleApi, '/rules/<string:rule_id>/toggle')
api.add_resource(TemplateListApi, '/templates')
api.add_resource(TemplateDetailApi, '/templates/<string:template_id>')
api.add_resource(TemplateImportApi, '/templates/import')
api.add_resource(ReportListApi, '/reports')
api.add_resource(ReportDetailApi, '/reports/<string:report_id>')


# ==================== 报告导出/下载 API ====================

from flask import send_file, current_app, Response
from controllers.governance.report_exporter import ReportExporter


class ReportDownloadApi(Resource):
    """报告下载"""

    def get(self, report_id):
        """下载报告文件
        可选查询参数:
        - file_id: 指定要下载的文件ID（从 governance_report_files 表中获取）
                   如果不传，则下载报告的最新导出文件
        """
        from flask_login import current_user
        from flask import request

        print(f"\n{'='*60}")
        print(f"[环节四 - 下载报告] 开始下载 | report_id={report_id}")
        print(f"{'='*60}\n")

        # 获取可选的 file_id 参数
        file_id = request.args.get('file_id')

        report = GovernanceReport.query.filter_by(
            id=report_id,
            user_id=current_user.id
        ).first()

        if not report:
            print(f"[环节四 - 下载报告] 报告不存在 | report_id={report_id}")
            return resp(code=404, msg="报告不存在", http_status=404)

        print(f"[环节四 - 下载报告] 报告查询成功 | report_name={report.report_name}, exported_file_name={report.exported_file_name}, file_status={report.file_status}")

        # 如果指定了 file_id，下载对应文件
        if file_id:
            print(f"[环节四 - 下载报告] 指定文件下载 | file_id={file_id}")
            from models.governance_report_file import GovernanceReportFile
            report_file = GovernanceReportFile.query.filter_by(
                id=file_id,
                report_id=report_id
            ).first()

            if not report_file:
                print(f"[环节四 - 下载报告] 文件记录不存在 | file_id={file_id}")
                return resp(code=404, msg="文件记录不存在", http_status=404)

            if not os.path.exists(report_file.file_path):
                print(f"[环节四 - 下载报告] 文件不存在，可能已被删除 | path={report_file.file_path}")
                return resp(code=404, msg="文件不存在，可能已被删除", http_status=404)

            file_path = report_file.file_path
            download_filename = report_file.file_name

            # 根据文件类型确定 MIME 类型
            mime_types = {
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'html': 'text/html',
                'md': 'text/markdown'
            }
            mime_type = mime_types.get(report_file.file_type, 'application/octet-stream')

            print(f"[环节四 - 下载报告] 历史文件下载 | file_path={file_path}, file_name={download_filename}")
        else:
            # 不指定 file_id，下载最新文件（原有逻辑）
            print(f"[环节四 - 下载报告] 文件路径: {report.exported_file_path}")

            # 生成下载文件名（优先使用 exported_file_name，否则使用 report_name 或默认值）
            if report.exported_file_name:
                download_filename = report.exported_file_name
            else:
                report_name = report.report_name or 'governance_report'
                timestamp = datetime.now().strftime('%Y%m%d')
                extension_map = {
                    'pdf': 'pdf', 'docx': 'docx', 'excel': 'xlsx', 'xlsx': 'xlsx',
                    'html': 'html', 'md': 'md'
                }
                extension = extension_map.get(report.exported_file_type, 'xlsx')
                download_filename = f"{report_name}_{timestamp}.{extension}"
            print(f"[环节四 - 下载报告] 最终下载文件名: {download_filename}")

            if not report.exported_file_path:
                print(f"[环节四 - 下载报告] 报告文件未生成，请先导出")
                return resp(code=404, msg="报告文件未生成，请先导出", http_status=404)

            if not os.path.exists(report.exported_file_path):
                print(f"[环节四 - 下载报告] 报告文件不存在，可能已被删除 | path={report.exported_file_path}")
                return resp(code=404, msg="报告文件不存在，可能已被删除", http_status=404)

            file_path = report.exported_file_path

            # 确定 MIME 类型
            mime_types = {
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'html': 'text/html',
                'md': 'text/markdown'
            }
            mime_type = mime_types.get(report.exported_file_type, 'application/octet-stream')

        try:
            from urllib.parse import quote

            print(f"[环节四 - 下载报告] 开始发送文件 | file_path={file_path}, mime={mime_type}")

            # 对中文文件名进行 RFC 5987 编码
            encoded_filename = quote(download_filename, safe='')

            # 构建 Content-Disposition 头，同时提供传统 filename 和 RFC 5987 filename*
            # 传统 filename 处理英文和 URL 编码文件名，filename* 处理中文等特殊字符
            content_disposition = f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"

            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # 使用 Response 对象直接返回，确保 Content-Disposition 头正确设置
            response = Response(
                file_data,
                mimetype=mime_type,
                headers={
                    'Content-Disposition': content_disposition,
                    'Content-Length': len(file_data),
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )

            print(f"[环节四 - 下载报告] Content-Disposition 头已设置: {content_disposition}")
            return response
        except Exception as e:
            print(f"[环节四 - 下载报告] 下载失败: {e}")
            import traceback
            traceback.print_exc()
            return resp(code=500, msg=f"下载失败: {str(e)}", http_status=500)


class ReportFileDeleteApi(Resource):
    """删除报告文件"""

    def delete(self, report_id):
        """删除报告的导出文件（保留报告记录）"""
        from flask_login import current_user

        report = GovernanceReport.query.filter_by(
            id=report_id,
            user_id=current_user.id
        ).first()

        if not report:
            return resp(code=404, msg="报告不存在", http_status=404)

        if not report.exported_file_path:
            return resp(code=404, msg="报告文件不存在", http_status=404)

        try:
            exporter = ReportExporter()
            deleted = exporter.delete_export_file(report.exported_file_path)

            if deleted:
                # 清除文件记录
                report.exported_file_path = None
                report.exported_file_type = None
                report.file_size = None
                report.file_created_at = None
                db.session.commit()
                return resp(msg="文件删除成功")
            else:
                return resp(code=500, msg="文件删除失败", http_status=500)

        except Exception as e:
            return resp(code=500, msg=f"删除失败: {str(e)}", http_status=500)


class ReportFileRecordDeleteApi(Resource):
    """删除单个导出文件记录（从 governance_report_files 表中删除指定文件）"""

    def delete(self, file_id):
        """删除指定的导出文件记录

        Args:
            file_id: 文件记录ID（来自 governance_report_files 表的 id 字段）

        Returns:
            删除结果
        """
        from flask_login import current_user
        from models.governance_report_file import GovernanceReportFile

        # 1. 查询文件记录
        report_file = GovernanceReportFile.query.filter_by(
            id=file_id,
            user_id=current_user.id
        ).first()

        if not report_file:
            return resp(code=404, msg="文件记录不存在", http_status=404)

        # 2. 删除物理文件
        try:
            exporter = ReportExporter()
            deleted = exporter.delete_export_file(report_file.file_path)

            if not deleted:
                print(f"[删除文件记录] 物理文件删除失败（可能已不存在）| file_id={file_id}, path={report_file.file_path}")

        except Exception as e:
            print(f"[删除文件记录] 物理文件删除异常 | file_id={file_id}, error={str(e)}")

        # 3. 删除数据库记录
        try:
            db.session.delete(report_file)
            db.session.commit()

            # 4. 如果被删除的文件是报告的最新导出文件（记录在 governance_reports.exported_file_path），
            #    需要更新报告的最新文件信息
            report = GovernanceReport.query.filter_by(id=report_file.report_id).first()
            if report and report.exported_file_path == report_file.file_path:
                # 查询该报告还有没有其他导出文件
                latest_file = GovernanceReportFile.query.filter_by(
                    report_id=report.id
                ).order_by(GovernanceReportFile.created_at.desc()).first()

                if latest_file:
                    report.exported_file_path = latest_file.file_path
                    report.exported_file_name = latest_file.file_name
                    report.exported_file_type = latest_file.file_type
                    report.file_size = latest_file.file_size
                    report.file_created_at = latest_file.created_at
                else:
                    # 没有其他文件了，清除最新文件记录
                    report.exported_file_path = None
                    report.exported_file_name = None
                    report.exported_file_type = None
                    report.file_size = None
                    report.file_created_at = None
                    report.file_status = 'pending'

                db.session.commit()

            return resp(msg="文件删除成功")

        except Exception as e:
            db.session.rollback()
            return resp(code=500, msg=f"删除失败: {str(e)}", http_status=500)


# 注册新路由
api.add_resource(ReportDownloadApi, '/reports/<string:report_id>/download')
api.add_resource(ReportFileDeleteApi, '/reports/<string:report_id>/file')
api.add_resource(ReportFileRecordDeleteApi, '/files/<string:file_id>')


# ==================== 治理规则执行 API（环节二） ====================
# 说明：执行治理规则，将结果写入 rule_execution_results 表，并更新报告的统计字段
#        不生成文档，文档生成由环节三 GovernanceReportGenerateApi 单独处理

class GovernanceRuleExecutionApi(Resource):
    """执行治理规则（环节二：仅执行，返回执行结果）

    与环节三 GovernanceReportGenerateApi 的区别：
    - 仅执行规则，不生成文档
    - 立即返回执行结果，前端可分层展示
    - 文档生成由环节三独立接口触发
    """

    def post(self):
        """执行治理规则

        请求参数:
        {
            "datasource_id": "xxx",              # 数据源ID（必填）
            "library_ids": ["lib1", "lib2"],     # 规则库ID列表（可选）
            "rule_ids": ["rule1", "rule2"],     # 规则ID列表（可选，与 library_ids 互斥）
            "include_basic_audit": true,         # 是否包含基础空值检测（可选，默认 false）
            "include_relation_discovery": true   # 是否包含表关系发现（可选，默认 false）
        }

        返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "report_id": "xxx",              # 报告ID（执行容器）
                "quality_score": 85.5,
                "grade": "良好",
                "summary": {
                    "total_rules": 20,
                    "passed_rules": 17,
                    "failed_rules": 3,
                    "error_rules": 0,
                    "quality_score": 85.0,
                    "grade": "良好"
                },
                "results": [                    # 每条规则的执行结果，前端可直接呈现
                    {
                        "id": "xxx",
                        "rule_id": "xxx",
                        "rule_name": "手机号非空检测",
                        "rule_type": "null_check",
                        "severity": "critical",
                        "table_name": "users",
                        "column_name": "phone",
                        "total_count": 10000,
                        "passed_count": 9980,
                        "failed_count": 20,
                        "failed_rate": 0.20,
                        "failed_samples": [...],  # 带条件上下文
                        "status": "passed"
                    },
                    ...
                ]
            }
        }
        """
        from flask_login import current_user
        from controllers.datasource.database_schema_extractor import get_db_engine
        from controllers.governance.audit_executor import AuditExecutor

        try:
            data = request.get_json(force=True, silent=True)
        except Exception as json_err:
            return resp(code=400, msg=f"请求参数格式错误: {str(json_err)}", http_status=400)

        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        datasource_id = data.get('datasource_id')
        if not datasource_id:
            return resp(code=400, msg="数据源ID不能为空", http_status=400)

        print(f"\n{'='*60}")
        print(f"[环节二 - 规则执行] 开始执行 | datasource_id={datasource_id}")
        print(f"[环节二 - 规则执行] 请求参数: {data}")
        print(f"{'='*60}\n")

        datasource = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()
        if not datasource:
            return resp(code=404, msg="数据源不存在", http_status=404)

        # 1. 获取规则
        library_ids = data.get('library_ids', [])
        rule_ids = data.get('rule_ids', [])
        include_basic_audit = data.get('include_basic_audit', False)
        include_relation_discovery = data.get('include_relation_discovery', False)

        print(f"[环节二 - 规则执行] 开始查询规则 | library_ids={library_ids}, rule_ids={rule_ids}")

        rules = []
        # 只有在传入了 library_ids 或 rule_ids 时才查询治理规则库
        has_governance_scope = bool(library_ids) or bool(rule_ids)
        if has_governance_scope:
            rules_query = GovernanceRule.query.join(
                GovernanceRuleLibrary
            ).filter(
                GovernanceRule.enabled == True,
                GovernanceRuleLibrary.datasource_id == datasource_id,
                GovernanceRuleLibrary.created_by == current_user.id
            )
            if library_ids:
                rules_query = rules_query.filter(GovernanceRule.library_id.in_(library_ids))
            if rule_ids:
                rules_query = rules_query.filter(GovernanceRule.id.in_(rule_ids))
            rules = rules_query.all()
            print(f"[环节二 - 规则执行] 查询到 {len(rules)} 条规则")

        # 2. 构建连接
        import json
        connection_string = self._build_connection_string(datasource)

        print(f"[环节二 - 规则执行] 数据库连接字符串构建完成，准备获取引擎")

        try:
            engine = get_db_engine(connection_string, db_type=datasource.db_type)
            print(f"[环节二 - 规则执行] 数据库引擎获取成功")
        except Exception as e:
            print(f"[环节二 - 规则执行] 数据库连接失败: {e}")
            return resp(code=500, msg=f"数据库连接失败: {str(e)}", http_status=500)

        # 3. 创建报告记录（作为执行容器）
        print(f"[环节二 - 规则执行] 创建报告记录...")
        report = GovernanceReport(
            user_id=current_user.id,
            datasource_id=datasource_id,
            report_name=f"质检结果_{datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}",
            scope_tables=None,
            include_quality=has_governance_scope,
            include_basic_audit=include_basic_audit,
            include_relationship=include_relation_discovery,
            file_status='pending'
        )
        db.session.add(report)
        db.session.commit()

        print(f"[环节二 - 规则执行] 报告记录创建成功 | report_id={report.id}")

        # 4. 执行规则
        db_name = datasource.database_name or ''
        schema_name = datasource.schema_name
        # 兼容 audit_executor 复用 perform_data_audit：把原始 connect_info 转成 dict
        # （Oracle/Trino 需要 username/catalog/trino_catalog_type 等）
        # 注意：数据库中存储的是加密后的 connect_info，需要解密后再使用
        from core.connect_info_encryptor import decrypt_connect_info
        ci_raw = decrypt_connect_info(getattr(datasource, 'connect_info', None))
        connect_info_dict = None
        if ci_raw:
            import json as _json
            if isinstance(ci_raw, str):
                if '://' in ci_raw:
                    connect_info_dict = {'url': ci_raw}
                else:
                    try:
                        connect_info_dict = _json.loads(ci_raw)
                    except Exception:
                        connect_info_dict = None
            elif isinstance(ci_raw, dict):
                connect_info_dict = dict(ci_raw)
        if isinstance(connect_info_dict, dict):
            connect_info_dict.setdefault('database', datasource.database_name)
            connect_info_dict.setdefault('schema', datasource.schema_name)
            # Trino 的 catalog_type 在 datasource 上如果有，捎带传过去
            if hasattr(datasource, 'catalog_type') and datasource.catalog_type:
                connect_info_dict.setdefault('catalog_type', datasource.catalog_type)

        executor = AuditExecutor(
            engine, datasource.db_type, db_name, schema_name,
            connect_info=connect_info_dict,
        )

        # 收集各模块结果
        basic_audit_data = None  # 基础空值检测完整结果
        relation_discovery_result = None  # 关系盘点完整结果

        try:
            # execute_only 返回 (RuleExecutionResult列表, 基础审计数据列表或None)
            results, _basic_audit_data = executor.execute_only(
                report_id=str(report.id),
                rules=rules,
                include_basic_audit=include_basic_audit
            )
            basic_audit_data = _basic_audit_data
            print(f"[环节二 - 规则执行] 规则执行完成 | 执行结果数={len(results)}")
        except Exception as exec_err:
            report.file_status = 'failed'
            report.file_error_msg = str(exec_err)
            db.session.commit()
            print(f"[环节二 - 规则执行] 规则执行异常: {exec_err}")
            return resp(code=500, msg=f"规则执行失败: {str(exec_err)}", http_status=500)

        # 5. 表关系发现（复用全域盘点）
        if include_relation_discovery:
            try:
                from controllers.global_inventory.global_inventory_service import run_global_inventory
                from models.global_inventory import TableRelationship, TableRelationshipCard
                import uuid as uuid_module

                print(f"[环节二 - 规则执行] 开始执行表关系发现...")
                relation_discovery_result = run_global_inventory(
                    datasource_id=str(datasource_id),
                    user_id=str(current_user.id),
                    schema_name=datasource.schema_name,
                    confidence_threshold=0.5,
                    max_workers=10,
                    enable_profiling=True
                )
                print(f"[环节二 - 规则执行] 表关系发现完成: {relation_discovery_result.get('relationships_count', 0)} 个关系")

                # 关联本次关系结果到治理报告
                report_uuid = uuid_module.UUID(str(report.id))
                job_uuid = uuid_module.uuid4()
                self._tag_relation_results_with_report(
                    report_uuid, job_uuid, datasource_id
                )
            except Exception as rel_err:
                print(f"[环节二 - 规则执行] 表关系发现失败: {rel_err}")

        # 6. 计算质量统计并更新报告
        print(f"[环节二 - 规则执行] 计算质量统计...")
        stats = AuditExecutor.compute_quality_from_results(results)
        report.quality_score = stats['quality_score']
        report.grade = stats['grade']
        report.summary = stats['summary']
        report.rules_applied = len(results)

        # 只保留有 rule_id 的质检结果（便于追溯）
        quality_audit_result = [
            r.to_dict() for r in results if r.rule_id is not None
        ]

        # 对所有要写入 JSONB 字段的数据统一做序列化清洗，避免 datetime/UUID/Decimal 等类型无法被序列化
        # （PostgreSQL JSONB 内部使用 json.dumps，对 datetime 对象直接报错）
        # 注意：通过模块属性引用而非函数内 import，避免被 Python 当作局部变量导致 UnboundLocalError
        from controllers.governance import audit_executor as _ae_module
        from models.rule_execution_result import RuleExecutionResult
        _sanitize = _ae_module._sanitize_for_json
        report.basic_audit_result = _sanitize(basic_audit_data)
        report.full_relation_discovery = _sanitize(relation_discovery_result)
        report.quality_audit_result = _sanitize(quality_audit_result)

        # 从 rule_execution_results 表查询基础空值检测明细（execution_source='basic_audit'）
        basic_audit_detail_records = RuleExecutionResult.query.filter_by(
            report_id=report.id,
            execution_source=RuleExecutionResult.SOURCE_BASIC_AUDIT
        ).all()
        basic_audit_detail_list = [r.to_dict() for r in basic_audit_detail_records]
        # 统一写入 basic_audit_detail 字段，包含 rules_count 统计
        _basic_audit_detail = _sanitize({
            'rules_count': len(basic_audit_detail_list),
            'results': basic_audit_detail_list
        }) if basic_audit_detail_list else _sanitize({'rules_count': 0, 'results': []})
        report.basic_audit_detail = _basic_audit_detail

        # 构建执行接口完整返回值（保留用于兼容，核心数据已分散到各独立字段）
        response_data = {
            'report_id': str(report.id),
            'quality_score': float(report.quality_score) if report.quality_score else 0,
            'grade': str(report.grade) if report.grade else '一般',
            'summary': report.summary or {},
            'execution_time': datetime.now().isoformat(),
        }

        # 基础空值检测汇总（来自 executor.execute_only 返回的 basic_audit_data）
        if include_basic_audit and basic_audit_data:
            response_data['basic_audit'] = {
                'tables_count': len(basic_audit_data),
                'tables': _sanitize(basic_audit_data)
            }

        # 基础空值检测明细（execution_source='basic_audit'）
        response_data['basic_audit_detail'] = _basic_audit_detail

        # 基于规则库的质检明细（execution_source='rule_library'）
        if quality_audit_result:
            response_data['quality_audit'] = {
                'rules_count': len(quality_audit_result),
                'results': quality_audit_result
            }

        # 关系盘点结果：完整存入，不做列表截断
        # 字段完整列表（保证报告生成阶段拥有全部数据）：
        # - tables_count, relationships_count, cards_count
        # - relationships[]：全部关系记录
        # - cards[]：全部关系卡片
        # - statistics：关系盘点统计信息
        if include_relation_discovery and relation_discovery_result:
            response_data['relation_discovery'] = {
                'tables_count': relation_discovery_result.get('tables_count', 0),
                'relationships_count': relation_discovery_result.get('relationships_count', 0),
                'cards_count': relation_discovery_result.get('cards_count', 0),
                'statistics': relation_discovery_result.get('statistics', {}),
                'relationships': relation_discovery_result.get('relationships', []),
                'cards': relation_discovery_result.get('cards', []),
            }

        # 将完整执行接口返回值存入 execution_response，作为报告生成的唯一数据源
        # 旧字段 report.details / report.basic_audit_result / report.full_relation_discovery / report.quality_audit_result
        # 仍保留用于兼容，新字段 execution_response 作为报告生成唯一数据源
        # 先对整个 response_data 做 JSON 清洗，避免 datetime/UUID/Decimal 等类型无法被 SQLAlchemy JSONB 字段序列化
        report.execution_response = _sanitize(response_data)
        db.session.commit()

        print(f"[环节二 - 规则执行] 报告更新完成 | quality_score={stats['quality_score']}, grade={stats['grade']}, rules_applied={len(results)}")
        print(f"[环节二 - 规则执行] 执行完毕 | report_id={report.id}\n")

        return resp(data=response_data)

    @staticmethod
    def _build_connection_string(datasource):
        """构建数据库连接字符串"""
        import json
        # 注意：数据库中存储的是加密后的 connect_info，需要解密后再使用
        from core.connect_info_encryptor import decrypt_connect_info
        connect_info_raw = decrypt_connect_info(datasource.connect_info)
        connection_string = None

        if connect_info_raw:
            if isinstance(connect_info_raw, str):
                if '://' in connect_info_raw:
                    connection_string = connect_info_raw
                else:
                    try:
                        connect_info_dict = json.loads(connect_info_raw)
                    except (json.JSONDecodeError, ValueError):
                        connect_info_dict = {}
                    if connect_info_dict:
                        connect_info_dict['dbType'] = datasource.db_type
                        connect_info_dict.setdefault('database', datasource.database_name)
                        connect_info_dict.setdefault('schema', datasource.schema_name)
                        from controllers.datasource.database_schema_extractor import build_db_url_from_json
                        connection_string = build_db_url_from_json(connect_info_dict)
            else:
                connect_info_dict = {}
        else:
            connect_info_dict = {}

        if not connection_string:
            connect_info_dict = {
                'dbType': datasource.db_type,
                'database': datasource.database_name,
                'schema': datasource.schema_name
            }
            if hasattr(datasource, 'catalog_type') and datasource.catalog_type:
                connect_info_dict['catalog_type'] = datasource.catalog_type
            from controllers.datasource.database_schema_extractor import build_db_url_from_json
            connection_string = build_db_url_from_json(connect_info_dict)

        return connection_string

    def _tag_relation_results_with_report(
        self,
        report_uuid,
        job_uuid,
        datasource_id
    ):
        """
        将本次关系盘点产生的 table_relationship / table_relationship_card 记录
        标记上治理报告来源，便于追溯和查询。
        """
        from models.global_inventory import TableRelationship, TableRelationshipCard
        from extensions.ext_database import db

        # 标记关系记录
        db.session.query(TableRelationship).filter(
            TableRelationship.table_a_datasource_id == datasource_id,
            TableRelationship.source_type == 'global_inventory'
        ).update({
            TableRelationship.source_type: 'governance',
            TableRelationship.governance_report_id: report_uuid,
            TableRelationship.governance_job_id: job_uuid
        }, synchronize_session=False)

        # 标记卡片记录
        db.session.query(TableRelationshipCard).filter(
            TableRelationshipCard.datasource_id == datasource_id,
            TableRelationshipCard.source_type == 'global_inventory'
        ).update({
            TableRelationshipCard.source_type: 'governance',
            TableRelationshipCard.governance_report_id: report_uuid,
            TableRelationshipCard.governance_job_id: job_uuid
        }, synchronize_session=False)

        db.session.commit()
        print(f"[环节二 - 规则执行] 关系结果已关联报告 | report_id={report_uuid}, job_id={job_uuid}")


class GovernanceReportExecuteApi(Resource):
    """执行单条规则测试"""

    def post(self):
        """测试执行单条规则

        请求参数:
        {
            "datasource_id": "xxx",
            "rule_id": "xxx"
        }
        """
        from flask_login import current_user
        from controllers.datasource.database_schema_extractor import get_db_engine
        from controllers.governance.audit_executor import RuleExecutor

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        datasource_id = data.get('datasource_id')
        rule_id = data.get('rule_id')

        if not datasource_id:
            return resp(code=400, msg="数据源ID不能为空", http_status=400)
        if not rule_id:
            return resp(code=400, msg="规则ID不能为空", http_status=400)

        # 获取数据源
        datasource = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()

        if not datasource:
            return resp(code=404, msg="数据源不存在", http_status=404)

        # 获取规则
        rule = GovernanceRule.query.join(
            GovernanceRuleLibrary
        ).filter(
            GovernanceRule.id == rule_id,
            GovernanceRuleLibrary.datasource_id == datasource_id,
            GovernanceRuleLibrary.created_by == current_user.id
        ).first()

        if not rule:
            return resp(code=404, msg="规则不存在", http_status=404)

        # 验证规则是否配置了目标表和列
        if not rule.target_table or not rule.target_column:
            return resp(code=400, msg=f"规则「{rule.rule_name}」未配置目标表或目标列，无法执行", http_status=400)

        # 构建连接信息
        import json
        from core.connect_info_encryptor import decrypt_connect_info
        connect_info_raw = decrypt_connect_info(datasource.connect_info)
        connection_string = None

        # 判断存储格式：连接字符串 或 JSON 字典
        if connect_info_raw:
            if isinstance(connect_info_raw, str):
                if '://' in connect_info_raw:
                    connection_string = connect_info_raw
                else:
                    try:
                        connect_info_dict = json.loads(connect_info_raw)
                    except (json.JSONDecodeError, ValueError):
                        print(f"[WARN] 数据源连接信息解析失败: {connect_info_raw}")
                        connect_info_dict = {}

                    if connect_info_dict:
                        connect_info_dict['dbType'] = datasource.db_type
                        connect_info_dict.setdefault('database', datasource.database_name)
                        connect_info_dict.setdefault('schema', datasource.schema_name)
                        from controllers.datasource.database_schema_extractor import build_db_url_from_json
                        connection_string = build_db_url_from_json(connect_info_dict)
            else:
                connect_info_dict = {}
        else:
            connect_info_dict = {}

        if not connection_string:
            connect_info_dict = {
                'dbType': datasource.db_type,
                'database': datasource.database_name,
                'schema': datasource.schema_name
            }
            if hasattr(datasource, 'catalog_type') and datasource.catalog_type:
                connect_info_dict['catalog_type'] = datasource.catalog_type
            from controllers.datasource.database_schema_extractor import build_db_url_from_json
            connection_string = build_db_url_from_json(connect_info_dict)

        try:
            engine = get_db_engine(connection_string, db_type=datasource.db_type)
            db_name = datasource.database_name or ''
            schema_name = datasource.schema_name

            executor = RuleExecutor(engine, datasource.db_type, db_name, schema_name)
            result = executor.execute_rule(rule)

            return resp(data=result.to_dict())

        except Exception as e:
            return resp(code=500, msg=f"执行失败: {str(e)}", http_status=500)


# ==================== 治理报告生成 API（环节三） ====================
# 说明：基于已有报告（report_id），生成可下载的文档（DOCX/PDF/XLSX）
#        文档生成依赖 LibreOffice（soffice）或 python-docx/openpyxl

class GovernanceReportGenerateApi(Resource):
    """生成治理报告文档（环节三：文档生成）

    基于已有的 rule_execution_results 数据，通过 LibreOffice 或 python-docx
    生成可下载的 Word/PDF/Excel 文档。
    """

    def post(self):
        """生成报告文档

        请求参数:
        {
            "report_id": "xxx",              # 报告ID（必填，来自环节二）
            "format": "docx",                # 文档格式（可选，默认 docx）
                                              # 可选值: docx, pdf, xlsx, md
            "report_name": "自定义报告名称"    # 报告名称（可选，不传入则保持原名）
        }

        返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "report_id": "xxx",
                "file_path": "/path/to/report.docx",
                "file_name": "自定义报告名称_20260629.docx",
                "file_size": 12345,
                "format": "docx",
                "mode": "soffice"             # 生成模式: soffice | python-docx | openpyxl | markdown
            }
        }
        """
        from flask_login import current_user
        from controllers.governance.libreoffice_exporter import LibreOfficeExporter

        print(f"\n{'='*60}")
        print(f"[环节三 - 生成报告] 开始生成报告文档")
        print(f"{'='*60}\n")

        try:
            data = request.get_json(force=True, silent=True)
        except Exception as json_err:
            print(f"[环节三 - 生成报告] 请求参数格式错误: {json_err}")
            return resp(code=400, msg=f"请求参数格式错误: {str(json_err)}", http_status=400)

        if not data:
            print(f"[环节三 - 生成报告] 请求参数为空")
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        report_id = data.get('report_id')
        if not report_id:
            print(f"[环节三 - 生成报告] 缺少 report_id 参数")
            return resp(code=400, msg="report_id 不能为空", http_status=400)

        export_format = data.get('format', 'docx').lower()
        valid_formats = ['docx', 'pdf', 'xlsx', 'md']
        if export_format not in valid_formats:
            print(f"[环节三 - 生成报告] 不支持的格式: {export_format}")
            return resp(code=400, msg=f"不支持的格式: {export_format}，可选值: {', '.join(valid_formats)}", http_status=400)

        print(f"[环节三 - 生成报告] 参数 | report_id={report_id}, format={export_format}")

        # 1. 获取报告
        report = GovernanceReport.query.filter_by(
            id=report_id,
            user_id=current_user.id
        ).first()

        if not report:
            print(f"[环节三 - 生成报告] 报告不存在 | report_id={report_id}")
            return resp(code=404, msg="报告不存在", http_status=404)

        print(f"[环节三 - 生成报告] 报告查询成功 | report_name={report.report_name}, file_status={report.file_status}")

        # 支持自定义导出文件名（不传入则使用默认命名规则）
        custom_file_name = data.get('file_name')

        # 2. 获取执行结果
        results = RuleExecutionResult.query.filter_by(
            report_id=report_id
        ).all()

        print(f"[环节三 - 生成报告] 查询到 {len(results)} 条执行结果")

        if not results:
            print(f"[环节三 - 生成报告] 报告中没有执行结果，请先执行规则")
            return resp(code=400, msg="报告中没有执行结果，请先执行规则", http_status=400)

        # 3. 更新文件状态
        report.file_status = 'generating'
        report.exported_file_type = export_format
        db.session.commit()
        print(f"[环节三 - 生成报告] 文件状态更新为 generating，开始生成文档...")

        # 4. 生成文档
        try:
            user_id = str(current_user.id)
            if export_format == 'md':
                from controllers.governance.markdown_exporter import MarkdownExporter
                print(f"[环节三 - 生成报告] 初始化 MarkdownExporter...")
                exporter = MarkdownExporter(user_id=user_id)
                print(f"[环节三 - 生成报告] 开始导出 Markdown 格式...")
                export_result = exporter.export(report, results, fmt='md', custom_file_name=custom_file_name)
                print(f"[环节三 - 生成报告] Markdown 生成成功 | mode={export_result['mode']}, file_path={export_result['file_path']}")
            else:
                from controllers.governance.libreoffice_exporter import LibreOfficeExporter
                print(f"[环节三 - 生成报告] 初始化 LibreOfficeExporter...")
                exporter = LibreOfficeExporter(user_id=user_id)
                print(f"[环节三 - 生成报告] 开始导出 | format={export_format}")
                export_result = exporter.export(report, results, fmt=export_format, custom_file_name=custom_file_name)
                print(f"[环节三 - 生成报告] 文档生成成功 | mode={export_result['mode']}, file_path={export_result['file_path']}")
        except Exception as e:
            report.file_status = 'failed'
            report.file_error_msg = str(e)
            db.session.commit()
            print(f"[环节三 - 生成报告] 文档生成失败: {e}")
            return resp(code=500, msg=f"文档生成失败: {str(e)}", http_status=500)

        # 5. 更新报告的文件信息
        report.exported_file_path = export_result['file_path']
        report.exported_file_name = export_result['file_name']
        report.file_size = export_result.get('file_size')
        report.file_created_at = datetime.now()
        report.file_status = 'completed'
        report.file_error_msg = None

        # 6. 插入文件记录（追踪该报告的所有导出文件）
        from models.governance_report_file import GovernanceReportFile
        report_file = GovernanceReportFile(
            report_id=report.id,
            user_id=current_user.id,
            report_name=report.report_name,
            file_path=export_result['file_path'],
            file_name=export_result['file_name'],
            file_type=export_result['format'],
            file_size=export_result.get('file_size'),
        )
        db.session.add(report_file)

        db.session.commit()

        print(f"[环节三 - 生成报告] 报告更新完成 | file_status=completed, file_size={export_result.get('file_size')}")
        print(f"[环节三 - 生成报告] 生成完毕 | report_id={report.id}\n")

        return resp(data={
            'report_id': str(report.id),
            'file_path': export_result['file_path'],
            'file_name': export_result['file_name'],
            'file_size': export_result.get('file_size'),
            'format': export_result['format'],
            'mode': export_result['mode'],
        })


class GovernanceReportStatusApi(Resource):
    """查询报告文档生成状态

    GET /report/<report_id>
    """

    def get(self, report_id: str):
        """查询报告文档生成状态

        路径参数:
            report_id: 报告ID

        返回:
        {
            "code": 200,
            "data": {
                "report_id": "xxx",
                "file_status": "completed",
                "file_error_msg": null,
                "exported_file_name": "xxx.docx",
                "exported_file_path": "...",
                "file_size": 12345
            }
        }
        """
        from flask_login import current_user

        report = GovernanceReport.query.filter_by(
            id=report_id,
            user_id=current_user.id
        ).first()

        if not report:
            return resp(code=404, msg="报告不存在", http_status=404)

        return resp(data={
            'report_id': str(report.id),
            'file_status': report.file_status or 'pending',
            'file_error_msg': report.file_error_msg,
            'exported_file_name': report.exported_file_name,
            'exported_file_path': report.exported_file_path,
            'file_size': report.file_size,
        })


# 注册新路由
api.add_resource(GovernanceReportGenerateApi, '/report')
api.add_resource(GovernanceReportStatusApi, '/report/<string:report_id>')
api.add_resource(GovernanceReportExecuteApi, '/rules/execute')
api.add_resource(GovernanceRuleExecutionApi, '/execute')


# ==================== 智能规则解析 API（自然语言模式） ====================

class RuleParseApi(Resource):
    """
    智能规则解析（自然语言 → 结构化规则）

    支持二阶段交互：
    - 阶段1：用户输入自然语言，后端解析并返回候选（如有多个匹配）
    - 阶段2：用户选择候选后重新调用，后端使用用户选择进行解析

    作用域自动判别：
    - 无 target_table → 全局规则（AI 全库扫描）
    - 有 target_table + 无 target_column → 表级规则（AI 在指定表内推断）
    - 有 target_table + 有 target_column → 列级规则（AI 验证并解析）
    """

    def post(self):
        """解析自然语言规则

        === 首次调用（阶段1）===
        请求参数:
        {
            "user_input": "订单金额不能为负",           // 必填，自然语言规则描述
            "datasource_id": "xxx",                      // 必填，数据源ID
            "target_table": "orders",                   // 可选，用户指定的目标表
            "target_column": "total_amount",            // 可选，用户指定的目标列
            "db_type": "postgresql"                     // 可选，数据库类型（自动从数据源获取）
        }

        返回（成功解析）:
        {
            "code": 200,
            "data": {
                "success": true,
                "needs_confirmation": false,
                "stage": "rule_preview",
                "confidence": 0.95,
                "rule_config": {
                    "rule_type": "threshold",
                    "target_table": "orders",
                    "target_column": "total_amount",
                    "condition_expr": "total_amount > 0",
                    "severity": "warning"
                },
                "rule_configs": null,
                "candidates": null,                       // 不需要确认时为 null
                "sql_preview": "SELECT ...",
                "reasoning": "解析理由"
            }
        }

        返回（需要确认）:
        {
            "code": 200,
            "data": {
                "success": true,
                "needs_confirmation": true,
                "stage": "table_selection",
                "confidence": 0.7,
                "rule_config": null,
                "rule_configs": null,
                "candidates": {
                    "type": "table",
                    "items": [
                        {"name": "orders", "score": 0.9, "reason": "表名匹配", "description": "订单主表"},
                        {"name": "sales_orders", "score": 0.7, "reason": "实体匹配", "description": "销售订单"}
                    ]
                },
                "sql_preview": null,
                "reasoning": "找到多个候选表，请确认"
            }
        }

        === 二次调用（阶段2，用户选择后）===
        请求参数:
        {
            "user_input": "订单金额不能为负",           // 必填，原始输入
            "datasource_id": "xxx",                      // 必填
            "target_table": "订单",                     // 用户的原始输入（模糊）
            "target_column": null,
            "selected_table": "orders",                  // 必填，用户从候选中选择
            "selected_column": null,                     // 可选，用户选择的列
            "db_type": "postgresql"
        }

        返回:
        {
            "code": 200,
            "data": {
                "success": true,
                "needs_confirmation": false,
                // 同阶段1的成功返回
            }
        }
        """
        from flask_login import current_user
        from controllers.governance.rule_llm_parser import SmartRuleParser
        from controllers.governance.schema_context import get_schema_from_datasource, ColumnInfo, TableSchema

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        # ============================================
        # 阶段1：接收用户输入
        # ============================================
        user_input = data.get('user_input', '').strip()
        if not user_input:
            return resp(code=400, msg="规则描述不能为空", http_status=400)

        datasource_id = data.get('datasource_id')
        if not datasource_id:
            return resp(code=400, msg="datasource_id 不能为空", http_status=400)

        # 用户输入的表名（可能是模糊的）
        target_table_input = data.get('target_table', '').strip() or None
        # 用户输入的列名（可能是模糊的）
        target_column_input = data.get('target_column', '').strip() or None

        # ============================================
        # 阶段2：接收用户选择（优先级最高）
        # ============================================
        selected_table = data.get('selected_table', '').strip() or None
        selected_column = data.get('selected_column', '').strip() or None

        # 多列目标（逗号分隔，来自 multi_column_selection 阶段用户的选择）
        target_columns_str = data.get('target_columns', '').strip() or None
        final_columns = None
        if target_columns_str:
            final_columns = [c.strip() for c in target_columns_str.split(',') if c.strip()]

        # 最终目标：选择 > 输入
        final_table = selected_table or target_table_input
        final_column = selected_column or target_column_input

        # ============================================
        # 获取数据源信息
        # ============================================
        datasource = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()

        if not datasource:
            return resp(code=404, msg="数据源不存在", http_status=404)

        db_type = datasource.db_type

        # ============================================
        # 获取 Schema 信息（互斥获取）
        # 策略：
        # 1. 有目标表 → 只获取该表的信息（数据卡片 > UserSchema > 数据库）
        # 2. 无目标表 → 获取全量 Schema
        # ============================================
        schemas = []
        schema_source = None  # 记录 Schema 来源

        if final_table:
            # ============================================
            # 情况A: 有目标表 - 只获取该表的信息
            # ============================================
            table_schema, schema_source = self._get_single_table_schema(
                datasource_id, str(current_user.id), final_table,
                datasource.connect_info, datasource.schema_name, datasource.db_type
            )
            if table_schema:
                schemas = [table_schema]
                self._log_schema_source(final_table, schema_source)
            else:
                # 表不存在
                return resp(data={
                    'success': False,
                    'needs_confirmation': False,
                    'stage': None,
                    'confidence': 0,
                    'rule_config': None,
                    'rule_configs': None,
                    'candidates': None,
                    'sql_preview': None,
                    'reasoning': f'表 "{final_table}" 不存在，请检查表名'
                })
        else:
            # ============================================
            # 情况B: 无目标表 - 获取全量 Schema（用于全局规则）
            # ============================================
            try:
                from controllers.governance.schema_context import get_schema_from_datasource
                schemas = get_schema_from_datasource(datasource_id, str(current_user.id))
                schema_count = len(schemas) if schemas else 0
                schema_source = 'mixed'
                print(f"[INFO] 无目标表，获取全量 Schema: {schema_count} 张表")
                if schema_count == 0:
                    print("[WARN] Schema 为空，可能原因：数据源未同步或 DataCardDataSource/UserDatasourceSchema 均无数据")
            except Exception as e:
                print(f"[WARN] 获取全量 Schema 失败: {str(e)}")
                import traceback
                traceback.print_exc()
        # ============================================
        # 作用域判别与解析
        # ============================================
        # 初始化 LLM 客户端
        # ============================================
        from controllers.agents.qwen.QwenMaxLatest import qian_wen_llm_with_usage

        # 创建 LLM 客户端包装
        class LLMWrapper:
            def chat(self, prompt):
                content, _ = qian_wen_llm_with_usage(prompt, stream_type=False)
                return content

        self.llm_client = LLMWrapper()

        # ============================================
        parser = SmartRuleParser(llm_client=self.llm_client, db_type=db_type)

        # ============================================
        # ============================================
        # 接收用户从候选列表中选择的列信息（由第一阶段返回的 inferred_columns）
        # 格式：支持两种
        #   1. 逗号分隔的列名字符串（兼容旧版）："warehouse,quantity"
        #   2. JSON 数组（含 reason，来自 Stage 1 的 inferred_columns）：[{"column":"warehouse","reason":"..."},{"column":"quantity","reason":"..."}]
        # ============================================
        import json as _json
        inferred_columns_raw = data.get('inferred_columns')
        inferred_columns = None
        if inferred_columns_raw:
            if isinstance(inferred_columns_raw, str):
                inferred_columns = [{'column': c.strip()} for c in inferred_columns_raw.split(',') if c.strip()]
            elif isinstance(inferred_columns_raw, list):
                # 前端传了完整的 inferred_columns 数组（含 reason）
                inferred_columns = []
                for item in inferred_columns_raw:
                    if isinstance(item, dict):
                        col = (item.get('column') or '').strip()
                        if col:
                            inferred_columns.append({'column': col, 'reason': (item.get('reason') or '').strip()})

        print(f"[INFO] /governance/rules/parse 入口参数: user_input={user_input}, selected_table={selected_table}, target_table={target_table_input}, selected_column={selected_column}, target_column={target_column_input}, target_columns={target_columns_str}, inferred_columns={inferred_columns}")
        print(f"[INFO] schemas 数量: {len(schemas) if schemas else 0}, final_table={final_table}, final_column={final_column}, final_columns={final_columns}")

        # 情况1：无目标表 → 全局规则
        if not final_table:
            print(f"[INFO] 分支: final_table 为空，进入全局规则解析")
            parsed, alternatives = self._parse_global_rule(user_input, schemas, parser)
            return self._build_response(parsed, alternatives, db_type, 'table_selection', schema=datasource.schema_name)

        # 情况2：有目标表，检查表是否存在/模糊
        print(f"[INFO] 分支: final_table={final_table}，进入表匹配逻辑")
        table_match = self._match_table(final_table, schemas, db_type, datasource, prefer_card=True)

        # 判断是否从数据卡片获取
        has_card_data = len(schemas) > 0

        if table_match['match_type'] == 'multiple':
            # 多个候选表 → 返回候选列表
            return resp(data={
                'success': True,
                'needs_confirmation': True,
                'stage': 'table_selection',
                'confidence': 0.7,
                'rule_config': None,
                'rule_configs': None,
                'candidates': {
                    'type': 'table',
                    'items': table_match['candidates']
                },
                'sql_preview': None,
                'reasoning': f'找到 {len(table_match["candidates"])} 个匹配的表，请确认'
            })

        if table_match['match_type'] == 'single':
            actual_table = table_match['table_name']

            # ============================================
            # 精确匹配到表后，直接进行后续解析
            # Schema 已在 _get_single_table_schema 中互斥获取
            # ============================================

            # 情况4：有表有列（多列）→ 来自 multi_column_selection 阶段的选择
            # → 直接进入批量预览，跳过重复推断
            # ============================================
            if final_columns:
                return self._build_multi_preview(
                    user_input, schemas, actual_table, final_columns, parser, db_type,
                    schema=datasource.schema_name
                )

            # 情况3：有表无列 → 表级规则（推断列）
            if not final_column:
                parsed, alternatives, stage = self._parse_table_rule(
                    user_input, schemas, actual_table, parser,
                    inferred_columns=inferred_columns
                )
                return self._build_response(parsed, alternatives, db_type, stage, schema=datasource.schema_name)

            # 情况5：有表有列（单列），检查列是否存在/模糊
            # ============================================
            column_match = self._match_column(actual_table, final_column, schemas, db_type)

            if column_match['match_type'] == 'multiple':
                # 多个候选列 → 返回候选列表
                return resp(data={
                    'success': True,
                    'needs_confirmation': True,
                    'stage': 'column_selection',
                    'confidence': 0.7,
                    'rule_config': None,
                    'rule_configs': None,
                    'candidates': {
                        'type': 'column',
                        'items': column_match['candidates']
                    },
                    'sql_preview': None,
                    'reasoning': f'找到 {len(column_match["candidates"])} 个匹配的列，请确认'
                })

            if column_match['match_type'] == 'single':
                # 精确匹配 → 列级规则
                actual_column = column_match['column_name']
                parsed, alternatives = self._parse_column_rule(
                    user_input, schemas, actual_table, actual_column, parser
                )
                return self._build_response(parsed, alternatives, db_type, 'rule_preview', schema=datasource.schema_name)
        
        # 情况5：表不存在
        return resp(data={
            'success': False,
            'needs_confirmation': False,
            'stage': None,
            'confidence': 0,
            'rule_config': None,
            'rule_configs': None,
            'candidates': None,
            'sql_preview': None,
            'reasoning': f'表 "{final_table}" 不存在，请检查表名'
        })

    def _get_single_table_schema(
        self,
        datasource_id: str,
        user_id: str,
        table_name: str,
        connect_info: str,
        schema_name: str = None,
        db_type: str = None
    ) -> tuple:
        """
        互斥获取单个表的 Schema 信息

        策略（互斥，不同时传多个来源）：
        1. 优先从 DataCardDataSource 获取
        2. 如果没有，从 UserDatasourceSchema 获取
        3. 如果都没有，从数据库实时获取

        Returns:
            tuple: (TableSchema, source) 或 (None, None)
        """
        from controllers.governance.schema_context import (
            get_schema_for_target_table,
            SchemaSource,
            TableSchema,
            ColumnInfo
        )

        # 策略1: 从数据卡片获取
        schema, source = get_schema_for_target_table(datasource_id, user_id, table_name)
        if schema:
            return schema, SchemaSource.DATA_CARD

        # 策略2: 从 UserDatasourceSchema 获取
        # 注意：connect_info 在数据库中存储的是加密值，所以查询时用加密值
        from models.user_datasource_schema import UserDatasourceSchema
        db_schema = UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info=connect_info,  # 参数已是加密值
            table_name=table_name
        ).first()

        if db_schema and db_schema.schema_text:
            try:
                import json
                schema_info = json.loads(db_schema.schema_text)
                columns = []
                for col in schema_info.get('columns', []):
                    col_name = col.get('name', '')
                    if col_name:
                        columns.append(ColumnInfo(
                            name=col_name,
                            data_type=col.get('type', ''),
                            comment=col.get('comment', ''),
                            is_primary=col.get('is_primary', False),
                            is_foreign=col.get('is_foreign', False),
                            nullable=col.get('nullable', True),
                            default_value=col.get('default')
                        ))

                table_schema = TableSchema(
                    table_name=table_name,
                    schema_name=schema_info.get('schema', ''),
                    description=schema_info.get('description', ''),
                    columns=columns
                )
                return table_schema, SchemaSource.USER_SCHEMA
            except Exception as e:
                print(f"[WARN] 解析 UserDatasourceSchema {table_name} 失败: {str(e)}")

        # 策略3: 从数据库实时获取
        # 注意：connect_info 参数是加密值，需要解密后再使用
        if connect_info and isinstance(connect_info, str):
            try:
                from controllers.datasource.database_schema_extractor import get_db_engine
                from core.connect_info_encryptor import decrypt_connect_info
                from sqlalchemy import inspect

                connect_info_decrypted = decrypt_connect_info(connect_info)
                engine = get_db_engine(connect_info_decrypted, db_type=db_type)
                inspector = inspect(engine)

                try:
                    columns_info = inspector.get_columns(table_name, schema=schema_name)
                except Exception:
                    columns_info = inspector.get_columns(table_name)

                col_list = []
                for col in columns_info:
                    col_list.append(ColumnInfo(
                        name=col['name'],
                        data_type=str(col['type']),
                        comment=col.get('comment', ''),
                        is_primary=col.get('primary_key', False),
                        is_foreign=bool(col.get('foreign_keys')),
                        nullable=col.get('nullable', True),
                        default_value=str(col.get('default')) if col.get('default') else None
                    ))

                table_schema = TableSchema(
                    table_name=table_name,
                    schema_name=schema_name or 'public',
                    columns=col_list
                )
                return table_schema, SchemaSource.DATABASE
            except Exception as e:
                print(f"[WARN] 实时获取表 {table_name} 失败: {str(e)}")

        return None, None

    def _log_schema_source(self, table_name: str, source: str):
        """记录 Schema 来源日志"""
        source_names = {
            'data_card': '数据卡片（DataCardDataSource）',
            'user_schema': '用户Schema（UserDatasourceSchema）',
            'database': '数据库实时',
            'mixed': '混合来源'
        }
        source_name = source_names.get(source, source)
        print(f"[INFO] 表 {table_name} 的 Schema 来源: {source_name}")

    def _match_table(self, table_input: str, schemas: list, db_type: str, datasource, prefer_card: bool = True) -> dict:
        """
        匹配表名

        Args:
            table_input: 用户输入的表名（可能是模糊的）
            schemas: 当前已有的 Schema 列表（可能来自数据卡片）
            db_type: 数据库类型
            datasource: 数据源对象
            prefer_card: 是否优先使用数据卡片，默认为 True
        """
        table_input_lower = table_input.lower()
        candidates = []

        # 在 schemas 中查找匹配（数据卡片优先）
        for schema in schemas:
            table_name_lower = schema.table_name.lower()
            # 精确匹配
            if table_name_lower == table_input_lower:
                return {'match_type': 'single', 'table_name': schema.table_name, 'from_card': True}
            # 模糊匹配（包含关系）
            if table_input_lower in table_name_lower or table_name_lower in table_input_lower:
                candidates.append({
                    'name': schema.table_name,
                    'score': 0.9 if table_input_lower in table_name_lower else 0.7,
                    'reason': '名称匹配',
                    'description': schema.description or '',
                    'from_card': True
                })
            # 检查其他字段（数据卡片的业务语义）
            elif schema.matches_keyword(table_input_lower):
                candidates.append({
                    'name': schema.table_name,
                    'score': 0.6,
                    'reason': '业务语义匹配',
                    'description': schema.card_abstract or schema.description or '',
                    'from_card': True
                })

        # 如果 prefer_card=True 且 schemas 中有数据，不回退到数据库
        if prefer_card and candidates:
            if len(candidates) == 1:
                return {'match_type': 'single', 'table_name': candidates[0]['name'], 'from_card': True}
            else:
                candidates.sort(key=lambda x: x['score'], reverse=True)
                return {'match_type': 'multiple', 'candidates': candidates, 'from_card': True}

        # 回退到数据库获取表列表（仅当 prefer_card=False 或 schemas 为空时）
        if not candidates:
            try:
                from controllers.datasource.database_schema_extractor import get_db_engine
                from core.connect_info_encryptor import decrypt_connect_info
                from sqlalchemy import inspect

                connection_string = decrypt_connect_info(datasource.connect_info)
                if connection_string and isinstance(connection_string, str):
                    engine = get_db_engine(connection_string, db_type=datasource.db_type)
                    inspector = inspect(engine)
                    schema_name = datasource.schema_name or 'public'

                    try:
                        all_tables = inspector.get_table_names(schema=schema_name)
                    except Exception:
                        all_tables = inspector.get_table_names()

                    for tbl in all_tables:
                        tbl_lower = tbl.lower()
                        if table_input_lower == tbl_lower:
                            return {'match_type': 'single', 'table_name': tbl}
                        if table_input_lower in tbl_lower or tbl_lower in table_input_lower:
                            candidates.append({
                                'name': tbl,
                                'score': 0.8 if table_input_lower in tbl_lower else 0.6,
                                'reason': '表名匹配',
                                'description': ''
                            })
            except Exception as e:
                print(f"[WARN] 实时获取表列表失败: {str(e)}")

        if len(candidates) == 1:
            return {'match_type': 'single', 'table_name': candidates[0]['name']}
        elif len(candidates) > 1:
            # 按分数排序
            candidates.sort(key=lambda x: x['score'], reverse=True)
            return {'match_type': 'multiple', 'candidates': candidates}
        else:
            return {'match_type': 'none', 'table_name': None}

    def _match_column(self, table_name: str, column_input: str, schemas: list, db_type: str) -> dict:
        """匹配列名"""
        column_input_lower = column_input.lower()
        candidates = []

        # 找到目标表
        target_schema = None
        for schema in schemas:
            if schema.table_name.lower() == table_name.lower():
                target_schema = schema
                break

        if target_schema and target_schema.columns:
            for col in target_schema.columns:
                col_name_lower = col.name.lower()
                col_comment_lower = (col.comment or '').lower()

                # 精确匹配
                if col_name_lower == column_input_lower:
                    return {'match_type': 'single', 'column_name': col.name}

                # 模糊匹配
                score = 0
                reason = ''

                if column_input_lower in col_name_lower:
                    score = 0.9
                    reason = '列名匹配'
                elif col_name_lower in column_input_lower:
                    score = 0.8
                    reason = '列名包含'

                if column_input_lower in col_comment_lower:
                    score = max(score, 0.85)
                    reason = '注释匹配'

                if score > 0:
                    candidates.append({
                        'name': col.name,
                        'score': score,
                        'reason': reason,
                        'data_type': col.data_type,
                        'description': col.comment or ''
                    })

        if len(candidates) == 1:
            return {'match_type': 'single', 'column_name': candidates[0]['name']}
        elif len(candidates) > 1:
            candidates.sort(key=lambda x: x['score'], reverse=True)
            return {'match_type': 'multiple', 'candidates': candidates}
        else:
            return {'match_type': 'none', 'column_name': None}

    def _parse_global_rule(self, user_input: str, schemas: list, parser) -> tuple:
        """解析全局规则（无目标表）

        核心逻辑（分两步让 LLM 做语义判断）：
        1. 第一步：LLM 基于业务语义筛选相关表
        2. 第二步：LLM 在相关表中推断候选表和候选列
        """
        if not schemas:
            print("[WARN] _parse_global_rule: schemas 为空，跳过全局解析")
            return None, []

        print(f"[INFO] _parse_global_rule 开始解析，用户输入: {user_input}，共 {len(schemas)} 张表")

        # 如果表数量 <= 25，直接全量丢给 LLM
        if len(schemas) <= 25:
            print(f"[INFO] 表数量 {len(schemas)} <= 25，直接全量 LLM 解析")
            return self._parse_global_with_llm(user_input, schemas, parser)

        # 如果表太多，分批筛选
        # 每批最多 25 张表，LLM 筛选出相关的
        batch_size = 25
        relevant_tables = []

        for i in range(0, len(schemas), batch_size):
            batch = schemas[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(schemas) + batch_size - 1) // batch_size

            print(f"[INFO] 正在筛选第 {batch_num}/{total_batches} 批表...")

            # 构建这批表的上下文
            tables_context = self._build_tables_context_for_global(batch)

            # 第一步：LLM 筛选相关表
            prompt = self._build_table_filter_prompt(user_input, tables_context, len(batch))
            try:
                response = self.llm_client.chat(prompt)
                # 解析 LLM 返回的相关表名
                relevant_in_batch = self._parse_filter_response(response, batch)
                relevant_tables.extend(relevant_in_batch)
                print(f"[INFO] 第 {batch_num} 批筛选结果: {relevant_in_batch}")
            except Exception as e:
                print(f"[WARN] 第 {batch_num} 批筛选失败: {str(e)}")
                import traceback
                traceback.print_exc()

        if not relevant_tables:
            print("[WARN] _parse_global_rule: LLM 未筛选出任何相关表")
            return None, []

        print(f"[INFO] _parse_global_rule: LLM 筛选出 {len(relevant_tables)} 张相关表，进入第二步")
        # 第二步：在相关表中推断候选表和列
        return self._parse_global_with_llm(user_input, relevant_tables, parser)

    def _parse_global_with_llm(self, user_input: str, schemas: list, parser) -> tuple:
        """使用 LLM 在相关表中推断候选表和候选列

        Returns:
            (None, table_candidates) — parsed=None，候选表列表进 alternatives
        """
        if not schemas:
            print("[WARN] _parse_global_with_llm: schemas 为空")
            return None, []

        print(f"[INFO] _parse_global_with_llm 开始，用户输入: {user_input}")

        # ============================================
        # 先检测是否涉及多列关系比较（如"结束时间必须晚于开始时间"）
        # ============================================
        if parser and hasattr(parser, '_is_multi_column_relation_text') and parser._is_multi_column_relation_text(user_input):
            multi_col_result = parser._parse_multi_column_relation(user_input, schemas)
            if multi_col_result is not None and multi_col_result[0] is not None:
                parsed = multi_col_result[0]
                # 多列关系解析成功，直接返回预览
                return parsed, []

        # 构建相关表的上下文信息
        tables_context = self._build_tables_context_for_global(schemas)

        # 构建 LLM Prompt
        prompt = self._build_global_rule_prompt(user_input, tables_context, len(schemas))
        print(f"[INFO] _parse_global_with_llm: 构建 Prompt 完成，chars={len(prompt)}")

        try:
            response = self.llm_client.chat(prompt)
            print(f"[INFO] _parse_global_with_llm: LLM 返回 chars={len(response)}")
            print(f"[DEBUG] LLM 原始返回:\n{response[:2000]}")
            result = self._parse_global_llm_response(response, schemas)
            print(f"[DEBUG] _parse_global_with_llm: _parse_global_llm_response 返回 result={result}")
            if result:
                # result = (parsed, candidates)，parsed 总是 None（未确定），candidates 是候选表列表
                _, table_candidates = result
                print(f"[DEBUG] _parse_global_with_llm: table_candidates={table_candidates}, type={type(table_candidates)}")
                if table_candidates:
                    print(f"[INFO] _parse_global_with_llm: 解析出 {len(table_candidates)} 个候选表")
                    # parsed=None 表示尚未确定；表候选列表进 alternatives
                    return None, table_candidates
                else:
                    print("[WARN] _parse_global_with_llm: table_candidates 为空（解析失败）")
            else:
                print("[WARN] _parse_global_with_llm: _parse_global_llm_response 返回 None")
        except Exception as e:
            print(f"[WARN] LLM 全局规则解析失败: {str(e)}")
            import traceback
            traceback.print_exc()

        print("[WARN] _parse_global_with_llm: 解析失败，返回空结果")
        return None, []

    def _build_table_filter_prompt(self, user_input: str, tables_context: str, batch_size: int) -> str:
        """构建表筛选的 LLM Prompt（第一步）"""
        return f"""你是一个数据质量规则分析专家。用户需要为数据库中的表创建数据质量规则。

## 用户需求
"{user_input}"

## 数据库表信息（共 {batch_size} 张表）
{tables_context}

## 你的任务
理解用户的规则描述，从上述表中筛选出与规则相关的表。

## 判断标准
根据用户的规则描述，判断哪些表的业务含义可能与规则相关：
- 表的核心主题、摘要、实体是否与规则描述的业务相关
- 表的列名/列注释是否暗示与规则相关
- 即使不确定，也可以保留

## 输出要求
请严格输出 JSON 数组，只列出相关表的表名：
```json
["表名1", "表名2", ...]
```

如果没有任何表相关，返回空数组：[]

## 重要说明
- 只要表可能与规则相关，就应该列入
- 表名区分大小写，必须与上面提供的完全一致
- 只输出 JSON，不要其他文字
"""

    def _parse_filter_response(self, response: str, schemas: list) -> list:
        """解析 LLM 的表筛选响应，返回相关表的 schema 列表"""
        import json
        import re

        try:
            # 提取 JSON 数组
            json_str = None
            match = re.search(r'\[\s*("[^"]*"\s*,?\s*)+\]', response)
            if match:
                json_str = match.group(0)
            elif response.strip().startswith('['):
                json_str = response.strip()

            if not json_str:
                return []

            table_names = json.loads(json_str)
            if not isinstance(table_names, list):
                return []

            # 查找对应的 schema
            result = []
            for name in table_names:
                for schema in schemas:
                    if schema.table_name.lower() == name.lower():
                        result.append(schema)
                        break

            return result

        except Exception as e:
            print(f"[WARN] 解析筛选响应失败: {str(e)}")
            return []

    def _build_tables_context_for_global(self, schemas: list) -> str:
        """构建全局规则解析所需的表上下文信息"""
        lines = []
        lines.append(f"共 {len(schemas)} 张表的信息：\n")

        for i, schema in enumerate(schemas):
            # 表类型标识
            obj_type = "视图" if schema.is_view else "表"
            lines.append(f"--- {obj_type} {i+1}: {schema.table_name} ---")

            # 数据卡片核心信息
            if schema.card_topic:
                lines.append(f"核心主题: {schema.card_topic}")
            if schema.card_abstract:
                abstract = schema.card_abstract
                if len(abstract) > 200:
                    abstract = abstract[:200] + "..."
                lines.append(f"摘要: {abstract}")
            if schema.card_entities:
                lines.append(f"核心实体: {', '.join(schema.card_entities[:15])}")
            if schema.card_tags:
                lines.append(f"标签: {', '.join(schema.card_tags[:10])}")

            # 表描述
            if schema.description and not schema.card_abstract:
                lines.append(f"表描述: {schema.description}")

            # 列信息（简略）
            if schema.columns:
                col_names = [c.name for c in schema.columns[:10]]
                lines.append(f"主要列: {', '.join(col_names)}")
                if len(schema.columns) > 10:
                    lines.append(f"（共 {len(schema.columns)} 列）")

            lines.append("")

        return '\n'.join(lines)

    def _build_global_rule_prompt(self, user_input: str, tables_context: str, total_tables: int) -> str:
        """构建全局规则解析的 LLM Prompt"""
        return f"""你是一个数据质量规则分析专家。用户需要为数据库中的表创建数据质量规则。

## 用户需求
"{user_input}"

## 数据库表信息
{tables_context}

## 你的任务
1. 理解用户的规则描述（通常是中文的自然语言）
2. 从上述表中找出最可能相关的表（可能1-5个）
3. 对于每个候选表，推断最可能需要检测的列（可能是多个）

## 判断依据（按重要性排序）
1. **业务语义匹配**：表的摘要、核心实体、主题是否与用户描述的业务含义相关
2. **列名/列注释**：列的名称或注释是否暗示与规则相关
3. **表名**：表名本身是否暗示业务含义

## 多条件处理规则（关键）
用户的自然语言描述可能包含多个独立的校验条件，例如：
- "仓库名称不为空且库存数量不小于0" → 包含2个独立条件
- "订单金额不能为空且必须大于0" → 包含2个独立条件

当用户描述包含多个独立条件时，**必须返回所有相关的列**，而不是只返回1个。
每个列的 inferred_columns 中应包含与该列最相关的条件描述。

## 输出要求
请严格输出 JSON：
```json
{{
    "matched_tables": [
        {{
            "table_name": "表名",
            "confidence": 0.85,
            "reasoning": "为什么这张表相关：结合业务语义解释",
            "inferred_columns": [
                {{"column": "列名1", "reason": "具体说明该列与用户描述的哪部分意图相关，结合列的业务含义（如列注释、数据卡片实体）阐述推断理由"}},
                {{"column": "列名2", "reason": "具体说明该列与用户描述的哪部分意图相关，结合列的业务含义（如列注释、数据卡片实体）阐述推断理由"}}
            ],
            "column_reasoning": "为什么推断这些列：多条件的分别说明"
        }}
    ],
    "no_match_reason": "如果没有任何表匹配，说明原因"
}}
```

## 重要说明
- 即使只有一个表匹配，也请列出
- **inferred_columns 是数组，每个元素必须包含 column（干净列名）和 reason（推断原因）**
- **reason 字段必须具体说明：该列与用户描述的哪部分意图相关、该列的业务含义（如列注释、数据卡片中的实体）如何支撑这一推断**
- **reason 示例：❌ "该列与条件相关"  ✅ "name 列的注释为商品名称，用户描述中的'商品名称不能为空'直接对应此列"**
- **column 必须是数据库中真实存在的列名，不允许包含括号、中文、描述性文字**
- 如果不确定列，inferred_columns 设为空数组 []
- confidence 表示你对这张表是否相关的置信度（0-1）
- 如果用户描述是"订单金额不能为负"，应该找订单相关的表和金额相关的列
"""

    def _parse_global_llm_response(self, response: str, schemas: list) -> tuple:
        """解析 LLM 全局规则解析响应"""
        import json
        import re

        try:
            # 提取 JSON
            json_str = None
            match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()

            if not json_str:
                print(f"[WARN] _parse_global_llm_response: 无法从 LLM 返回中提取 JSON")
                print(f"[WARN] LLM 原始返回: {response[:500]}")
                return None, []

            data = json.loads(json_str)
            matched_tables = data.get('matched_tables', [])
            print(f"[INFO] _parse_global_llm_response: matched_tables count = {len(matched_tables)}")

            if not matched_tables:
                print("[WARN] _parse_global_llm_response: matched_tables 为空")
                print("[DEBUG] _parse_global_llm_response: 返回 (None, []) — matched_tables 为空")
                return None, []

            # 构建候选表列表
            candidates = []
            for idx, item in enumerate(matched_tables):
                try:
                    table_name = item.get('table_name', '')
                    confidence = item.get('confidence', 0.5)
                    reasoning = item.get('reasoning', '')
                    print(f"[DEBUG] 处理第 {idx+1} 个表: {table_name}")

                    # 查找对应的 schema 获取更多信息
                    target_schema = None
                    for schema in (schemas or []):
                        if schema and schema.table_name and schema.table_name.lower() == table_name.lower():
                            target_schema = schema
                            break

                    # 支持 inferred_columns 数组格式（新版）和 inferred_column 字符串格式（旧版兼容）
                    # 新版格式: [{"column": "warehouse", "reason": "..."}, ...]
                    # 旧版格式: ["warehouse", "quantity"] 或 "warehouse, quantity"
                    inferred_columns_raw = item.get('inferred_columns')
                    inferred_columns = []
                    if inferred_columns_raw is None:
                        # 兼容旧版单列格式
                        single_col = item.get('inferred_column')
                        inferred_columns = [{'column': single_col, 'reason': ''}] if single_col else []
                    elif isinstance(inferred_columns_raw, list):
                        # 解析新版对象格式或旧版字符串数组格式
                        for c in inferred_columns_raw:
                            if isinstance(c, dict):
                                col_name = (c.get('column') or '').strip()
                                reason = (c.get('reason') or '').strip()
                                if col_name:
                                    # 清除列名中的括号注释（如 "warehouse（仓库名称）" → "warehouse"）
                                    col_name = re.sub(r'（.+）$', '', col_name).strip()
                                    col_name = re.sub(r'\(.+\)$', '', col_name).strip()
                                    inferred_columns.append({'column': col_name, 'reason': reason})
                            elif isinstance(c, str) and c.strip():
                                # 兼容旧版字符串格式
                                col_name = re.sub(r'（.+）$', '', c).strip()
                                col_name = re.sub(r'\(.+\)$', '', col_name).strip()
                                inferred_columns.append({'column': col_name, 'reason': ''})
                    elif isinstance(inferred_columns_raw, str):
                        # 兼容 "col1, col2" 这种逗号分隔格式
                        for c in inferred_columns_raw.split(','):
                            col_name = re.sub(r'（.+）$', '', c.strip()).strip()
                            col_name = re.sub(r'\(.+\)$', '', col_name.strip()).strip()
                            if col_name:
                                inferred_columns.append({'column': col_name, 'reason': ''})

                    # 从 schema 中补充 data_type 和 comment
                    if target_schema:
                        col_name_to_meta = {}
                        print(f"[DEBUG] target_schema.columns type: {type(target_schema.columns)}, value: {target_schema.columns}")
                        for col in (target_schema.columns or []):
                            col_n = col.name if hasattr(col, 'name') else col.get('name', '')
                            if col_n:
                                col_name_to_meta[col_n.lower()] = {
                                    'data_type': (col.data_type if hasattr(col, 'data_type') else col.get('data_type', '')),
                                    'comment': (col.comment if hasattr(col, 'comment') else col.get('comment', ''))
                                }
                        for ic in inferred_columns:
                            meta = col_name_to_meta.get(ic['column'].lower(), {})
                            ic['data_type'] = meta.get('data_type', '')
                            ic['comment'] = meta.get('comment', '')

                    # 提取干净列名列表，供前端传递给第二阶段
                    inferred_column_names = ','.join([ic['column'] for ic in inferred_columns if ic['column']])

                    candidates.append({
                        'name': table_name,
                        'score': confidence,
                        'reason': reasoning,
                        'description': target_schema.card_abstract if target_schema else '',
                        'from_card': bool(target_schema.card_entities if target_schema else False),
                        'is_view': target_schema.is_view if target_schema else False,
                        'inferred_columns': inferred_columns,
                        'inferred_column_names': inferred_column_names,
                        'column_reasoning': item.get('column_reasoning', '')
                    })
                except Exception as e:
                    import traceback
                    print(f"[WARN] 处理第 {idx+1} 个表 ({item.get('table_name', '')}) 时出错: {str(e)}")
                    traceback.print_exc()
                    continue

            # 按置信度排序
            if candidates:
                candidates.sort(key=lambda x: x['score'], reverse=True)

            # 构建返回格式
            print(f"[DEBUG] _parse_global_llm_response: 返回 (None, candidates={candidates})")
            return None, candidates or []

        except Exception as e:
            import traceback
            print(f"[WARN] 解析 LLM 全局响应失败: {str(e)}")
            traceback.print_exc()
            print("[DEBUG] _parse_global_llm_response: 返回 (None, []) — 外层 except")
            return None, []

    def _parse_table_rule(self, user_input: str, schemas: list, table_name: str, parser, inferred_columns=None) -> tuple:
        """解析表级规则（有目标表，推断列）

        Args:
            inferred_columns: 从第一阶段传递的多列信息，为列表格式，如 ["warehouse", "quantity"]
                               如果为 None，则由 LLM 自行推断
        Returns:
            (parsed, alternatives, stage) 三元组
            - stage = 'multi_column_selection' 表示多列候选，需要用户确认
            - stage = 'table_selection'        表示正常表级规则解析
        """
        print(f"[INFO] _parse_table_rule: user_input={user_input}, table={table_name}, inferred_columns={inferred_columns}")
        parsed, alternatives, stage = parser.parse_for_table(
            user_input, schemas, table_name, inferred_columns=inferred_columns
        )
        print(f"[INFO] _parse_table_rule: parsed={parsed is not None}, alternatives={len(alternatives)}, stage={stage}")
        return parsed, alternatives, stage

    def _parse_column_rule(
        self, user_input: str, schemas: list,
        table_name: str, column_name: str, parser
    ) -> tuple:
        """解析列级规则（有目标表和列）

        当 user_input 包含多个条件（如"仓库名称不能为空且库存量不小于0"）但用户只选了其中一列时，
        将 user_input 拆分为独立条件片段，只保留与选中列相关的片段传给 LLM。
        """
        print(f"[INFO] _parse_column_rule: user_input={user_input}, table={table_name}, column={column_name}")

        # 如果用户输入包含多个条件，只保留与选中列相关的条件片段
        filtered_input = user_input
        if hasattr(parser, '_split_conditions'):
            condition_parts = parser._split_conditions(user_input)
            if len(condition_parts) > 1:
                # 多条件：只保留涉及选中列的片段（通过列名/注释/语义匹配）
                col_name_lower = column_name.lower()
                col_comment_cn = ''
                for schema in (schemas or []):
                    if schema.table_name.lower() == table_name.lower():
                        for col in (schema.columns or []):
                            cn = col.name if hasattr(col, 'name') else col.get('name', '')
                            if cn.lower() == col_name_lower:
                                col_comment_cn = (col.comment if hasattr(col, 'comment') else col.get('comment', '')).strip()
                                break

                relevant_parts = []
                for part in condition_parts:
                    text = part['text']
                    text_lower = text.lower()
                    is_match = False

                    # 1) 英文列名匹配（如 "warehouse" 出现在英文描述中）
                    if col_name_lower in text_lower:
                        is_match = True
                    # 2) 列名去除下划线后与文本去除空格后的直接匹配
                    elif column_name.replace('_', '') in text.replace('_', '').replace(' ', ''):
                        is_match = True
                    # 3) 列注释中文匹配：支持包含关系（如"库存数量" 包含于 "库存数量不小于0"）
                    elif col_comment_cn:
                        # 直接包含
                        if col_comment_cn in text:
                            is_match = True
                        # 注释和文本有 ≥2 字重叠（如 "仓库名称" vs "仓库名"）
                        else:
                            overlap = set(col_comment_cn) & set(text)
                            if len(overlap) >= 2 and len(col_comment_cn) >= 2:
                                # 取注释中出现在文本中的连续子串长度 ≥ 2 才匹配
                                for start in range(len(col_comment_cn)):
                                    for end in range(start + 2, len(col_comment_cn) + 1):
                                        sub = col_comment_cn[start:end]
                                        if sub in text:
                                            is_match = True
                                            break
                                    if is_match:
                                        break

                    if is_match:
                        relevant_parts.append(text)

                if relevant_parts:
                    filtered_input = (' 且 '.join(relevant_parts)) if len(relevant_parts) > 1 else relevant_parts[0]
                    print(f"[INFO] _parse_column_rule: 多条件筛选后 user_input='{filtered_input}'")
                else:
                    print(f"[WARN] _parse_column_rule: 多条件中未匹配到选中列 '{column_name}' 的条件，使用全量输入")

        parsed, alternatives = parser.parse_with_column(
            filtered_input, schemas, table_name, column_name
        )
        print(f"[INFO] _parse_column_rule: parsed={parsed is not None}, alternatives={len(alternatives)}")
        return parsed, alternatives

    def _build_multi_preview(
        self,
        user_input: str,
        schemas: list,
        table_name: str,
        column_names: list,
        parser,
        db_type: str,
        schema: str = None
    ) -> dict:
        """多列批量预览：为每个列分别生成规则配置

        用户在 multi_column_selection 阶段选择了多个列后，调用此方法
        批量生成每列的规则配置和 SQL 预览。

        核心处理流程：
        1. 拆条件：用关键词（且/并且/and）将用户输入拆成独立的条件片段
        2. 建映射：每个选中的列对应到它自己那个条件片段
        3. 各自解析：每个列只拿自己的条件片段去生成规则，确保各列的 condition_expr 互不污染

        Args:
            schema: Schema 名（可选，用于 SQL 预览中的表引用）
        """
        from controllers.governance.dialect_adapter import DialectAdapter

        print(f"[INFO] _build_multi_preview: user_input={user_input}, table={table_name}, columns={column_names}, schema={schema}")
        adapter = DialectAdapter(db_type)

        # ① 拆条件：按"且/并且/and"切分成独立片段
        # 结果如 [{"text": "仓库名称不为空", "connector": "AND"}, {"text": "库存量不能小于0", "connector": None}]
        condition_parts = parser._split_conditions(user_input)

        # ② 建立 {列名: 条件片段} 映射
        # 同时做兜底：如果条件数量 < 列数量，给多余的列分配最后一个条件
        col_condition_map = {}

        if len(condition_parts) == len(column_names):
            # 数量一致，按顺序一一对应
            for col, part in zip(column_names, condition_parts):
                col_condition_map[col] = part['text']
        else:
            # 数量不一致：按顺序匹配，剩余的列用最后一个条件（兜底）
            for i, col in enumerate(column_names):
                if i < len(condition_parts):
                    col_condition_map[col] = condition_parts[i]['text']
                else:
                    col_condition_map[col] = condition_parts[-1]['text']

        # ③ 逐列为各自的条件片段生成规则配置
        rule_configs = []
        conditions_for_composite = []  # 收集所有列的条件，供 composite 规则使用

        for col, cond_text in col_condition_map.items():
            parsed, _ = parser.parse_with_column(cond_text, schemas, table_name, col)
            if not parsed:
                continue

            sql_preview = adapter.build_check_sql(
                table=table_name,
                column=col,
                condition=parsed.condition_expr or '',
                rule_type=parsed.rule_type,
                schema=schema
            )

            rule_configs.append({
                'target_column': col,
                'rule_type': parsed.rule_type,
                'condition_expr': parsed.condition_expr,
                'severity': parsed.severity,
                'confidence': parsed.confidence,
                'reasoning': parsed.reasoning,
                'sql_preview': sql_preview
            })

            # 收集到 composite 条件列表
            conditions_for_composite.append({
                'column': col,
                'rule_type': parsed.rule_type,
                'condition': parsed.condition_expr,
                'description': cond_text
            })

        if not rule_configs:
            return resp(data={
                'success': False,
                'needs_confirmation': False,
                'stage': 'multi_preview',
                'confidence': 0,
                'rule_config': None,
                'rule_configs': None,
                'candidates': None,
                'sql_preview': None,
                'reasoning': '无法为所选列生成规则，请检查输入'
            })

        # ④ 构建 composite 规则配置（用户选全部列时用）
        composite_condition_mode = 'AND'  # 默认用 AND（与用户输入"且/并且"语义一致）
        separator = f' {composite_condition_mode} '
        combined_condition = separator.join(rc['condition_expr'] for rc in rule_configs)

        composite_sql_preview = adapter.build_check_sql(
            table=table_name,
            column=None,
            condition=combined_condition,
            rule_type='composite',
            schema=schema
        )

        composite_rule_config = {
            'rule_type': 'composite',
            'target_table': table_name,
            'target_column': None,
            'condition_expr': combined_condition,
            'condition_mode': composite_condition_mode,
            'conditions': conditions_for_composite,
            'severity': max((rc['severity'] for rc in rule_configs), default='warning'),
            'sql_preview': composite_sql_preview
        }

        # 取各列置信度的平均值
        avg_confidence = sum(rc['confidence'] for rc in rule_configs) / len(rule_configs)

        return resp(data={
            'success': True,
            # 用户已在第一阶段确认了候选列，这里直接展示最终聚合规则预览
            'needs_confirmation': False,
            'stage': 'rule_preview',
            'confidence': avg_confidence,
            'rule_config': composite_rule_config,
            'rule_configs': rule_configs,
            'candidates': None,
            'sql_preview': composite_sql_preview,
            'reasoning': f'已为 {len(rule_configs)} 个字段生成聚合规则预览，确认后直接创建'
        })

    def _build_response(self, parsed, alternatives, db_type: str, stage: str, schema: str = None) -> dict:
        """构建响应数据

        stage 可选值：
        - 'table_selection':       选表阶段（无目标表），返回表候选
        - 'column_selection':      选列阶段（有目标表），返回列候选
        - 'multi_column_selection': 多列候选阶段，需要用户确认每个列
        - 'rule_preview':          最终规则预览阶段，有 rule_config

        Args:
            schema: Schema 名（可选，用于 SQL 预览中的表引用）
        """
        # 如果解析失败但有备选项，根据 stage 返回候选列表
        if parsed is None and alternatives:
            # 判断候选类型
            candidate_type = 'table' if stage == 'table_selection' else 'column'

            # 判断是否为候选格式（dict格式 = 表候选，ParsedRule格式 = 列候选）
            is_table_candidates = (
                stage == 'table_selection' or
                (alternatives and isinstance(alternatives[0], dict) and 'name' in alternatives[0])
            )

            if is_table_candidates:
                candidate_type = 'table'
                reasoning = f'在全库中找到 {len(alternatives)} 个可能的表，请确认目标表'
            else:
                candidate_type = 'column'
                reasoning = f'找到 {len(alternatives)} 个可能的列，请确认'

            return resp(data={
                'success': True,
                'needs_confirmation': True,
                'stage': stage,
                'confidence': 0.6,
                'rule_config': None,
                'rule_configs': None,
                'candidates': {
                    'type': candidate_type,
                    'items': alternatives
                },
                'sql_preview': None,
                'reasoning': reasoning
            })

        if parsed is None:
            return resp(data={
                'success': False,
                'needs_confirmation': False,
                'stage': stage,
                'confidence': 0,
                'rule_config': None,
                'rule_configs': None,
                'candidates': None,
                'sql_preview': None,
                'reasoning': '无法解析规则描述，请检查输入或使用专家模式手动配置'
            })

        # 生成 SQL 预览（仅最终预览阶段）
        sql_preview = ""
        rule_config = None

        # ============================================
        # 路径A：需要用户确认 → 只返回候选列表
        # （stage = table_selection | column_selection | multi_column_selection）
        # ============================================
        if parsed.needs_confirmation:
            response_candidates = None
            if hasattr(parsed, 'alternatives') and parsed.alternatives:
                candidate_type = 'multi_column' if stage == 'multi_column_selection' else 'column'
                response_candidates = {
                    'type': candidate_type,
                    'items': parsed.alternatives
                }
            return resp(data={
                'success': True,
                'needs_confirmation': True,
                'stage': stage,
                'confidence': parsed.confidence,
                'rule_config': None,
                'rule_configs': None,
                'candidates': response_candidates,
                'sql_preview': None,
                'reasoning': parsed.reasoning
            })

        # ============================================
        # 路径B：最终预览（rule_preview）→ 返回完整规则配置
        # ============================================
        if parsed.target_table and parsed.target_column:
            from controllers.governance.dialect_adapter import DialectAdapter
            adapter = DialectAdapter(db_type)
            sql_preview = adapter.build_check_sql(
                table=parsed.target_table,
                column=parsed.target_column,
                condition=parsed.condition_expr,
                rule_type=parsed.rule_type,
                schema=schema
            )
        elif parsed.target_table and parsed.conditions:
            from controllers.governance.dialect_adapter import DialectAdapter
            adapter = DialectAdapter(db_type)
            conditions_data = []
            for cond in parsed.conditions:
                if isinstance(cond, dict):
                    conditions_data.append({
                        'column': cond.get('column', ''),
                        'condition': cond.get('condition', '')
                    })
                else:
                    conditions_data.append({
                        'column': cond.column,
                        'condition': cond.condition
                    })
            if conditions_data:
                sql_preview = adapter.build_multi_condition_sql(
                    table=parsed.target_table,
                    conditions=conditions_data,
                    condition_mode=parsed.condition_mode,
                    schema=schema
                )
        elif parsed.target_table:
            sql_preview = f"-- 表: {parsed.target_table}\n-- 规则类型: {parsed.rule_type}\n-- 条件: {parsed.condition_expr}"

        rule_config = {
            'rule_type': parsed.rule_type,
            'target_table': parsed.target_table,
            'target_column': parsed.target_column,
            'condition_expr': parsed.condition_expr,
            'severity': parsed.severity,
            'conditions': parsed.conditions if hasattr(parsed, 'conditions') and parsed.conditions else None,
            'condition_mode': parsed.condition_mode if hasattr(parsed, 'condition_mode') else None,
            'sql_preview': sql_preview
        }

        return resp(data={
            'success': True,
            'needs_confirmation': False,
            'stage': stage,
            'confidence': parsed.confidence,
            'rule_config': rule_config,
            'rule_configs': None,
            'candidates': None,
            'sql_preview': sql_preview,
            'reasoning': parsed.reasoning
        })


class RulePreviewApi(Resource):
    """规则预览（预览生成的 SQL）"""

    def post(self):
        """预览规则 SQL

        === 模板模式 ===
        {
            "template_id": "tmpl-null-check",  // 模板ID
            "target_table": "users",            // 必填
            "target_column": "price",           // 必填
            "condition_expr": "column IS NOT NULL",  // 可选，用户可修改的条件
            "db_type": "postgresql"
        }

        === 单条件专家模式 ===
        {
            "rule_type": "null_check",
            "target_table": "users",
            "target_column": "price",
            "condition_expr": "column IS NOT NULL",
            "db_type": "postgresql"
        }

        === 复合规则模式 ===
        {
            "rule_type": "composite",
            "target_table": "users",
            "conditions": [
                {"column": "price", "condition": "column >= 0"},
                {"column": "price", "condition": "column IS NOT NULL"}
            ],
            "condition_mode": "AND",
            "db_type": "postgresql"
        }

        === 可选参数（用于有 Schema 概念的数据库）===
        {
            "library_id": "xxx",   // 规则库ID（可选，从关联的数据源获取 schema_name）
            "schema": "my_schema"  // Schema 名（可选，优先级高于 library_id）
        }

        模式优先级: template_id > conditions > condition_expr > auto

        返回:
        {
            "success": true,
            "sql": "SELECT ...",
            "scope": "column" | "table",
            "mode": "template" | "multi_condition" | "expert" | "auto",
            "rule_type": "null_check",
            "rule_type_label": "空值检测",
            "description": "..."
        }
        """
        from flask_login import current_user

        data = request.get_json()
        if not data:
            return resp(code=400, msg="请求参数不能为空", http_status=400)

        # 从 library_id 获取 schema_name 和 db_type（优先级低于显式传入的参数）
        schema_name = None
        db_type = data.get('db_type', 'postgresql')

        library_id = data.get('library_id')
        if library_id:
            library = GovernanceRuleLibrary.query.filter_by(
                id=library_id,
                created_by=current_user.id
            ).first()
            if library:
                ds = DatasourceInfo.query.get(library.datasource_id)
                if ds:
                    db_type = ds.db_type
                    schema_name = ds.schema_name

        # 显式传入的 schema 优先级最高
        if data.get('schema'):
            schema_name = data.get('schema')

        target_table = data.get('target_table')
        target_column = data.get('target_column')

        # 验证：表名不能为空
        if not target_table:
            return resp(code=400, msg="目标表不能为空", http_status=400)

        # ---- 模板模式 ----
        template_id = data.get('template_id')
        template = None
        template_rule_type = None
        if template_id:
            template = GovernanceRuleTemplate.query.get(template_id)
            if not template:
                return resp(code=404, msg=f"模板「{template_id}」不存在", http_status=404)
            template_rule_type = template.rule_type

        rule_type = data.get('rule_type') or (template_rule_type if template else 'custom_sql')
        condition_expr = data.get('condition_expr', '').strip()
        conditions = data.get('conditions', [])
        condition_mode = data.get('condition_mode', 'AND')

        # 使用模板默认值（未传入 condition_expr 时）
        if not condition_expr and template and template.default_condition:
            condition_expr = template.default_condition

        try:
            from controllers.governance.dialect_adapter import DialectAdapter
            adapter = DialectAdapter(db_type)

            from models.governance_rule import GovernanceRule
            rule_type_name = GovernanceRule.RULE_TYPE_NAMES.get(rule_type, rule_type)

            # 确定模式
            if template_id and condition_expr:
                mode = 'template'
                if target_column:
                    sql = adapter.build_check_sql(
                        table=target_table,
                        column=target_column,
                        condition=condition_expr,
                        rule_type=rule_type,
                        schema=schema_name
                    )
                else:
                    sql = adapter.build_table_check_sql(
                        table=target_table,
                        condition=condition_expr,
                        rule_type=rule_type,
                        schema=schema_name
                    )
                mode_desc = f"模板模式：基于「{template.template_name}」模板，条件已替换 column → {target_column or '(全局)'}"
            elif conditions and len(conditions) > 0:
                mode = 'multi_condition'
                sql = adapter.build_multi_condition_sql(
                    table=target_table,
                    conditions=conditions,
                    condition_mode=condition_mode,
                    schema=schema_name
                )
                mode_desc = '多条件模式：使用 conditions 数组中的所有条件'
            elif condition_expr:
                mode = 'expert'
                if target_column:
                    sql = adapter.build_check_sql(
                        table=target_table,
                        column=target_column,
                        condition=condition_expr,
                        rule_type=rule_type,
                        schema=schema_name
                    )
                else:
                    sql = adapter.build_table_check_sql(
                        table=target_table,
                        condition=condition_expr,
                        rule_type=rule_type,
                        schema=schema_name
                    )
                mode_desc = '专家模式：直接使用用户输入的条件'
            else:
                mode = 'auto'
                if target_column:
                    sql = adapter.build_check_sql(
                        table=target_table,
                        column=target_column,
                        condition='',
                        rule_type=rule_type,
                        schema=schema_name
                    )
                else:
                    sql = adapter.build_table_check_sql(
                        table=target_table,
                        condition='',
                        rule_type=rule_type,
                        schema=schema_name
                    )
                mode_desc = '自动模式：根据规则类型生成默认条件'

            return resp(data={
                'success': True,
                'sql': sql,
                'scope': 'column' if target_column else 'table',
                'mode': mode,
                'rule_type': rule_type,
                'rule_type_label': rule_type_name,
                'description': mode_desc,
                'template_name': template.template_name if template else None
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return resp(code=500, msg=f"预览失败: {str(e)}", http_status=500)


class RuleSuggestApi(Resource):
    """规则建议（基于真实 Schema + LLM 智能推荐）"""

    # 预定义规则模板（纯兜底用，当 LLM 不可用时）
    RULE_TEMPLATES = [
        {
            'type': 'null_check', 'name': '空值检测',
            'keywords': ['null', 'empty', '空', '必填', '必填项', '不能为空', 'required'],
            'applies_to': ['varchar', 'text', 'char', 'string', 'int', 'bigint', 'decimal']
        },
        {
            'type': 'format_phone', 'name': '手机号格式检测',
            'keywords': ['phone', 'mobile', 'tel', '手机', '电话'],
            'applies_to': ['varchar', 'text', 'char'],
            'condition_hint': '手机号格式校验（11位，以1开头）'
        },
        {
            'type': 'format_email', 'name': '邮箱格式检测',
            'keywords': ['email', 'mail', '邮箱', '电子邮件'],
            'applies_to': ['varchar', 'text', 'char'],
            'condition_hint': '邮箱格式校验'
        },
        {
            'type': 'format_idcard', 'name': '身份证格式检测',
            'keywords': ['idcard', 'id_card', '身份证', '证件号'],
            'applies_to': ['varchar', 'text', 'char'],
            'condition_hint': '身份证格式校验（18位）'
        },
        {
            'type': 'threshold_positive', 'name': '正数检测',
            'keywords': ['amount', 'price', 'total', 'money', '金额', '价格', '数量', 'quantity'],
            'applies_to': ['int', 'bigint', 'decimal', 'numeric', 'float', 'double', 'real'],
            'condition_hint': '数值必须大于0'
        },
        {
            'type': 'threshold_non_negative', 'name': '非负数检测',
            'keywords': ['count', 'num', 'number', '数量', '数目'],
            'applies_to': ['int', 'bigint', 'decimal', 'numeric', 'float', 'double', 'real'],
            'condition_hint': '数值必须大于等于0'
        },
        {
            'type': 'threshold_non_positive', 'name': '非正数检测',
            'keywords': ['discount', 'ratio', 'rate', '折扣', '比率', '比例'],
            'applies_to': ['int', 'bigint', 'decimal', 'numeric', 'float', 'double', 'real'],
            'condition_hint': '数值必须小于等于0'
        },
        {
            'type': 'unique', 'name': '唯一性检测',
            'keywords': ['code', 'no', 'number', '编号', '编码'],
            'applies_to': ['varchar', 'text', 'char', 'int', 'bigint'],
            'condition_hint': '值不能重复'
        },
        {
            'type': 'date_not_future', 'name': '日期不能为未来',
            'keywords': ['birth', 'create_date', 'created', '出生', '创建日期'],
            'applies_to': ['date', 'timestamp', 'datetime'],
            'condition_hint': '日期不能晚于当前日期'
        },
        {
            'type': 'length_check', 'name': '长度检测',
            'keywords': ['name', 'title', 'address', '名称', '标题', '地址'],
            'applies_to': ['varchar', 'text', 'char'],
            'condition_hint': '长度在合理范围内'
        },
    ]

    def post(self):
        """获取规则建议

        请求参数:
        {
            "datasource_id": "xxx"
        }

        返回:
        {
            "success": true,
            "source": "llm|fallback",
            "suggestions": [
                {
                    "table": "users",
                    "column": "phone",
                    "column_comment": "手机号码",
                    "data_type": "varchar(20)",
                    "rule_type": "format",
                    "rule_name": "手机号格式检测",
                    "rule_description": "手机号应为11位，以1开头",
                    "confidence": 0.95,
                    "reasoning": "基于列名和注释推断为手机号字段，建议进行格式校验"
                }
            ]
        }
        """
        from flask_login import current_user
        from models.datasource_infos import DatasourceInfo

        data = request.get_json() or {}
        datasource_id = data.get('datasource_id')

        if not datasource_id:
            return resp(code=400, msg="数据源ID不能为空", http_status=400)

        datasource = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()

        if not datasource:
            return resp(code=404, msg="数据源不存在", http_status=404)

        # Step 1: 收集目标数据源的完整 Schema（互斥策略：数据卡片 > UserDatasourceSchema）
        schemas = self._collect_schemas(datasource_id, str(current_user.id))

        if not schemas:
            return resp(data={
                'success': True,
                'source': 'empty',
                'suggestions': [],
                'message': '该数据源暂无表结构信息，请先同步数据'
            })

        # Step 2: 调用 LLM 智能推荐
        suggestions, source = self._generate_suggestions_with_llm(schemas, datasource.db_type)

        if source == 'llm' and suggestions:
            return resp(data={
                'success': True,
                'source': 'llm',
                'suggestions': suggestions
            })

        # Step 3: LLM 不可用或失败 → 基于规则模板 + 真实 Schema 做启发式推荐
        suggestions = self._generate_suggestions_fallback(schemas)

        return resp(data={
            'success': True,
            'source': source,
            'suggestions': suggestions
        })

    def _collect_schemas(self, datasource_id: str, user_id: str) -> List[Dict]:
        """收集目标数据源中所有表的 Schema 信息（互斥策略）"""
        import json
        from models.datacards_datasource import DataCardDataSource
        from models.user_datasource_schema import UserDatasourceSchema
        from models.datasource_infos import DatasourceInfo

        # 先获取 datasource 确认 connect_info
        datasource = DatasourceInfo.query.filter_by(id=datasource_id).first()
        if not datasource:
            return []

        # 查询所有数据卡片（优先级最高）
        data_cards = DataCardDataSource.query.filter_by(
            datasource_id=datasource_id
        ).all()

        # 查询 UserDatasourceSchema（用于 is_view 和兜底表结构）
        db_schemas = UserDatasourceSchema.query.filter_by(
            user_id=user_id,
            connect_info=datasource.connect_info
        ).all()

        # 构建 is_view 映射
        table_is_view_map = {s.table_name.lower(): bool(s.is_view) for s in db_schemas}

        schemas = []
        card_table_names = set()

        # 优先级1：从数据卡片获取（SQLMeta.columns 包含 LLM 增强的注释）
        for card in data_cards:
            if not card.card_data:
                continue
            try:
                card_data = json.loads(card.card_data)
                is_view = table_is_view_map.get(card.table_name.lower(), False)
                schema = self._build_schema_from_card(card.table_name, card_data, is_view)
                if schema:
                    schemas.append(schema)
                    card_table_names.add(card.table_name.lower())
            except Exception as e:
                print(f"[WARN] 解析数据卡片 {card.table_name} 失败: {str(e)}")

        # 优先级2：从 UserDatasourceSchema 获取（数据卡片没有的表）
        for db_schema in db_schemas:
            if db_schema.table_name.lower() in card_table_names:
                continue
            if not db_schema.schema_text:
                continue
            try:
                schema_info = json.loads(db_schema.schema_text)
                schema = self._build_schema_from_db_schema(db_schema.table_name, schema_info, bool(db_schema.is_view))
                if schema:
                    schemas.append(schema)
            except Exception as e:
                print(f"[WARN] 解析 UserDatasourceSchema {db_schema.table_name} 失败: {str(e)}")

        return schemas

    def _build_schema_from_card(self, table_name: str, card_info: Dict, is_view: bool = False) -> Optional[Dict]:
        """从数据卡片构建表 Schema（含 SQLMeta）"""
        card_sql_meta = card_info.get('SQLMeta', {})
        card_columns = card_sql_meta.get('columns', [])
        if not card_columns:
            return None

        key_concepts = card_info.get('KeyConcepts', {})

        columns = []
        for c in card_columns:
            col_name = c.get('name', '')
            if not col_name:
                continue
            columns.append({
                'name': col_name,
                'data_type': c.get('type', ''),
                'comment': c.get('comment', ''),  # 数据卡片的注释经过 LLM 增强
                'is_primary': c.get('is_primary', False),
                'is_foreign': c.get('is_foreign', False),
                'nullable': c.get('nullable', True),
            })

        return {
            'table_name': table_name,
            'is_view': is_view,
            'description': card_info.get('Abstract', ''),
            'card_topic': key_concepts.get('canonical_topic', ''),
            'card_entities': key_concepts.get('key_entities', []),
            'card_scenarios': key_concepts.get('applicable_scenarios', []),
            'card_tags': card_info.get('Tags', []),
            'columns': columns,
        }

    def _build_schema_from_db_schema(self, table_name: str, schema_info: Dict, is_view: bool = False) -> Optional[Dict]:
        """从 UserDatasourceSchema 构建表 Schema"""
        columns = []
        for col in schema_info.get('columns', []):
            col_name = col.get('name', '')
            if not col_name:
                continue
            columns.append({
                'name': col_name,
                'data_type': col.get('type', ''),
                'comment': col.get('comment', ''),
                'is_primary': col.get('is_primary', False),
                'is_foreign': col.get('is_foreign', False),
                'nullable': col.get('nullable', True),
            })

        if not columns:
            return None

        return {
            'table_name': table_name,
            'is_view': is_view,
            'description': schema_info.get('description', ''),
            'card_topic': '',
            'card_entities': [],
            'card_scenarios': [],
            'card_tags': [],
            'columns': columns,
        }

    def _generate_suggestions_with_llm(self, schemas: List[Dict], db_type: str) -> tuple:
        """调用 LLM 智能生成规则推荐"""
        try:
            from controllers.agents.qwen.QwenMaxLatest import qian_wen_llm_with_usage

            # 构建 Schema 上下文
            schema_context = self._build_schema_context_for_llm(schemas)

            # 构建 LLM Prompt
            prompt = self._build_llm_prompt(schema_context, db_type)

            # 调用 LLM
            response, _ = qian_wen_llm_with_usage(prompt, stream_type=False)

            # 解析 LLM 响应
            suggestions = self._parse_llm_response(response, schemas)
            if suggestions:
                return suggestions, 'llm'

        except Exception as e:
            print(f"[WARN] LLM 规则推荐失败: {str(e)}")
            import traceback
            traceback.print_exc()

        return [], 'llm_failed'

    def _build_schema_context_for_llm(self, schemas: List[Dict]) -> str:
        """构建适合 LLM 的 Schema 上下文"""
        lines = []
        for schema in schemas:
            table_name = schema['table_name']
            lines.append(f"### 表: {table_name}")

            # 数据卡片业务语义
            if schema.get('card_topic'):
                lines.append(f"- 核心主题: {schema['card_topic']}")
            if schema.get('description'):
                lines.append(f"- 表描述: {schema['description']}")
            if schema.get('card_entities'):
                lines.append(f"- 核心实体: {', '.join(schema['card_entities'])}")
            if schema.get('card_tags'):
                lines.append(f"- 标签: {', '.join(schema['card_tags'])}")

            lines.append("")
            lines.append("**列信息（注释以数据卡片 LLM 增强结果为准）**:")
            lines.append("| 列名 | 数据类型 | 注释 | 主键 | 外键 |")
            lines.append("|------|----------|------|------|------|")
            for col in schema['columns']:
                pk = "✓" if col.get('is_primary') else ""
                fk = "✓" if col.get('is_foreign') else ""
                comment = col.get('comment') or ''
                lines.append(f"| {col['name']} | {col['data_type']} | {comment} | {pk} | {fk} |")
            lines.append("")

        return '\n'.join(lines)

    def _build_llm_prompt(self, schema_context: str, db_type: str) -> str:
        """构建 LLM 规则推荐 Prompt"""
        return f"""你是一个数据质量规则推荐专家。请根据给定的数据库 Schema 信息，为每个需要治理的列推荐合适的数据质量规则。

## 数据库类型
{db_type.upper()}

## Schema 信息
{schema_context}

## 你的任务
1. 仔细分析每张表的业务含义（表描述、核心主题、核心实体）
2. 分析每个列的注释和数据类型
3. 结合业务语义，为需要数据质量检测的列推荐合适的治理规则

## 规则类型说明
- **null_check**: 空值检测（适用于必填字段、可为空但业务上不应为空的字段）
- **format_phone**: 手机号格式检测（11位，以1开头，适用于手机号相关字段）
- **format_email**: 邮箱格式检测（适用于邮箱字段）
- **format_idcard**: 身份证格式检测（18位，适用于身份证字段）
- **threshold_positive**: 正数检测（适用于金额、价格等正数字段）
- **threshold_non_negative**: 非负数检测（适用于数量、计数等非负字段）
- **unique**: 唯一性检测（适用于编码、编号等唯一字段）
- **date_not_future**: 日期不能为未来（适用于出生日期、创建日期等历史日期字段）
- **length_check**: 长度检测（适用于名称、地址等有长度要求的字段）
- **enum**: 枚举值检测（适用于状态、类型等有限取值的字段）

## 推荐策略
- **优先推荐空值检测**：对于主键、外键、业务必填字段
- **格式检测需谨慎**：仅当列名/注释明确表明是手机号、邮箱、身份证时推荐
- **阈值检测看业务**：结合列的业务含义（如金额>0，价格>=0）
- **唯一性检测**：对于编号、编码类字段
- **日期检测**：对于出生日期等不应为未来的字段
- **长度检测**：对于名称、地址等有明确长度要求的字段
- **跳过明显不需要治理的列**：如 id、created_at、updated_at 等通用字段

## 输出要求
请严格输出 JSON 数组，每个元素对应一个推荐规则：
```json
[
    {{
        "table": "表名",
        "column": "列名",
        "column_comment": "列注释",
        "data_type": "数据类型",
        "rule_type": "规则类型",
        "rule_name": "规则名称",
        "rule_description": "规则描述，说明推荐理由",
        "confidence": 0.95,
        "reasoning": "推荐理由，结合业务语义和字段特征说明为什么推荐这个规则"
    }}
]
```

## 重要说明
- **confidence 表示推荐置信度（0-1），0.9以上表示非常确定，0.7-0.9 表示较确定，0.5-0.7 表示建议性质
- **reasoning 必须具体说明推荐理由**，如"该列注释为'手机号码'，数据类型为varchar，推荐手机号格式检测"
- **不要推荐过于通用的规则**，如只为所有 varchar 列都推荐空值检测
- **只输出有意义的推荐**，不强制要求每列都有推荐
- 如果没有找到值得推荐的列，返回空数组 []
"""

    def _parse_llm_response(self, response: str, schemas: List[Dict]) -> List[Dict]:
        """解析 LLM 返回的推荐结果"""
        import re
        try:
            # 提取 JSON
            json_str = None
            match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
                if match:
                    json_str = match.group(0).strip()

            if not json_str:
                return []

            suggestions = json.loads(json_str)
            if not isinstance(suggestions, list):
                return []

            # 验证每条推荐是否指向真实存在的表和列
            valid_suggestions = []
            for sug in suggestions:
                table = sug.get('table', '').strip()
                column = sug.get('column', '').strip()
                if not table or not column:
                    continue
                # 验证表和列是否存在
                if self._validate_suggestion(table, column, schemas):
                    valid_suggestions.append({
                        'table': table,
                        'column': column,
                        'column_comment': sug.get('column_comment', ''),
                        'data_type': sug.get('data_type', ''),
                        'rule_type': sug.get('rule_type', ''),
                        'rule_name': sug.get('rule_name', ''),
                        'rule_description': sug.get('rule_description', ''),
                        'confidence': float(sug.get('confidence', 0.5)),
                        'reasoning': sug.get('reasoning', ''),
                    })

            return valid_suggestions

        except Exception as e:
            print(f"[WARN] 解析 LLM 响应失败: {str(e)}")
            return []

    def _validate_suggestion(self, table: str, column: str, schemas: List[Dict]) -> bool:
        """验证推荐是否指向真实存在的表和列"""
        for schema in schemas:
            if schema['table_name'].lower() == table.lower():
                for col in schema['columns']:
                    if col['name'].lower() == column.lower():
                        return True
        return False

    def _generate_suggestions_fallback(self, schemas: List[Dict]) -> List[Dict]:
        """基于规则模板 + 真实 Schema 做启发式推荐（当 LLM 不可用时的兜底方案）"""
        suggestions = []
        skip_columns = {
            'id', 'uuid', 'created_at', 'updated_at', 'create_time', 'update_time',
            'created_by', 'updated_by', 'deleted_at', 'is_deleted', 'version', 'sort'
        }

        for schema in schemas:
            table_name = schema['table_name']
            table_entities = [e.lower() for e in schema.get('card_entities', [])]

            for col in schema['columns']:
                col_name = col['name'].lower()
                col_comment = (col.get('comment') or '').lower()
                col_type = col.get('data_type', '').lower()
                col_name_raw = col['name']

                # 跳过通用字段
                if col_name in skip_columns or any(col_name.startswith(s) for s in skip_columns):
                    continue

                matched_rules = self._match_rules_for_column(
                    col_name, col_comment, col_type, table_entities
                )

                for rule in matched_rules:
                    suggestions.append({
                        'table': table_name,
                        'column': col_name_raw,
                        'column_comment': col.get('comment', ''),
                        'data_type': col.get('data_type', ''),
                        'rule_type': rule['type'],
                        'rule_name': rule['name'],
                        'rule_description': rule.get('condition_hint', ''),
                        'confidence': rule.get('confidence', 0.5),
                        'reasoning': rule.get('reasoning', ''),
                    })

        # 按 confidence 降序排序
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions

    def _match_rules_for_column(
        self,
        col_name: str,
        col_comment: str,
        col_type: str,
        table_entities: List[str]
    ) -> List[Dict]:
        """为单个列匹配适用的规则模板"""
        matched = []
        col_lower = col_name.lower()
        comment_lower = col_comment.lower()

        for tmpl in self.RULE_TEMPLATES:
            rule_type = tmpl['type']
            keywords = tmpl.get('keywords', [])
            applies_to = tmpl.get('applies_to', [])

            # 关键词匹配：列名或注释中包含关键词
            keyword_hit = any(kw.lower() in col_lower or kw.lower() in comment_lower for kw in keywords)
            # 实体匹配：表的核心实体包含关键词
            entity_hit = any(kw.lower() in entity for kw in keywords for entity in table_entities)

            if not (keyword_hit or entity_hit):
                continue

            # 数据类型匹配
            if applies_to and not any(t in col_type for t in applies_to):
                continue

            # 计算置信度
            if keyword_hit and col_comment and keywords[0].lower() in comment_lower:
                confidence = 0.95  # 列注释明确命中
            elif keyword_hit and keywords[0].lower() in col_lower:
                confidence = 0.85  # 列名命中
            else:
                confidence = 0.7   # 实体命中

            # 特殊规则置信度调整
            if rule_type == 'null_check' and not col_comment:
                confidence = 0.6  # 无注释的空值检测置信度降低

            matched.append({
                'type': rule_type,
                'name': tmpl['name'],
                'condition_hint': tmpl.get('condition_hint', ''),
                'confidence': confidence,
                'reasoning': self._build_reasoning(rule_type, tmpl['name'], col_name, col_comment)
            })

        return matched

    def _build_reasoning(self, rule_type: str, rule_name: str, col_name: str, col_comment: str) -> str:
        """生成推荐理由"""
        comment_note = f"，注释为'{col_comment}'" if col_comment else ""
        reasoning_map = {
            'null_check': f"列'{col_name}'{comment_note}可能为业务必填字段，建议检测空值",
            'format_phone': f"列'{col_name}'{comment_note}可能为手机号字段，建议进行格式校验",
            'format_email': f"列'{col_name}'{comment_note}可能为邮箱字段，建议进行格式校验",
            'format_idcard': f"列'{col_name}'{comment_note}可能为身份证字段，建议进行格式校验",
            'threshold_positive': f"列'{col_name}'{comment_note}可能为金额/价格字段，建议检测正数",
            'threshold_non_negative': f"列'{col_name}'{comment_note}可能为数量字段，建议检测非负数",
            'threshold_non_positive': f"列'{col_name}'{comment_note}可能为折扣/比率字段，建议检测非正数",
            'unique': f"列'{col_name}'{comment_note}可能为编号字段，建议检测唯一性",
            'date_not_future': f"列'{col_name}'{comment_note}可能为历史日期字段，建议检测不为未来日期",
            'length_check': f"列'{col_name}'{comment_note}可能有长度限制，建议检测长度",
        }
        return reasoning_map.get(rule_type, f"列'{col_name}'建议应用{rule_name}")


# ==================== 治理概览 API ====================

class QualityOverviewApi(Resource):
    """治理概览 - 返回治理模块首页统计数据"""

    def get(self):
        """
        获取治理概览数据
        Query 参数:
        - datasource_id: string, 可选，按数据源过滤
        - date_range: string, 可选，统计时间范围，如 7d、30d、90d、custom:2026-06-01,2026-06-30
        """
        from flask_login import current_user
        from models.datasource_infos import DatasourceInfo
        from datetime import datetime
        from sqlalchemy import func, case, and_

        datasource_id = request.args.get('datasource_id')
        date_range = request.args.get('date_range', '30d')

        # 计算日期范围
        end_date = datetime.now()
        start_date = self._parse_date_range(date_range, end_date)

        # 1. 获取统计基础查询条件
        # 规则库统计
        library_query = GovernanceRuleLibrary.query.filter_by(created_by=current_user.id)
        if datasource_id:
            library_query = library_query.filter_by(datasource_id=datasource_id)
        library_count = library_query.count()

        # 规则统计
        rule_query = GovernanceRule.query.join(
            GovernanceRuleLibrary,
            GovernanceRule.library_id == GovernanceRuleLibrary.id
        ).filter(GovernanceRuleLibrary.created_by == current_user.id)
        if datasource_id:
            rule_query = rule_query.filter(GovernanceRuleLibrary.datasource_id == datasource_id)
        rule_count = rule_query.count()

        # 启用规则数
        enabled_rule_count = rule_query.filter(GovernanceRule.enabled == True).count()

        # 报告统计
        report_query = GovernanceReport.query.filter_by(user_id=current_user.id)
        if datasource_id:
            report_query = report_query.filter_by(datasource_id=datasource_id)
        # 按日期范围过滤
        report_query = report_query.filter(
            GovernanceReport.execution_time >= start_date,
            GovernanceReport.execution_time <= end_date
        )
        report_count = report_query.count()

        # 2. 获取最新报告的质量评分和等级
        latest_report = GovernanceReport.query.filter_by(user_id=current_user.id)
        if datasource_id:
            latest_report = latest_report.filter_by(datasource_id=datasource_id)
        latest_report = latest_report.order_by(GovernanceReport.execution_time.desc()).first()

        quality_score = float(latest_report.quality_score) if latest_report and latest_report.quality_score else None
        grade = latest_report.grade if latest_report else None

        # 3. 计算维度评分（基于规则类型分布和执行结果）
        dimensions = self._calculate_dimensions(rule_query, report_query)

        # 4. 获取严重问题摘要
        critical_findings = self._get_critical_findings(
            report_query, rule_query, current_user.id, datasource_id
        )

        # 5. 获取报告趋势数据
        report_trend = self._get_report_trend(report_query, start_date, end_date)

        # 6. 按规则类型统计
        rule_type_stats = self._get_rule_type_stats(rule_query, current_user.id)

        return resp(data={
            'quality_score': quality_score,
            'grade': grade,
            'report_count': report_count,
            'library_count': library_count,
            'rule_count': rule_count,
            'enabled_rule_count': enabled_rule_count,
            'dimensions': dimensions,
            'critical_findings': critical_findings,
            'report_trend': report_trend,
            'rule_type_stats': rule_type_stats,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'range': date_range
            }
        })

    def _parse_date_range(self, date_range: str, end_date: datetime) -> datetime:
        """解析日期范围参数"""
        if date_range == '7d':
            return end_date - timedelta(days=7)
        elif date_range == '30d':
            return end_date - timedelta(days=30)
        elif date_range == '90d':
            return end_date - timedelta(days=90)
        elif date_range.startswith('custom:'):
            try:
                dates = date_range.split(':')[1].split(',')
                if len(dates) == 2:
                    return datetime.strptime(dates[0], '%Y-%m-%d')
            except:
                pass
        return end_date - timedelta(days=30)  # 默认30天

    # 数据质量维度 → 规则类型 的映射关系
    # 扩展归类，把语义上同属一类的规则类型合并，避免遗漏
    DIMENSION_RULE_TYPES = {
        'completeness': {'null_check'},
        'uniqueness':   {'unique'},
        'validity':     {'format', 'enum', 'threshold',
                         'length_check', 'range_check',
                         'date_check', 'value_distribution',
                         'custom_sql'},
        'consistency':  {'consistency_check'},
        'timeliness':   {'freshness_check'},
        # composite 单独展示，不混入主维度
        'composite':    {'composite'},
    }

    def _calculate_dimensions(self, rule_query, report_query):
        """
        计算维度评分。

        语义说明：
        - 本字段代表"各质量维度在最近一次报告中的数据通过率"，
          而非"规则覆盖度"或"规则占比"。
        - 通过率 = (Σ passed_count) / (Σ total_count) × 100
        - 复合规则(composite)由于横跨多维度，单独展示，不与五大基础维度混合。
        - 当维度下没有可统计的执行结果时，返回 0.0（前端可理解为"未覆盖"）。
        """
        # 初始化所有维度为 0（含 composite）
        dimensions = {dim: 0.0 for dim in self.DIMENSION_RULE_TYPES.keys()}

        try:
            # 取最近一次报告（report_query 已按时间范围过滤，且按时间倒序在外部用）
            latest_report = report_query.order_by(
                GovernanceReport.execution_time.desc()
            ).first()
            if not latest_report:
                return dimensions

            # 拉取该报告下所有规则执行结果
            exec_results = RuleExecutionResult.query.filter_by(
                report_id=latest_report.id
            ).all()
            if not exec_results:
                return dimensions

            # 按维度聚合：total / passed
            agg_total = {dim: 0 for dim in dimensions.keys()}
            agg_passed = {dim: 0 for dim in dimensions.keys()}

            for r in exec_results:
                rtype = r.rule_type
                if not rtype:
                    continue
                total = int(r.total_count or 0)
                passed = int(r.passed_count or 0)
                # 异常兜底：passed 不能超过 total
                if total < 0:
                    total = 0
                if passed < 0:
                    passed = 0
                if passed > total:
                    passed = total

                for dim, types in self.DIMENSION_RULE_TYPES.items():
                    if rtype in types:
                        agg_total[dim] += total
                        agg_passed[dim] += passed
                        # composite 可能同时命中多个基础维度（理论上不应发生，
                        # 但若发生只计入第一个匹配维度，避免重复计算）
                        if dim != 'composite':
                            break

            # 计算各维度通过率
            for dim in dimensions.keys():
                t = agg_total[dim]
                if t > 0:
                    dimensions[dim] = round(agg_passed[dim] / t * 100, 1)
                else:
                    dimensions[dim] = 0.0
        except Exception as e:
            # 任意异常时，保持全 0 返回，保证接口可用
            print(f'[QualityOverviewApi] 计算维度评分失败: {e}')
            return {dim: 0.0 for dim in self.DIMENSION_RULE_TYPES.keys()}

        return dimensions

    def _get_critical_findings(self, report_query, rule_query, user_id, datasource_id):
        """获取严重问题摘要"""
        findings = []

        try:
            # 获取最近报告的执行结果中状态为 failed 且严重级别为 critical 的
            recent_report_ids = [r.id for r in report_query.limit(5).all()]

            if recent_report_ids:
                critical_results = RuleExecutionResult.query.filter(
                    RuleExecutionResult.report_id.in_(recent_report_ids),
                    RuleExecutionResult.status == 'failed'
                ).order_by(RuleExecutionResult.failed_rate.desc()).limit(10).all()

                for result in critical_results:
                    # 获取对应的规则信息
                    rule = GovernanceRule.query.get(result.rule_id) if result.rule_id else None
                    severity = rule.severity if rule else 'warning'

                    findings.append({
                        'rule_name': result.rule_name or (rule.rule_name if rule else '未知规则'),
                        'table_name': result.table_name,
                        'column_name': result.column_name,
                        'failed_count': result.failed_count or 0,
                        'failed_rate': float(result.failed_rate) if result.failed_rate else 0,
                        'status': result.status,
                        'severity': severity,
                        'rule_id': str(result.rule_id) if result.rule_id else None,
                        'report_id': str(result.report_id) if result.report_id else None
                    })
        except Exception as e:
            pass

        return findings

    def _get_report_trend(self, report_query, start_date, end_date):
        """获取报告趋势数据"""
        trend = []

        try:
            # 按天统计报告数量和质量评分
            from sqlalchemy import extract

            reports = report_query.order_by(GovernanceReport.execution_time.asc()).all()

            # 按日期分组
            daily_stats = {}
            for report in reports:
                if report.execution_time:
                    date_key = report.execution_time.strftime('%Y-%m-%d')
                    if date_key not in daily_stats:
                        daily_stats[date_key] = {
                            'date': date_key,
                            'count': 0,
                            'total_score': 0,
                            'score_count': 0,
                            'avg_score': None
                        }
                    daily_stats[date_key]['count'] += 1
                    if report.quality_score:
                        daily_stats[date_key]['total_score'] += float(report.quality_score)
                        daily_stats[date_key]['score_count'] += 1

            # 计算每日平均分
            for date_key in sorted(daily_stats.keys()):
                stat = daily_stats[date_key]
                if stat['score_count'] > 0:
                    stat['avg_score'] = round(stat['total_score'] / stat['score_count'], 2)
                del stat['total_score']
                del stat['score_count']
                trend.append(stat)
        except Exception as e:
            pass

        return trend

    def _get_rule_type_stats(self, rule_query, user_id):
        """获取规则类型统计"""
        stats = []

        try:
            # 使用已过滤的 rule_query 统计规则类型
            all_rules = rule_query.all()
            type_map = {}
            for rule in all_rules:
                rule_type = rule.rule_type
                if rule_type not in type_map:
                    type_map[rule_type] = 0
                type_map[rule_type] += 1

            total = sum(type_map.values()) or 1

            for rule_type, count in type_map.items():
                stats.append({
                    'type': rule_type,
                    'type_name': GovernanceRule.RULE_TYPE_NAMES.get(rule_type, rule_type),
                    'count': count,
                    'percentage': round((count / total) * 100, 1)
                })
        except Exception as e:
            pass

        return stats


# ==================== 数据源元数据 API ====================

class DatasourceTablesApi(Resource):
    """获取数据源下的所有表"""

    def get(self, datasource_id):
        """
        根据数据源ID获取该数据源下的所有表和视图
        从 UserDatasourceSchema 表中读取已存储的表结构信息

        参数:
            datasource_id: UUID，数据源ID（路径参数）

        返回:
            成功: {"code": 200, "msg": "success", "data": {"tables": [...], "total": N}}
            失败: {"code": 4xx, "msg": "...", "data": None}
        """
        from flask_login import current_user

        # 验证数据源
        datasource = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()

        if not datasource:
            return resp(code=404, msg="数据源不存在或无权访问", http_status=404)

        # 从 UserDatasourceSchema 读取该数据源下的所有表
        connect_info = datasource.connect_info
        schemas = UserDatasourceSchema.query.filter_by(
            user_id=current_user.id,
            connect_info=connect_info
        ).all()

        if not schemas:
            return resp(data={
                'tables': [],
                'total': 0
            })

        # 解析每个 schema 的表结构信息
        import json
        tables = []
        for schema in schemas:
            table_info = {
                'table_name': schema.table_name,
                'type': 'VIEW' if schema.is_view else 'TABLE',
                'description': '',
                'column_count': 0,
                'columns': []
            }

            # 解析 schema_text 获取详细表结构
            if schema.schema_text:
                try:
                    schema_data = json.loads(schema.schema_text)
                    table_info['description'] = schema_data.get('description', '')
                    columns = schema_data.get('columns', [])
                    table_info['column_count'] = len(columns)
                    # 只返回列名列表供前端展示
                    table_info['columns'] = [col.get('name') for col in columns if col.get('name')]
                except (json.JSONDecodeError, TypeError):
                    pass

            tables.append(table_info)

        # 按表名排序
        tables.sort(key=lambda x: x['table_name'])

        return resp(data={
            'tables': tables,
            'total': len(tables)
        })


class DatasourceColumnsApi(Resource):
    """获取数据源指定表的字段列表"""

    def get(self, datasource_id, table_name):
        """
        根据数据源ID和表名获取该表下的所有字段
        从 UserDatasourceSchema 表中读取已存储的字段信息

        参数:
            datasource_id: UUID，数据源ID（路径参数）
            table_name: string，表名称（路径参数）

        返回:
            成功: {"code": 200, "msg": "success", "data": {"table_name": "...", "columns": [...], "total": N}}
            失败: {"code": 4xx, "msg": "...", "data": None}
        """
        from flask_login import current_user

        # 验证数据源
        datasource = DatasourceInfo.query.filter_by(
            id=datasource_id,
            user_id=current_user.id
        ).first()

        if not datasource:
            return resp(code=404, msg="数据源不存在或无权访问", http_status=404)

        # 验证表名
        if not table_name or not str(table_name).strip():
            return resp(code=400, msg="表名称不能为空", http_status=400)

        # 从 UserDatasourceSchema 读取指定表的字段信息
        connect_info = datasource.connect_info
        schema = UserDatasourceSchema.query.filter_by(
            user_id=current_user.id,
            connect_info=connect_info,
            table_name=table_name
        ).first()

        if not schema:
            return resp(code=404, msg=f"表 '{table_name}' 不存在或未提取结构信息", http_status=404)

        # 解析 schema_text 获取字段列表
        import json
        columns = []
        table_description = ''
        if schema.schema_text:
            try:
                schema_data = json.loads(schema.schema_text)
                table_description = schema_data.get('description', '')
                raw_columns = schema_data.get('columns', [])
                for col in raw_columns:
                    columns.append({
                        'name': col.get('name'),
                        'type': col.get('type'),
                        'nullable': col.get('nullable', True),
                        'default': col.get('default'),
                        'comment': col.get('comment', ''),
                        'is_primary': col.get('is_primary', False),
                        'is_foreign': col.get('is_foreign', False)
                    })
            except (json.JSONDecodeError, TypeError) as e:
                print(f"[WARN] 解析表 {table_name} 的 schema_text 失败: {e}")

        return resp(data={
            'table_name': table_name,
            'table_description': table_description,
            'columns': columns,
            'total': len(columns)
        })


# 注册新路由
api.add_resource(RuleParseApi, '/rules/parse')
api.add_resource(RulePreviewApi, '/rules/preview')
api.add_resource(RuleSuggestApi, '/rules/suggest')
api.add_resource(QualityOverviewApi, '/quality/overview')
api.add_resource(DatasourceTablesApi, '/datasources/<string:datasource_id>/tables')
api.add_resource(DatasourceColumnsApi, '/datasources/<string:datasource_id>/tables/<string:table_name>/columns')
