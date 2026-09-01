# -*- coding:utf-8 -*-
"""
@File: report_summary_llm.py
@Description: 报告 LLM 总结生成器 - 基于质检结果调用大模型生成总结描述
@Author: 韩小豪 849631113@qq.com
@Create: 2026-07-07
"""

import os
import json
from typing import Dict, Any, List, Optional

from models.governance_report import GovernanceReport
from models.rule_execution_result import RuleExecutionResult


class ReportSummaryLLM:
    """基于 LLM 的报告总结生成器

    接收三个模块的质检结果，注入提示词模板，调用大模型生成结构化总结描述。
    """

    PROMPT_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'libs', 'prompt', 'governance', 'report_summary_prompt.txt'
    )

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

    def __init__(self):
        self._prompt_template = None

    @property
    def prompt_template(self) -> str:
        """惰性加载提示词模板（优先从数据库读取）"""
        if self._prompt_template is None:
            # 优先从数据库加载（需要应用上下文）
            try:
                from flask import has_app_context
                if has_app_context():
                    from models.prompt_config import prompt_manager
                    content = prompt_manager.get_prompt("report_summary_prompt.txt", use_cache=True)
                    if content:
                        self._prompt_template = content
                        return self._prompt_template
                else:
                    print(f"[WARN] 当前无应用上下文，report_summary_prompt.txt 跳过数据库加载")
            except Exception as e:
                print(f"[WARN] 从数据库加载 report_summary_prompt.txt 失败: {str(e)}")

            # 回退到文件读取（reports_generate 目录）
            from pathlib import Path
            prompt_file = Path(__file__).resolve().parent.parent.parent / "libs" / "prompt" / "governance" / "reports_generate" / "report_summary_prompt.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    self._prompt_template = f.read()
            else:
                raise FileNotFoundError(
                    f"提示词模板未找到: {prompt_file}，"
                    "请确保 libs/prompt/governance/reports_generate/report_summary_prompt.txt 存在。"
                )
        return self._prompt_template

    def _build_basic_audit_section(self, report: GovernanceReport) -> str:
        """构建基础空值检测章节

        数据源：report.details['basic_audit']（完整表级空值检测数据）
        格式: {"tables_count": int, "tables": [{db_type, database, schema, table, report: [{col_info}]}]}
        """
        details = getattr(report, 'details', None) or {}
        basic_audit = details.get('basic_audit')

        if not basic_audit or not basic_audit.get('tables'):
            return "（本次未包含基础空值检测模块）"

        tables = basic_audit.get('tables', [])
        all_columns = []
        table_map = {}
        for tbl in tables:
            table_name = tbl.get('table', 'N/A')
            table_map[table_name] = tbl
            for col in tbl.get('report', []):
                col_copy = dict(col)
                col_copy['_table'] = table_name
                all_columns.append(col_copy)

        total_rows_all = sum(c.get('total_rows', 0) for c in all_columns)
        total_null = sum(c.get('null_count', 0) for c in all_columns)
        total_empty = sum(c.get('empty_str_count', 0) for c in all_columns)
        total_missing = sum(c.get('missing_count', 0) for c in all_columns)

        # 有问题的列（missing_pct > 0）
        problem_cols = sorted(
            [c for c in all_columns if c.get('missing_pct', 0) > 0],
            key=lambda x: x.get('missing_pct', 0),
            reverse=True
        )

        lines = [
            f"共检测 {len(tables)} 张表的 {len(all_columns)} 个字段，"
            f"其中空值 {total_null} 条，空字符串 {total_empty} 条，"
            f"总缺失 {total_missing} 条（占 {total_rows_all} 行的 "
            f"{total_missing / total_rows_all * 100:.2f}%）。"
        ]

        if problem_cols:
            top_issues = problem_cols[:5]
            lines.append("\n存在空值问题的字段（按缺失率排序）：")
            for c in top_issues:
                rate = c.get('missing_pct', 0)
                lines.append(
                    f"  - {c.get('_table', 'N/A')}.{c.get('column_name', 'N/A')}: "
                    f"缺失率 {rate:.2f}%，空值 {c.get('null_count', 0)} 条，"
                    f"空字符串 {c.get('empty_str_count', 0)} 条"
                )

        return '\n'.join(lines)

    def _build_relation_discovery_section(
        self, report: GovernanceReport
    ) -> str:
        """构建关系盘点章节"""
        details = getattr(report, 'details', None)
        if not details or not isinstance(details, dict):
            rd = details
        else:
            rd = details.get('relation_discovery')

        if not rd:
            return "（本次未包含关系盘点模块）"

        rel_count = rd.get('relationships_count', 0)
        tables_count = rd.get('tables_count', 0)
        cards_count = rd.get('cards_count', 0)
        cross_source = rd.get('cross_source_count', 0)
        is_multi = rd.get('is_multi_source', False)
        stats = rd.get('statistics', {}) or {}

        lines = [
            f"共发现 {rel_count} 个表关系，涉及 {tables_count} 张表，"
            f"生成 {cards_count} 张关系卡片。"
        ]

        if is_multi:
            lines.append(f"其中包含 {cross_source} 个跨数据源关系。")

        if stats:
            stat_lines = [f"\n关系类型分布："]
            for key, val in stats.items():
                if isinstance(val, dict):
                    stat_lines.append(f"  - {key}: {val.get('count', 0)} 条")
                else:
                    stat_lines.append(f"  - {key}: {val}")
            lines.append('\n'.join(stat_lines))

        return '\n'.join(lines)

    def _build_rule_execution_section(
        self, results: List[RuleExecutionResult]
    ) -> str:
        """构建规则校验章节"""
        rule_results = [
            r for r in results
            if r.rule_type not in ('null_check', 'table_stats')
        ]
        if not rule_results:
            return "（本次未包含基于规则库的校验）"

        passed = [r for r in rule_results if r.status == 'passed']
        failed = [r for r in rule_results if r.status == 'failed']
        errors = [r for r in rule_results if r.status == 'error']
        total_rows = sum(r.failed_count or 0 for r in failed)

        lines = [
            f"共执行 {len(rule_results)} 条规则，"
            f"通过 {len(passed)} 条，失败 {len(failed)} 条，"
            f"错误 {len(errors)} 条，累计影响 {total_rows} 条记录。"
        ]

        if failed:
            by_type = {}
            for r in failed:
                rt = r.rule_type or 'unknown'
                if rt not in by_type:
                    by_type[rt] = []
                by_type[rt].append(r)

            lines.append("\n失败规则分布（按类型）：")
            for rule_type, items in sorted(
                by_type.items(),
                key=lambda x: sum(r.failed_count or 0 for r in x[1]),
                reverse=True
            ):
                type_name = self.RULE_TYPE_NAMES.get(rule_type, rule_type)
                rows = sum(r.failed_count or 0 for r in items)
                tables = list(set(r.table_name for r in items if r.table_name))
                lines.append(
                    f"  - {type_name}: {len(items)} 条规则失败，"
                    f"涉及 {rows} 条记录，受影响表: {', '.join(tables[:3])}"
                    + (f" 等{len(tables)}个表" if len(tables) > 3 else "")
                )

            top_issues = sorted(
                failed, key=lambda x: x.failed_rate or 0, reverse=True
            )[:5]
            lines.append("\n失败率最高的规则：")
            for r in top_issues:
                rate = f"{float(r.failed_rate):.2f}%" if r.failed_rate is not None else "N/A"
                lines.append(
                    f"  - {r.rule_name} ({r.table_name}.{r.column_name}): "
                    f"失败率 {rate}"
                )

        return '\n'.join(lines)

    def _call_llm(self, prompt: str) -> str:
        """调用大模型生成总结

        Returns:
            LLM 生成的总结文本
        """
        try:
            from controllers.agents.qwen.QwenMaxLatest import qian_wen_llm_with_usage
        except ImportError:
            raise ImportError(
                "LLM 调用失败：请确保 controllers.agents.qwen.QwenMaxLatest 可用。"
            )

        content, _ = qian_wen_llm_with_usage(prompt, stream_type=False)
        if not content:
            raise RuntimeError("LLM 返回内容为空")

        return content.strip()

    def generate_summary(
        self,
        report: GovernanceReport,
        results: List[RuleExecutionResult],
        timeout: int = 60,
    ) -> str:
        """生成报告总结描述

        Args:
            report: 报告对象
            results: 规则执行结果列表
            timeout: LLM 调用超时时间（秒），默认 60

        Returns:
            LLM 生成的 Markdown 格式总结文本
        """
        quality_score = float(report.quality_score) if report.quality_score else 0
        grade = report.grade or '一般'
        execution_time = (
            report.execution_time.strftime('%Y-%m-%d %H:%M:%S')
            if report.execution_time else 'N/A'
        )
        scope_tables = (
            ', '.join(report.scope_tables)
            if report.scope_tables else '全部表'
        )
        datasource_id = (
            str(report.datasource_id) if report.datasource_id else 'N/A'
        )

        null_section = self._build_basic_audit_section(report)
        relation_section = self._build_relation_discovery_section(report)
        rule_section = self._build_rule_execution_section(results)

        prompt = self.prompt_template.format(
            report_name=report.report_name or '数据治理质量报告',
            quality_score=f"{quality_score:.1f}",
            grade=grade,
            execution_time=execution_time,
            scope_tables=scope_tables,
            datasource_id=datasource_id,
            null_check_section=null_section,
            relation_discovery_section=relation_section,
            rule_execution_section=rule_section,
        )

        return self._call_llm(prompt)


