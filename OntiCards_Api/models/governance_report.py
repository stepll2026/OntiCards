"""
@File: governance_report.py
@Description: 治理报告模型
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
"""

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func, text
from extensions.ext_database import db


class GovernanceReport(db.Model):
    """治理报告模型"""
    __tablename__ = 'governance_reports'

    # 评级常量
    GRADE_EXCELLENT = '优秀'
    GRADE_GOOD = '良好'
    GRADE_AVERAGE = '一般'
    GRADE_POOR = '较差'
    GRADE_BAD = '差'

    GRADES = [GRADE_EXCELLENT, GRADE_GOOD, GRADE_AVERAGE, GRADE_POOR, GRADE_BAD]

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text('uuid_generate_v4()'),
        comment='报告ID'
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        nullable=False,
        comment='用户ID'
    )
    datasource_id = db.Column(
        UUID(as_uuid=True),
        nullable=True,
        comment='数据源ID'
    )
    report_name = db.Column(
        db.String(255),
        nullable=True,
        comment='报告名称'
    )
    execution_time = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        comment='执行时间'
    )
    scope_tables = db.Column(
        db.ARRAY(db.String),
        nullable=True,
        comment='涉及的表列表'
    )
    rules_applied = db.Column(
        db.Integer,
        nullable=True,
        comment='应用的规则数'
    )
    include_quality = db.Column(
        db.Boolean,
        default=True,
        comment='是否包含质量检测'
    )
    include_basic_audit = db.Column(
        db.Boolean,
        default=False,
        comment='是否包含基础空值检测'
    )
    include_relationship = db.Column(
        db.Boolean,
        default=False,
        comment='是否包含关系发现'
    )
    quality_score = db.Column(
        db.Numeric(5, 2),
        nullable=True,
        comment='数据质量评分'
    )
    grade = db.Column(
        db.String(20),
        nullable=True,
        comment='评级'
    )
    # 基础空值检测完整结果（以表为单位，每表包含所有列的检测结果）
    basic_audit_result = db.Column(
        db.JSON,
        nullable=True,
        comment='基础空值检测完整结果'
    )
    # 基础空值检测执行明细（从 rule_execution_results 表查询 execution_source='basic_audit' 的记录）
    basic_audit_detail = db.Column(
        db.JSON,
        nullable=True,
        comment='基础空值检测执行明细'
    )
    # 关系盘点完整结果（直接复用全域盘点返回值）
    full_relation_discovery = db.Column(
        db.JSON,
        nullable=True,
        comment='关系盘点完整结果'
    )
    # 基于规则库的质检完整结果（仅保留有 rule_id 的规则执行结果）
    quality_audit_result = db.Column(
        db.JSON,
        nullable=True,
        comment='基于规则库质检完整结果'
    )
    summary = db.Column(
        db.JSON,
        nullable=True,
        comment='汇总数据'
    )
    details = db.Column(
        db.JSON,
        nullable=True,
        comment='详细结果'
    )
    # 导出文件路径
    exported_file_path = db.Column(
        db.String(512),
        nullable=True,
        comment='导出文件路径'
    )
    exported_file_type = db.Column(
        db.String(20),
        nullable=True,
        comment='导出文件类型: pdf, excel, docx'
    )
    exported_file_name = db.Column(
        db.String(255),
        nullable=True,
        comment='导出文件显示名称'
    )
    # 文件元信息
    file_size = db.Column(
        db.BigInteger,
        nullable=True,
        comment='文件大小（字节）'
    )
    file_created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        nullable=True,
        comment='文件创建时间'
    )
    file_status = db.Column(
        db.String(20),
        default='pending',
        nullable=True,
        comment='文件生成状态: pending, generating, completed, failed'
    )
    file_error_msg = db.Column(
        db.Text,
        nullable=True,
        comment='文件生成失败时的错误信息'
    )
    created_at = db.Column(
        db.TIMESTAMP(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
        comment='创建时间'
    )

    # 完整执行接口返回值（三大模块完整数据，作为报告生成的唯一真实数据源）
    execution_response = db.Column(
        db.JSON,
        nullable=True,
        comment='执行接口完整返回值（report_id/quality_score/summary/basic_audit/quality_audit/relation_discovery）'
    )

    # 关联执行结果
    execution_results = db.relationship(
        'RuleExecutionResult',
        backref='report',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def _format_datetime(self, value):
        """安全格式化时间字段，支持 datetime 对象或字符串"""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return str(value)

    def to_summary_dict(self, datasource_dict=None):
        """轻量级摘要，用于报告列表页。datasource_dict 为 {datasource_id: DatasourceInfo} 的映射"""
        ds = datasource_dict.get(self.datasource_id) if datasource_dict and self.datasource_id else None
        return {
            'id': str(self.id),
            'datasource_id': str(self.datasource_id) if self.datasource_id else None,
            'datasource_name': ds.connect_name if ds else None,
            'database_name': ds.database_name if ds else None,
            'schema_name': ds.schema_name if ds else None,
            'report_name': self.report_name,
            'execution_time': self._format_datetime(self.execution_time),
            'rules_applied': self.rules_applied,
            'quality_score': float(self.quality_score) if self.quality_score else None,
            'grade': self.grade,
            'include_quality': self.include_quality,
            'include_basic_audit': self.include_basic_audit,
            'include_relationship': self.include_relationship,
            'file_status': self.file_status,
            'has_export': bool(self.exported_file_path) and self.file_status == 'completed',
            'exported_file_name': self.exported_file_name,
            'exported_file_type': self.exported_file_type,
            'created_at': self._format_datetime(self.created_at),
        }

    def to_dict(self, include_details=False):
        result = {
            'id': str(self.id),
            'user_id': str(self.user_id) if self.user_id else None,
            'datasource_id': str(self.datasource_id) if self.datasource_id else None,
            'report_name': self.report_name,
            'execution_time': self._format_datetime(self.execution_time),
            'scope_tables': self.scope_tables,
            'rules_applied': self.rules_applied,
            'include_quality': self.include_quality,
            'include_basic_audit': self.include_basic_audit,
            'include_relationship': self.include_relationship,
            'quality_score': float(self.quality_score) if self.quality_score else None,
            'grade': self.grade,
            'basic_audit_result': self.basic_audit_result,
            'basic_audit_detail': self.basic_audit_detail,
            'full_relation_discovery': self.full_relation_discovery,
            'quality_audit_result': self.quality_audit_result,
            'summary': self.summary,
            'created_at': self._format_datetime(self.created_at),
            # 导出文件信息
            'exported_file_path': self.exported_file_path,
            'exported_file_type': self.exported_file_type,
            'exported_file_name': self.exported_file_name,
            'file_size': self.file_size,
            'file_created_at': self._format_datetime(self.file_created_at),
            'file_status': self.file_status,
            'file_error_msg': self.file_error_msg,
            'has_export': bool(self.exported_file_path) and self.file_status == 'completed'
        }
        if include_details:
            result['details'] = self.details
            # 返回该报告的所有历史导出文件列表
            from models.governance_report_file import GovernanceReportFile
            history_files = GovernanceReportFile.query.filter_by(report_id=self.id).order_by(
                GovernanceReportFile.created_at.desc()
            ).all()
            result['history_files'] = [f.to_dict() for f in history_files]
        return result
