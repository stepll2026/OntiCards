"""
@File: rule_llm_parser.py
@Description: 规则 LLM 解析器 - 将自然语言规则描述转换为结构化规则
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-02
@Update: 2026-06-02 - 集成数据卡片上下文，支持多条件解析

核心能力：
1. 加载规则解析提示词
2. 结合数据库 Schema 和数据卡片信息生成 Prompt
3. 调用 LLM 解析自然语言规则
4. 返回结构化的规则配置
5. 支持基于数据卡片的智能表/列定位
6. 支持多条件组合（AND/OR）
"""

import json
import os
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict, field

from controllers.governance.dialect_adapter import DialectAdapter, get_dialect_prompt_context
from controllers.governance.schema_context import TableSchema, ColumnInfo


@dataclass
class ColumnCondition:
    """列级条件"""
    column: str
    rule_type: str
    condition: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedRule:
    """解析后的规则"""
    rule_type: str
    target_table: Optional[str]
    target_column: Optional[str] = None
    condition_expr: str = ""
    stage: str = "column"
    conditions: List[ColumnCondition] = field(default_factory=list)
    condition_mode: str = "AND"
    severity: str = "warning"
    confidence: float = 0.5
    needs_confirmation: bool = False
    reasoning: str = ""
    alternatives: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['conditions'] = [c.to_dict() if isinstance(c, ColumnCondition) else c for c in self.conditions]
        return data

    def is_multi_condition(self) -> bool:
        return len(self.conditions) > 1


class RuleLLMParser:
    """规则 LLM 解析器"""

    def __init__(self, llm_client, db_type: str = 'postgresql'):
        self.llm_client = llm_client
        self.db_type = db_type.lower()
        self.dialect_adapter = DialectAdapter(db_type)
        self._prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """从数据库加载提示词模板，失败则回退到文件"""
        try:
            from models.prompt_config import prompt_manager
            content = prompt_manager.get_prompt("rule_parsing_prompt.txt", use_cache=True)
            if content:
                return content
        except Exception as e:
            print(f"[WARN] 从数据库加载 rule_parsing_prompt.txt 失败: {str(e)}")

        # 回退到文件读取
        try:
            from pathlib import Path
            prompt_file = Path(__file__).resolve().parent.parent.parent / "libs" / "prompt" / "governance" / "rule_parsing_prompt.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            print(f"[WARN] 加载提示词模板失败: {str(e)}")
        return self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        return """你是一个数据质量规则解析引擎。
## 任务
将用户的自然语言描述转换为结构化的数据治理规则。
## 输入
- 数据库类型: {db_type}
- Schema: {schema_context}
- 用户描述: "{user_input}"
## 输出格式
请严格输出 JSON：
{
    "rule_type": "规则类型",
    "target_table": "表名",
    "target_column": "列名",
    "condition_expr": "条件表达式",
    "severity": "critical|warning|info",
    "confidence": 0.0-1.0,
    "needs_confirmation": true|false,
    "reasoning": "解析理由"
}
"""

    def _build_schema_context(self, schemas: List[TableSchema]) -> str:
        """
        构建适合 LLM 的 Schema 上下文

        数据卡片优先级：
        1. 列注释以数据卡片为准（经过 LLM 增强）
        2. 表描述以数据卡片为准
        3. 数据卡片的业务信息作为参考
        """
        if not schemas:
            return "（无可用数据库结构信息）"

        lines = []
        for schema in schemas:
            lines.append(f"### 表: {schema.table_name}")

            # 数据卡片的业务信息（优先级最高）
            if schema.card_topic:
                lines.append(f"- 核心主题: {schema.card_topic}")
            if schema.card_abstract:
                lines.append(f"- 摘要: {schema.card_abstract}")
            if schema.card_tags:
                lines.append(f"- 标签: {', '.join(schema.card_tags)}")

            # 数据卡片的实体信息
            if schema.card_entities:
                lines.append(f"- 核心实体: {', '.join(schema.card_entities)}")

            # 表描述（优先使用数据卡片的）
            if schema.description:
                lines.append(f"- 表描述: {schema.description}")

            lines.append("")
            lines.append("**列信息（注释以数据卡片为准）**:")
            lines.append("| 列名 | 类型 | 注释（数据卡片增强）|")
            lines.append("|------|------|----------------------|")
            for col in schema.columns:
                # 支持 ColumnInfo 对象和字典两种格式
                if hasattr(col, 'name'):
                    # ColumnInfo dataclass
                    col_name = col.name
                    col_type = col.data_type
                    col_comment = col.comment
                else:
                    # 字典格式
                    col_name = col.get('name', '')
                    col_type = col.get('data_type', '')
                    col_comment = col.get('comment', '')
                lines.append(f"| {col_name} | {col_type} | {col_comment} |")
            lines.append("")
        return '\n'.join(lines)

    def _build_data_card_context(self, schemas: List[TableSchema]) -> str:
        """
        构建数据卡片业务语义上下文

        数据卡片包含丰富的业务语义信息，用于帮助 LLM 理解表的用途和列的业务含义
        """
        if not schemas:
            return "（无可用数据卡片信息）"

        lines = []
        lines.append("=== 数据卡片业务语义信息（优先级最高）===\n")

        for schema in schemas:
            has_card_info = (schema.card_abstract or schema.card_topic or
                           schema.card_entities or schema.card_tags or schema.card_scenarios)

            if has_card_info:
                lines.append(f"## {schema.table_name}")
                if schema.card_topic:
                    lines.append(f"- 核心主题: {schema.card_topic}")
                if schema.card_abstract:
                    abstract = schema.card_abstract
                    if len(abstract) > 200:
                        abstract = abstract[:200] + "..."
                    lines.append(f"- 摘要: {abstract}")
                if schema.card_entities:
                    lines.append(f"- 核心实体: {', '.join(schema.card_entities[:10])}")
                if schema.card_scenarios:
                    lines.append(f"- 适用场景: {', '.join(schema.card_scenarios[:5])}")
                if schema.card_tags:
                    lines.append(f"- 标签: {', '.join(schema.card_tags[:15])}")

                # 输出列的注释（来自数据卡片）
                card_columns = [(col.name, col.comment) for col in schema.columns
                               if hasattr(col, 'comment') and col.comment]
                if card_columns:
                    lines.append("\n  **列业务注释（数据卡片增强）**:")
                    for col_name, col_comment in card_columns[:10]:
                        lines.append(f"  - {col_name}: {col_comment}")
                lines.append("")

        if len(lines) <= 2:  # 只有标题行
            return "（无可用数据卡片信息）"

        return '\n'.join(lines)

    def _build_prompt(self, user_input: str, schemas: List[TableSchema]) -> str:
        dialect_context = get_dialect_prompt_context(self.db_type)
        schema_context = self._build_schema_context(schemas)
        data_card_context = self._build_data_card_context(schemas)
        return self._prompt_template.format(
            db_type=self.db_type.upper(),
            data_card_context=data_card_context,
            schema_context=schema_context,
            user_input=user_input,
            identifier_quote=dialect_context['identifier_quote'],
            date_functions=dialect_context['date_functions'],
            string_functions=dialect_context['string_functions'],
            regex_syntax=dialect_context['regex_syntax'],
            null_check_syntax=dialect_context['null_check_syntax']
        )

    def parse(self, user_input: str, schemas: List[TableSchema] = None, prefer_high_confidence: bool = True) -> Tuple[Optional[ParsedRule], List]:
        if schemas is None:
            schemas = []

        # 先检测是否涉及多列关系比较（如"结束时间必须晚于开始时间"）
        if self._is_multi_column_relation_text(user_input):
            multi_col_result = self._parse_multi_column_relation(user_input, schemas)
            if multi_col_result is not None and multi_col_result[0] is not None:
                return multi_col_result

        prompt = self._build_prompt(user_input, schemas)
        try:
            response = self.llm_client.chat(prompt)
            parsed = self._parse_response(response)
            if parsed is None:
                return None, []
            return parsed, parsed.alternatives or []
        except Exception as e:
            print(f"[ERROR] LLM 解析失败: {str(e)}")
            return None, []

    def _is_multi_column_relation_text(self, text: str) -> bool:
        """快速检测文本是否可能涉及多列关系比较"""
        text_lower = text.lower()
        relation_keywords = [
            '晚于', '早于', '先于', '后于',
            '大于', '小于', '不低于', '不高于', '高于', '低于', '少于', '多于', '超过',
        ]
        connectors = ['和', '与', '跟', '同']
        return any(kw in text_lower for kw in relation_keywords) and any(c in text_lower for c in connectors)

    def parse_with_column(
        self,
        user_input: str,
        schemas: List[TableSchema],
        target_table: str,
        target_column: str
    ) -> Tuple[Optional[ParsedRule], List]:
        """
        用户已指定表和列，强制使用 LLM 解析

        构建一个专门的 Prompt，包含：
        1. 目标表的完整信息
        2. 目标列的详细信息（来自数据卡片）
        3. 用户输入的自然语言描述
        """
        # 构建目标表的上下文
        schema_context = self._build_schema_context(schemas)
        data_card_context = self._build_data_card_context(schemas)

        # 获取数据库方言语法
        dialect_context = get_dialect_prompt_context(self.db_type)

        # 构建专门的 Prompt
        prompt = f"""你是一个数据质量规则解析引擎，专门将自然语言转换为数据质量检测的【业务条件】。

## 核心概念

**业务条件**（必须满足的条件）：这是一个 SQL 条件，用于描述"合格的记录应该满足什么"。
- 如果记录符合规则（业务条件 = TRUE），这是一个合格的记录
- 如果记录违反规则（业务条件 = FALSE），这是一个违规的记录

**重要**：
- 业务条件描述的是【必须满足】的语义
- 违规判定由 SQL 执行层自动完成：`NOT(业务条件) = 违规`
- condition_expr 必须直接表达用户的【正向意图】，不要写成取反形式

## 重要约束
- **target_table**：`{target_table}`
- **target_column**：`{target_column}`
- **用户描述**：「{user_input}」
- **condition_expr 必须是业务条件**：当这条记录符合规则时，条件返回 TRUE

## 语义转换规则

根据用户描述的语义，确定业务条件：

| 用户描述 | 含义 | 业务条件（condition_expr） |
|---------|------|---------------------------|
| "仓库名不为空" | 仓库名必须有值 | warehouse IS NOT NULL AND warehouse != '' |
| "仓库名为空" | 仓库名必须为空 | warehouse IS NULL OR warehouse = '' |
| "金额大于0" | 金额必须 > 0 | amount > 0 |
| "金额不能为负" | 金额必须 >= 0 | amount >= 0 |
| "日期不能过期" | 日期必须 >= 当前日期 | expire_date >= CURRENT_DATE |
| "数量在1-100之间" | 数量必须在范围内 | quantity >= 1 AND quantity <= 100 |

## 数据库方言语法参考
{dialect_context['null_check_syntax']}

## 表结构和列信息
{schema_context}

## 数据卡片业务语义
{data_card_context}

## 输出要求
请严格输出 JSON：
```json
{{
    "target_table": "{target_table}",
    "target_column": "{target_column}",
    "rule_type": "规则类型（threshold/null_check/format/unique/enum/length_check/date_check）",
    "condition_expr": "业务条件（当记录符合规则时返回 TRUE，例如 column > 0）",
    "severity": "critical|warning|info",
    "confidence": 0.95,
    "needs_confirmation": false,
    "reasoning": "解析理由，说明如何理解用户描述"
}}
```

## 示例

### 示例1：不为空
- 用户描述: "仓库名不为空"
- 业务条件: warehouse IS NOT NULL AND warehouse != ''
- 含义: 仓库名必须有值，这是合格记录的条件

### 示例2：为空
- 用户描述: "仓库名为空"
- 业务条件: warehouse IS NULL OR warehouse = ''
- 含义: 仓库名必须为空，这是合格记录的条件

### 示例3：大于0
- 用户描述: "优惠值必须大于0"
- 业务条件: discount_value > 0
- 含义: 优惠值必须 > 0，这是合格记录的条件

### 示例4：范围检查
- 用户描述: "发行数量在1-100之间"
- 业务条件: issued_count >= 1 AND issued_count <= 100
- 含义: 发行数量必须在 1-100 范围内，这是合格记录的条件
"""
        try:
            response = self.llm_client.chat(prompt)
            parsed = self._parse_response(response)
            if parsed is None:
                return None, []
            return parsed, parsed.alternatives or []
        except Exception as e:
            print(f"[ERROR] LLM 解析失败: {str(e)}")
            return None, []

    def _parse_response(self, response: str) -> Optional[ParsedRule]:
        try:
            json_str = self._extract_json(response)
            if not json_str:
                return None
            data = json.loads(json_str)
            conditions_data = data.get('conditions', [])
            conditions = [ColumnCondition(
                column=cond.get('column', ''),
                rule_type=cond.get('rule_type', 'custom_sql'),
                condition=cond.get('condition', ''),
                description=cond.get('description', '')
            ) for cond in conditions_data]
            return ParsedRule(
                rule_type=data.get('rule_type', 'custom_sql'),
                target_table=data.get('target_table'),
                target_column=data.get('target_column'),
                condition_expr=data.get('condition_expr', ''),
                stage=data.get('scope_type', 'column'),
                conditions=conditions,
                condition_mode=data.get('condition_mode', 'AND'),
                severity=data.get('severity', 'warning'),
                confidence=data.get('confidence', 0.5),
                needs_confirmation=data.get('needs_confirmation', False),
                reasoning=data.get('reasoning', ''),
                alternatives=data.get('alternatives', [])
            )
        except json.JSONDecodeError:
            return None

    def _extract_json(self, text: str) -> Optional[str]:
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        text = text.strip()
        if text.startswith('{') and text.endswith('}'):
            return text
        return None