def generate_report_summary(
    report: GovernanceReport,
    results: List[RuleExecutionResult],
    timeout: int = 60,
) -> str:
    """便捷函数：生成报告总结

    Args:
        report: 报告对象
        results: 规则执行结果列表
        timeout: LLM 调用超时时间

    Returns:
        LLM 生成的 Markdown 格式总结文本
    """
    generator = ReportSummaryLLM()
    return generator.generate_summary(report, results, timeout=timeout)


def _load_prompt_template(template_name: str, force_file: bool = False) -> str:
    """加载提示词模板

    Args:
        template_name: 模板文件名
        force_file: 是否强制从文件读取（用于子线程中避免上下文问题）

    Returns:
        提示词模板内容
    """
    # reports_generate 目录下的提示词文件
    reports_generate_templates = [
        "report_basic_audit_chunk.txt",
        "report_relation_chunk.txt",
        "report_quality_chunk.txt",
        "report_overall_summary_chunk.txt",
        "report_summary_prompt.txt",
        "report_dynamic_prompt.txt",
        "report_chunk_prompt.txt",
    ]

    # 构建文件路径
    from pathlib import Path
    if template_name in reports_generate_templates:
        prompt_file = Path(__file__).resolve().parent.parent.parent / "libs" / "prompt" / "governance" / "reports_generate" / template_name
    else:
        prompt_file = Path(__file__).resolve().parent.parent.parent / "libs" / "prompt" / "governance" / template_name

    # 如果强制从文件读取或无应用上下文，直接读文件
    if force_file:
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        raise FileNotFoundError(f"提示词模板未找到: {prompt_file}")

    # 优先尝试从数据库加载（需要应用上下文）
    try:
        from flask import has_app_context
        if has_app_context():
            from models.prompt_config import prompt_manager
            content = prompt_manager.get_prompt(template_name, use_cache=True)
            if content:
                return content
        else:
            print(f"[WARN] 当前无应用上下文，{template_name} 跳过数据库加载")
    except Exception as e:
        print(f"[WARN] 从数据库加载 {template_name} 失败: {str(e)}")

    # 回退到文件读取
    if prompt_file.exists():
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()

    raise FileNotFoundError(f"提示词模板未找到: {prompt_file}")


