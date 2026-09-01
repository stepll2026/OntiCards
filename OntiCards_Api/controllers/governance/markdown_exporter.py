# -*- coding:utf-8 -*-
"""
@File: markdown_exporter.py
@Description: 数据治理报告 Markdown 导出服务
@Author: 韩小豪 849631113@qq.com
@Create: 2026-07-07

核心设计原则：
- 唯一真实数据源：report.execution_response（执行接口完整返回值）
- 报告内容完全对齐规则执行接口返回值的结构和内容
- LLM 总结阶段传入完整 execution_response JSON，让大模型动态生成分析
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from models.governance_report import GovernanceReport
from models.rule_execution_result import RuleExecutionResult


class MarkdownExporter:
    """Markdown 格式报告导出器"""

    RULE_TYPE_NAMES = {
        'null_check': '空值检测',
        'unique': '唯一性检测',
        'format': '格式检测',
        'threshold': '阈值检测',
        'enum': '枚举检测',
        'custom_sql': '自定义SQL检测',
        'length_check': '长度检测',
        'range_check': '范围检测',
        'date_check': '日期检测',
        'consistency_check': '一致性检测',
        'freshness_check': '新鲜度检测',
        'value_distribution': '值分布检测',
        'composite': '复合条件检测',
        'table_stats': '表级统计',
    }

    SEVERITY_NAMES = {
        'critical': '严重',
        'warning': '警告',
        'info': '信息'
    }

    STATUS_NAMES = {
        'passed': '通过',
        'failed': '失败',
        'error': '错误'
    }

    RELATIONSHIP_TYPE_NAMES = {
        'foreign_key': '外键',
        'shared_field': '共享字段',
        'value_overlap': '值域重叠',
        'name_similarity': '名称相似',
        'schema_inference': 'Schema推断',
    }

    CARDINALITY_NAMES = {
        'one_to_one': '1:1 一对一',
        'one_to_many': '1:N 一对多',
        'many_to_one': 'N:1 多对一',
        'many_to_many': 'N:N 多对多',
    }

    def __init__(self, export_path: str = None, user_id: str = None):
        if export_path is None:
            from flask import current_app
            base_path = current_app.config.get(
                'GOVERNANCE_EXPORT_PATH',
                os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    'exports', 'governance'
                )
            )
        else:
            base_path = export_path

        if user_id:
            export_path = os.path.join(base_path, str(user_id))
        else:
            export_path = base_path

        # 统一使用正斜杠 '/'，确保跨平台一致性
        self.export_path = export_path.replace('\\', '/')
        self.user_id = user_id
        os.makedirs(self.export_path, exist_ok=True)

    def export(
        self,
        report: GovernanceReport,
        results: List[RuleExecutionResult],
        fmt: str = 'md',
        include_llm_summary: bool = True,
        custom_file_name: str = None,
    ) -> Dict[str, Any]:
        """导出 Markdown 报告

        Args:
            report: 报告对象
            results: 规则执行结果列表
            fmt: 导出格式（本类仅支持 'md'）
            include_llm_summary: 是否包含 LLM 总结章节（默认 True）
            custom_file_name: 自定义导出文件名（不含扩展名），不传则使用默认命名规则

        Returns:
            {
                'file_path': str,
                'file_name': str,
                'file_size': int,
                'format': str,
                'mode': str,
            }
        """
        print(f"[Markdown-Exporter] 开始生成 Markdown 报告 | report_id={report.id}")

        file_name = self._make_filename(report, custom_file_name=custom_file_name)
        file_path = os.path.join(self.export_path, file_name)
        # 统一使用正斜杠
        file_path = file_path.replace('\\', '/')

        content = self._build_content(report, results, include_llm_summary)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        file_size = os.path.getsize(file_path)

        print(f"[Markdown-Exporter] Markdown 报告生成完成 | path={file_path}, size={file_size}")

        return {
            'file_path': file_path,
            'file_name': file_name,
            'file_size': file_size,
            'format': 'md',
            'mode': 'markdown',
        }

    def _make_filename(self, report: GovernanceReport, custom_file_name: str = None) -> str:
        """生成带时间戳的文件名

        Args:
            report: 报告对象
            custom_file_name: 自定义文件名（不含扩展名），不传则使用默认命名规则
        """
        # 过滤文件名中的非法字符：/ \ : * ? " < > |
        if custom_file_name and custom_file_name.strip():
            # 自定义文件名：添加中文时间戳
            ts = datetime.now().strftime('%Y年%m月%d日%H点%M分%S秒')
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', custom_file_name.strip())
            return f"{safe_name}_{ts}.md"
        else:
            # 默认文件名：将 report.report_name 中的冒号替换，并转成中文时间格式
            raw_name = report.report_name or 'governance_report'
            safe_name = self._sanitize_and_format_name(raw_name)
            return f"{safe_name}.md"

    def _sanitize_and_format_name(self, name: str) -> str:
        """清理文件名中的非法字符，并将时间戳转成中文格式

        例如：
        - 质检结果_2026-07-20_14:07:43 -> 质检结果_2026年07月20日14点07分43秒
        - 质检结果_2026-07-20_14_07_43 -> 质检结果_2026年07月20日14点07分43秒
        """
        # 过滤非法字符：/ \ : * ? " < > |
        safe = re.sub(r'[\\/:*?"<>|]', '', name)
        # 匹配时间戳模式：YYYY-MM-DD_HH:MM:SS 或 YYYY-MM-DD_HH_MM_SS
        time_pattern = r'(\d{4})-(\d{2})-(\d{2})[_-](\d{2})[_:](\d{2})[_:](\d{2})'
        def replace_time(m):
            year, month, day, hour, minute, second = m.groups()
            return f"{year}年{month}月{day}日{hour}点{minute}分{second}秒"
        return re.sub(time_pattern, replace_time, safe)

    def _build_content(
        self,
        report: GovernanceReport,
        results: List[RuleExecutionResult],
        include_llm_summary: bool,
    ) -> str:
        """构建 Markdown 全文内容

        唯一数据源：report.execution_response（执行接口完整返回值，三大模块数据齐全）
        results：保留 RuleExecutionResult ORM 对象原始数据（用于执行明细表格）
        """
        exec_resp = getattr(report, 'execution_response', None) or {}
        basic_audit = exec_resp.get('basic_audit') or {}
        quality_audit = exec_resp.get('quality_audit') or {}
        relation_data = exec_resp.get('relation_discovery') or {}
        has_basic = bool(basic_audit and basic_audit.get('tables'))
        has_rel = bool(relation_data and relation_data.get('relationships_count', 0) > 0)
        has_quality = bool(quality_audit and quality_audit.get('results'))

        parts = []
        parts.append(self._build_header(report))
        parts.append(self._build_basic_info(report, exec_resp))
        parts.append(self._build_quality_overview(
            report, results, exec_resp, basic_audit, quality_audit, relation_data
        ))

        if has_basic:
            parts.append(self._build_basic_audit_by_table(basic_audit))

        if has_rel:
            parts.append(self._build_relation_discovery_full(relation_data))

        parts.append(self._build_execution_detail(report, results, has_rel, has_basic))
        parts.append(self._build_failed_samples(results, has_rel, has_basic))

        # 生成 LLM 各模块分析 + 综合总结（包含细分建议和全局视角）
        if include_llm_summary:
            llm_summary = self._generate_llm_summary(report, results, exec_resp)
            parts.append(self._build_llm_summary_section(llm_summary, has_rel, has_basic))
            # 添加综合总结章节（包含细分视角 + 全局视角的完整建议）
            overall_summary = self._generate_overall_summary(report, results, exec_resp)
            parts.append(self._build_overall_summary_section(overall_summary, has_rel, has_basic))

        parts.append(self._build_footer(report))

        return '\n\n'.join(parts)

    def _build_header(self, report: GovernanceReport) -> str:
        title = report.report_name or '数据治理质量报告'
        report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""# {title}

> 本报告由 OntiCards AI数据中枢 自动生成
> 生成时间: {report_time}
"""

    def _build_basic_info(self, report: GovernanceReport, exec_resp: Dict[str, Any]) -> str:
        datasource_id = str(report.datasource_id) if report.datasource_id else 'N/A'
        execution_time = (
            report.execution_time.strftime('%Y-%m-%d %H:%M:%S')
            if report.execution_time else 'N/A'
        )
        tables = ', '.join(report.scope_tables) if report.scope_tables else '全部表'

        datasource_name = datasource_id
        if relation_data := exec_resp.get('relation_discovery'):
            if rels := relation_data.get('relationships'):
                datasource_name = rels[0].get('from_datasource_name') or datasource_id

        included_modules = self._get_included_modules_text(exec_resp)

        return f"""## 一、基本信息

| 项目 | 内容 |
|------|------|
| 数据源 | {datasource_name}（{datasource_id}） |
| 执行时间 | {execution_time} |
| 涉及表 | {tables} |
| 包含模块 | {included_modules} |
"""

    def _get_included_modules_text(self, exec_resp: Dict[str, Any]) -> str:
        modules = []
        if exec_resp.get('basic_audit') and exec_resp['basic_audit'].get('tables'):
            modules.append('基础空值检测')
        if exec_resp.get('quality_audit') and exec_resp['quality_audit'].get('results'):
            modules.append('规则库质检')
        if exec_resp.get('relation_discovery') and exec_resp['relation_discovery'].get('relationships_count', 0) > 0:
            modules.append('表关系盘点')
        return '、'.join(modules) if modules else '无'

    def _build_quality_overview(
        self,
        report: GovernanceReport,
        results: List[RuleExecutionResult],
        exec_resp: Dict[str, Any],
        basic_audit: Dict[str, Any],
        quality_audit: Dict[str, Any],
        relation_data: Dict[str, Any],
    ) -> str:
        """质量概览——三大模块质检结果的全面汇总

        数据源：execution_response['summary'] + 各模块数据聚合
        """
        quality_score = float(report.quality_score) if report.quality_score else 0
        grade = report.grade or '一般'
        grade_emoji = {'优秀': '🟢', '良好': '🔵', '一般': '🟡', '较差': '🟠', '差': '🔴'}.get(grade, '⚪')

        summary = exec_resp.get('summary') or {}
        quality_total = summary.get('total_rules', 0)
        quality_passed = summary.get('passed_rules', 0)
        quality_failed = summary.get('failed_rules', 0)
        quality_errors = summary.get('error_rules', 0)

        # 基础空值检测统计
        basic_tables = basic_audit.get('tables', []) if basic_audit else []
        basic_all_cols = [c for tbl in basic_tables for c in tbl.get('report', [])]
        basic_problem = [c for c in basic_all_cols if c.get('missing_pct', 0) > 0]
        basic_null = sum(c.get('null_count', 0) for c in basic_all_cols)
        basic_empty = sum(c.get('empty_str_count', 0) for c in basic_all_cols)

        # 关系盘点统计
        rel_total = relation_data.get('relationships_count', 0) if relation_data else 0
        rel_tables = relation_data.get('tables_count', 0) if relation_data else 0
        rel_cards = relation_data.get('cards_count', 0) if relation_data else 0
        stats = (relation_data.get('statistics') or {}) if relation_data else {}
        rel_high = stats.get('high_confidence_count', 0)
        rel_low = stats.get('low_confidence_count', 0)

        quality_failed_rows = sum(r.failed_count or 0 for r in results if r.status == 'failed')

        lines = ['## 二、质量概览', '']

        # 整体评分
        lines.append(f"| 整体指标 | 数值 |")
        lines.append(f"|----------|------|")
        lines.append(f"| 质量评分 | **{quality_score:.1f}** / 100 |")
        lines.append(f"| 质量评级 | {grade_emoji} {grade} |")
        lines.append('')

        # 三大模块概览
        lines.append(f"| 模块 | 核心指标 | 详情 |")
        lines.append(f"|------|----------|------|")

        if basic_tables:
            lines.append(
                f"| 基础空值检测 | "
                f"扫描 {len(basic_tables)} 张表，{len(basic_all_cols)} 个列 | "
                f"有缺失列 {len(basic_problem)}，空值 {basic_null}，空字符串 {basic_empty} |"
            )
        else:
            lines.append(f"| 基础空值检测 | 未包含 | - |")

        if quality_audit.get('results'):
            lines.append(
                f"| 规则库质检 | "
                f"执行 {quality_total} 条规则 | "
                f"通过 {quality_passed}，失败 {quality_failed}，错误 {quality_errors} |"
            )
        else:
            lines.append(f"| 规则库质检 | 未包含 | - |")

        if rel_total > 0:
            lines.append(
                f"| 表关系盘点 | "
                f"发现 {rel_total} 个关系，涉及 {rel_tables} 张表 | "
                f"高置信度 {rel_high}，低置信度 {rel_low}，卡片 {rel_cards} 张 |"
            )
        else:
            lines.append(f"| 表关系盘点 | 未包含 | - |")

        lines.append('')

        # 规则库质检汇总
        lines.append(f"| 规则库质检 | 数值 |")
        lines.append(f"|--------------|------|")
        lines.append(f"| 执行规则数 | {quality_total} 条 |")
        lines.append(f"| 通过 | ✅ {quality_passed} 条 |")
        lines.append(f"| 失败 | ❌ {quality_failed} 条 |")
        lines.append(f"| 执行错误 | ⚠️ {quality_errors} 条 |")
        lines.append(f"| 影响行数 | ⚠️ {quality_failed_rows} 条 |")

        return '\n'.join(lines)

    def _build_basic_audit_by_table(self, basic_audit: Dict[str, Any]) -> str:
        """基础空值检测结果——以表为单位展示每张表所有列的检测结果"""
        tables = basic_audit.get('tables', [])
        if not tables:
            return ''

        lines = ['## 三、基础空值检测结果', '']

        for tbl in tables:
            table_name = tbl.get('table', 'N/A')
            db_type = tbl.get('db_type', 'N/A')
            schema = tbl.get('schema', '')
            report_cols = tbl.get('report', [])

            if not report_cols:
                continue

            # 表级统计
            total_rows = report_cols[0].get('total_rows', 0) if report_cols else 0
            table_null = sum(c.get('null_count', 0) for c in report_cols)
            table_empty = sum(c.get('empty_str_count', 0) for c in report_cols)
            table_missing = sum(c.get('missing_count', 0) for c in report_cols)
            problem_cols = [c for c in report_cols if c.get('missing_pct', 0) > 0]
            max_pct = max((c.get('missing_pct', 0) for c in report_cols), default=0)

            # 表头
            lines.append(f"### {table_name}")
            lines.append('')
            lines.append(f"**表信息：** `{schema}.{table_name}` | 数据库类型：`{db_type}` | 总行数：`{total_rows}`")
            lines.append('')
            lines.append(f"| 列名 | 数据类型 | 总行数 | 空值数 | 空字符串 | 缺失率 |")
            lines.append(f"|------|----------|--------|--------|----------|--------|")

            # 按缺失率降序排列
            sorted_cols = sorted(report_cols, key=lambda x: x.get('missing_pct', 0), reverse=True)
            for c in sorted_cols:
                pct = c.get('missing_pct', 0)
                pct_str = f"{pct:.2f}%" if pct > 0 else "0.00%"
                emoji = '🔴' if pct >= 20 else ('🟡' if pct > 0 else '✅')
                lines.append(
                    f"| {emoji} {c.get('column_name', 'N/A')} | {c.get('data_type', 'N/A')} | "
                    f"{c.get('total_rows', 0)} | {c.get('null_count', 0)} | "
                    f"{c.get('empty_str_count', 0)} | {pct_str} |"
                )

            lines.append(
                f"\n**表级汇总：** 空值 {table_null}，空字符串 {table_empty}，总缺失 {table_missing}，最高缺失率 {max_pct:.2f}%"
            )
            if problem_cols:
                prob_strs = [f"{c.get('column_name')}={c.get('missing_pct', 0):.1f}%" for c in problem_cols[:3]]
                lines.append(f"（{'、'.join(prob_strs)}）")
            lines.append('')

        return '\n'.join(lines)

    def _build_relation_discovery_full(self, relation_data: Dict[str, Any]) -> str:
        """表关系发现结果——完整关系信息 + 关系卡片详情"""
        if not relation_data or relation_data.get('relationships_count', 0) == 0:
            return ''

        stats = relation_data.get('statistics') or {}
        rel_total = relation_data.get('relationships_count', 0)
        rel_tables = relation_data.get('tables_count', 0)
        rel_cards = relation_data.get('cards_count', 0)
        relationships = relation_data.get('relationships', [])
        cards = relation_data.get('cards', [])

        # 关系类型映射
        rel_type_names = self.RELATIONSHIP_TYPE_NAMES
        card_names = self.CARDINALITY_NAMES

        lines = ['## 四、表关系发现结果', '']

        # 统计概览
        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 发现关系总数 | {rel_total} |")
        lines.append(f"| 涉及表数 | {rel_tables} |")
        lines.append(f"| 生成关系卡片数 | {rel_cards} |")
        lines.append('')

        # 关系类型分布
        rel_types = stats.get('relationship_types', {})
        if rel_types:
            lines.append(f"| 关系类型 | 数量 |")
            lines.append(f"|----------|------|")
            for rtype, count in rel_types.items():
                rtype_name = rel_type_names.get(rtype, rtype)
                lines.append(f"| {rtype_name}（{rtype}） | {count} |")
            lines.append('')

        # 基数分布
        card_dist = stats.get('cardinality_distribution', {})
        if card_dist:
            lines.append(f"| 基数类型 | 数量 |")
            lines.append(f"|----------|------|")
            for cardinality, count in card_dist.items():
                card_name = card_names.get(cardinality, cardinality)
                lines.append(f"| {card_name}（{cardinality}） | {count} |")
            lines.append('')

        # 置信度统计
        avg_conf = stats.get('avg_confidence', 0)
        high_conf = stats.get('high_confidence_count', 0)
        low_conf = stats.get('low_confidence_count', 0)
        lines.append(f"| 置信度指标 | 数值 |")
        lines.append(f"|------------|------|")
        lines.append(f"| 平均置信度 | {avg_conf:.4f} |")
        lines.append(f"| 高置信度（≥0.8） | {high_conf} 个 |")
        lines.append(f"| 低置信度（<0.8） | {low_conf} 个 |")
        lines.append('')

        # 关系明细（展示所有）
        if relationships:
            lines.append(f"### 关系明细（共 {len(relationships)} 个）")
            lines.append('')
            lines.append(f"| # | 源表 | 源列 | → | 目标表 | 目标列 | 类型 | 基数 | 置信度 | 推断原因 |")
            lines.append(f"|---|------|------|---|--------|------|------|------|--------|----------|")
            for i, rel in enumerate(relationships, 1):
                rtype = rel.get('relationship_type', 'N/A')
                rtype_name = rel_type_names.get(rtype, rtype)
                card = rel.get('cardinality', 'N/A')
                card_name = card_names.get(card, card)
                conf = rel.get('confidence', 0)
                conf_str = f"{conf:.2f}"
                reasoning = rel.get('reasoning', '') or ''
                # 推断原因列：Markdown表格中|符号需要转义
                reasoning_cell = reasoning.replace('|', '\\|').replace('\n', ' ')

                lines.append(
                    f"| {i} | `{rel.get('from_table', 'N/A')}` | `{rel.get('from_column', 'N/A')}` | → "
                    f"| `{rel.get('to_table', 'N/A')}` | `{rel.get('to_column', 'N/A')}` | "
                    f"{rtype_name} | {card_name} | {conf_str} | {reasoning_cell} |"
                )

            lines.append('')

        # 关系卡片详情（展示前 3 张）
        if cards:
            lines.append(f"### 关系卡片（共 {len(cards)} 张，展示前 3 张）")
            lines.append('')
            for card in cards[:3]:
                doc_info = card.get('DocInfo', {})
                table_info = card.get('TableInfo', {})
                rels_in_card = card.get('Relationships', [])
                fusion = card.get('FusionHints') or {}
                join_summary = card.get('JoinSummary', '')
                card_stats = card.get('Statistics') or {}

                title = doc_info.get('title', 'N/A')
                table_name = doc_info.get('table_name', 'N/A')
                fields_count = table_info.get('fields_count', 0)
                primary_key = table_info.get('primary_key', 'N/A')
                related_count = card_stats.get('related_tables_count', 0)
                avg_conf_card = card_stats.get('avg_confidence', 0)

                lines.append(f"#### {title}")
                lines.append('')
                lines.append(
                    f"**表信息：** `{table_name}` | 字段数 {fields_count} | 主键 `{primary_key}` | "
                    f"关联表 {related_count} 张 | 平均置信度 {avg_conf_card:.2f}"
                )
                if join_summary:
                    lines.append(f"\n{join_summary}")
                lines.append('')

                if rels_in_card:
                    lines.append(f"| 关联表 | 关系类型 | 基数 | 置信度 | 关联字段 |")
                    lines.append(f"|--------|----------|------|--------|----------|")
                    for rel in rels_in_card:
                        join_fields = rel.get('join_fields', [])
                        fields_str = '、'.join(
                            f"`{jf.get('local_field','?')}`→`{jf.get('remote_field','?')}`"
                            for jf in join_fields
                        ) if join_fields else '-'
                        rtype = rel.get('relationship_type', 'N/A')
                        card2 = rel.get('cardinality', 'N/A')
                        lines.append(
                            f"| `{rel.get('related_table', 'N/A')}` | "
                            f"{rel_type_names.get(rtype, rtype)} | "
                            f"{card_names.get(card2, card2)} | "
                            f"{rel.get('confidence', 0):.2f} | {fields_str} |"
                        )
                    lines.append('')

                fusion_as_master = fusion.get('as_master', []) if fusion else []
                if fusion_as_master:
                    lines.append(f"**融合建议（作为主表）：**")
                    for hint in fusion_as_master[:2]:
                        lines.append(f"- {hint}")
                    lines.append('')

        return '\n'.join(lines)

    def _build_execution_detail(
        self,
        report: GovernanceReport,
        results: List[RuleExecutionResult],
        has_rel: bool,
        has_basic: bool,
    ) -> str:
        if has_basic and has_rel:
            sec_detail, sec_fail = '五', '六'
        elif has_basic or has_rel:
            sec_detail, sec_fail = '四', '五'
        else:
            sec_detail, sec_fail = '三', '四'

        lines = [f"## {sec_detail}、执行明细（基于规则库）", '']

        lines.append('| 规则名称 | 目标表 | 目标列 | 规则类型 | 严重级别 | 状态 | 失败率 | 失败/总数 |')
        lines.append('|----------|--------|--------|----------|----------|------|--------|----------|')

        for r in results:
            status_emoji = {'passed': '✅', 'failed': '❌', 'error': '⚠️'}.get(r.status, '❓')
            status_txt = self.STATUS_NAMES.get(r.status, r.status or 'N/A')
            severity_txt = self.SEVERITY_NAMES.get(r.severity, r.severity or 'N/A')
            type_txt = self.RULE_TYPE_NAMES.get(r.rule_type, r.rule_type or 'N/A')
            rate = f"{float(r.failed_rate):.2f}%" if r.failed_rate is not None else 'N/A'
            failed = r.failed_count or 0
            total = r.total_count or 0

            lines.append(
                f"| {r.rule_name or 'N/A'} | {r.table_name or 'N/A'} | {r.column_name or 'N/A'} | "
                f"{type_txt} | {severity_txt} | {status_emoji} {status_txt} | {rate} | {failed}/{total} |"
            )

        return '\n'.join(lines)

    def _has_relation_discovery(self, report: GovernanceReport) -> bool:
        details = getattr(report, 'details', None)
        if not details or not isinstance(details, dict):
            return False
        rd = details.get('relation_discovery')
        return bool(rd and rd.get('relationships_count', 0) > 0)

    def _build_failed_samples(self, results: List[RuleExecutionResult], has_rel: bool, has_basic: bool) -> str:
        """失败样本明细板块

        适配新版 _get_sample_data 的样本结构：
        - 单列规则：sample_value 是单值（值或字符串）
        - 多列规则（composite）：sample_value 是 dict，violated_column 是逗号分隔字符串

        注意：为保持章节编号连续，即使没有失败样本也输出章节标题，
        内容提示"本次检测无失败样本"。
        """
        if has_basic and has_rel:
            sec_fail = '六'
        elif has_basic or has_rel:
            sec_fail = '五'
        else:
            sec_fail = '四'

        failed_results = [r for r in results if r.status == 'failed' and r.failed_samples]
        if not failed_results:
            # 即使没有失败样本也输出章节标题，保持编号连续
            return f"""## {sec_fail}、失败样本明细

> 本次检测无失败样本，数据质量符合规则要求。

"""

        lines = [f'## {sec_fail}、失败样本明细', '']
        lines.append(
            '> 本章节展示每个失败规则的具体违反样本（最多展示前 20 条，'
            '实际采集样本数 = `failed_count` 中的前 20 条）。'
        )
        lines.append('')

        # 展示数量：失败规则超过 10 个时只展示前 10 个规则，样本数 20
        max_rules_shown = 10
        max_samples_per_rule = 20

        for r in failed_results[:max_rules_shown]:
            rate = f"{float(r.failed_rate or 0):.2f}%"
            lines.append(f"### {r.rule_name or 'N/A'}")
            lines.append('')
            lines.append(f"- **表**: `{r.table_name or 'N/A'}`")
            lines.append(f"- **列**: `{r.column_name or 'N/A'}`")
            lines.append(f"- **状态**: ❌ 失败  |  **失败率**: {rate}  |  **失败数**: {r.failed_count or 0} 条")

            samples = r.failed_samples
            if isinstance(samples, str):
                try:
                    samples = json.loads(samples)
                except Exception:
                    samples = []

            if samples:
                # 收集所有样本对象中的违规记录
                all_records = []
                for s in samples:
                    if isinstance(s, dict):
                        records = self._extract_sample_records(s)
                        all_records.extend(records)

                total_violated_records = len(all_records)
                lines.append('')
                lines.append(f'**失败样本（前 {min(total_violated_records, max_samples_per_rule)} 条 / 共 {total_violated_records} 条）：**')
                lines.append('')

                # 合并所有记录到一个表格中显示
                if all_records:
                    # 只展示前 max_samples_per_rule 条
                    records_to_show = all_records[:max_samples_per_rule]
                    table_lines = self._build_sample_records_table(records_to_show)
                    lines.extend(table_lines)
                    lines.append('')

            lines.append('')

        return '\n'.join(lines)

    def _extract_sample_records(self, s: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从一条失败样本中抽取违规记录列表

        适配不同历史结构：
        - 新版结构：s['sample_value'] 是 list[dict]，每项是一条完整数据库记录
        - 旧版结构：s['sample_value'] 是 dict（单条记录）或 单值
        """
        sv = s.get('sample_value', '')
        if isinstance(sv, list):
            records = [r for r in sv if isinstance(r, dict)]
            return records
        if isinstance(sv, dict):
            return [sv]
        # 单值场景（单列规则 + 历史格式）：包装成单条记录
        return [{'样本值': sv}]

    def _build_sample_records_table(
        self, records: List[Dict[str, Any]]
    ) -> List[str]:
        """把多条违规记录渲染成 Markdown 表格（包含表头、分隔行与每条数据）

        - 表头：来自全部记录的字段名并集（按首次出现顺序，去重）
        - 单元格：值为 None → NULL；dict/list → JSON；其余 → 字符串
        """
        if not records:
            return []

        # 合并所有记录的字段名（按首次出现顺序）
        columns: List[str] = []
        seen = set()
        for r in records:
            for k in r.keys():
                if k not in seen:
                    seen.add(k)
                    columns.append(k)

        lines: List[str] = []
        lines.append('| ' + ' | '.join(columns) + ' |')
        lines.append('| ' + ' | '.join(['---'] * len(columns)) + ' |')

        for r in records:
            row_cells = []
            for col in columns:
                val = r.get(col, '')
                if isinstance(val, dict):
                    cell = '`' + json.dumps(val, ensure_ascii=False) + '`'
                elif isinstance(val, list):
                    cell = '`' + json.dumps(val, ensure_ascii=False) + '`'
                elif val is None:
                    cell = 'NULL'
                else:
                    cell = str(val).replace('|', '\\|').replace('\n', ' ')
                row_cells.append(cell)
            lines.append('| ' + ' | '.join(row_cells) + ' |')

        return lines

    def _generate_llm_summary(
        self,
        report: GovernanceReport,
        results: List[RuleExecutionResult],
        exec_resp: Dict[str, Any],
    ) -> Optional[str]:
        """调用 LLM 生成各模块总结——使用分块模式逐部分生成

        优先使用分块模式，每个板块独立调用 LLM 生成内容，然后组装。
        这样可以避免上下文超限，也便于追踪每个板块的生成状态。
        """
        try:
            from controllers.governance.report_summary_llm import generate_report_chunks
            print(f"[Markdown-Exporter] 开始调用 LLM 生成各模块总结（并行分块模式）...")
            chunks = generate_report_chunks(report, exec_resp)
            print(f"[Markdown-Exporter] LLM 总结分块生成完成")
            return self._assemble_chunks(chunks)
        except Exception as e:
            print(f"[Markdown-Exporter] ⚠️ 分块模式 LLM 生成失败: {e}，尝试整体模式...")
            try:
                from controllers.governance.report_summary_llm import generate_report_summary_from_response
                summary = generate_report_summary_from_response(report, exec_resp)
                print(f"[Markdown-Exporter] 整体模式 LLM 总结生成成功 | chars={len(summary)}")
                return summary
            except Exception as e2:
                print(f"[Markdown-Exporter] ⚠️ 整体模式也失败: {e2}，将跳过总结章节")
                return None

    def _generate_overall_summary(
        self,
        report: GovernanceReport,
        results: List[RuleExecutionResult],
        exec_resp: Dict[str, Any],
    ) -> Optional[str]:
        """调用 LLM 生成综合总结——基于各模块检测结果的跨模块综合分析"""
        try:
            from controllers.governance.report_summary_llm import generate_overall_summary
            print(f"[Markdown-Exporter] 开始调用 LLM 生成综合总结...")
            summary = generate_overall_summary(report, exec_resp)
            print(f"[Markdown-Exporter] 综合总结生成完成 | chars={len(summary) if summary else 0}")
            return summary
        except Exception as e:
            print(f"[Markdown-Exporter] ⚠️ 综合总结生成失败: {e}，将跳过该章节")
            return None

    def _assemble_chunks(self, chunks: Dict[str, Optional[str]]) -> str:
        """将分块内容组装成完整总结

        各模块提示词已包含完整章节结构（包含 ### 标题），
        此处仅做简单拼接。
        """
        sections = []

        if chunks.get('basic_audit'):
            sections.append(chunks['basic_audit'])

        if chunks.get('relation_discovery'):
            sections.append(chunks['relation_discovery'])

        if chunks.get('quality_audit'):
            sections.append(chunks['quality_audit'])

        if not sections:
            return "（本次检测未发现明显数据质量问题）"

        return '\n\n---\n\n'.join(sections)

    def _build_llm_summary_section(self, llm_summary: Optional[str], has_rel: bool, has_basic: bool) -> str:
        if has_basic and has_rel:
            sec_llm = '七'
        elif has_basic or has_rel:
            sec_llm = '六'
        else:
            sec_llm = '五'

        if not llm_summary:
            return f"""## {sec_llm}、智能总结

> LLM 总结生成失败（可能原因：LLM 服务暂时不可用），已记录基础统计数据供您参考。

"""
        return f"""## {sec_llm}、智能总结

{llm_summary}

"""

    def _build_overall_summary_section(self, overall_summary: Optional[str], has_rel: bool, has_basic: bool) -> str:
        """构建综合总结章节

        章节编号：LLM智能总结之后，改进建议之前
        - 有关系 + 有基础：八
        - 仅基础 或 仅关系：七
        - 都没有：六

        注意：为保持章节编号连续，即使生成失败也输出章节标题。
        """
        if has_basic and has_rel:
            sec_overall = '八'
        elif has_basic or has_rel:
            sec_overall = '七'
        else:
            sec_overall = '六'

        if not overall_summary:
            # 即使生成失败也输出章节标题，保持编号连续
            return f"""## {sec_overall}、综合总结与改进建议

> 综合总结生成失败（可能原因：LLM 服务暂时不可用），已记录各模块分析供您参考。

"""

        # 综合总结的内容已经包含 ## 一级标题，直接在其前添加章节编号
        # 如果内容不是以 ## 开头，则添加章节标题
        if overall_summary.strip().startswith('##'):
            return overall_summary
        else:
            return f"## {sec_overall}、综合总结与改进建议\n\n{overall_summary}"

    def _build_recommendations(self, results: List[RuleExecutionResult], has_rel: bool, has_basic: bool) -> str:
        """构建改进建议章节

        章节编号计算：
        - 一、基本信息
        - 二、质量概览
        - 三、基础空值检测结果（条件）
        - 四、表关系发现结果（条件）
        - 四/五、执行明细（基于规则库）
        - 五/六、失败样本明细
        - 六/七、智能总结
        - 七/八、综合总结与改进建议（新增）
        - 八/九、改进建议（最终章节）

        最终章节编号 = 7（固定前6章 + LLM总结）+ 1（综合总结）+ 1 = 8/9
        """
        # 章节编号：基于前序章节数量 + 1
        # 前序章节：基本信息和质量概览（2）+ 条件章节 + 执行明细 + 失败样本 + LLM总结 + 综合总结
        base_num = 8  # 综合总结后面是第8章（如果综合总结生成成功）

        failed_results = [r for r in results if r.status == 'failed']

        if not failed_results:
            return f"""## {base_num}、改进建议

✅ **数据质量良好，未发现问题，建议继续保持当前的数据管理规范。**
"""

        by_type = {}
        for r in failed_results:
            rt = r.rule_type or 'unknown'
            if rt not in by_type:
                by_type[rt] = []
            by_type[rt].append(r)

        priority = [
            ('null_check', '空值问题'),
            ('unique', '唯一性问题'),
            ('format', '格式问题'),
            ('threshold', '阈值问题'),
            ('enum', '枚举问题'),
            ('custom_sql', '自定义规则问题'),
        ]

        lines = [f'## {base_num}、改进建议', '']

        for rule_type, label in priority:
            if rule_type not in by_type:
                continue
            items = by_type[rule_type]
            tables = list(set(r.table_name for r in items if r.table_name))
            total_rows = sum(r.failed_count or 0 for r in items)
            tbl_list = ', '.join(tables[:3])
            if len(tables) > 3:
                tbl_list += f' 等{len(tables)}个表'

            advice_map = {
                'null_check': f'发现 {len(items)} 个字段存在空值，共 {total_rows} 条记录，建议检查 {tbl_list} 等表的数据录入流程，确保必填字段有值。',
                'unique': f'发现 {len(items)} 个字段存在重复值，共 {total_rows} 条重复记录，建议对 {tbl_list} 等表进行去重处理。',
                'format': f'发现 {len(items)} 个字段存在格式不规范问题，建议统一 {tbl_list} 等表的字段录入格式标准。',
                'threshold': f'发现 {len(items)} 个字段存在超出阈值范围的数据，建议检查 {tbl_list} 等表数据来源的合法性。',
                'enum': f'发现 {len(items)} 个字段存在非法枚举值，建议规范 {tbl_list} 等表的数据取值范围。',
                'custom_sql': f'发现 {len(items)} 条自定义规则检测失败，建议检查对应的 SQL 条件是否需要调整。',
            }

            lines.append(f"### {label}")
            lines.append('')
            lines.append(f"{advice_map.get(rule_type, '建议进行检查和修复。')}")
            lines.append('')

        return '\n'.join(lines)

    def _build_footer(self, report: GovernanceReport) -> str:
        report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f"""---

*本报告由 OntiCards AI数据中枢 自动生成*
*报告生成时间: {report_time}*
"""


def export_markdown_report(
    report: GovernanceReport,
    results: List[RuleExecutionResult],
    include_llm_summary: bool = True,
    user_id: str = None,
) -> Dict[str, Any]:
    """便捷函数：导出 Markdown 报告

    Args:
        report: 报告对象
        results: 规则执行结果列表
        include_llm_summary: 是否包含 LLM 总结
        user_id: 用户ID，用于按用户分组存储报告文件
    """
    exporter = MarkdownExporter(user_id=user_id)
    return exporter.export(report, results, include_llm_summary=include_llm_summary)
