"""
@File: condition_generator.py
@Description: 条件生成器 - 支持自然语言和 SQL 两种方式定义规则条件
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-02

核心能力：
1. SQL 表达式直接使用
2. 自然语言 → NL2SQL → 解析为条件
3. 多表批量执行时，自动识别列并生成对应条件
4. 支持方言适配（跨数据库类型）
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from controllers.governance.dialect_adapter import DialectAdapter


@dataclass
class ColumnInfo:
    """列信息"""
    table_name: str
    column_name: str
    data_type: str
    comment: str = ""


@dataclass
class RuleCondition:
    """规则条件"""
    table_name: str
    column_name: str
    condition_expr: str
    rule_type: str
    generated_sql: str = ""


class ConditionGenerator:
    """
    条件生成器

    支持两种输入方式：
    1. SQL 表达式：直接使用用户输入的条件
    2. 自然语言：通过 NL2SQL 解析为条件
    """

    # 预定义的自然语言映射
    NATURAL_LANGUAGE_PATTERNS = {
        # 空值相关
        r'为空|是空|没有值|未填写|缺失': 'IS NULL OR {column} = \'\'',
        r'不为空|非空|已填写|有值': 'IS NOT NULL AND {column} != \'\'',

        # 格式相关
        r'手机号|电话号码|电话': '~* \'^1[3-9]\\d{{9}}$\'',
        r'邮箱|email': '~* \'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{{2,}}$\'',
        r'身份证号.*18位|18位身份证|身份证.*18位': '~* \'^[1-9]\\d{{5}}(18|19|20)\\d{{2}}(0[1-9]|1[0-2])(0[1-9]|[12]\\d|3[01])\\d{{3}}[\\dXx]$\'',
        r'身份证(?!.*15位)|身份证号': '~* \'^[1-9]\\d{{5}}(18|19|20)\\d{{2}}(0[1-9]|1[0-2])(0[1-9]|[12]\\d|3[01])\\d{{3}}[\\dXx]$\'',
        r'邮编|邮政编码': '~* \'^\\d{{6}}$\'',
        r'URL|网址': '~* \'^https?://[\\w.-]+\\.[a-zA-Z]{2,}.*$\'',

        # 格式相关 - 行政区划
        r'行政区划|行政区域|区划代码|区划6位|6位区划': '~* \'^\\d{{6}}$\'',

        # 格式相关 - 日期时间（正则中的 {数字} 需要用 {{数字}} 转义）
        r'日期.*YYYY.*HH.*SS|标准日期.*YYYY|统一日期.*格式': '~* \'^\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}:\\d{{2}}$\'',
        r'yyyy.*mm.*dd.*hh.*ss|yyyy-mm-dd.*hh:mm:ss|标准时间格式': '~* \'^\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}:\\d{{2}}$\'',
        r'日期格式|时间格式|日期统一|时间统一': '~* \'^\\d{{4}}-\\d{{2}}-\\d{{2}} \\d{{2}}:\\d{{2}}:\\d{{2}}$\'',

        # 数值相关
        r'正数|大于0': '> 0',
        r'负数|小于0': '< 0',
        r'零|等于0': '= 0',
        r'整数': '= CAST({column} AS BIGINT)',
        r'不小于0|大于等于0|不能小于0': '>= 0',
        r'不能为负|不为负|非负': '>= 0',

        # 枚举值相关（性别等）
        r'性别.*只能是|只能是.*男.*女|男或女|男女': 'IN (\'男\', \'女\')',
        r'性别.*男|性别.*女|只能是男|只能男|只能是女|只能女': None,  # 需要特殊处理
        r'状态.*只能是|只能是.*启用.*禁用|启用.*禁用': None,  # 需要特殊处理

        # 长度相关
        r'长度.*\d+': None,  # 需要提取具体数字
        r'超过.*长度': None,
        r'少于.*长度': None,

        # 范围相关
        r'在.*范围内': None,  # 需要提取范围
        r'大于|超过|高于': '> {value}',
        r'小于|低于': '< {value}',

        # 日期相关
        r'是未来|在未来': '> NOW()',
        r'是过去|在过去': '< NOW()',
        r'今天': '= CURRENT_DATE',
        r'本周': '>= DATE_TRUNC(\'week\', CURRENT_DATE)',
        r'本月': '>= DATE_TRUNC(\'month\', CURRENT_DATE)',
        r'\d+天前': '< NOW() - INTERVAL \'{days} days\'',
    }

    def __init__(self, llm_client=None, db_type: str = 'postgresql'):
        """
        初始化条件生成器

        Args:
            llm_client: LLM 客户端（用于自然语言解析），可选
            db_type: 数据库类型（用于方言适配），默认 postgresql
        """
        self.llm_client = llm_client
        self.db_type = db_type.lower()
        self.dialect_adapter = DialectAdapter(db_type)

    def generate_condition(
        self,
        rule_type: str,
        table_name: str,
        column_name: str,
        user_input: str,
        is_natural_language: bool = False
    ) -> RuleCondition:
        """
        生成规则条件

        Args:
            rule_type: 规则类型
            table_name: 表名
            column_name: 列名
            user_input: 用户输入（SQL 表达式或自然语言）
            is_natural_language: 是否为自然语言

        Returns:
            RuleCondition 对象
        """
        if is_natural_language:
            condition_expr = self._parse_natural_language(user_input, column_name, rule_type)
        else:
            # 用户输入为空时，生成默认条件
            if not user_input or not user_input.strip():
                condition_expr = self._generate_default_condition(rule_type, column_name)
            else:
                # 替换 column 占位符为实际列名
                condition_expr = self._replace_column_placeholder(user_input, column_name)

        return RuleCondition(
            table_name=table_name,
            column_name=column_name,
            condition_expr=condition_expr,
            rule_type=rule_type
        )

    def _generate_default_condition(self, rule_type: str, column_name: str) -> str:
        """
        根据规则类型生成默认条件表达式

        Args:
            rule_type: 规则类型
            column_name: 列名

        Returns:
            默认的 SQL 条件表达式
        """
        if rule_type == 'null_check':
            # 空值检测：IS NOT NULL AND != ''
            return f"{column_name} IS NOT NULL AND {column_name} != ''"

        elif rule_type == 'unique':
            # 唯一性检测：非空值
            return "1=1"  # 唯一性检测使用特殊逻辑，不在这里处理

        elif rule_type == 'threshold':
            # 阈值检测：大于 0
            return f"{column_name} > 0"

        elif rule_type == 'format':
            # 格式检测：非空（基本格式验证）
            return f"{column_name} IS NOT NULL"

        elif rule_type == 'range_check':
            # 范围检测：非空
            return f"{column_name} IS NOT NULL"

        elif rule_type == 'enum':
            # 枚举检测：非空
            return f"{column_name} IS NOT NULL"

        else:
            # 默认：非空
            return f"{column_name} IS NOT NULL"

    def _parse_natural_language(self, text: str, column_name: str, rule_type: str) -> str:
        """
        解析自然语言为条件表达式

        Args:
            text: 自然语言文本
            column_name: 列名
            rule_type: 规则类型

        Returns:
            条件表达式
        """
        # 1. 尝试预定义模式匹配
        for pattern, expr in self.NATURAL_LANGUAGE_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                if expr is None:
                    continue  # 需要特殊处理
                return expr.format(column=column_name)

        # 2. 尝试特殊模式处理（枚举值、长度、范围等）
        special_result = self._handle_special_patterns(text, column_name, rule_type)
        if special_result:
            return special_result

        # 3. 如果配置了 LLM，尝试使用 NL2SQL
        if self.llm_client:
            return self._nl2sql(text, column_name, rule_type)

        # 4. 默认返回通用条件
        return f'{column_name} IS NOT NULL'

    def _handle_special_patterns(self, text: str, column_name: str, rule_type: str) -> Optional[str]:
        """
        处理需要特殊提取的模式（枚举值、长度、范围等）

        Args:
            text: 自然语言文本
            column_name: 列名
            rule_type: 规则类型

        Returns:
            条件表达式，如果没有匹配则返回 None
        """
        # 枚举值提取
        enum_values = self._extract_enum_values(text)
        if enum_values:
            # 构建 IN 条件
            quoted_values = ', '.join([f"'{v}'" for v in enum_values])
            return f"{column_name} IN ({quoted_values})"

        # 范围值提取
        range_result = self._extract_range_values(text, column_name)
        if range_result:
            return range_result

        # 长度值提取
        length_result = self._extract_length(text, column_name)
        if length_result:
            return length_result

        return None

    def _extract_enum_values(self, text: str) -> Optional[List[str]]:
        """
        从文本中提取枚举值

        支持的格式：
        - "只能是男或女" -> ["男", "女"]
        - "只能是A,B,C" -> ["A", "B", "C"]
        - "允许值为男/女" -> ["男", "女"]

        Args:
            text: 自然语言文本

        Returns:
            枚举值列表
        """
        # 预处理文本
        text = text.strip()

        # 性别枚举值快速识别
        if re.search(r'性别.*男.*女|男或女|男女', text):
            return ['男', '女']

        if re.search(r'性别.*男[^女]', text):
            return ['男']
        if re.search(r'性别.*女', text):
            return ['女']

        # 启用/禁用状态
        if re.search(r'启用.*禁用|状态.*只能是', text):
            return ['启用', '禁用']

        # 通用枚举提取：只能是A,B,C 或 允许值为A,B,C
        # 匹配 "只能是XXX" 或 "允许值为XXX" 后面的内容
        patterns = [
            r'只能是[：:]([^\s，,]+(?:[，,]\s*[^\s，,]+)*)',
            r'允许值为[：:]([^\s，,]+(?:[，,]\s*[^\s，,]+)*)',
            r'枚举[：:]([^\s，,]+(?:[，,]\s*[^\s，,]+)*)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                values_str = match.group(1)
                # 分割并清理值
                values = re.split(r'[，,\s/]+', values_str)
                values = [v.strip() for v in values if v.strip()]
                if values:
                    return values

        # 匹配用顿号、逗号分隔的枚举值
        enum_match = re.search(r'只能是\s*[""\"\']([^""\'"]+)[""\']|只能是\s*([^\s]+(?:\s+[^\s]+)?)', text)
        if enum_match:
            values = enum_match.group(1) or enum_match.group(2)
            if values:
                # 尝试用多种分隔符分割
                for sep in [',', '，', '/', '、']:
                    if sep in values:
                        return [v.strip() for v in values.split(sep) if v.strip()]

        return None

    def _extract_range_values(self, text: str, column_name: str) -> Optional[str]:
        """
        从文本中提取范围值

        支持的格式：
        - "在1-100之间" -> col >= 1 AND col <= 100
        - "范围1到100" -> col >= 1 AND col <= 100
        - "大于100且小于200" -> col > 100 AND col < 200

        Args:
            text: 自然语言文本
            column_name: 列名

        Returns:
            范围条件表达式
        """
        # 匹配 "在X-Y之间" 或 "X到Y"
        range_pattern = r'(?:在|从|)\s*(\d+(?:\.\d+)?)\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*(?:之间|)'
        match = re.search(range_pattern, text)
        if match:
            min_val, max_val = match.groups()
            return f"{column_name} >= {min_val} AND {column_name} <= {max_val}"

        # 匹配 "大于X且小于Y"
        and_pattern = r'大于\s*(\d+(?:\.\d+)?)\s*(?:且|并且|and)\s*(?:小于|低于)\s*(\d+(?:\.\d+)?)'
        match = re.search(and_pattern, text)
        if match:
            gt_val, lt_val = match.groups()
            return f"{column_name} > {gt_val} AND {column_name} < {lt_val}"

        # 匹配 "大于X" 或 "不小于X"
        gt_pattern = r'(?:大于|超过|高于|不小于|至少|最小)\s*(\d+(?:\.\d+)?)'
        match = re.search(gt_pattern, text)
        if match and '且' not in text and '并且' not in text:
            return f"{column_name} >= {match.group(1)}"

        # 匹配 "小于X" 或 "不超过X"
        lt_pattern = r'(?:小于|低于|不超过|至多|最大)\s*(\d+(?:\.\d+)?)'
        match = re.search(lt_pattern, text)
        if match and '且' not in text and '并且' not in text:
            return f"{column_name} <= {match.group(1)}"

        return None

    def _extract_length(self, text: str, column_name: str) -> Optional[str]:
        """
        从文本中提取长度限制

        支持的格式：
        - "长度不超过100" -> LENGTH(col) <= 100
        - "字符数至少10" -> LENGTH(col) >= 10
        - "不能超过20个字符" -> LENGTH(col) <= 20

        Args:
            text: 自然语言文本
            column_name: 列名

        Returns:
            长度条件表达式
        """
        # 匹配长度限制
        # 长度不超过X / 最多X个字符 / 不能超过X
        max_pattern = r'(?:长度|字符数)(?:不(?:超过|大于)|最多|不能超过|不超过|不能大于)\s*(\d+)'
        match = re.search(max_pattern, text)
        if match:
            return f"CHAR_LENGTH({column_name}) <= {match.group(1)}"

        # 不能少于X / 至少X个字符 / 长度不少于X
        min_pattern = r'(?:长度|字符数)(?:不能少于|至少|不少于|不能小于)\s*(\d+)'
        match = re.search(min_pattern, text)
        if match:
            return f"CHAR_LENGTH({column_name}) >= {match.group(1)}"

        # 匹配 "X个字符" 形式的精确长度
        exact_pattern = r'(?:正好|恰好|正好是)\s*(\d+)\s*(?:个字符|字符)'
        match = re.search(exact_pattern, text)
        if match:
            return f"CHAR_LENGTH({column_name}) = {match.group(1)}"

        return None

    def _nl2sql(self, natural_text: str, column_name: str, rule_type: str) -> str:
        """
        使用 LLM 进行自然语言转 SQL

        Args:
            natural_text: 自然语言描述
            column_name: 列名
            rule_type: 规则类型

        Returns:
            SQL 条件表达式
        """
        prompt = f"""将以下自然语言规则转换为 SQL 条件表达式。