def _sanitize_for_llm(
    data: Any,
    max_str_len: int = 300,
    max_items: int = 30,
    _depth: int = 0,
) -> Any:
    """对 execution_response JSON 进行容量管理，避免 LLM 输入 token 超出限制

    保留策略（关键证据完整保留）：
    - failed_samples 失败样本：保留全部（最关键的诊断证据）
    - executed_sql_text 执行 SQL：保留全部（规则定义的核心证据）
    - join_suggestion / fusion_suggestion：保留全部（含 SQL 提示词与业务关系描述）
    - relationships / cards：保留全部（关系盘点是报告核心板块）
    - quality_audit.results / basic_audit.tables：保留全部（两个核心质检板块）
    - evidence / reasoning：压缩到 200 字符内（保留语义要点）

    截断策略（防止 token 爆炸）：
    - 超长字符串按 max_str_len 截断
    - 超大数组保留前 max_items 项，超出部分标注数量
    """
    # 保护性深度限制，避免极端嵌套结构导致栈溢出
    if _depth > 12:
        return "<数据嵌套层级过深，已省略>"

    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            # 这些字段全部保留（不裁剪、不截断）
            if k in ('failed_samples', 'executed_sql_text',
                     'join_suggestion', 'fusion_suggestion'):
                result[k] = v if isinstance(v, (list, dict)) else _sanitize_for_llm(
                    v, max_str_len, max_items, _depth + 1
                )
                continue
            # 长文本字段：限长
            if k in ('reasoning', 'evidence', 'sample_sql', 'description',
                     'reasoning_text', 'business_relation', 'FusionHints'):
                result[k] = _sanitize_for_llm(v, 200, max_items, _depth + 1)
                continue
            result[k] = _sanitize_for_llm(v, max_str_len, max_items, _depth + 1)
        return result
    elif isinstance(data, list):
        if len(data) > max_items:
            # 截断前 max_items 项，并在末尾添加提示
            truncated = [
                _sanitize_for_llm(item, max_str_len, max_items, _depth + 1)
                for item in data[:max_items]
            ]
            truncated.append(f"...（共 {len(data)} 项，已截断前 {max_items} 项）")
            return truncated
        return [
            _sanitize_for_llm(item, max_str_len, max_items, _depth + 1)
            for item in data
        ]
    elif isinstance(data, str):
        if len(data) > max_str_len:
            return data[:max_str_len] + '...（已截断）'
        return data
    else:
        return data


