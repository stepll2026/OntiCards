"""
@File: governance_rule.py
@Description: 治理规则模型
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
@Update: 2026-06-02 - 支持多条件和作用域

规则作用域设计：
1. 全局规则：target_table = '*' 或 null，表示对所有表执行
2. 表级规则：target_table = 具体表名
3. 列级规则：target_column = 具体列名，支持多条件
"""

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func, text
from extensions.ext_database import db
from models.utils import format_datetime
import json
from typing import List, Dict


class GovernanceRule(db.Model):
    """治理规则模型"""
    __tablename__ = 'governance_rules'

    # 规则类型常量
    # 基础类型
    RULE_TYPE_NULL_CHECK = 'null_check'
    RULE_TYPE_UNIQUE = 'unique'
    RULE_TYPE_FORMAT = 'format'
    RULE_TYPE_THRESHOLD = 'threshold'
    RULE_TYPE_ENUM = 'enum'
    RULE_TYPE_CUSTOM_SQL = 'custom_sql'

    # 扩展类型
    RULE_TYPE_LENGTH_CHECK = 'length_check'
    RULE_TYPE_RANGE_CHECK = 'range_check'
    RULE_TYPE_DATE_CHECK = 'date_check'
    RULE_TYPE_CONSISTENCY_CHECK = 'consistency_check'
    RULE_TYPE_FRESHNESS_CHECK = 'freshness_check'
    RULE_TYPE_VALUE_DISTRIBUTION = 'value_distribution'

    # 多列比较类型
    RULE_TYPE_MULTI_COLUMN_COMPARE = 'multi_column_compare'

    # 复合规则类型
    RULE_TYPE_COMPOSITE = 'composite'
    RULE_TYPE_TABLE_STATS = 'table_stats'

    RULE_TYPES = [
        # 基础类型
        RULE_TYPE_NULL_CHECK,
        RULE_TYPE_UNIQUE,
        RULE_TYPE_FORMAT,
        RULE_TYPE_THRESHOLD,
        RULE_TYPE_ENUM,
        RULE_TYPE_CUSTOM_SQL,
        # 扩展类型
        RULE_TYPE_LENGTH_CHECK,
        RULE_TYPE_RANGE_CHECK,
        RULE_TYPE_DATE_CHECK,
        RULE_TYPE_CONSISTENCY_CHECK,
        RULE_TYPE_FRESHNESS_CHECK,
        RULE_TYPE_VALUE_DISTRIBUTION,
        # 多列比较类型
        RULE_TYPE_MULTI_COLUMN_COMPARE,
        # 复合类型
        RULE_TYPE_COMPOSITE,
        RULE_TYPE_TABLE_STATS
    ]

    # 规则类型中文名称映射
    RULE_TYPE_NAMES = {
        'null_check': '空值检测',
        'unique': '唯一性检测',
        'format': '格式检测',
        'threshold': '阈值检测',
        'enum': '枚举检测',
        'custom_sql': '自定义SQL',
        'length_check': '长度检测',
        'range_check': '范围检测',
        'date_check': '日期检测',
        'consistency_check': '一致性检测',
        'freshness_check': '新鲜度检测',
        'value_distribution': '值分布检测',
        'multi_column_compare': '多列比较',
        'composite': '复合条件',
        'table_stats': '表级统计'
    }

    # 严重级别常量
    SEVERITY_CRITICAL = 'critical'
    SEVERITY_WARNING = 'warning'
    SEVERITY_INFO = 'info'

    SEVERITIES = [SEVERITY_CRITICAL, SEVERITY_WARNING, SEVERITY_INFO]

    # 条件关系常量
    COND_MODE_AND = 'AND'
    COND_MODE_OR = 'OR'

    CONDITION_MODES = [COND_MODE_AND, COND_MODE_OR]

    # 创建来源常量
    SOURCE_MANUAL = 'manual'      # 手动配置
    SOURCE_TEMPLATE = 'template'   # 模板导入
    SOURCE_AI = 'ai'             # AI智能解析

    CREATE_SOURCES = [SOURCE_MANUAL, SOURCE_TEMPLATE, SOURCE_AI]

    # 创建来源中文名称映射
    CREATE_SOURCE_NAMES = {
        'manual': '手动配置',
        'template': '模板导入',
        'ai': 'AI智能解析'
    }

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text('uuid_generate_v4()'),
        comment='规则ID'
    )
    library_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('governance_rule_libraries.id', ondelete='CASCADE'),
        nullable=True,
        comment='规则库ID'
    )
    rule_name = db.Column(
        db.String(255),
        nullable=False,
        comment='规则名称'
    )
    rule_type = db.Column(
        db.String(50),
        nullable=False,
        comment='规则类型'
    )

    # 作用域：目标表
    # - '*' 或 null: 对所有表执行（全局规则）
    # - 具体表名: 对指定表执行
    target_table = db.Column(
        db.String(255),
        nullable=True,
        comment='目标表，*表示所有表'
    )

    # 作用域：目标列（单列场景）
    target_column = db.Column(
        db.String(255),
        nullable=True,
        comment='目标列（单列场景）'
    )

    # 条件表达式（单列场景）
    condition_expr = db.Column(
        db.Text,
        nullable=True,
        comment='规则条件表达式'
    )

    # 多条件配置（JSON格式）
    # {
    #   "conditions": [
    #       {"column": "total_amount", "rule_type": "threshold", "condition": ">= 0"},
    #       {"column": "phone", "rule_type": "null_check", "condition": "IS NOT NULL"}
    #   ],
    #   "condition_mode": "AND"
    # }
    conditions_config = db.Column(
        db.Text,
        nullable=True,
        comment='多条件配置JSON'
    )

    # 检测SQL语句（用于预览和执行）
    sql_text = db.Column(
        db.Text,
        nullable=True,
        comment='检测SQL语句'
    )

    severity = db.Column(
        db.String(20),
        default='warning',
        comment='严重级别: critical, warning, info'
    )
    description = db.Column(
        db.Text,
        nullable=True,
        comment='规则描述'
    )
    enabled = db.Column(
        db.Boolean,
        default=True,
        comment='是否启用'
    )
    create_source = db.Column(
        db.String(20),
        default='manual',
        comment='创建来源: manual=手动配置, template=模板导入, ai=AI智能解析'
    )
    db_type = db.Column(
        db.String(20),
        nullable=True,
        comment='目标数据库类型（如 postgresql/mysql/mssql/oracle/sqlite/trino），从规则库关联的数据源继承'
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        comment='创建时间'
    )
    updated_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
        comment='更新时间'
    )

    def get_conditions(self) -> List[Dict]:
        """获取条件列表"""
        if not self.conditions_config:
            return []
        try:
            return json.loads(self.conditions_config)
        except:
            return []

    def set_conditions(self, conditions: List[Dict], condition_mode: str = 'AND'):
        """设置条件列表"""
        config = {
            "conditions": conditions,
            "condition_mode": condition_mode
        }
        self.conditions_config = json.dumps(config, ensure_ascii=False)

    def has_multiple_conditions(self) -> bool:
        """是否有多条件"""
        conditions = self.get_conditions()
        return len(conditions) > 1

    def is_global_rule(self) -> bool:
        """是否是全局规则（对所有表执行）"""
        return self.target_table is None or self.target_table == '*'

    def get_scope_description(self) -> str:
        """获取作用域描述"""
        if self.is_global_rule():
            return "全局规则（所有表）"
        return f"表: {self.target_table}"

    def to_dict(self, include_details=False):
        data = {
            'id': str(self.id),
            'library_id': str(self.library_id) if self.library_id else None,
            'rule_name': self.rule_name,
            'rule_type': self.rule_type,
            'rule_type_name': self.RULE_TYPE_NAMES.get(self.rule_type, self.rule_type),
            'target_table': self.target_table,
            'target_column': self.target_column,
            'condition_expr': self.condition_expr,
            'conditions_config': self.get_conditions() if self.has_multiple_conditions() else None,
            'sql_text': self.sql_text,
            'severity': self.severity,
            'description': self.description,
            'enabled': self.enabled,
            'create_source': self.create_source,
            'create_source_name': self.CREATE_SOURCE_NAMES.get(self.create_source, self.create_source),
            'db_type': self.db_type,
            'is_global': self.is_global_rule(),
            'scope_description': self.get_scope_description(),
            'created_at': format_datetime(self.created_at),
            'updated_at': format_datetime(self.updated_at)
        }
        if include_details:
            data['severity_name'] = {
                'critical': '严重',
                'warning': '警告',
                'info': '信息'
            }.get(self.severity, self.severity)
        return data