规则类型: {rule_type}
目标列: {column_name}
自然语言描述: {natural_text}

要求：
1. 只输出 SQL 条件表达式部分，不要包含 SELECT、FROM 等
2. 使用 "{column_name}" 代替表名
3. 支持的数据库: PostgreSQL

示例：
输入: "手机号为空"
输出: "{column_name} IS NULL OR {column_name} = ''"

输入: "金额大于1000"
输出: "{column_name} > 1000"

请输出 SQL 条件表达式:"""

        try:
            response = self.llm_client.chat(prompt)
            # 清理输出，只保留表达式
            expr = response.strip()
            # 移除引号
            expr = expr.strip('"\'')
            return expr
        except Exception as e:
            print(f"[WARN] NL2SQL 解析失败: {str(e)}，使用默认条件")
            return f'{column_name} IS NOT NULL'

    def _replace_column_placeholder(self, expr: str, column_name: str) -> str:
        """
        替换条件表达式中的 column 占位符为实际列名

        Args:
            expr: 原始表达式（可能包含 'column' 占位符）
            column_name: 实际列名

        Returns:
            替换后的表达式
        """
        if not expr:
            return ""

        # 替换 column（不区分大小写）
        pattern = r'\bcolumn\b'
        return re.sub(pattern, column_name, expr, flags=re.IGNORECASE)

    def batch_generate_for_tables(
        self,
        rule_type: str,
        user_input: str,
        is_natural_language: bool,
        tables_columns: List[ColumnInfo]
    ) -> List[RuleCondition]:
        """
        为多表批量生成条件

        Args:
            rule_type: 规则类型
            user_input: 用户输入
            is_natural_language: 是否为自然语言
            tables_columns: 表和列信息列表

        Returns:
            规则条件列表
        """
        conditions = []

        # 1. 根据规则类型筛选相关列
        relevant_columns = self._filter_relevant_columns(rule_type, user_input, tables_columns)

        # 2. 为每列生成条件
        for col in relevant_columns:
            condition = self.generate_condition(
                rule_type=rule_type,
                table_name=col.table_name,
                column_name=col.column_name,
                user_input=user_input,
                is_natural_language=is_natural_language
            )
            conditions.append(condition)

        return conditions

    def _filter_relevant_columns(
        self,
        rule_type: str,
        user_input: str,
        tables_columns: List[ColumnInfo]
    ) -> List[ColumnInfo]:
        """
        根据规则类型和用户输入筛选相关列

        匹配策略：
        1. 关键词匹配（列名、列注释）
        2. 数据类型匹配（数值类规则匹配数值列等）
        3. 无关键词时使用规则类型默认匹配

        Args:
            rule_type: 规则类型
            user_input: 用户输入
            tables_columns: 所有表列信息

        Returns:
            相关的列列表
        """
        relevant = []
        user_input_lower = user_input.lower() if user_input else ""

        # 根据关键词匹配
        keywords = self._extract_keywords(user_input_lower)

        # 预定义的数据类型分类
        numeric_types = ('int', 'integer', 'bigint', 'smallint', 'decimal', 'numeric', 'float', 'double', 'real')
        text_types = ('varchar', 'text', 'char', 'string')
        date_types = ('date', 'datetime', 'timestamp', 'time')

        for col in tables_columns:
            col_name_lower = col.column_name.lower()
            data_type_lower = col.data_type.lower() if col.data_type else ""

            # 排除明显的系统字段
            if col_name_lower in ('id', 'create_time', 'update_time', 'create_at', 'update_at', 'deleted_at'):
                continue

            matched = False

            # 1. 关键词匹配
            if keywords:
                if any(kw in col_name_lower for kw in keywords):
                    matched = True

                if col.comment and any(kw in col.comment.lower() for kw in keywords):
                    matched = True

            # 2. 无关键词时，根据规则类型默认匹配
            if not matched:
                if rule_type == 'null_check':
                    # 空值检测：匹配所有有意义的列（排除主键ID）
                    if col_name_lower not in ('id',):
                        matched = True

                elif rule_type in ('threshold', 'range_check'):
                    # 数值检测：匹配数值类型列
                    if any(nt in data_type_lower for nt in numeric_types):
                        matched = True

                elif rule_type == 'format':
                    # 格式检测：匹配文本类型列
                    if any(tt in data_type_lower for tt in text_types):
                        matched = True

                elif rule_type == 'unique':
                    # 唯一性检测：匹配数值和文本类型列
                    if any(nt in data_type_lower for nt in numeric_types) or any(tt in data_type_lower for tt in text_types):
                        matched = True

                elif rule_type in ('length_check', 'date_check', 'consistency_check', 'freshness_check', 'value_distribution', 'enum'):
                    # 其他规则类型：匹配常见业务列（排除ID和时间戳）
                    if col_name_lower not in ('id', 'create_time', 'update_time') and (any(tt in data_type_lower for tt in text_types + numeric_types) or not data_type_lower):
                        matched = True

            if matched:
                relevant.append(col)

        return relevant

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        # 定义常见字段关键词映射
        keyword_map = {
            '手机': ['phone', 'mobile', 'tel', 'telephone'],
            '电话': ['phone', 'mobile', 'tel', 'telephone'],
            '邮箱': ['email', 'mail'],
            '邮箱地址': ['email', 'mail'],
            '身份证': ['id_card', 'idcard', 'identity', 'cert_no'],
            '姓名': ['name', 'username', 'real_name'],
            '地址': ['address', 'addr'],
            '金额': ['amount', 'money', 'price', 'total', 'balance'],
            '价格': ['price', 'cost', 'amount'],
            '日期': ['date', 'day', 'time'],
            '创建时间': ['create_time', 'created_at', 'create_date'],
            '更新时间': ['update_time', 'updated_at'],
            '状态': ['status', 'state'],
            '年龄': ['age'],
            '性别': ['gender', 'sex'],
        }

        keywords = []
        for cn_keyword, en_keywords in keyword_map.items():
            if cn_keyword in text:
                keywords.extend(en_keywords)

        # 添加英文关键词
        for word in text.split():
            if len(word) > 2 and word.isascii():
                keywords.append(word)

        return keywords


class MultiTableExecutor:
    """
    多表批量执行器

    用于：用户不指定表名时，对所有相关表执行同一规则
    """

    def __init__(self, engine, db_type: str, schema_name: str = None):
        """
        初始化

        Args:
            engine: SQLAlchemy Engine
            db_type: 数据库类型
            schema_name: Schema 名称
        """
        self.engine = engine
        self.db_type = db_type
        self.schema_name = schema_name

    def get_all_columns(self, tables: List[str] = None) -> List[ColumnInfo]:
        """
        获取所有表和列信息

        Args:
            tables: 指定表列表，不指定则获取所有表

        Returns:
            列信息列表
        """
        from sqlalchemy import text, inspect

        columns = []

        # 获取数据库中的所有表
        inspector = inspect(self.engine)
        schema = self.schema_name or 'public'

        try:
            all_tables = inspector.get_table_names(schema=schema)
        except Exception:
            all_tables = inspector.get_table_names()

        # 过滤指定表
        if tables:
            all_tables = [t for t in all_tables if t in tables]

        for table_name in all_tables:
            try:
                table_columns = inspector.get_columns(table_name, schema=schema)
                for col in table_columns:
                    columns.append(ColumnInfo(
                        table_name=table_name,
                        column_name=col['name'],
                        data_type=str(col['type']),
                        comment=""
                    ))
            except Exception as e:
                print(f"[WARN] 获取表 {table_name} 的列信息失败: {str(e)}")
                continue

        return columns

    def build_condition_sql(self, condition: RuleCondition) -> str:
        """
        根据条件构建完整的 SQL

        Args:
            condition: 规则条件

        Returns:
            完整的 SQL 语句
        """
        # 构建带 schema 的表引用
        from controllers.governance.dialect_adapter import DialectAdapter
        adapter = DialectAdapter(self.db_type)
        quoted_table = adapter.quote_table_reference(condition.table_name, self.schema_name)
        quoted_column = adapter.quote_identifier(condition.column_name)
        expr = condition.condition_expr

        # 根据规则类型生成 SQL
        if condition.rule_type in ('null_check', 'format', 'threshold', 'enum', 'custom_sql'):
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(CASE WHEN NOT ({expr}) THEN 1 ELSE 0 END) as failed_count
                FROM {quoted_table}
            """
        elif condition.rule_type == 'unique':
            sql = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT({quoted_column}) as non_null_count,
                    COUNT(DISTINCT {quoted_column}) as unique_count,
                    COUNT(*) - COUNT(DISTINCT {quoted_column}) as duplicate_count
                FROM {quoted_table}
                WHERE {quoted_column} IS NOT NULL AND {quoted_column} != ''
            """
        else:
            sql = f"""
                SELECT COUNT(*) as total_count, 0 as failed_count
                FROM {quoted_table}
            """

        return sql.strip()


def nl2sql_convert(natural_text: str, table_schema: str = None, llm_client = None) -> str:
    """
    自然语言转 SQL 的便捷函数

    Args:
        natural_text: 自然语言描述
        table_schema: 表结构信息（可选，用于提供上下文）
        llm_client: LLM 客户端

    Returns:
        SQL 条件表达式
    """
    generator = ConditionGenerator(llm_client)
    return generator._parse_natural_language(natural_text, "column", "custom_sql")