def _call_qwen_llm(prompt: str, model_config_dict: Dict[str, Any] = None) -> str:
    """调用 Qwen LLM 生成内容

    Args:
        prompt: 提示词
        model_config_dict: 模型配置字典（可选），用于避免子线程中访问数据库
            {
                "api_key": str,
                "api_url": str,
                "model_name": str,
                "timeout": int
            }
    """
    try:
        from controllers.agents.qwen.QwenMaxLatest import qian_wen_llm_with_usage
    except ImportError:
        raise ImportError("LLM 调用失败：请确保 controllers.agents.qwen.QwenMaxLatest 可用。")

    content, _ = qian_wen_llm_with_usage(prompt, stream_type=False, model_config_dict=model_config_dict)
    if not content:
        raise RuntimeError("LLM 返回内容为空")
    return content.strip()


def _generate_basic_audit_chunk(basic_audit_data: Dict[str, Any]) -> Optional[str]:
    """分块生成：基础空值检测板块分析

    Args:
        basic_audit_data: 基础空值检测数据，格式：
            {"tables_count": int, "tables": [{table, database, schema, report: [{col_info}]}]}

    Returns:
        生成的 Markdown 格式分析内容，如果数据为空则返回 None
    """
    tables = basic_audit_data.get('tables', []) if basic_audit_data else []
    if not tables:
        return None

    try:
        prompt_template = _load_prompt_template("report_basic_audit_chunk.txt")
    except FileNotFoundError:
        print("[WARN] 基础空值检测提示词模板未找到，跳过该板块生成")
        return None

    import json
    data_json = json.dumps(basic_audit_data, ensure_ascii=False, separators=(',', ':'))

    prompt = prompt_template.format(
        basic_audit_data=data_json,
    )

    try:
        content = _call_qwen_llm(prompt)
        print(f"[Chunk-Gen] 基础空值检测板块生成成功 | chars={len(content)}")
        return content
    except Exception as e:
        print(f"[Chunk-Gen] 基础空值检测板块生成失败: {e}")
        return None


def _generate_relation_chunk(relation_data: Dict[str, Any]) -> Optional[str]:
    """分块生成：关系发现板块分析

    Args:
        relation_data: 关系发现数据，格式：
            {"relationships_count": int, "tables_count": int, "cards_count": int,
             "relationships": [], "cards": [], "statistics": {}}

    Returns:
        生成的 Markdown 格式分析内容，如果数据为空则返回 None
    """
    if not relation_data or relation_data.get('relationships_count', 0) == 0:
        return None

    try:
        prompt_template = _load_prompt_template("report_relation_chunk.txt")
    except FileNotFoundError:
        print("[WARN] 关系发现提示词模板未找到，跳过该板块生成")
        return None

    import json
    data_json = json.dumps(relation_data, ensure_ascii=False, separators=(',', ':'))

    prompt = prompt_template.format(
        relation_data=data_json,
    )

    try:
        content = _call_qwen_llm(prompt)
        print(f"[Chunk-Gen] 关系发现板块生成成功 | chars={len(content)}")
        return content
    except Exception as e:
        print(f"[Chunk-Gen] 关系发现板块生成失败: {e}")
        return None