class SmartRuleParser:
    """
    智能规则解析器 - 基于数据卡片业务语义的智能匹配

    核心设计理念：
    1. 规则类型识别：通过正则模式识别通用规则类型（与业务无关）
    2. 列匹配：优先使用 LLM 智能分析自然语言 + 数据卡片信息
    3. 候选返回：当有多个可能匹配时，返回候选列表供用户选择

    注意：列的匹配必须由 LLM 结合业务语义分析，代码层面不写死任何业务关键词映射
    """

    # 通用规则类型识别模式（用于识别用户想做什么类型的检查，不涉及业务）
    RULE_TYPE_PATTERNS = {
        'null_check': [
            r'为空|是空|没有值|未填写|缺失|必填|必须填写|不能为空|未填|没填',
            r'must|required|null|empty|missing'
        ],
        'unique': [
            r'不能重复|必须唯一|唯一性|重复|不能出现',
            r'unique|duplicate|repeated'
        ],
        'format': [
            r'格式|格式校验|格式不对|格式错误|格式规范',
            r'身份证.*位|手机号.*位|区划.*位|邮编',
            r'行政区划|行政区域|YYYY|yyyy-mm-dd',
            r'format|pattern'
        ],
        'threshold': [
            r'大于|小于|超过|低于|不能小于|不能大于|不能为负|不能为正|不能小于0|不能大于0|不小于0',
            r'正数|负数|零|大于0|小于0|大于等于|小于等于|非负',
            r'greater|less|above|below|negative|positive'
        ],
        'enum': [
            r'只能是|枚举|只能为|只能是以下|允许的值为|男或女|男女|男.*女',
            r'enum|only.*allowed|must.*be.*one'
        ],
        'length_check': [
            r'长度|字符数|太长|太短|字符长度|不能超过|不能少于|不超过',
            r'length|too.*long|too.*short'
        ],
        'date_check': [
            r'未来日期|过去日期|过期|不能是未来|不能是过去|日期格式|时间格式',
            r'future|past|expired|outdated'
        ],
        'consistency_check': [
            r'一致性|一致|匹配|相符|相同|证件.*姓名|号码.*一致',
            r'consistency|match|same'
        ],
        'freshness_check': [
            r'新鲜度|及时|更新|多久|太旧|过期',
            r'fresh|recent|outdated|stale'
        ]
    }

    def __init__(self, llm_client=None, db_type: str = 'postgresql'):
        self.llm_client = llm_client
        self.db_type = db_type
        self.dialect_adapter = DialectAdapter(db_type)

    def parse(self, user_input: str, schemas: List[TableSchema] = None, mode: str = 'auto') -> Tuple[Optional[ParsedRule], List]:
        if mode == 'llm' and self.llm_client:
            llm_parser = RuleLLMParser(self.llm_client, self.db_type)
            return llm_parser.parse(user_input, schemas)
        elif mode == 'pattern':
            result = self._pattern_match(user_input, schemas)
            return result, []
        else:
            result = self._smart_match(user_input, schemas)
            if result[0] and result[0].confidence >= 0.85:
                return result
            elif self.llm_client:
                llm_parser = RuleLLMParser(self.llm_client, self.db_type)
                return llm_parser.parse(user_input, schemas)
            return result

    def _split_conditions(self, user_input: str) -> List[Dict[str, Any]]:
        and_pattern = r'\s*(?:并且?|而且?|且|同时|and)\s*'
        or_pattern = r'\s*(?:或者|或|or)\s*'
        parts = re.split(and_pattern, user_input, flags=re.IGNORECASE)
        if len(parts) > 1:
            condition_mode = 'AND'
        else:
            parts = re.split(or_pattern, user_input, flags=re.IGNORECASE)
            if len(parts) > 1:
                condition_mode = 'OR'
            else:
                return [{'text': user_input.strip(), 'connector': None}]
        conditions = []
        for i, part in enumerate(parts):
            connector = condition_mode if i < len(parts) - 1 else None
            conditions.append({'text': part.strip(), 'connector': connector})
        return conditions if conditions else [{'text': user_input, 'connector': None}]

    def _is_multi_column_relation_text(self, text: str) -> bool:
        """快速检测文本是否可能涉及多列关系比较"""
        text_lower = text.lower()
        relation_keywords = [
            '晚于', '早于', '先于', '后于',
            '大于', '小于', '不低于', '不高于', '高于', '低于', '少于', '多于', '超过',
        ]
        connectors = ['和', '与', '跟', '同']
        return any(kw in text_lower for kw in relation_keywords) and any(c in text_lower for c in connectors)

    def _build_schema_context(self, schemas: List[TableSchema]) -> str:
        """
        构建适合 LLM 的 Schema 上下文

        数据卡片优先级：
        1. 列注释以数据卡片为准（经过 LLM 增强）
        2. 表描述以数据卡片为准
        3. 数据卡片的业务信息作为参考
        """
        if not schemas:
            return "（无可用数据库结构信息）"

        lines = []
        for schema in schemas:
            lines.append(f"### 表: {schema.table_name}")

            # 数据卡片的业务信息（优先级最高）
            if schema.card_topic:
                lines.append(f"- 核心主题: {schema.card_topic}")
            if schema.card_abstract:
                lines.append(f"- 摘要: {schema.card_abstract}")
            if schema.card_tags:
                lines.append(f"- 标签: {', '.join(schema.card_tags)}")

            # 数据卡片的实体信息
            if schema.card_entities:
                lines.append(f"- 核心实体: {', '.join(schema.card_entities)}")

            # 表描述（优先使用数据卡片的）
            if schema.description:
                lines.append(f"- 表描述: {schema.description}")

            lines.append("")
            lines.append("**列信息（注释以数据卡片为准）**:")
            lines.append("| 列名 | 类型 | 注释（数据卡片增强）|")
            lines.append("|------|------|----------------------|")
            for col in schema.columns:
                # 支持 ColumnInfo 对象和字典两种格式
                if hasattr(col, 'name'):
                    # ColumnInfo dataclass
                    col_name = col.name
                    col_type = col.data_type
                    col_comment = col.comment
                else:
                    # 字典格式
                    col_name = col.get('name', '')
                    col_type = col.get('data_type', '')
                    col_comment = col.get('comment', '')
                lines.append(f"| {col_name} | {col_type} | {col_comment} |")
            lines.append("")
        return '\n'.join(lines)

    def _build_data_card_context(self, schemas: List[TableSchema]) -> str:
        """
        构建数据卡片业务语义上下文

        数据卡片包含丰富的业务语义信息，用于帮助 LLM 理解表的用途和列的业务含义
        """
        if not schemas:
            return "（无可用数据卡片信息）"

        lines = []
        lines.append("=== 数据卡片业务语义信息（优先级最高）===\n")

        for schema in schemas:
            has_card_info = (schema.card_abstract or schema.card_topic or
                           schema.card_entities or schema.card_tags or schema.card_scenarios)

            if has_card_info:
                lines.append(f"## {schema.table_name}")
                if schema.card_topic:
                    lines.append(f"- 核心主题: {schema.card_topic}")
                if schema.card_abstract:
                    abstract = schema.card_abstract
                    if len(abstract) > 200:
                        abstract = abstract[:200] + "..."
                    lines.append(f"- 摘要: {abstract}")
                if schema.card_entities:
                    lines.append(f"- 核心实体: {', '.join(schema.card_entities[:10])}")
                if schema.card_scenarios:
                    lines.append(f"- 适用场景: {', '.join(schema.card_scenarios[:5])}")
                if schema.card_tags:
                    lines.append(f"- 标签: {', '.join(schema.card_tags[:10])}")
                lines.append("")
            else:
                lines.append(f"## {schema.table_name}（无数据卡片信息）")
                lines.append("")

        return '\n'.join(lines)

    def _smart_match(self, user_input: str, schemas: List[TableSchema] = None) -> Tuple[Optional[ParsedRule], List]:
        condition_parts = self._split_conditions(user_input)
        if len(condition_parts) > 1:
            return self._parse_multi_conditions(condition_parts, schemas, user_input)
        return self._pattern_match(user_input, schemas)

    def _pattern_match(self, user_input: str, schemas: List[TableSchema] = None) -> Tuple[Optional[ParsedRule], List]:
        user_input_lower = user_input.lower()

        # 0. 特殊处理：单表内多字段比较关系（晚于/早于/大于/小于等）
        # 在一致性检测之前处理，因为"XX和YY一致"会被一致性检测捕获
        if schemas and self.llm_client:
            multi_col_result = self._parse_multi_column_relation(user_input, schemas)
            if multi_col_result is not None and multi_col_result[0] is not None:
                return multi_col_result

        # 1. 特殊处理：一致性检测（单表内多字段一致）- 场景A
        if schemas:
            consistency_result = self._parse_consistency_pattern(user_input, schemas)
            if consistency_result is not None and consistency_result[0] is not None:
                return consistency_result

        # 1. 识别规则类型（通用规则，不依赖业务）
        rule_type = self._detect_rule_type(user_input_lower)
        if not rule_type:
            rule_type = 'threshold'  # 默认阈值检测

        # 2. 生成条件表达式
        condition_expr = self._get_condition_for_type(user_input_lower, rule_type)

        # 3. 在 schemas 中查找匹配的列（利用数据卡片业务语义）
        if schemas:
            matched = self._find_matching_column(user_input_lower, schemas, rule_type)
            if matched:
                return matched

        return None, []

    def _find_matching_column(self, user_input_lower: str, schemas: List[TableSchema], rule_type: str) -> Optional[Tuple[ParsedRule, List]]:
        """
        利用数据卡片的业务语义查找匹配的列

        匹配优先级：
        1. 数据卡片 key_entities 精确匹配
        2. 列注释匹配
        3. 列名模糊匹配
        4. 基于数据类型推荐
        """
        for schema in schemas:
            # 1. 利用 key_entities 做业务语义匹配
            if schema.card_entities:
                for entity in schema.card_entities:
                    entity_lower = entity.lower()
                    if entity_lower in user_input_lower or self._fuzzy_match(entity_lower, user_input_lower):
                        # 找到了匹配的实体，在该表中查找对应列
                        matched = self._find_column_by_entity(entity, schema, rule_type, user_input_lower)
                        if matched:
                            return matched

            # 2. 利用列注释匹配
            for col in schema.columns:
                comment = (col.comment or '').lower()
                if comment and self._semantic_match(comment, user_input_lower):
                    col_name = col.name if hasattr(col, 'name') else col.get('name')
                    condition_expr = self._get_condition_for_type(user_input_lower, rule_type)
                    return ParsedRule(
                        rule_type=rule_type,
                        target_table=schema.table_name,
                        target_column=col_name,
                        condition_expr=condition_expr.replace('{col}', col_name),
                        severity=self._detect_severity(user_input_lower),
                        confidence=0.9,
                        needs_confirmation=False,
                        reasoning=f'通过列注释 "{comment}" 匹配到 {schema.table_name}.{col_name}',
                        alternatives=[]
                    ), []

            # 3. 利用列名模糊匹配
            for col in schema.columns:
                col_name = col.name if hasattr(col, 'name') else col.get('name')
                col_name_lower = col_name.lower()

                if self._fuzzy_match(col_name_lower, user_input_lower):
                    condition_expr = self._get_condition_for_type(user_input_lower, rule_type)
                    return ParsedRule(
                        rule_type=rule_type,
                        target_table=schema.table_name,
                        target_column=col_name,
                        condition_expr=condition_expr.replace('{col}', col_name),
                        severity=self._detect_severity(user_input_lower),
                        confidence=0.75,
                        needs_confirmation=False,
                        reasoning=f'通过列名 "{col_name}" 模糊匹配',
                        alternatives=[]
                    ), []

            # 4. 基于数据类型推荐（兜底）
            best_col = self._find_best_column_by_type(schema, rule_type)
            if best_col:
                col_name = best_col.name if hasattr(best_col, 'name') else best_col.get('name')
                condition_expr = self._get_condition_for_type(user_input_lower, rule_type)
                return ParsedRule(
                    rule_type=rule_type,
                    target_table=schema.table_name,
                    target_column=col_name,
                    condition_expr=condition_expr.replace('{col}', col_name),
                    severity=self._detect_severity(user_input_lower),
                    confidence=0.6,
                    needs_confirmation=True,
                    reasoning=f'基于数据类型推荐列 {col_name}，请确认',
                    alternatives=[]
                ), []

        return None

    def _find_column_by_entity(self, entity: str, schema: TableSchema, rule_type: str, user_input_lower: str) -> Optional[Tuple[ParsedRule, List]]:
        """根据实体名称在表中查找对应的列"""
        entity_lower = entity.lower()

        # 1. 在列名中查找
        for col in schema.columns:
            col_name = col.name if hasattr(col, 'name') else col.get('name')
            col_name_lower = col_name.lower()

            if entity_lower in col_name_lower or col_name_lower in entity_lower:
                condition_expr = self._get_condition_for_type(user_input_lower, rule_type)
                return ParsedRule(
                    rule_type=rule_type,
                    target_table=schema.table_name,
                    target_column=col_name,
                    condition_expr=condition_expr.replace('{col}', col_name),
                    severity=self._detect_severity(user_input_lower),
                    confidence=0.95,
                    needs_confirmation=False,
                    reasoning=f'通过数据卡片实体 "{entity}" 匹配到 {schema.table_name}.{col_name}',
                    alternatives=[]
                ), []

        # 2. 在列注释中查找
        for col in schema.columns:
            comment = (col.comment or '').lower()
            if comment and (entity_lower in comment or self._fuzzy_match(entity_lower, comment)):
                col_name = col.name if hasattr(col, 'name') else col.get('name')
                condition_expr = self._get_condition_for_type(user_input_lower, rule_type)
                return ParsedRule(
                    rule_type=rule_type,
                    target_table=schema.table_name,
                    target_column=col_name,
                    condition_expr=condition_expr.replace('{col}', col_name),
                    severity=self._detect_severity(user_input_lower),
                    confidence=0.9,
                    needs_confirmation=False,
                    reasoning=f'通过实体 "{entity}" 在注释中匹配到 {schema.table_name}.{col_name}',
                    alternatives=[]
                ), []

        return None

    def _semantic_match(self, text1: str, text2: str) -> bool:
        """语义匹配：检查两个文本是否有语义交集"""
        words1 = set(re.split(r'[\s,，、_]', text1.lower()))
        words2 = set(re.split(r'[\s,，、_]', text2.lower()))
        words1 = {w for w in words1 if len(w) > 1}
        words2 = {w for w in words2 if len(w) > 1}
        common = words1 & words2
        return len(common) > 0

    def _fuzzy_match(self, keyword: str, text: str, threshold: float = 0.6) -> bool:
        """模糊匹配：简单的包含关系或交集"""
        keyword = keyword.lower().strip()
        text = text.lower()

        if keyword in text:
            return True

        keyword_words = set(re.split(r'[\s,，、_]', keyword))
        text_words = set(re.split(r'[\s,，、_]', text))

        if not keyword_words or not text_words:
            return False

        intersection = keyword_words & text_words
        return len(intersection) / len(keyword_words) >= threshold

    def _parse_multi_conditions(self, condition_parts: List[Dict], schemas: List[TableSchema], original_input: str) -> Tuple[Optional[ParsedRule], List]:
        """解析多条件"""
        conditions = []
        condition_mode = 'AND'
        matched_table = None

        if schemas:
            for part in condition_parts:
                text = part['text']
                if part['connector']:
                    condition_mode = part['connector']

                rule_type = self._detect_rule_type(text.lower()) or 'threshold'
                condition_expr = self._get_condition_for_type(text.lower(), rule_type)

                matched = self._find_matching_column(text.lower(), schemas, rule_type)
                if matched and matched[0]:
                    col_name = matched[0].target_column
                    if not matched_table:
                        matched_table = matched[0].target_table
                    conditions.append(ColumnCondition(
                        column=col_name or '',
                        rule_type=rule_type,
                        condition=condition_expr.format(col=col_name or 'column'),
                        description=text
                    ))

        if conditions:
            return ParsedRule(
                rule_type='composite',
                target_table=matched_table,
                stage='column',
                conditions=conditions,
                condition_mode=condition_mode,
                severity=self._detect_severity(original_input.lower()),
                confidence=0.85 if matched_table else 0.7,
                needs_confirmation=matched_table is None,
                reasoning=f'识别出{len(conditions)}个条件' + (f'，定位到表 {matched_table}' if matched_table else '，请确认目标表'),
                alternatives=[]
            ), []
        return None, []

    def _map_columns_to_conditions(
        self,
        inferred_columns,
        schema: TableSchema,
        condition_parts: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        将拆分子条件与列进行匹配，建立 {列名: 对应子条件文本} 的映射。

        匹配策略：
        1. 先在子条件文本中查找是否明确提到了列名（或列名的中文注释关键词）
        2. 若子条件文本中没提到列名，则尝试用子条件文本与列注释/实体做语义匹配
        3. 未能精确匹配时，按顺序一一对应（位置映射兜底）
        """
        col_list = []
        if inferred_columns:
            for item in inferred_columns:
                if isinstance(item, dict):
                    col_name = (item.get('column') or '').strip()
                elif isinstance(item, str):
                    col_name = item.strip()
                else:
                    continue
                if col_name:
                    import re as _re
                    col_name = _re.sub(r'（.+）$', '', col_name).strip()
                    col_name = _re.sub(r'\(.+\)$', '', col_name).strip()
                if col_name:
                    col_list.append(col_name)

        if not col_list or not condition_parts:
            return {}

        col_meta = {}
        for c in (schema.columns if schema else []):
            c_name = c.name if hasattr(c, 'name') else c.get('name', '')
            if c_name:
                col_meta[c_name] = {
                    'comment': (c.comment if hasattr(c, 'comment') else c.get('comment', '') or ''),
                    'entities': list(getattr(schema, 'card_entities', []) or [])
                }

        part_texts = [p['text'] for p in condition_parts]

        # 策略1：在子条件文本中查找是否直接提到了列名或列注释关键词
        matched_cols = {}
        unmatched_parts = []
        for text in part_texts:
            text_lower = text.lower()
            found = False
            for col_name in col_list:
                if col_name.lower() in text_lower:
                    matched_cols[col_name] = text
                    found = True
                    break
            if not found:
                unmatched_parts.append(text)

        if not unmatched_parts:
            return matched_cols

        # 策略2：用子条件文本与列注释/实体做匹配
        for text in unmatched_parts:
            text_lower = text.lower()
            best_col = None
            best_score = 0.0
            for col_name in col_list:
                if col_name in matched_cols:
                    continue
                meta = col_meta.get(col_name, {})
                comment = (meta.get('comment') or '').lower()
                # 检查子条件文本与列注释的词交集
                words_text = set(re.split(r'[\s,，、_\-]', text_lower))
                words_comment = set(re.split(r'[\s,，、_\-]', comment))
                words_text = {w for w in words_text if len(w) > 1}
                words_comment = {w for w in words_comment if len(w) > 1}
                overlap = words_text & words_comment
                if overlap:
                    score = len(overlap) / max(len(words_text), 1)
                    if score > best_score:
                        best_score = score
                        best_col = col_name
            if best_col:
                matched_cols[best_col] = text
                unmatched_parts.remove(text)

        if not unmatched_parts:
            return matched_cols

        # 策略3：按顺序一一对应（位置映射兜底）
        remaining_cols = [c for c in col_list if c not in matched_cols]
        for i, text in enumerate(unmatched_parts):
            if i < len(remaining_cols):
                matched_cols[remaining_cols[i]] = text

        return matched_cols

    def _map_columns_to_conditions_inline(
        self,
        candidates: List[Dict],
        schema: TableSchema,
        condition_parts: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        将拆分子条件与候选列列表进行匹配（内联版本，candidates 已构建好）。
        建立 {列名: 对应子条件文本} 的映射。
        """
        col_list = [c['name'] for c in candidates]

        col_meta = {}
        for c in (schema.columns if schema else []):
            c_name = c.name if hasattr(c, 'name') else c.get('name', '')
            if c_name:
                col_meta[c_name] = {
                    'comment': (c.comment if hasattr(c, 'comment') else c.get('comment', '') or ''),
                    'entities': list(getattr(schema, 'card_entities', []) or [])
                }

        part_texts = [p['text'] for p in condition_parts] if condition_parts else []
        return self._do_map_columns(part_texts, col_list, col_meta)

    def _do_map_columns(
        self,
        part_texts: List[str],
        col_list: List[str],
        col_meta: Dict[str, Dict]
    ) -> Dict[str, str]:
        """
        执行列名到子条件的映射核心逻辑。
        """
        if not part_texts or not col_list:
            return {}

        # 策略1：在子条件文本中直接查找列名
        matched_cols = {}
        unmatched_parts = []
        for text in part_texts:
            text_lower = text.lower()
            found = False
            for col_name in col_list:
                if col_name.lower() in text_lower:
                    matched_cols[col_name] = text
                    found = True
                    break
            if not found:
                unmatched_parts.append(text)

        if not unmatched_parts:
            return matched_cols

        # 策略2：用子条件文本与列注释做匹配
        for text in unmatched_parts:
            text_lower = text.lower()
            best_col = None
            best_score = 0.0
            for col_name in col_list:
                if col_name in matched_cols:
                    continue
                comment = (col_meta.get(col_name, {}).get('comment') or '').lower()
                words_text = set(re.split(r'[\s,，、_\-]', text_lower))
                words_comment = set(re.split(r'[\s,，、_\-]', comment))
                words_text = {w for w in words_text if len(w) > 1}
                words_comment = {w for w in words_comment if len(w) > 1}
                overlap = words_text & words_comment
                if overlap:
                    score = len(overlap) / max(len(words_text), 1)
                    if score > best_score:
                        best_score = score
                        best_col = col_name
            if best_col:
                matched_cols[best_col] = text
                unmatched_parts.remove(text)

        if not unmatched_parts:
            return matched_cols

        # 策略3：按顺序一一对应（位置映射兜底）
        remaining_cols = [c for c in col_list if c not in matched_cols]
        for i, text in enumerate(unmatched_parts):
            if i < len(remaining_cols):
                matched_cols[remaining_cols[i]] = text

        return matched_cols

    def _find_best_column_by_type(self, schema: TableSchema, rule_type: str) -> Optional[Any]:
        """基于规则类型查找最佳列"""
        if not schema.columns:
            return None

        is_dataclass = hasattr(schema.columns[0], 'name')

        type_rules = {
            'null_check': ['varchar', 'text', 'char', 'string'],
            'unique': ['varchar', 'text', 'char', 'string', 'int', 'bigint'],
            'format': ['varchar', 'text', 'char', 'string'],
            'threshold': ['int', 'bigint', 'decimal', 'numeric', 'float', 'double', 'real'],
            'enum': ['varchar', 'text', 'char', 'string'],
            'length_check': ['varchar', 'text', 'char', 'string'],
            'date_check': ['date', 'timestamp', 'datetime', 'time'],
        }

        target_types = type_rules.get(rule_type, [])

        for col in schema.columns:
            dt = col.data_type.lower() if is_dataclass else col.get('data_type', '').lower()
            if any(t in dt for t in target_types):
                return col

        for col in schema.columns:
            comment = col.comment if is_dataclass else col.get('comment')
            if comment:
                return col

        return schema.columns[0] if schema.columns else None

    def _detect_rule_type(self, text_lower: str) -> Optional[str]:
        """识别规则类型"""
        for rule_type, patterns in self.RULE_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return rule_type
        return None

    def _get_condition_for_type(self, text_lower: str, rule_type: str) -> str:
        """获取【业务条件】表达式（必须满足的条件）

        重要：本函数返回的是业务条件（正相条件），例如：
        - "金额不能为负" → "{col} >= 0"（业务上金额必须非负）
        - "仓库名不为空" → "{col} IS NOT NULL AND {col} != ''"
        - "数量在1-100之间" → "{col} >= 1 AND {col} <= 100"

        SQL 执行层会通过 NOT(业务条件) 得到违规条件。
        """
        # 阈值类规则：判断方向（返回业务条件）
        if rule_type == 'threshold':
            if '负数' in text_lower or '负' in text_lower:
                # "不能为负" / "不能小于0" → 业务：col >= 0
                if '不能' in text_lower or '不能为' in text_lower or '不允许' in text_lower:
                    return '{col} >= 0'
                # "金额为负" → 业务：col < 0（说明负数才合规？少见，不变）
                return '{col} < 0'
            if '正数' in text_lower:
                if '不能' in text_lower:
                    return '{col} > 0'
                return '{col} >= 0'
            if '零' in text_lower or '等于0' in text_lower:
                return '{col} = 0'
            if '不小于0' in text_lower or '大于等于0' in text_lower or '非负' in text_lower:
                return '{col} >= 0'
            # 默认：金额必须大于0
            return '{col} > 0'

        # 各规则类型的业务条件
        conditions = {
            # 空值检测：业务条件=字段必须有值
            'null_check': "{col} IS NOT NULL AND {col} != ''",
            # 唯一性检测：业务条件=每组只出现一次（这个特殊，后续 SQL 单独处理）
            'unique': 'COUNT(*) = 1',
            # 枚举检测：业务条件=值在枚举列表内（默认示例，实际由输入确定）
            'enum': "{col} IN ('男', '女')",
            # 长度检测：业务条件=长度大于0
            'length_check': 'CHAR_LENGTH({col}) > 0',
            # 日期检测：业务条件=日期小于等于当前（示例）
            'date_check': '{col} <= NOW()',
            # 一致性检测（单表内多字段一致性）
            'consistency_check': "{col} IS NOT NULL",  # 基础条件，实际逻辑由专项方法处理
            # 新鲜度检测：业务条件=更新时间在7天内
            'freshness_check': "{col} >= NOW() - INTERVAL '7 days'",
        }

        if rule_type == 'format':
            # 格式校验：根据关键词选择对应的正则
            if '手机' in text_lower or '电话' in text_lower:
                return r"{col} ~* '^1[3-9]\d{{9}}$'"
            if '邮箱' in text_lower or 'email' in text_lower:
                return r"{col} ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{{2,}}$'"
            if '身份证' in text_lower:
                return r"{col} ~* '^[1-9]\d{{5}}(18|19|20)\d{{2}}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{{3}}[\dXx]$'"
            if '邮编' in text_lower:
                return r"{col} ~* '^\d{{6}}$'"
            # 行政区划代码：6位数字
            if '区划' in text_lower or '行政' in text_lower:
                return r"{col} ~* '^\d{{6}}$'"
            # 日期时间格式：YYYY-MM-DD HH:MM:SS
            if '日期' in text_lower or '时间' in text_lower or 'yyyy' in text_lower:
                return r"{col} ~* '^\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}$'"
            # 默认：业务条件=任意字符串匹配
            return r"{col} ~* '.*'"

        return conditions.get(rule_type, "{col} IS NOT NULL")

    def _parse_consistency_pattern(self, text: str, schemas: List[TableSchema], target_table: str = None) -> Tuple[Optional[ParsedRule], List]:
        """
        解析一致性检测模式（场景A：单表内多字段一致）

        支持的模式：
        1. "XX和YY一致/相同/匹配" - 两字段值应相同
        2. "XX、YY一致" - 多字段值应相同
        3. "证件号码和姓名一致" - 在同一表中验证两个字段

        Args:
            text: 用户输入的自然语言
            schemas: 表结构信息
            target_table: 目标表名（如果有）

        Returns:
            Tuple[ParsedRule, List] - 解析结果和候选列表
        """
        text_lower = text.lower()

        # 一致性检测的关键词
        consistency_keywords = [
            '一致', '相同', '匹配', '相符', '相等',
        ]

        # 检查是否包含一致性关键词
        has_consistency_keyword = any(kw in text_lower for kw in consistency_keywords)
        if not has_consistency_keyword:
            return None, []

        # 一致性检测的连接词
        connectors = ['和', '与', '跟', '同', '、']

        # 尝试提取两个字段
        for connector in connectors:
            if connector not in text_lower:
                continue

            # 查找 connector 的位置
            idx = text_lower.find(connector)
            while idx != -1:
                # 提取 connector 前后的文本
                before = text_lower[:idx].strip()
                after = text_lower[idx + 1:].strip()  # +1 是因为 connector 是单字符

                # 在 after 中查找一致性关键词
                field2_raw = None
                kw_found = None
                for kw in consistency_keywords:
                    kw_idx = after.find(kw)
                    if kw_idx != -1:
                        field2_raw = after[:kw_idx].strip()
                        kw_found = kw
                        break

                if field2_raw and before:
                    # 清理 field1 中的修饰词（这些词不影响语义匹配，但会干扰匹配）
                    modifiers = ['需要', '应该', '必须', '的', '是']
                    field1_cleaned = before
                    for m in modifiers:
                        field1_cleaned = field1_cleaned.replace(m, '')
                    field1_cleaned = field1_cleaned.strip()

                    # 在 schemas 中查找这两个字段
                    matched_columns = self._find_consistency_columns(
                        field1_cleaned, field2_raw, schemas, target_table
                    )
                    if matched_columns and len(matched_columns) == 2:
                        col1, col2 = matched_columns

                        # 检查是否是同一张表的字段
                        if col1['table'] == col2['table']:
                            rule = self._build_consistency_rule(
                                text, col1, col2, schemas
                            )
                            return rule, []

                # 继续查找下一个 connector
                idx = text_lower.find(connector, idx + 1)

        return None, []

    def _parse_multi_column_relation(self, text: str, schemas: List[TableSchema]) -> Tuple[Optional[ParsedRule], List]:
        """
        解析单表内多字段比较关系（如：结束时间必须晚于开始时间）

        支持的模式：
        1. "XX的YY必须/不能晚于/早于/大于/小于ZZ" - 两字段比较
        2. "XX和ZZ比较" - 通过连接词关联两字段

        Args:
            text: 用户输入的自然语言
            schemas: 表结构信息

        Returns:
            Tuple[ParsedRule, List] - 解析结果和候选列表
        """
        text_lower = text.lower()

        # 检测是否涉及多列关系比较
        relation_keywords = [
            # 时间比较
            '晚于', '早于', '先于', '后于',
            # 数值比较
            '大于', '小于', '不低于', '不高于', '高于', '低于', '少于', '多于', '超过',
        ]

        # 检测是否包含关系比较关键词
        has_relation = any(kw in text_lower for kw in relation_keywords)
        if not has_relation:
            return None, []

        # 构建专门的 LLM prompt 来解析多列关系
        schema_context = self._build_schema_context(schemas)
        data_card_context = self._build_data_card_context(schemas)
        dialect_context = get_dialect_prompt_context(self.db_type)

        prompt = f"""你是一个数据质量规则解析引擎，专门处理【单表内多字段比较关系】的质检规则。

## 任务
分析用户描述，判断是否涉及同一个表中两个字段的比较关系，如果是，生成正确的业务条件表达式。

## 核心概念

**业务条件**：当这条记录符合规则时，条件返回 TRUE。
**违规条件**：NOT(业务条件) = 违规

## 重要约束
- 只处理【单表内】两个字段的比较关系
- condition_expr 中直接使用列名，不需要加表名前缀
- 如果描述涉及多个表的字段关联，返回 null（这不是单表多列质检）
- condition_expr 必须是业务条件，表达"合格记录必须满足"的状态

## 用户描述
「{text}」

## 表结构和列信息
{schema_context}

## 数据卡片业务语义
{data_card_context}

## 数据库方言语法参考
{dialect_context['null_check_syntax']}

## 判断逻辑

请先判断用户描述是否涉及【同一个表中两个字段的比较关系】：

### 场景1：单表多列质检（应该处理）
- "订单的结束时间必须晚于开始时间" → 是
- "订单的实付金额不能大于原价金额" → 是
- "用户的结束日期必须晚于开始日期" → 是
- "收货地址不能和发货地址相同" → 是（同一表的两个地址字段比较）
- "数量不能少于最低库存" → 是

### 场景2：多表关联（不处理，返回 null）
- "订单金额应该等于明细表金额之和" → 否（涉及多表）
- "用户表中的用户名应该存在于权限表中" → 否（多表关联）

## 输出格式

请严格输出 JSON：
```json
{{
    "is_multi_column_relation": true|false,
    "target_table": "表名（如果判断为单表多列）",
    "column1": "第一个列名",
    "column2": "第二个列名",
    "relation_type": ">=|<=|>|<",
    "condition_expr": "业务条件（如：end_time >= start_time）",
    "rule_type": "multi_column_compare",
    "reasoning": "解析理由"
}}
```

如果 is_multi_column_relation 为 false，整个返回 null。

## 示例

### 示例1：结束时间晚于开始时间
- 输入: "订单的结束时间必须晚于开始时间"
- 输出: {{"is_multi_column_relation": true, "target_table": "orders", "column1": "end_time", "column2": "start_time", "relation_type": ">=", "condition_expr": "end_time >= start_time", "rule_type": "multi_column_compare", "reasoning": "用户描述了结束时间必须晚于开始时间的比较关系"}}

### 示例2：实付金额不能大于原价金额
- 输入: "订单的实付金额不能大于原价金额"
- 输出: {{"is_multi_column_relation": true, "target_table": "orders", "column1": "paid_amount", "column2": "original_amount", "relation_type": "<=", "condition_expr": "paid_amount <= original_amount", "rule_type": "multi_column_compare", "reasoning": "用户描述了实付金额不能超过原价金额的比较关系"}}

### 示例3：不是单表多列
- 输入: "用户名应该在用户表中存在"
- 输出: null
"""
        try:
            response = self.llm_client.chat(prompt)
            return self._parse_multi_column_response(response, text, schemas)
        except Exception as e:
            print(f"[ERROR] LLM 多列关系解析失败: {str(e)}")
            return None, []

    def _parse_multi_column_response(self, response: str, original_text: str, schemas: List[TableSchema]) -> Tuple[Optional[ParsedRule], List]:
        """解析 LLM 返回的多列关系结果"""
        try:
            json_str = self._extract_json(response)
            if not json_str:
                return None, []

            result = json.loads(json_str)
            if not result or result.get('is_multi_column_relation') is not True:
                return None, []

            target_table = result.get('target_table')
            column1 = result.get('column1')
            column2 = result.get('column2')
            condition_expr = result.get('condition_expr', '')
            reasoning = result.get('reasoning', '')

            if not all([target_table, column1, column2, condition_expr]):
                return None, []

            # 验证列名确实存在于表中
            col1_exists = self._verify_column_exists(target_table, column1, schemas)
            col2_exists = self._verify_column_exists(target_table, column2, schemas)

            if not col1_exists or not col2_exists:
                print(f"[WARN] 多列关系解析：列不存在 col1={column1}, col2={column2}")
                return None, []

            # 构建 ParsedRule
            conditions = [
                ColumnCondition(
                    column=column1,
                    rule_type='multi_column_compare',
                    condition=condition_expr,
                    description=f"与 {column2} 的比较关系"
                ),
                ColumnCondition(
                    column=column2,
                    rule_type='multi_column_compare',
                    condition=condition_expr,
                    description=f"与 {column1} 的比较关系"
                )
            ]

            return ParsedRule(
                rule_type='multi_column_compare',
                target_table=target_table,
                target_column=column1,  # 主字段
                condition_expr=condition_expr,  # 不含 column 占位符
                stage='multi_column',
                conditions=conditions,
                condition_mode='AND',
                severity=self._detect_severity(original_text.lower()),
                confidence=0.9,
                needs_confirmation=False,
                reasoning=reasoning,
                alternatives=[]
            ), []

        except (json.JSONDecodeError, TypeError) as e:
            print(f"[ERROR] 解析多列关系响应失败: {str(e)}")
            return None, []

    def _verify_column_exists(self, table_name: str, column_name: str, schemas: List[TableSchema]) -> bool:
        """验证列是否存在于指定表中"""
        for schema in schemas:
            if schema.table_name.lower() == table_name.lower():
                for col in schema.columns:
                    col_name = col.name if hasattr(col, 'name') else col.get('name')
                    if col_name.lower() == column_name.lower():
                        return True
        return False

    def _find_consistency_columns(
        self,
        field1_raw: str,
        field2_raw: str,
        schemas: List[TableSchema],
        target_table: str = None
    ) -> List[Dict]:
        """
        在表中查找与输入匹配的两个字段

        Args:
            field1_raw: 第一个字段的原始文本
            field2_raw: 第二个字段的原始文本
            schemas: 表结构信息
            target_table: 目标表名

        Returns:
            两个字段的匹配信息列表
        """
        field1_lower = field1_raw.lower().strip()
        field2_lower = field2_raw.lower().strip()

        for schema in schemas:
            # 如果指定了目标表，只在该表中查找
            if target_table and schema.table_name.lower() != target_table.lower():
                continue

            col1_match = None
            col2_match = None

            for col in schema.columns:
                col_name = col.name if hasattr(col, 'name') else col.get('name')
                col_comment = (col.comment or '').lower()
                col_name_lower = col_name.lower()

                # 匹配第一个字段
                if col1_match is None:
                    if (field1_lower == col_name_lower or
                        field1_lower in col_name_lower or
                        col_name_lower in field1_lower or
                        self._semantic_match(field1_lower, col_name_lower) or
                        self._semantic_match(field1_lower, col_comment)):
                        col1_match = {
                            'table': schema.table_name,
                            'column': col_name,
                            'col_obj': col
                        }

                # 匹配第二个字段
                if col2_match is None:
                    # 如果第一个字段已经匹配，跳过与第一个字段相同的列
                    if col1_match and col_name_lower == col1_match['column'].lower():
                        continue

                    if (field2_lower == col_name_lower or
                        field2_lower in col_name_lower or
                        col_name_lower in field2_lower or
                        self._semantic_match(field2_lower, col_name_lower) or
                        self._semantic_match(field2_lower, col_comment)):
                        col2_match = {
                            'table': schema.table_name,
                            'column': col_name,
                            'col_obj': col
                        }

            # 如果两个字段都匹配到了
            if col1_match and col2_match:
                return [col1_match, col2_match]

            # 如果只匹配到一个，尝试在同一张表的其他列中找另一个
            if col1_match and not col2_match:
                for col in schema.columns:
                    col_name = col.name if hasattr(col, 'name') else col.get('name')
                    col_comment = (col.comment or '').lower()
                    col_name_lower = col_name.lower()

                    # 跳过已匹配的列
                    if col_name_lower == col1_match['column'].lower():
                        continue

                    if (field2_lower == col_name_lower or
                        field2_lower in col_name_lower or
                        col_name_lower in field2_lower or
                        self._semantic_match(field2_lower, col_name_lower) or
                        self._semantic_match(field2_lower, col_comment)):
                        return [col1_match, {
                            'table': schema.table_name,
                            'column': col_name,
                            'col_obj': col
                        }]

            if col2_match and not col1_match:
                for col in schema.columns:
                    col_name = col.name if hasattr(col, 'name') else col.get('name')
                    col_comment = (col.comment or '').lower()
                    col_name_lower = col_name.lower()

                    if col_name_lower == col2_match['column'].lower():
                        continue

                    if (field1_lower == col_name_lower or
                        field1_lower in col_name_lower or
                        col_name_lower in field1_lower or
                        self._semantic_match(field1_lower, col_name_lower) or
                        self._semantic_match(field1_lower, col_comment)):
                        return [{
                            'table': schema.table_name,
                            'column': col_name,
                            'col_obj': col
                        }, col2_match]

        return []

    def _build_consistency_rule(
        self,
        original_text: str,
        col1: Dict,
        col2: Dict,
        schemas: List[TableSchema]
    ) -> ParsedRule:
        """
        构建一致性规则

        重要：存储的是【业务条件】（正向条件），不是违规条件！

        业务条件：{col1} = {col2} OR ({col1} IS NULL AND {col2} IS NULL)
        违规条件：NOT(业务条件) = {col1} <> {col2} OR ({col1} IS NULL) <> ({col2} IS NULL)

        SQL 执行层会根据 condition_expr 和 rule_type 动态生成违规 SQL。
        build_check_sql 中的 consistency_check 特殊处理会提取 col1 和 col2，
        直接构建违规条件（不用 NOT()，因为 NULL 值会导致问题）。
        """
        table_name = col1['table']
        col1_name = col1['column']
        col2_name = col2['column']

        # 【业务条件】：两列应相等，或双方都为 NULL
        # 合规记录必须满足：col1 = col2 OR (col1 IS NULL AND col2 IS NULL)
        condition_expr = f"({col1_name} = {col2_name} OR ({col1_name} IS NULL AND {col2_name} IS NULL))"

        return ParsedRule(
            rule_type='consistency_check',
            target_table=table_name,
            target_column=col1_name,  # 主字段
            condition_expr=condition_expr,  # 【业务条件】，SQL 层会处理
            stage='multi_column',
            conditions=None,  # 不设置 conditions，让 build_check_sql 走 consistency_check 特殊路径
            condition_mode='AND',
            severity=self._detect_severity(original_text.lower()),
            confidence=0.9,
            needs_confirmation=False,
            reasoning=f'一致性检测：{table_name}.{col1_name} 与 {col2_name} 的值应保持一致',
            alternatives=[]
        )

    def _detect_severity(self, text_lower: str) -> str:
        """检测严重级别"""
        if any(kw in text_lower for kw in ['必须', '严重', '关键', '重要', '负数', '过期']):
            return 'critical'
        if any(kw in text_lower for kw in ['建议', '应该', '最好', '最好不']):
            return 'info'
        return 'warning'

    def parse_with_column(
        self,
        user_input: str,
        schemas: List[TableSchema],
        target_table: str,
        target_column: str
    ) -> Tuple[Optional[ParsedRule], List]:
        """用户已指定表和列，强制使用 LLM 解析规则"""
        user_input_lower = user_input.lower()

        # 强制使用 LLM 解析（即使有 llm_client）
        if self.llm_client:
            try:
                # 构建 LLM 解析器
                llm_parser = RuleLLMParser(self.llm_client, self.db_type)

                # 构建上下文：只包含目标表的信息
                target_schemas = [s for s in schemas if s.table_name.lower() == target_table.lower()]
                if not target_schemas:
                    # 如果 schemas 中没有该表，创建一个简化版本
                    from controllers.governance.schema_context import TableSchema, ColumnInfo
                    target_schemas.append(TableSchema(
                        table_name=target_table,
                        columns=[
                            ColumnInfo(
                                name=target_column,
                                data_type='',
                                comment=''
                            )
                        ]
                    ))

                parsed, alternatives = llm_parser.parse_with_column(
                    user_input, target_schemas, target_table, target_column
                )

                if parsed:
                    return parsed, alternatives
            except Exception as e:
                print(f"[WARN] LLM 解析失败，使用模板兜底: {str(e)}")

        # LLM 失败时的兜底逻辑
        rule_type = self._detect_rule_type(user_input_lower) or 'threshold'
        condition_expr = self._get_condition_for_type(user_input_lower, rule_type)

        parsed = ParsedRule(
            rule_type=rule_type,
            target_table=target_table,
            target_column=target_column,
            condition_expr=condition_expr.replace('{col}', target_column),
            severity=self._detect_severity(user_input_lower),
            confidence=0.95,
            needs_confirmation=False,
            reasoning=f'在指定表 {target_table} 的列 {target_column} 上解析规则',
            alternatives=[]
        )

        return parsed, []

    def parse_for_table(
        self,
        user_input: str,
        schemas: List[TableSchema],
        target_table: str,
        inferred_columns: List[str] = None
    ) -> Tuple[Optional['ParsedRule'], List, str]:
        """
        用户只指定了表，需要推断使用哪一列

        核心逻辑：
        1. 如果第一阶段传入了 inferred_columns（多列），直接构建多列候选，让用户确认每个列
        2. 否则，优先使用 LLM 智能分析
        3. LLM 返回最佳匹配 + 候选列列表
        4. 如果 LLM 不可用，使用启发式规则但必须返回候选列表

        Returns:
            (parsed, alternatives, stage) 三元组
            - stage = 'multi_column_selection' 表示多列候选（第一阶段传来了多个列）
            - stage = 'column_selection'       表示正常表级规则解析
        """
        user_input_lower = user_input.lower()

        # 找到目标表
        target_schema = None
        for schema in schemas:
            if schema.table_name.lower() == target_table.lower():
                target_schema = schema
                break

        if not target_schema:
            return None, [], 'column_selection'

        # 识别规则类型
        rule_type = self._detect_rule_type(user_input_lower) or 'threshold'

        # 如果第一阶段传来了多列信息 → 直接进入多列候选流程
        if inferred_columns:
            parsed, alternatives = self._build_multi_column_candidates(
                user_input, target_schema, inferred_columns, rule_type
            )
            return parsed, alternatives, 'multi_column_selection'

        # 优先使用 LLM 智能分析
        if self.llm_client:
            # 直接让 LLM 分析用户描述的语义类型和结构
            return self._parse_with_llm_for_table(
                user_input, target_schema, rule_type
            )

        # LLM 不可用时，使用启发式规则但必须返回候选列表
        parsed, alternatives = self._parse_heuristic_for_table(
            user_input, target_schema, rule_type
        )
        return parsed, alternatives, 'column_selection'

    def _enrich_candidate_reasons_with_llm(
        self,
        user_input: str,
        schema: TableSchema,
        candidates: list
    ) -> None:
        """使用 LLM 为候选列生成详细的原因描述，就地修改 candidates 的 reason 字段

        当 inferred_columns 未携带 Stage 1 返回的详细 reason 时（如前端仅传递列名字符串），
        调用 LLM 为每个候选列生成类似 Stage 1 品质的 reason，而不是使用简单的 fallback 描述。
        """
        if not candidates or not self.llm_client:
            return

        # 检查是否已有 Stage 1 传来的详细 reason（有则不需要 LLM 补充）
        has_detailed_reason = any(
            c.get('reason', '') and '与规则相关' not in c.get('reason', '')
            and '未找到' not in c.get('reason', '')
            for c in candidates
        )
        if has_detailed_reason:
            return

        try:
            col_info_lines = []
            for col in schema.columns:
                col_name = col.name if hasattr(col, 'name') else col.get('name', '')
                col_type = col.data_type if hasattr(col, 'data_type') else col.get('data_type', '')
                col_comment = col.comment if hasattr(col, 'comment') else col.get('comment', '')
                col_info_lines.append(
                    f"- {col_name}（{col_type}）: {col_comment or '（无注释）'}"
                )

            candidate_names = [c['name'] for c in candidates]
            sub_conditions = {}
            for c in candidates:
                hint = c.get('condition_hint', '') or ''
                if hint and hint != user_input:
                    sub_conditions[c['name']] = hint

            table_parts = [schema.table_name]
            if schema.description:
                table_parts.append(schema.description)
            if schema.card_topic:
                table_parts.append(f"- 核心主题: {schema.card_topic}")
            if schema.card_abstract:
                table_parts.append(f"- 摘要: {schema.card_abstract}")
            if schema.card_entities:
                table_parts.append(f"- 核心实体: {', '.join(schema.card_entities)}")
            table_header = '\n'.join(table_parts)

            prompt = f"""你是一个数据质量规则解析专家。请为每个候选列生成详细的推断理由，说明该列为什么对应用户描述中的某个条件。

## 用户描述
{user_input}

## 目标表
{table_header}

## 候选列信息
{chr(10).join(col_info_lines)}

## 需要生成理由的列
{', '.join(candidate_names)}
"""
            if sub_conditions:
                prompt += "\n## 各列对应的子条件\n"
                for col, cond in sub_conditions.items():
                    prompt += f"- {col}: {cond}\n"

            prompt += """
## 输出要求
请严格输出 JSON 数组：
```json
[
    {
        "column": "列名",
        "reason": "详细推断理由（类似：price列的业务含义为商品的销售价格（常见区间39.00-2999.00元），直接对应用户需求中的第二个独立条件"价格不小于0"。必须具体说明该列的业务含义、数据类型、典型值，以及如何与用户描述中的特定条件关联）"
    }
]
```
每个 reason 必须：
1. 说明该列的业务含义（结合注释、数据卡片实体）
2. 说明该列的数据类型和典型值
3. 具体说明对应了用户描述中的哪个独立条件
4. 不少于 30 个中文字符
"""

            response = self.llm_client.chat(prompt)
            reasons = self._parse_column_reasons_response(response)

            if reasons:
                for c in candidates:
                    col_key = c['name'].lower()
                    enriched = reasons.get(col_key, '')
                    if enriched:
                        c['reason'] = enriched

        except Exception as e:
            print(f"[WARN] LLM 生成候选列详细理由失败: {str(e)}")

    def _parse_column_reasons_response(self, response: str) -> dict:
        """解析 LLM 返回的列 reason 数组，返回 {列名小写: reason} 字典"""
        import json
        import re

        try:
            json_str = None
            match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
            else:
                match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()

            if not json_str:
                return {}

            data = json.loads(json_str)
            if not isinstance(data, list):
                return {}

            result = {}
            for item in data:
                col_name = (item.get('column') or '').strip()
                reason = (item.get('reason') or '').strip()
                if col_name and reason:
                    result[col_name.lower()] = reason
            return result

        except Exception as e:
            print(f"[WARN] 解析列 reason 响应失败: {str(e)}")
            return {}

    def _build_multi_column_candidates(
        self,
        user_input: str,
        schema: 'TableSchema',
        inferred_columns,
        rule_type: str
    ) -> Tuple[Optional['ParsedRule'], List]:
        """
        根据第一阶段传来的多列信息，构建多列候选。

        inferred_columns 支持两种格式：
        - 列表字符串（前端传递）：["warehouse", "quantity"]
        - 列表字典（内部处理）：[{"column": "warehouse", "reason": "..."}]
        """
        # 先拆分用户输入为子条件，便于为每列匹配对应的条件描述
        condition_parts = self._split_conditions(user_input)

        # 建立列名到条件文本的映射
        col_condition_map = self._map_columns_to_conditions(
            inferred_columns, schema, condition_parts
        ) if condition_parts else {}

        # 统一转换为字符串列表，同时保留 Stage 1 LLM 返回的原始 reason（如果有）
        col_names = []
        # col_reason_map: 列名小写 → Stage 1 LLM 返回的 reason
        col_reason_map = {}
        if inferred_columns:
            for item in inferred_columns:
                if isinstance(item, dict):
                    col_name = (item.get('column') or '').strip()
                    llm_reason = (item.get('reason') or '').strip()
                elif isinstance(item, str):
                    col_name = item.strip()
                    llm_reason = ''
                else:
                    continue
                if col_name:
                    # 清除列名中的括号注释
                    import re as _re
                    col_name = _re.sub(r'（.+）$', '', col_name).strip()
                    col_name = _re.sub(r'\(.+\)$', '', col_name).strip()
                    if col_name:
                        col_names.append(col_name)
                        # 只在首次遇到该列时记录 reason（避免重复字典项覆盖）
                        col_key = col_name.lower()
                        if col_key not in col_reason_map and llm_reason:
                            col_reason_map[col_key] = llm_reason

        if not col_names:
            return None, []

        candidates = []
        for col_name in col_names:
            col_key = col_name.lower()

            # 检查列是否在表 schema 中存在
            col_exists = any(
                (c.name if hasattr(c, 'name') else c.get('name', '')).lower() == col_key
                for c in schema.columns
            )

            # 从 schema 中获取列类型和注释
            col_meta = {}
            for c in schema.columns:
                c_name = c.name if hasattr(c, 'name') else c.get('name', '')
                if c_name.lower() == col_key:
                    col_meta = {
                        'data_type': (c.data_type if hasattr(c, 'data_type') else c.get('data_type', '')),
                        'comment': (c.comment if hasattr(c, 'comment') else c.get('comment', ''))
                    }
                    break

            # 获取该列对应的子条件文本，独立检测 rule_type
            sub_condition_text = col_condition_map.get(col_name, user_input)
            col_rule_type = self._detect_rule_type(sub_condition_text.lower()) or rule_type

            # reason 构建优先级：
            # 1. Stage 1 LLM 返回的原始 reason（最有意义）
            # 2. 列注释 fallback
            # 3. 通用兜底
            llm_reason = col_reason_map.get(col_key, '')
            if llm_reason:
                reason = llm_reason
            elif col_meta.get('comment'):
                reason = f'字段 "{col_name}"（{col_meta["comment"]}）与规则相关'
            elif col_exists:
                reason = f'字段 "{col_name}" 与规则相关'
            else:
                reason = f'字段 "{col_name}" 在表中未找到，请确认列名是否正确'

            candidates.append({
                'name': col_name,
                'score': 1.0 if col_exists else 0.3,
                'reason': reason,
                'data_type': col_meta.get('data_type', ''),
                'comment': col_meta.get('comment', ''),
                'rule_type': col_rule_type,
                'condition_hint': sub_condition_text
            })

        if not candidates:
            return None, []

        # 使用 LLM 为候选列生成详细的原因描述（当 inferred_columns 未携带 Stage 1 的详细 reason 时）
        self._enrich_candidate_reasons_with_llm(user_input, schema, candidates)

        # 构建 ParsedRule：needs_confirmation=True，要求用户逐列确认
        best = candidates[0]
        parsed = ParsedRule(
            rule_type=rule_type,
            target_table=schema.table_name,
            target_column=best['name'],
            condition_expr='',
            severity=self._detect_severity(user_input.lower()),
            confidence=0.6,
            needs_confirmation=True,
            reasoning=f'检测到您的描述涉及 {len(candidates)} 个字段（{", ".join([c["name"] for c in candidates])}），请分别确认每个字段对应的规则',
            alternatives=candidates
        )
        return parsed, candidates

    def _parse_with_llm_for_table(
        self,
        user_input: str,
        schema: TableSchema,
        rule_type: str
    ) -> Tuple[Optional[ParsedRule], List, str]:
        """
        使用 LLM 智能分析列匹配

        LLM 会结合：
        1. 用户输入的自然语言（理解业务意图）
        2. 数据卡片信息（card_entities, card_topic, card_abstract）
        3. 列注释和列名（结构信息）

        Returns:
            (parsed, alternatives, stage) 三元组
        """
        # 构建详细的上下文信息供 LLM 分析
        schema_context = self._build_schema_context_for_llm_analysis(schema)
        data_card_context = self._build_data_card_context_for_llm(schema)

        # 构建 LLM Prompt
        prompt = self._build_column_selection_prompt(
            user_input=user_input,
            schema_context=schema_context,
            data_card_context=data_card_context,
            rule_type=rule_type
        )

        try:
            response = self.llm_client.chat(prompt)
            result = self._parse_llm_column_response(response, schema.table_name, rule_type, schema)
            if result:
                return result
        except Exception as e:
            print(f"[WARN] LLM 列匹配失败: {str(e)}")

        # LLM 失败时，使用启发式规则
        parsed, alternatives = self._parse_heuristic_for_table(user_input, schema, rule_type)
        return parsed, alternatives, 'column_selection'

    def _build_schema_context_for_llm_analysis(self, schema: TableSchema) -> str:
        """构建供 LLM 分析的 Schema 信息"""
        lines = []
        lines.append(f"表名: {schema.table_name}")
        if schema.description:
            lines.append(f"表描述: {schema.description}")
        lines.append("")
        lines.append("列信息:")
        lines.append("| 列名 | 数据类型 | 注释 |")
        lines.append("|------|----------|------|")
        for col in schema.columns:
            col_name = col.name if hasattr(col, 'name') else col.get('name', '')
            col_type = col.data_type if hasattr(col, 'data_type') else col.get('data_type', '')
            col_comment = col.comment if hasattr(col, 'comment') else col.get('comment', '')
            lines.append(f"| {col_name} | {col_type} | {col_comment} |")
        return '\n'.join(lines)

    def _build_data_card_context_for_llm(self, schema: TableSchema) -> str:
        """构建供 LLM 分析的数据卡片信息"""
        lines = []
        if schema.card_topic:
            lines.append(f"核心主题: {schema.card_topic}")
        if schema.card_abstract:
            lines.append(f"摘要: {schema.card_abstract}")
        if schema.card_entities:
            lines.append(f"核心实体: {', '.join(schema.card_entities)}")
        if schema.card_tags:
            lines.append(f"标签: {', '.join(schema.card_tags)}")
        if schema.card_scenarios:
            lines.append(f"适用场景: {', '.join(schema.card_scenarios)}")
        return '\n'.join(lines) if lines else "（无可用数据卡片信息）"

    def _build_column_selection_prompt(
        self,
        user_input: str,
        schema_context: str,
        data_card_context: str,
        rule_type: str
    ) -> str:
        """构建列选择的 LLM Prompt"""
        return """你是一个数据质量规则解析专家。你需要分析用户的自然语言描述，判断其语义类型，然后选择最合适的列。

## 重要优先级说明
- **数据卡片信息优先级最高**：列的业务含义、注释都存储在数据卡片中，经过 LLM 增强
- 数据库原始注释可能不完整，应优先参考数据卡片信息
- 当两者不一致时，以数据卡片为准

## 用户描述
"{user_input}"

## 数据卡片业务语义（优先级最高）
{data_card_context}

## 表结构信息（参考）
{schema_context}

## 规则类型（参考）
{rule_type}

## 你的任务
1. **理解用户描述的业务意图**
2. **判断描述的语义类型**（见下方详细说明）
3. 根据语义类型选择合适的列
4. 返回结构化的解析结果

## 语义类型判断规则（核心）

### 类型A：单表多列一致性检测
**特征**：描述中涉及同一个表中两个字段的值应该"相同"、"一致"、"匹配"、"相符"。
**识别方式**：根据语义理解，而不是关键词匹配。
**示例**：
- "证件姓名需要和客户姓名相同" → 两列应相同
- "收货人要和下单人一致" → 两列应相同
- "两个地址要匹配" → 两列应相同
- "手机号要和注册手机号相符" → 两列应相同
- "AB列的值应该相等" → 两列应相同

**处理方式**：找出这两个字段，生成一致性检测条件。

### 类型B：单表内多字段比较关系
**特征**：描述中涉及同一个表中两个字段的比较关系（如大小、时间先后）。
**识别方式**：根据语义理解。
**示例**：
- "结束时间必须晚于开始时间" → end_time > start_time
- "实付金额不能大于原价金额" → paid_amount <= original_amount
- "数量要少于最低库存" → quantity < min_stock
- "结束日期要在开始日期之后" → end_date > start_date

**处理方式**：找出这两个字段和比较关系，生成比较条件。

### 类型C：单列检测
**特征**：描述中只涉及一个字段的各种检测（空值、格式、枚举、范围等）。
**示例**：
- "用户名不能为空" → 单列空值检测
- "手机号格式要正确" → 单列格式检测
- "状态只能是已处理或已拒绝" → 单列枚举检测
- "金额不能为负数" → 单列范围检测

**处理方式**：找出对应的单个字段。

### 类型D：多条件组合
**特征**：描述中包含多个独立的检测条件（通常由"且"、"和"等连接）。
**示例**：
- "用户名不能为空且金额要大于0" → 两个独立条件
- "名称不为空且状态是已处理" → 两个独立条件

**处理方式**：将每个条件分别与对应的列关联。

## 输出要求

请严格输出 JSON：
```json
{{
    "semantic_type": "类型标识（A/B/C/D）",
    "semantic_type_description": "类型描述（如：一表内两列一致性检测）",

    // 类型A（一致性检测）需要返回：
    "column1": "第一个列名",
    "column2": "第二个列名",
    "condition_expr": "两列一致性检测的表达式（如：col1 <> col2 OR (col1 IS NULL) <> (col2 IS NULL)）",

    // 类型B（比较关系）需要返回：
    "column1": "第一个列名（如结束时间）",
    "column2": "第二个列名（如开始时间）",
    "relation": "比较关系（>=、<=、>、<）",
    "condition_expr": "比较表达式（如：end_time >= start_time）",

    // 类型C（单列检测）需要返回：
    "column": "列名",
    "condition_expr": "条件表达式",

    // 类型D（多条件组合）需要返回：
    "conditions": [
        {{"column": "列1", "condition": "条件1"}},
        {{"column": "列2", "condition": "条件2"}}
    ],

    "best_match": {{
        "column": "最佳匹配的列名",
        "confidence": 0.95,
        "reasoning": "选择理由：结合业务语义和数据结构分析"
    }},

    "candidates": [
        {{
            "column": "候选列名1",
            "score": 0.85,
            "reasoning": "候选理由"
        }},
        {{
            "column": "候选列名2",
            "score": 0.70,
            "reasoning": "候选理由"
        }}
    ],

    "confidence": 0.95,
    "reasoning": "整体解析理由"
}}
```

## 重要说明
- **semantic_type 是最关键的判断**：根据语义判断用户描述属于哪种类型
- 对于类型A和B，必须返回两个列名
- reasoning 必须具体说明为什么选择这两个列，以及它们在业务上代表什么含义
- 结合数据卡片的业务语义（如 key_entities、card_topic）来理解用户意图
- 如果不确定，给出多个候选列供用户确认
""".format(
            user_input=user_input,
            data_card_context=data_card_context,
            schema_context=schema_context,
            rule_type=rule_type
        )

    def _parse_llm_column_response(
        self,
        response: str,
        table_name: str,
        rule_type: str,
        schema: TableSchema = None
    ) -> Optional[Tuple[ParsedRule, List, str]]:
        """解析 LLM 返回的列选择结果

        支持语义类型判断：
        1. 类型A（consistency）：一致性检测，两列应相同
        2. 类型B（comparison）：比较关系，如结束时间晚于开始时间
        3. 类型C（single）：单列检测
        4. 类型D（multi_condition）：多条件组合

        Returns:
            (parsed, alternatives, stage) 三元组
        """
        try:
            import json
            import re

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
                return None

            data = json.loads(json_str)

            # ========================================
            # 类型A：一致性检测（两列应相同）
            # ========================================
            semantic_type = data.get('semantic_type', '')
            if semantic_type in ['A', 'consistency', '一致性检测']:
                col1 = (data.get('column1') or '').strip()
                col2 = (data.get('column2') or '').strip()
                condition_expr = (data.get('condition_expr') or '').strip()
                reasoning = data.get('reasoning', '')
                confidence = data.get('confidence', 0.9)

                if col1 and col2:
                    # 业务条件：两列应相等，或双方都为 NULL
                    # 合规条件：col1 = col2 OR (col1 IS NULL AND col2 IS NULL)
                    # 违规条件：(col1 <> col2) OR (col1 IS NULL) <> (col2 IS NULL)
                    business_condition = f"({col1} = {col2} OR ({col1} IS NULL AND {col2} IS NULL))"

                    # 注意：不设置 parsed.conditions，让 _build_response 走单列分支，
                    # 这样 build_check_sql 会正确处理 consistency_check 的特殊逻辑
                    parsed = ParsedRule(
                        rule_type='consistency_check',
                        target_table=table_name,
                        target_column=col1,
                        condition_expr=business_condition,
                        stage='rule_preview',
                        conditions=None,  # 不设置 conditions，避免走 build_multi_condition_sql
                        condition_mode='AND',
                        severity=self._detect_severity(''),
                        confidence=confidence,
                        needs_confirmation=False,
                        reasoning=reasoning or f'一致性检测：{col1} 与 {col2} 的值应保持一致',
                        alternatives=[]
                    )
                    return parsed, [], 'rule_preview'

            # ========================================
            # 类型B：比较关系（结束时间晚于开始时间等）
            # ========================================
            if semantic_type in ['B', 'comparison', '比较关系']:
                col1 = (data.get('column1') or '').strip()
                col2 = (data.get('column2') or '').strip()
                condition_expr = (data.get('condition_expr') or '').strip()
                reasoning = data.get('reasoning', '')
                confidence = data.get('confidence', 0.9)

                if col1 and col2:
                    conditions = [
                        ColumnCondition(
                            column=col1,
                            rule_type='multi_column_compare',
                            condition=condition_expr,
                            description=f"与 {col2} 的比较关系"
                        ),
                        ColumnCondition(
                            column=col2,
                            rule_type='multi_column_compare',
                            condition=condition_expr,
                            description=f"与 {col1} 的比较关系"
                        )
                    ]

                    parsed = ParsedRule(
                        rule_type='multi_column_compare',
                        target_table=table_name,
                        target_column=col1,
                        condition_expr=condition_expr,
                        stage='rule_preview',
                        conditions=conditions,
                        condition_mode='AND',
                        severity=self._detect_severity(''),
                        confidence=confidence,
                        needs_confirmation=False,
                        reasoning=reasoning or f'多列比较：{col1} 与 {col2} 的比较关系',
                        alternatives=[]
                    )
                    return parsed, [], 'rule_preview'

            # ========================================
            # 类型D：多条件组合
            # ========================================
            conditions = data.get('conditions', [])
            multi_condition_detected = data.get('multi_condition_detected', False) or len(conditions) > 1

            if conditions and multi_condition_detected:
                return self._parse_multi_condition_response(
                    data, conditions, table_name, rule_type, schema
                )

            # ========================================
            # 类型C：单列检测（默认行为）
            # ========================================
            best_match = data.get('best_match', {})
            best_column = best_match.get('column')
            if not best_column:
                return None

            condition_expr = self._get_condition_for_type('', rule_type)
            condition_expr = condition_expr.replace('{col}', best_column)

            parsed = ParsedRule(
                rule_type=rule_type,
                target_table=table_name,
                target_column=best_column,
                condition_expr=condition_expr,
                severity=self._detect_severity(''),
                confidence=best_match.get('confidence', 0.8),
                needs_confirmation=best_match.get('confidence', 0.8) < 0.9,
                reasoning=best_match.get('reasoning', ''),
                alternatives=[]
            )

            # 从 schema 中获取候选列的 data_type 和 comment
            def _get_col_meta(schema, col_name):
                """从 schema 中查找列的 data_type 和 comment"""
                if not schema or not col_name:
                    return '', ''
                for c in (schema.columns or []):
                    c_name = c.name if hasattr(c, 'name') else c.get('name', '')
                    if c_name.lower() == col_name.lower():
                        return (
                            (c.data_type if hasattr(c, 'data_type') else c.get('data_type', '')) or '',
                            (c.comment if hasattr(c, 'comment') else c.get('comment', '')) or ''
                        )
                return '', ''

            alternatives = []
            for cand in data.get('candidates', []):
                col = cand.get('column')
                if col and col != best_column:
                    data_type, comment = _get_col_meta(schema, col)
                    alternatives.append({
                        'name': col,
                        'score': cand.get('score', 0.5),
                        'reason': cand.get('reasoning', ''),
                        'data_type': data_type,
                        'comment': comment
                    })

            return parsed, alternatives, 'column_selection'

        except Exception as e:
            print(f"[WARN] 解析 LLM 列选择响应失败: {str(e)}")
            return None

    def _parse_multi_condition_response(
        self,
        data: dict,
        conditions: list,
        table_name: str,
        rule_type: str,
        schema: TableSchema = None
    ) -> Tuple[ParsedRule, List, str]:
        """解析多条件 LLM 响应，构建多列候选

        Args:
            data: 完整 LLM 响应 JSON
            conditions: conditions 数组
            table_name: 目标表名
            rule_type: 规则类型
            schema: 表结构信息（含列的 data_type 和 comment）

        Returns:
            (parsed, candidates, 'multi_column_selection')
        """
        def _get_col_meta(schema, col_name):
            """从 schema 中查找列的 data_type 和 comment"""
            if not schema or not col_name:
                return '', ''
            for c in (schema.columns or []):
                c_name = c.name if hasattr(c, 'name') else c.get('name', '')
                if c_name.lower() == col_name.lower():
                    return (
                        (c.data_type if hasattr(c, 'data_type') else c.get('data_type', '')) or '',
                        (c.comment if hasattr(c, 'comment') else c.get('comment', '')) or ''
                    )
            return '', ''

        candidates = []
        # 去重：同一个列可能出现多次（LLM 可能对同一列给出多个条件）
        seen_columns = set()

        for cond in conditions:
            col_name = (cond.get('column') or '').strip()
            if not col_name:
                continue

            # 清除列名中的括号注释
            import re as _re
            col_name = _re.sub(r'（.+）$', '', col_name).strip()
            col_name = _re.sub(r'\(.+\)$', '', col_name).strip()

            if not col_name or col_name in seen_columns:
                continue
            seen_columns.add(col_name)

            # 优先用 LLM 返回的详细 reasoning 构建 reason；fallback 到原有的条件描述格式
            llm_reasoning = cond.get('reasoning', '').strip()
            if llm_reasoning:
                reason = llm_reasoning
            else:
                reason = f'字段 "{col_name}" 对应条件：{cond.get("condition", "")}'

            # 每个列独立检测 rule_type（从子条件文本推断，而非共用全局 rule_type）
            cond_text = cond.get('condition', '') or ''
            col_rule_type = self._detect_rule_type(cond_text.lower()) or rule_type

            # 从 schema 中获取列的 data_type 和 comment
            col_data_type, col_comment = _get_col_meta(schema, col_name)

            candidates.append({
                'name': col_name,
                'score': cond.get('confidence', 0.9),
                'reason': reason,
                'data_type': col_data_type,
                'comment': col_comment,
                'rule_type': col_rule_type,
                'condition_hint': cond.get('condition', '')
            })

        if not candidates:
            return None, [], 'multi_column_selection'

        # 构建 ParsedRule（best_match 为最高分候选）
        best = candidates[0]
        condition_expr = self._get_condition_for_type('', rule_type)
        condition_expr = condition_expr.replace('{col}', best['name'])

        parsed = ParsedRule(
            rule_type=rule_type,
            target_table=table_name,
            target_column=best['name'],
            condition_expr=condition_expr,
            severity=self._detect_severity(''),
            confidence=sum(c['score'] for c in candidates) / len(candidates),
            needs_confirmation=True,
            reasoning=f'检测到您的描述涉及 {len(candidates)} 个字段（{", ".join([c["name"] for c in candidates])}），请分别确认每个字段对应的规则',
            alternatives=candidates
        )

        return parsed, candidates, 'multi_column_selection'

    def _parse_heuristic_for_table(
        self,
        user_input: str,
        schema: TableSchema,
        rule_type: str
    ) -> Tuple[Optional[ParsedRule], List, str]:
        """
        启发式规则（当 LLM 不可用时的兜底方案）

        重要：必须返回候选列表，不能直接选择一个列

        Returns:
            (parsed, alternatives, stage) 三元组
        """
        candidates = []

        # 收集所有列作为候选
        for col in schema.columns:
            col_name = col.name if hasattr(col, 'name') else col.get('name', '')
            col_comment = col.comment if hasattr(col, 'comment') else col.get('comment', '')
            col_type = col.data_type if hasattr(col, 'data_type') else col.get('data_type', '')

            # 简单规则匹配
            score = 0.5  # 基础分

            # 检查列注释
            if col_comment:
                comment_lower = col_comment.lower()
                if any(kw in user_input.lower() for kw in [col_comment, col_name]):
                    score = 0.8

            # 检查列名
            col_name_lower = col_name.lower()
            if any(kw in user_input.lower() for kw in col_name_lower.split('_')):
                score = max(score, 0.7)

            # 检查数据卡片 entities
            if schema.card_entities:
                for entity in schema.card_entities:
                    entity_lower = entity.lower()
                    if entity_lower in col_name_lower or entity_lower in (col_comment or '').lower():
                        score = max(score, 0.75)

            candidates.append({
                'name': col_name,
                'score': score,
                'reason': f"候选列 {col_name}（类型: {col_type}，注释: {col_comment or '无'}）",
                'data_type': col_type,
                'comment': col_comment
            })

        # 按分数排序
        candidates.sort(key=lambda x: x['score'], reverse=True)

        if not candidates:
            return None, [], 'column_selection'

        # 检测多条件：从输入中判断是否包含多个独立条件
        user_lower = user_input.lower()
        multi_condition_keywords = ['且', '并且', '而且', '同时', 'and ', ' and', '&']
        has_multi_condition = any(kw in user_lower for kw in multi_condition_keywords)

        # 收集所有得分较高的列（score >= 0.7）
        matched_cols = [c for c in candidates if c['score'] >= 0.7]

        # 如果检测到多条件，或者有多个较高分数的列 → 进入 multi_column_selection
        if has_multi_condition or len(matched_cols) >= 2:
            multi_candidates = matched_cols if matched_cols else candidates[:3]

            # 拆分用户输入，为每个候选列匹配对应的子条件，独立检测 rule_type
            condition_parts = self._split_conditions(user_input)
            part_texts = [p['text'] for p in condition_parts] if len(condition_parts) > 1 else []

            # 建立列名到子条件文本的映射（复用 _map_columns_to_conditions 的逻辑）
            col_to_cond = self._map_columns_to_conditions_inline(
                multi_candidates, schema, condition_parts
            ) if part_texts else {}

            for mc in multi_candidates:
                sub_text = col_to_cond.get(mc['name'], user_input)
                mc['rule_type'] = self._detect_rule_type(sub_text.lower()) or rule_type
                mc['condition_hint'] = sub_text

            multi_parsed = ParsedRule(
                rule_type=rule_type,
                target_table=schema.table_name,
                target_column=multi_candidates[0]['name'],
                condition_expr=self._get_condition_for_type(user_lower, rule_type).replace('{col}', multi_candidates[0]['name']),
                severity=self._detect_severity(user_lower),
                confidence=sum(c['score'] for c in multi_candidates) / len(multi_candidates),
                needs_confirmation=True,
                reasoning=f'检测到您的描述涉及 {len(multi_candidates)} 个字段（{", ".join([c["name"] for c in multi_candidates])}），请分别确认每个字段对应的规则',
                alternatives=multi_candidates
            )
            return multi_parsed, multi_candidates, 'multi_column_selection'

        # 单条件模式
        best = candidates[0]
        condition_expr = self._get_condition_for_type(user_lower, rule_type)
        condition_expr = condition_expr.replace('{col}', best['name'])

        parsed = ParsedRule(
            rule_type=rule_type,
            target_table=schema.table_name,
            target_column=best['name'],
            condition_expr=condition_expr,
            severity=self._detect_severity(user_lower),
            confidence=best['score'],
            needs_confirmation=True,
            reasoning=f"找到可能的列 {best['name']}，请确认或选择其他候选",
            alternatives=candidates[1:6]
        )

        return parsed, candidates[1:6], 'column_selection'


def parse_rule_with_llm(user_input: str, llm_client, db_type: str, schemas: List[TableSchema] = None) -> Optional[ParsedRule]:
    parser = RuleLLMParser(llm_client, db_type)
    result, _ = parser.parse(user_input, schemas)
    return result


def parse_rule_smart(user_input: str, llm_client=None, db_type: str = 'postgresql', schemas: List[TableSchema] = None, mode: str = 'auto') -> Optional[ParsedRule]:
    parser = SmartRuleParser(llm_client, db_type)
    result, _ = parser.parse(user_input, schemas, mode)
    return result
