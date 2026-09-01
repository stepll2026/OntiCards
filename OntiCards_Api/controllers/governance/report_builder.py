"""
@File: report_builder.py
@Description: 报告构建器 - 生成详细的治理报告
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-01
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from models.governance_report import GovernanceReport
from models.rule_execution_result import RuleExecutionResult


class ReportBuilder:
    """报告构建器"""

    # 评级标准
    GRADE_THRESHOLDS = {
        '优秀': 95,
        '良好': 85,
        '一般': 70,
        '较差': 60,
        '差': 0
    }

    # 规则类型名称映射
    RULE_TYPE_NAMES = {
        'null_check': '空值检测',
        'unique': '唯一性检测',
        'format': '格式检测',
        'threshold': '阈值检测',
        'enum': '枚举检测',
        'custom_sql': '自定义SQL检测'
    }

    # 严重级别名称映射
    SEVERITY_NAMES = {
        'critical': '严重',
        'warning': '警告',
        'info': '信息'
    }

    # 状态名称映射
    STATUS_NAMES = {
        'passed': '通过',
        'failed': '失败',
        'error': '错误'
    }

    def __init__(self, report: GovernanceReport):
        """初始化报告构建器

        Args:
            report: 报告对象
        """
        self.report = report

    def _calculate_quality_score(self, results: List[RuleExecutionResult]) -> float:
        """计算质量评分

        Args:
            results: 规则执行结果列表

        Returns:
            质量评分 (0-100)
        """
        if not results:
            return 100.0

        total = len(results)
        passed = sum(1 for r in results if r.status == 'passed')
        failed = sum(1 for r in results if r.status == 'failed')

        if total == 0:
            return 100.0

        # 基础评分 = 通过率
        base_score = (passed / total) * 100

        # 根据失败数量和严重级别扣分
        critical_fails = sum(1 for r in results if r.severity == 'critical' and r.status == 'failed')
        warning_fails = sum(1 for r in results if r.severity == 'warning' and r.status == 'failed')

        deduction = (critical_fails * 5) + (warning_fails * 2)
        final_score = max(0, min(100, base_score - deduction))

        return round(final_score, 2)

    def _determine_grade(self, score: float) -> str:
        """根据评分确定评级

        Args:
            score: 质量评分

        Returns:
            评级
        """
        if score >= 95:
            return '优秀'
        elif score >= 85:
            return '良好'
        elif score >= 70:
            return '一般'
        elif score >= 60:
            return '较差'
        else:
            return '差'

    def _build_summary(self, results: List[RuleExecutionResult]) -> Dict[str, Any]:
        """构建汇总信息

        Args:
            results: 规则执行结果列表

        Returns:
            汇总信息字典
        """
        total = len(results)
        passed = sum(1 for r in results if r.status == 'passed')
        failed = sum(1 for r in results if r.status == 'failed')
        errors = sum(1 for r in results if r.status == 'error')

        # 按规则类型统计
        by_type = {}
        for r in results:
            rule_type = r.rule_type or 'unknown'
            if rule_type not in by_type:
                by_type[rule_type] = {'total': 0, 'passed': 0, 'failed': 0}
            by_type[rule_type]['total'] += 1
            if r.status == 'passed':
                by_type[rule_type]['passed'] += 1
            elif r.status == 'failed':
                by_type[rule_type]['failed'] += 1

        # 按严重级别统计
        by_severity = {
            'critical': {'total': 0, 'passed': 0, 'failed': 0},
            'warning': {'total': 0, 'passed': 0, 'failed': 0},
            'info': {'total': 0, 'passed': 0, 'failed': 0}
        }
        for r in results:
            severity = r.severity or 'info'
            if severity not in by_severity:
                by_severity[severity] = {'total': 0, 'passed': 0, 'failed': 0}
            by_severity[severity]['total'] += 1
            if r.status == 'passed':
                by_severity[severity]['passed'] += 1
            elif r.status == 'failed':
                by_severity[severity]['failed'] += 1

        # 计算总影响行数
        total_affected_rows = sum(r.failed_count or 0 for r in results if r.status == 'failed')

        return {
            'total_rules': total,
            'passed_rules': passed,
            'failed_rules': failed,
            'error_rules': errors,
            'pass_rate': round((passed / total * 100) if total > 0 else 100, 2),
            'fail_rate': round((failed / total * 100) if total > 0 else 0, 2),
            'total_affected_rows': total_affected_rows,
            'by_rule_type': by_type,
            'by_severity': by_severity
        }

    def _build_critical_findings(self, results: List[RuleExecutionResult]) -> List[Dict[str, Any]]:
        """构建关键问题列表

        Args:
            results: 规则执行结果列表

        Returns:
            关键问题列表
        """
        findings = []

        # 只关注失败且严重级别较高的规则
        failed_results = [r for r in results if r.status == 'failed']
        sorted_results = sorted(
            failed_results,
            key=lambda x: (
                {'critical': 0, 'warning': 1, 'info': 2}.get(x.severity, 3),
                -(x.failed_count or 0)
            )
        )

        for r in sorted_results[:10]:  # 最多返回 10 条
            findings.append({
                'rule_id': str(r.rule_id) if r.rule_id else None,
                'rule_name': r.rule_name,
                'rule_type': r.rule_type,
                'rule_type_name': self.RULE_TYPE_NAMES.get(r.rule_type, r.rule_type),
                'table_name': r.table_name,
                'column_name': r.column_name,
                'severity': r.severity,
                'severity_name': self.SEVERITY_NAMES.get(r.severity, r.severity),
                'failed_count': r.failed_count or 0,
                'failed_rate': float(r.failed_rate) if r.failed_rate else 0,
                'recommendation': self._generate_recommendation(r)
            })

        return findings

    def _generate_recommendation(self, result: RuleExecutionResult) -> str:
        """根据执行结果生成改进建议

        Args:
            result: 规则执行结果

        Returns:
            改进建议
        """
        rule_type = result.rule_type
        table = result.table_name or ''
        column = result.column_name or ''

        recommendations = {
            'null_check': f'建议检查表 {table} 中字段 {column} 的数据录入流程，确保必填项不为空。',
            'unique': f'建议对表 {table} 中字段 {column} 进行去重处理，重复值数量: {result.failed_count}。',
            'format': f'建议统一表 {table} 中字段 {column} 的数据格式标准。',
            'threshold': f'建议检查表 {table} 中字段 {column} 的取值范围，超出阈值的记录数量: {result.failed_count}。',
            'enum': f'建议规范表 {table} 中字段 {column} 的取值范围，当前存在 {result.failed_count} 条非法枚举值。',
            'custom_sql': f'建议检查表 {table} 中不满足规则条件的 {result.failed_count} 条记录。'
        }

        return recommendations.get(rule_type, f'建议检查表 {table} 中存在问题的 {result.failed_count} 条记录。')

    def _build_dimensional_scores(self, results: List[RuleExecutionResult]) -> Dict[str, Any]:
        """构建维度评分

        Args:
            results: 规则执行结果列表

        Returns:
            维度评分字典
        """
        # 完整性：空值检测结果
        null_results = [r for r in results if r.rule_type == 'null_check']
        completeness = 100.0
        if null_results:
            avg_failed_rate = sum(r.failed_rate or 0 for r in null_results) / len(null_results)
            completeness = max(0, 100 - avg_failed_rate)

        # 准确性：格式检测、阈值检测
        accuracy_results = [r for r in results if r.rule_type in ('format', 'threshold', 'custom_sql')]
        accuracy = 100.0
        if accuracy_results:
            avg_failed_rate = sum(r.failed_rate or 0 for r in accuracy_results) / len(accuracy_results)
            accuracy = max(0, 100 - avg_failed_rate)

        # 一致性：枚举检测、唯一性检测
        consistency_results = [r for r in results if r.rule_type in ('enum', 'unique')]
        consistency = 100.0
        if consistency_results:
            avg_failed_rate = sum(r.failed_rate or 0 for r in consistency_results) / len(consistency_results)
            consistency = max(0, 100 - avg_failed_rate)

        return {
            'completeness': {'score': round(completeness, 2), 'name': '完整性'},
            'accuracy': {'score': round(accuracy, 2), 'name': '准确性'},
            'consistency': {'score': round(consistency, 2), 'name': '一致性'}
        }

    def build_report(self, results: List[RuleExecutionResult]) -> Dict[str, Any]:
        """构建完整报告

        Args:
            results: 规则执行结果列表

        Returns:
            完整报告字典
        """
        # 计算评分和评级
        quality_score = self._calculate_quality_score(results)
        grade = self._determine_grade(quality_score)

        # 构建报告结构
        report_dict = {
            'report_id': str(self.report.id),
            'report_name': self.report.report_name,
            'generated_at': datetime.now().isoformat(),
            'datasource_id': str(self.report.datasource_id) if self.report.datasource_id else None,
            'scope': {
                'tables': self.report.scope_tables or [],
                'rules_applied': len(results)
            },
            'quality_score': quality_score,
            'grade': grade,
            'dimensions': self._build_dimensional_scores(results),
            'summary': self._build_summary(results),
            'critical_findings': self._build_critical_findings(results),
            'recommendations': self._generate_recommendations(results),
            'execution_results': [r.to_dict() for r in results]
        }

        return report_dict

    def _generate_recommendations(self, results: List[RuleExecutionResult]) -> List[str]:
        """生成改进建议列表

        Args:
            results: 规则执行结果列表

        Returns:
            建议列表
        """
        recommendations = []
        failed_results = [r for r in results if r.status == 'failed']

        if not failed_results:
            recommendations.append('数据质量良好，继续保持当前的数据管理规范。')
            return recommendations

        # 按规则类型分组统计
        by_type = {}
        for r in failed_results:
            rule_type = r.rule_type or 'unknown'
            if rule_type not in by_type:
                by_type[rule_type] = []
            by_type[rule_type].append(r)

        # 生成针对性建议
        if 'null_check' in by_type:
            tables = list(set(r.table_name for r in by_type['null_check'] if r.table_name))
            recommendations.append(f'1. 空值问题：发现 {len(by_type["null_check"])} 个字段存在空值，建议重点检查表 {", ".join(tables[:3])} 等的数据完整性。')

        if 'unique' in by_type:
            tables = list(set(r.table_name for r in by_type['unique'] if r.table_name))
            total_duplicates = sum(r.failed_count or 0 for r in by_type['unique'])
            recommendations.append(f'2. 唯一性问题：发现 {len(by_type["unique"])} 个字段存在重复值，共计 {total_duplicates} 条重复记录，建议进行去重处理。')

        if 'format' in by_type:
            recommendations.append(f'3. 格式问题：发现 {len(by_type["format"])} 个字段存在格式不规范问题，建议统一数据录入格式标准。')

        if 'threshold' in by_type:
            recommendations.append(f'4. 阈值问题：发现 {len(by_type["threshold"])} 个字段存在超出阈值范围的数据，建议检查数据来源的合法性。')

        if 'enum' in by_type:
            recommendations.append(f'5. 枚举问题：发现 {len(by_type["enum"])} 个字段存在非法枚举值，建议规范数据取值范围。')

        return recommendations

    def update_report_with_builder(self, results: List[RuleExecutionResult]) -> GovernanceReport:
        """使用构建器更新报告

        Args:
            results: 规则执行结果列表

        Returns:
            更新后的报告对象
        """
        from extensions.ext_database import db

        report_data = self.build_report(results)

        # 更新报告字段
        self.report.quality_score = report_data['quality_score']
        self.report.grade = report_data['grade']
        self.report.summary = report_data['summary']
        self.report.details = report_data

        db.session.commit()

        return self.report


def build_governance_report(report: GovernanceReport,
                             results: List[RuleExecutionResult]) -> Dict[str, Any]:
    """构建治理报告的便捷函数

    Args:
        report: 报告对象
        results: 规则执行结果列表

    Returns:
        报告字典
    """
    builder = ReportBuilder(report)
    return builder.build_report(results)