def _generate_quality_audit_chunk(quality_audit_data: Dict[str, Any]) -> Optional[str]:
    """分块生成：规则库质检板块分析

    Args:
        quality_audit_data: 规则库质检数据，格式：
            {"rules_count": int, "results": [{rule_name, rule_type, table_name, ...}]}

    Returns:
        生成的 Markdown 格式分析内容，如果数据为空则返回 None
    """
    results = quality_audit_data.get('results', []) if quality_audit_data else []
    if not results:
        return None

    try:
        prompt_template = _load_prompt_template("report_quality_chunk.txt")
    except FileNotFoundError:
        print("[WARN] 规则库质检提示词模板未找到，跳过该板块生成")
        return None

    import json
    data_json = json.dumps(quality_audit_data, ensure_ascii=False, separators=(',', ':'))

    prompt = prompt_template.format(
        quality_audit_data=data_json,
    )

    try:
        content = _call_qwen_llm(prompt)
        print(f"[Chunk-Gen] 规则库质检板块生成成功 | chars={len(content)}")
        return content
    except Exception as e:
        print(f"[Chunk-Gen] 规则库质检板块生成失败: {e}")
        return None


def _get_model_config_dict() -> Optional[Dict[str, Any]]:
    """获取模型配置字典（用于避免子线程中访问数据库）

    Returns:
        模型配置字典，包含 api_key, api_url, model_name, timeout
        如果获取失败则返回 None
    """
    try:
        from flask import has_app_context
        if not has_app_context():
            print("[WARN] 当前无应用上下文，无法获取模型配置")
            return None

        from models.model_config import Model_configuration
        model_config = Model_configuration.query.filter_by(model_class='base').first()

        if not model_config:
            print("[WARN] 未找到 model_class 为 'base' 的模型配置")
            return None

        return {
            "api_key": model_config.model_api_key,
            "api_url": model_config.url,
            "model_name": model_config.model_name,
            "timeout": getattr(model_config, 'timeout', 180),
        }
    except Exception as e:
        print(f"[WARN] 获取模型配置失败: {str(e)}")
        return None


