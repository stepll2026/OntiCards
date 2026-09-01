"""
@File: governance_rule_template.py
@Description: 治理规则模板模型
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
"""

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func, text
from extensions.ext_database import db
from models.utils import format_datetime


# =============================================
# 规则类型常量
# =============================================
RULE_TYPE_NULL_CHECK = 'null_check'
RULE_TYPE_UNIQUE = 'unique'
RULE_TYPE_FORMAT = 'format'
RULE_TYPE_THRESHOLD = 'threshold'
RULE_TYPE_ENUM = 'enum'
RULE_TYPE_CUSTOM_SQL = 'custom_sql'
RULE_TYPE_LENGTH_CHECK = 'length_check'
RULE_TYPE_RANGE_CHECK = 'range_check'
RULE_TYPE_DATE_CHECK = 'date_check'
RULE_TYPE_CONSISTENCY_CHECK = 'consistency_check'
RULE_TYPE_FRESHNESS_CHECK = 'freshness_check'
RULE_TYPE_VALUE_DISTRIBUTION = 'value_distribution'
RULE_TYPE_COMPOSITE = 'composite'
RULE_TYPE_TABLE_STATS = 'table_stats'

RULE_TYPES = [
    RULE_TYPE_NULL_CHECK, RULE_TYPE_UNIQUE, RULE_TYPE_FORMAT,
    RULE_TYPE_THRESHOLD, RULE_TYPE_ENUM, RULE_TYPE_CUSTOM_SQL,
    RULE_TYPE_LENGTH_CHECK, RULE_TYPE_RANGE_CHECK, RULE_TYPE_DATE_CHECK,
    RULE_TYPE_CONSISTENCY_CHECK, RULE_TYPE_FRESHNESS_CHECK,
    RULE_TYPE_VALUE_DISTRIBUTION, RULE_TYPE_COMPOSITE, RULE_TYPE_TABLE_STATS
]

RULE_TYPE_NAMES = {
    RULE_TYPE_NULL_CHECK: '空值检测',
    RULE_TYPE_UNIQUE: '唯一性检测',
    RULE_TYPE_FORMAT: '格式检测',
    RULE_TYPE_THRESHOLD: '阈值检测',
    RULE_TYPE_ENUM: '枚举检测',
    RULE_TYPE_CUSTOM_SQL: '自定义SQL',
    RULE_TYPE_LENGTH_CHECK: '长度检测',
    RULE_TYPE_RANGE_CHECK: '范围检测',
    RULE_TYPE_DATE_CHECK: '日期检测',
    RULE_TYPE_CONSISTENCY_CHECK: '一致性检测',
    RULE_TYPE_FRESHNESS_CHECK: '新鲜度检测',
    RULE_TYPE_VALUE_DISTRIBUTION: '值分布检测',
    RULE_TYPE_COMPOSITE: '复合条件',
    RULE_TYPE_TABLE_STATS: '表级统计'
}

# 严重级别常量
SEVERITY_CRITICAL = 'critical'
SEVERITY_WARNING = 'warning'
SEVERITY_INFO = 'info'
SEVERITIES = [SEVERITY_CRITICAL, SEVERITY_WARNING, SEVERITY_INFO]

SEVERITY_NAMES = {
    SEVERITY_CRITICAL: '严重',
    SEVERITY_WARNING: '警告',
    SEVERITY_INFO: '信息'
}


class GovernanceRuleTemplate(db.Model):
    """治理规则模板模型（系统预置）"""
    __tablename__ = 'governance_rule_templates'

    id = db.Column(
        db.String(50),
        primary_key=True,
        comment='模板ID'
    )
    rule_type = db.Column(
        db.String(50),
        nullable=False,
        comment='规则类型'
    )
    template_name = db.Column(
        db.String(255),
        nullable=False,
        comment='模板名称'
    )
    description = db.Column(
        db.Text,
        nullable=True,
        comment='模板描述'
    )
    default_condition = db.Column(
        db.Text,
        nullable=True,
        comment='默认条件表达式'
    )
    applicable_columns = db.Column(
        db.Text,
        nullable=True,
        comment='适用的列类型'
    )
    default_severity = db.Column(
        db.String(20),
        default='warning',
        comment='默认严重级别: critical, warning, info'
    )
    condition_placeholder_hint = db.Column(
        db.Text,
        nullable=True,
        comment='条件占位符提示（如 min/max/days 等参数的说明）'
    )
    category = db.Column(
        db.String(50),
        nullable=True,
        comment='模板分类：基础检测、格式检测、阈值检测、枚举检测、日期检测、一致性检测、新鲜度检测、分布检测'
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        comment='创建时间'
    )

    @property
    def rule_type_name(self) -> str:
        """返回规则类型中文名称"""
        return RULE_TYPE_NAMES.get(self.rule_type, self.rule_type)

    @property
    def applicable_columns_list(self) -> list:
        """返回适用列类型的列表"""
        if not self.applicable_columns:
            return []
        return [c.strip() for c in self.applicable_columns.split(',') if c.strip()]

    @property
    def severity_name(self) -> str:
        """返回严重级别中文名称"""
        return SEVERITY_NAMES.get(self.default_severity, self.default_severity)

    @property
    def has_placeholder(self) -> bool:
        """判断条件表达式是否含有需要替换的占位符"""
        if not self.default_condition:
            return False
        # 常见的需要替换的占位符
        placeholders = ['column', '{min}', '{max}', '{min_length}', '{max_length}',
                       '{days}', '{hours}', '{threshold}', '{start_date}', '{end_date}',
                       'min', 'max', 'reference_table', 'referenced_id',
                       'start_date', 'end_date', 'column1', 'column2']
        return any(p in self.default_condition for p in placeholders)

    def to_dict(self, include_details=False):
        """序列化为字典"""
        data = {
            'id': self.id,
            'rule_type': self.rule_type,
            'rule_type_name': self.rule_type_name,
            'template_name': self.template_name,
            'description': self.description,
            'default_condition': self.default_condition,
            'applicable_columns': self.applicable_columns,
            'applicable_columns_list': self.applicable_columns_list,
            'default_severity': self.default_severity,
            'severity_name': self.severity_name,
            'condition_placeholder_hint': self.condition_placeholder_hint,
            'category': self.category,
            'has_placeholder': self.has_placeholder,
            'created_at': format_datetime(self.created_at)
        }
        if include_details:
            data['rule_type_options'] = RULE_TYPES
            data['severity_options'] = SEVERITIES
        return data
