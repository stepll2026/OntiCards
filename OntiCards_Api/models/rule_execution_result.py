"""
@File: rule_execution_result.py
@Description: 规则执行结果模型
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
"""

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func, text
from extensions.ext_database import db
from models.utils import format_datetime


class RuleExecutionResult(db.Model):
    """规则执行结果模型"""
    __tablename__ = 'rule_execution_results'

    # 状态常量
    STATUS_PASSED = 'passed'
    STATUS_FAILED = 'failed'
    STATUS_ERROR = 'error'

    STATUSES = [STATUS_PASSED, STATUS_FAILED, STATUS_ERROR]

    # 执行模式常量（与 SQL 注释中的三个值保持一致）
    MODE_SCOPED_SINGLE = 'scoped_single'         # 有 target_table + target_column（单列/单条件）
    MODE_SCOPED_MULTI_COND = 'scoped_multi_cond' # 有 target_table + conditions_config（多条件）
    MODE_UNSCOPED = 'unscoped'                  # 无 target_table（全局规则）

    # 执行来源常量
    SOURCE_RULE_LIBRARY = 'rule_library'  # 规则库质检
    SOURCE_BASIC_AUDIT = 'basic_audit'    # 基础空值检测

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text('uuid_generate_v4()'),
        comment='结果ID'
    )
    report_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('governance_reports.id', ondelete='CASCADE'),
        nullable=True,
        comment='报告ID'
    )
    library_id = db.Column(
        UUID(as_uuid=True),
        nullable=True,
        comment='规则库ID（追溯结果来源）'
    )
    rule_id = db.Column(
        UUID(as_uuid=True),
        nullable=True,
        comment='规则ID'
    )
    rule_name = db.Column(
        db.String(255),
        nullable=True,
        comment='规则名称'
    )
    rule_type = db.Column(
        db.String(50),
        nullable=True,
        comment='规则类型'
    )
    severity = db.Column(
        db.String(20),
        nullable=True,
        comment='严重级别: critical, warning, info'
    )
    table_name = db.Column(
        db.String(255),
        nullable=True,
        comment='表名'
    )
    column_name = db.Column(
        db.String(255),
        nullable=True,
        comment='列名'
    )
    # 执行模式：scoped_single / scoped_multi_cond / unscoped
    rule_mode = db.Column(
        db.String(30),
        nullable=True,
        comment='执行模式'
    )
    total_count = db.Column(
        db.BigInteger,
        nullable=True,
        comment='总记录数'
    )
    passed_count = db.Column(
        db.BigInteger,
        nullable=True,
        comment='通过记录数'
    )
    failed_count = db.Column(
        db.BigInteger,
        nullable=True,
        comment='失败记录数'
    )
    failed_rate = db.Column(
        db.Numeric(5, 2),
        nullable=True,
        comment='失败率'
    )
    failed_samples = db.Column(
        db.JSON,
        nullable=True,
        comment='失败样本'
    )
    # 本次执行的检测 SQL 文本
    executed_sql_text = db.Column(
        db.Text,
        nullable=True,
        comment='本次执行的检测SQL文本'
    )
    # SQL 执行耗时（毫秒）
    execution_time_ms = db.Column(
        db.Integer,
        nullable=True,
        comment='SQL执行耗时（毫秒）'
    )
    # SQL 原始执行结果：以键值对形式存储查询返回的完整列名和值
    raw_result = db.Column(
        db.JSON,
        nullable=True,
        comment='SQL查询原始返回结果'
    )
    status = db.Column(
        db.String(20),
        nullable=True,
        comment='状态: passed, failed, error'
    )
    # 规则执行出错时的错误信息
    error_message = db.Column(
        db.Text,
        nullable=True,
        comment='规则执行错误信息'
    )
    # 执行结果来源: rule_library=规则库质检, basic_audit=基础空值检测
    execution_source = db.Column(
        db.String(30),
        nullable=True,
        comment='执行结果来源'
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        comment='创建时间'
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'report_id': str(self.report_id) if self.report_id else None,
            'library_id': str(self.library_id) if self.library_id else None,
            'rule_id': str(self.rule_id) if self.rule_id else None,
            'rule_name': self.rule_name,
            'rule_type': self.rule_type,
            'severity': self.severity,
            'table_name': self.table_name,
            'column_name': self.column_name,
            'rule_mode': self.rule_mode,
            'total_count': self.total_count,
            'passed_count': self.passed_count,
            'failed_count': self.failed_count,
            'failed_rate': float(self.failed_rate) if self.failed_rate else None,
            'failed_samples': self.failed_samples,
            'executed_sql_text': self.executed_sql_text,
            'execution_time_ms': self.execution_time_ms,
            'raw_result': self.raw_result,
            'status': self.status,
            'error_message': self.error_message,
            'execution_source': self.execution_source,
            'created_at': format_datetime(self.created_at)
        }