def generate_report_chunks(
    report: GovernanceReport,
    exec_resp: Dict[str, Any],
) -> Dict[str, Optional[str]]:
    """分块生成报告各板块内容（并行模式）

    使用 ThreadPoolExecutor 并行调用三个 LLM 生成函数，
    显著提升生成速度。

    Args:
        report: 报告对象
        exec_resp: 执行接口完整返回值

    Returns:
        Dict[str, Optional[str]]，包含各板块生成的内容：
        {
            'basic_audit': str,      # 基础空值检测分析（可能为 None）
            'relation_discovery': str, # 关系发现分析（可能为 None）
            'quality_audit': str,    # 规则库质检分析（可能为 None）
        }
    """
    print(f"[Chunk-Gen] 开始并行分块生成报告 | report_id={report.id}")

    result = {
        'basic_audit': None,
        'relation_discovery': None,
        'quality_audit': None,
    }

    # 准备各模块数据
    basic_audit = exec_resp.get('basic_audit') or {}
    relation_data = exec_resp.get('relation_discovery') or {}
    quality_audit = exec_resp.get('quality_audit') or {}

    # 构建需要生成的任务列表
    tasks = []
    task_names = []

    # 在主线程中预先加载所有需要的提示词模板（避免子线程中访问数据库上下文问题）
    prompt_templates = {}
    template_files = {
        'basic_audit': 'report_basic_audit_chunk.txt',
        'relation_discovery': 'report_relation_chunk.txt',
        'quality_audit': 'report_quality_chunk.txt',
    }

    for key, template_name in template_files.items():
        try:
            prompt_templates[key] = _load_prompt_template(template_name)
            print(f"[Chunk-Gen] 加载提示词模板: {template_name}")
        except FileNotFoundError:
            print(f"[WARN] 提示词模板 {template_name} 未找到，跳过该板块生成")
            prompt_templates[key] = None

    if basic_audit and prompt_templates.get('basic_audit'):
        tasks.append(('basic_audit', basic_audit, prompt_templates['basic_audit']))
        task_names.append('基础空值检测')

    if relation_data and relation_data.get('relationships_count', 0) > 0 and prompt_templates.get('relation_discovery'):
        tasks.append(('relation_discovery', relation_data, prompt_templates['relation_discovery']))
        task_names.append('关系发现')

    if quality_audit and quality_audit.get('results') and prompt_templates.get('quality_audit'):
        tasks.append(('quality_audit', quality_audit, prompt_templates['quality_audit']))
        task_names.append('规则库质检')

    print(f"[Chunk-Gen] 待生成模块: {task_names}")

    if not tasks:
        print(f"[Chunk-Gen] 无需生成的模块，返回空结果")
        return result

    # 在主线程中预先获取模型配置（用于避免子线程中访问数据库）
    model_config_dict = _get_model_config_dict()
    if model_config_dict:
        print(f"[Chunk-Gen] 已获取模型配置: {model_config_dict.get('model_name')}")
    else:
        print(f"[Chunk-Gen] 未能获取模型配置，子线程中将尝试使用应用上下文")

    # 并行执行所有 LLM 调用
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    llm_call_lock = threading.Lock()

    def safe_call_gen(key, data, prompt_template):
        """安全的 LLM 调用包装器，带锁确保并发安全"""
        try:
            with llm_call_lock:
                content = _generate_chunk_with_template(
                    key, data, prompt_template, model_config_dict=model_config_dict
                )
            return key, content
        except Exception as e:
            print(f"[Chunk-Gen] {key} 板块生成失败: {e}")
            return key, None

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(safe_call_gen, key, data, prompt): key
            for key, data, prompt in tasks
        }

        for future in as_completed(futures):
            key, content = future.result()
            result[key] = content
            if content:
                print(f"[Chunk-Gen] {key} 板块生成完成 | chars={len(content)}")

    print(f"[Chunk-Gen] 并行分块生成完成 | "
          f"basic={bool(result['basic_audit'])}, "
          f"relation={bool(result['relation_discovery'])}, "
          f"quality={bool(result['quality_audit'])}")

    return result


def _generate_chunk_with_template(
    chunk_type: str,
    data: Dict[str, Any],
    prompt_template: str,
    model_config_dict: Dict[str, Any] = None,
) -> Optional[str]:
    """使用预加载的提示词模板生成分块内容

    Args:
        chunk_type: 分块类型 ('basic_audit', 'relation_discovery', 'quality_audit')
        data: 分块数据
        prompt_template: 预加载的提示词模板内容
        model_config_dict: 模型配置字典（可选），用于避免子线程中访问数据库

    Returns:
        生成的 Markdown 格式分析内容
    """
    import json

    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

    if chunk_type == 'basic_audit':
        prompt = prompt_template.format(basic_audit_data=data_json)
    elif chunk_type == 'relation_discovery':
        prompt = prompt_template.format(relation_data=data_json)
    elif chunk_type == 'quality_audit':
        prompt = prompt_template.format(quality_audit_data=data_json)
    else:
        return None

    try:
        content = _call_qwen_llm(prompt, model_config_dict=model_config_dict)
        print(f"[Chunk-Gen] {chunk_type} 板块生成成功 | chars={len(content)}")
        return content
    except Exception as e:
        print(f"[Chunk-Gen] {chunk_type} 板块生成失败: {e}")
        return None


def generate_report_summary_from_response(
    report: GovernanceReport,
    exec_resp: Dict[str, Any],
    timeout: int = 60,
) -> str:
    """基于完整 execution_response JSON 让 LLM 动态生成报告总结（整体模式）

    当数据量较小时，可以使用整体模式一次性生成完整总结。
    当数据量较大时，推荐使用 generate_report_chunks() 进行分块生成。

    Args:
        report: 报告对象（提供报告名、执行时间等基础信息）
        exec_resp: 执行接口完整返回值（包含 basic_audit / quality_audit / relation_discovery / summary）
        timeout: LLM 调用超时时间（秒），默认 60

    Returns:
        LLM 生成的 Markdown 格式总结文本
    """
    try:
        prompt_template = _load_prompt_template("report_dynamic_prompt.txt")
    except FileNotFoundError:
        raise FileNotFoundError(
            "动态报告提示词模板未找到，请确保 libs/prompt/governance/report_dynamic_prompt.txt 存在。"
        )

    # 提取数据源名称
    datasource_name = str(report.datasource_id) if report.datasource_id else 'N/A'
    if relation_data := exec_resp.get('relation_discovery'):
        if rels := relation_data.get('relationships'):
            datasource_name = rels[0].get('from_datasource_name') or datasource_name

    # 基础信息
    report_name = report.report_name or '数据治理质量报告'
    execution_time = (
        report.execution_time.strftime('%Y-%m-%d %H:%M:%S')
        if report.execution_time else 'N/A'
    )
    quality_score = float(exec_resp.get('quality_score') or 0)
    grade = exec_resp.get('grade') or '一般'
    scope_tables = ', '.join(report.scope_tables) if report.scope_tables else '全部表'

    # 将 execution_response 序列化为 JSON 字符串
    exec_resp_sanitized = _sanitize_for_llm(exec_resp)
    exec_resp_json = json.dumps(exec_resp_sanitized, ensure_ascii=False, separators=(',', ':'))

    # 上限检查
    max_json_len = 100000
    if len(exec_resp_json) > max_json_len:
        exec_resp_sanitized = _sanitize_for_llm(exec_resp, max_str_len=200, max_items=50)
        exec_resp_json = json.dumps(exec_resp_sanitized, ensure_ascii=False, separators=(',', ':'))
        if len(exec_resp_json) > max_json_len:
            exec_resp_json = exec_resp_json[:max_json_len] + '\n...（数据已截断）'

    prompt = prompt_template.format(
        report_name=report_name,
        execution_time=execution_time,
        quality_score=f"{quality_score:.1f}",
        grade=grade,
        scope_tables=scope_tables,
        datasource_id=datasource_name,
        EXECUTION_RESPONSE_JSON=exec_resp_json,
    )

    try:
        content = _call_qwen_llm(prompt)
        return content.strip()
    except Exception as e:
        print(f"[WARN] 整体模式 LLM 生成失败: {e}，尝试分块模式...")
        # 回退到分块模式
        chunks = generate_report_chunks(report, exec_resp)
        return _assemble_chunks_to_summary(chunks)


def _assemble_chunks_to_summary(chunks: Dict[str, Optional[str]]) -> str:
    """将分块生成的内容组装成完整总结

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


def _build_summary_json_for_module(module_data: Any, module_type: str) -> str:
    """根据模块类型构建用于综合总结的摘要 JSON

    Args:
        module_data: 模块的原始数据
        module_type: 模块类型 ('basic_audit' | 'quality_audit' | 'relation_discovery')

    Returns:
        摘要 JSON 字符串或 "未执行该模块"
    """
    import json

    if module_type == 'basic_audit':
        if not module_data or not module_data.get('tables'):
            return "未执行该模块"

        tables = module_data.get('tables', [])
        all_columns = [c for tbl in tables for c in tbl.get('report', [])]

        total_rows = sum(c.get('total_rows', 0) for c in all_columns)
        null_count = sum(c.get('null_count', 0) for c in all_columns)
        empty_str_count = sum(c.get('empty_str_count', 0) for c in all_columns)
        missing_count = sum(c.get('missing_count', 0) for c in all_columns)
        missing_pct = (missing_count / total_rows * 100) if total_rows > 0 else 0

        problem_cols = sorted(
            [c for c in all_columns if c.get('missing_pct', 0) > 0],
            key=lambda x: x.get('missing_pct', 0),
            reverse=True
        )[:5]

        top_problems = [
            {
                "table": tbl.get('table', 'N/A'),
                "column": c.get('column_name', 'N/A'),
                "missing_pct": c.get('missing_pct', 0)
            }
            for tbl in tables
            for c in tbl.get('report', [])
            if c.get('missing_pct', 0) > 0
        ]
        top_problems = sorted(top_problems, key=lambda x: x['missing_pct'], reverse=True)[:5]

        return json.dumps({
            "tables_count": len(tables),
            "columns_count": len(all_columns),
            "total_rows": total_rows,
            "null_count": null_count,
            "empty_str_count": empty_str_count,
            "missing_count": missing_count,
            "missing_pct": round(missing_pct, 2),
            "problem_columns": len(problem_cols),
            "top_problems": top_problems
        }, ensure_ascii=False)

    elif module_type == 'quality_audit':
        if not module_data or not module_data.get('results'):
            return "未执行该模块"

        results = module_data.get('results', [])
        passed = [r for r in results if r.get('status') == 'passed']
        failed = [r for r in results if r.get('status') == 'failed']
        errors = [r for r in results if r.get('status') == 'error']

        total_failed_rows = sum(r.get('failed_count', 0) for r in failed)
        pass_rate = (len(passed) / len(results) * 100) if results else 0
        critical_count = len([r for r in failed if r.get('severity') == 'critical'])

        top_failures = sorted(
            failed,
            key=lambda x: x.get('failed_rate', 0),
            reverse=True
        )[:5]
        top_failures = [
            {
                "rule_name": r.get('rule_name', 'N/A'),
                "table": r.get('table_name', 'N/A'),
                "column": r.get('column_name', 'N/A'),
                "failed_rate": r.get('failed_rate', 0),
                "severity": r.get('severity', 'info')
            }
            for r in top_failures
        ]

        return json.dumps({
            "rules_count": len(results),
            "passed_count": len(passed),
            "failed_count": len(failed),
            "error_count": len(errors),
            "pass_rate": round(pass_rate, 2),
            "total_failed_rows": total_failed_rows,
            "critical_count": critical_count,
            "top_failures": top_failures
        }, ensure_ascii=False)

    elif module_type == 'relation_discovery':
        if not module_data or module_data.get('relationships_count', 0) == 0:
            return "未执行该模块"

        stats = module_data.get('statistics') or {}
        relationships = module_data.get('relationships', [])[:10]  # 取前10个用于摘要

        top_relationships = [
            {
                "from": f"{r.get('from_table', 'N/A')}.{r.get('from_column', 'N/A')}",
                "to": f"{r.get('to_table', 'N/A')}.{r.get('to_column', 'N/A')}",
                "confidence": r.get('confidence', 0),
                "type": r.get('relationship_type', 'N/A')
            }
            for r in sorted(relationships, key=lambda x: x.get('confidence', 0), reverse=True)[:5]
        ]

        return json.dumps({
            "relationships_count": module_data.get('relationships_count', 0),
            "tables_count": module_data.get('tables_count', 0),
            "cards_count": module_data.get('cards_count', 0),
            "avg_confidence": stats.get('avg_confidence', 0),
            "high_confidence_count": stats.get('high_confidence_count', 0),
            "low_confidence_count": stats.get('low_confidence_count', 0),
            "top_relationships": top_relationships
        }, ensure_ascii=False)

    return "未知模块类型"


def generate_overall_summary(
    report: GovernanceReport,
    exec_resp: Dict[str, Any],
) -> Optional[str]:
    """生成综合总结——基于三大模块检测结果的跨模块综合分析

    Args:
        report: 报告对象
        exec_resp: 执行接口完整返回值

    Returns:
        LLM 生成的 Markdown 格式综合总结文本
    """
    try:
        prompt_template = _load_prompt_template("report_overall_summary_chunk.txt")
    except FileNotFoundError:
        print("[WARN] 综合总结提示词模板未找到，跳过该章节生成")
        return None

    # 构建各模块摘要
    basic_audit = exec_resp.get('basic_audit') or {}
    quality_audit = exec_resp.get('quality_audit') or {}
    relation_data = exec_resp.get('relation_discovery') or {}

    basic_summary = _build_summary_json_for_module(basic_audit, 'basic_audit')
    quality_summary = _build_summary_json_for_module(quality_audit, 'quality_audit')
    relation_summary = _build_summary_json_for_module(relation_data, 'relation_discovery')

    prompt = prompt_template.format(
        basic_audit_summary=basic_summary,
        quality_audit_summary=quality_summary,
        relation_discovery_summary=relation_summary,
    )

    try:
        content = _call_qwen_llm(prompt)
        print(f"[Overall-Summary] 综合总结生成成功 | chars={len(content)}")
        return content
    except Exception as e:
        print(f"[Overall-Summary] 综合总结生成失败: {e}")
        return None

