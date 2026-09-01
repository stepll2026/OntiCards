"""
@File: dialect_adapter.py
@Description: SQL 方言适配器 - 支持多数据库类型的 SQL 语法适配
@Author: 韩小豪 849631113@qq.com
@Create: 2026-06-02

核心能力：
1. 标识符引号适配
2. 日期函数适配
3. 字符串函数适配
4. 正则表达式适配
5. SQL 语句自动修复
"""

import re
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class DialectInfo:
    """数据库方言信息"""
    name: str
    identifier_quote: str
    date_now: str
    date_current_date: str
    date_add: str
    string_length: str
    regex_match: str
    null_check_eq: str
    type_cast: str
    # 基础空值检测专用：用于"列转字符串后与 '' 比较"的方言适配
    # 例如 MySQL 需要 CAST AS CHAR，Oracle 需要 TO_CHAR(col)
    empty_string_cast: str  # CAST(col AS <type>) 的目标类型
    cast_as_text_supported: bool  # 该方言是否支持 CAST AS TEXT
    supports_limit: bool  # 该方言是否支持 LIMIT 语法（SQL Server/Oracle/达梦不支持，需要用 TOP/FETCH FIRST）


# 数据库方言配置
DIALECT_CONFIGS: Dict[str, DialectInfo] = {
    'postgresql': DialectInfo(
        name='PostgreSQL',
        identifier_quote='"{}"',
        date_now='NOW()',
        date_current_date='CURRENT_DATE',
        date_add="INTERVAL '{}'",
        string_length='CHAR_LENGTH({})',
        regex_match="{} ~* '{}'",
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='TEXT',
        cast_as_text_supported=True,
        supports_limit=True  # 支持 LIMIT 语法
    ),
    'mysql': DialectInfo(
        name='MySQL',
        identifier_quote='`{}`',
        date_now='NOW()',
        date_current_date='CURRENT_DATE',
        date_add='INTERVAL {}',
        string_length='LENGTH({})',
        regex_match='{} REGEXP "{}"',
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='CHAR',
        cast_as_text_supported=False,
        supports_limit=True  # 支持 LIMIT 语法
    ),
    'mssql': DialectInfo(
        name='SQL Server',
        identifier_quote='[{}]',
        date_now='GETDATE()',
        date_current_date='CAST(GETDATE() AS DATE)',
        date_add="DATEADD(day, {}, GETDATE())",
        string_length='LEN({})',
        regex_match='LIKE "%{}%"',  # MSSQL 不支持 REGEXP，降级为 LIKE
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='VARCHAR(MAX)',
        cast_as_text_supported=False,
        supports_limit=False  # 不支持 LIMIT，使用 TOP N 语法
    ),
    'oracle': DialectInfo(
        name='Oracle',
        identifier_quote='"{})"'.replace('})', '}') + ")",  # 特殊处理
        date_now='SYSDATE',
        date_current_date='TRUNC(SYSDATE)',
        date_add='SYSDATE + {}',
        string_length='LENGTH({})',
        regex_match="REGEXP_LIKE({}, '{}')",
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='VARCHAR2(4000)',
        cast_as_text_supported=False,
        supports_limit=False  # 不支持 LIMIT，使用 FETCH FIRST N ROWS ONLY
    ),
    'sqlite': DialectInfo(
        name='SQLite',
        identifier_quote='"{}"',
        date_now="datetime('now')",
        date_current_date="date('now')",
        date_add="datetime('now', '{}')",
        string_length='LENGTH({})',
        regex_match='LIKE "%{}%"',  # SQLite 不支持 REGEXP，降级为 LIKE
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='TEXT',
        cast_as_text_supported=True,
        supports_limit=True  # 支持 LIMIT 语法
    ),
    'trino': DialectInfo(
        name='Trino',
        identifier_quote='"{})"'.replace('})', '}') + ")",  # 特殊处理
        date_now='NOW()',
        date_current_date='CURRENT_DATE',
        date_add="INTERVAL '{}'",
        string_length='LENGTH({})',
        regex_match="REGEXP_LIKE({}, '{}')",
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='VARCHAR',
        cast_as_text_supported=False,
        supports_limit=True  # Trino 支持 LIMIT 语法
    ),
    # 人大金仓（KingBase）- 基于 PostgreSQL 内核，语法与 PostgreSQL 高度兼容
    'kingbase': DialectInfo(
        name='KingBase',
        identifier_quote='"{}"',
        date_now='NOW()',
        date_current_date='CURRENT_DATE',
        date_add="INTERVAL '{}'",
        string_length='CHAR_LENGTH({})',
        regex_match="{} ~* '{}'",
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='TEXT',
        cast_as_text_supported=True,
        supports_limit=True  # KingBase 基于 PostgreSQL，支持 LIMIT 语法
    ),
    # OceanBase MySQL 模式租户：语法与 MySQL 完全兼容，引用标准同 MySQL
    'oceanbase': DialectInfo(
        name='OceanBase (MySQL)',
        identifier_quote='`{}`',
        date_now='NOW()',
        date_current_date='CURRENT_DATE',
        date_add='INTERVAL {}',
        string_length='LENGTH({})',
        regex_match='{} REGEXP "{}"',
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        empty_string_cast='CHAR',
        cast_as_text_supported=False,
        supports_limit=True  # OceanBase MySQL 模式支持 LIMIT 语法
    ),
    # 达梦 DM：基于 Oracle 内核，语法与 Oracle 高度兼容
    # - 标识符引号：双引号（与 Oracle 一致，沿用 Oracle 表达式的特殊处理以保持代码一致性）
    # - 日期函数：SYSDATE / TRUNC(SYSDATE)，与 Oracle 一致
    # - 字符串函数：LENGTH、SUBSTR、TO_CHAR 等（Oracle 风格）
    # - 正则：REGEXP_LIKE（Oracle 风格）
    # - 空字符串：达梦沿用 Oracle 行为——空字符串 = NULL
    # - 空值检测：基础空值检测需要把数字/日期类型先转字符串再比较 ''，达梦用 TO_CHAR（Oracle 风格）
    'dm': DialectInfo(
        name='达梦 DM',
        # 与 Oracle 表达式保持一致（项目内历史遗留的特殊写法）
        identifier_quote='"{})"'.replace('})', '}') + ")",
        date_now='SYSDATE',
        date_current_date='TRUNC(SYSDATE)',
        # 达梦日期加法：与 Oracle 类似，使用 SYSDATE + N
        date_add='SYSDATE + {}',
        string_length='LENGTH({})',
        # 达梦正则：与 Oracle 一致，使用 REGEXP_LIKE 函数
        regex_match="REGEXP_LIKE({}, '{}')",
        null_check_eq="{} = ''",
        type_cast='CAST({} AS {})',
        # 达梦字符串类型：VARCHAR2（Oracle 风格）
        empty_string_cast='VARCHAR2(4000)',
        cast_as_text_supported=False,
        supports_limit=False  # 达梦基于 Oracle 内核，不支持 LIMIT，使用 FETCH FIRST N ROWS ONLY
    ),
}


class DialectAdapter:
    """
    SQL 方言适配器

    功能：
    1. 将 PostgreSQL 风格的 SQL 适配到目标数据库
    2. 处理标识符引号、函数语法、正则表达式等差异
    3. 为 LLM 生成的 SQL 提供语法参考
    """

    def __init__(self, db_type: str):
        """
        初始化适配器

        Args:
            db_type: 数据库类型 (postgresql/mysql/mssql/oracle/sqlite/trino/kingbase)
        """
        self.db_type = db_type.lower()
        self.dialect = self._get_dialect()

    def _get_dialect(self) -> DialectInfo:
        """获取方言配置"""
        return DIALECT_CONFIGS.get(self.db_type, DIALECT_CONFIGS['postgresql'])

    def quote_identifier(self, name: str) -> str:
        """
        添加标识符引号

        Args:
            name: 标识符名称（表名、列名等）

        Returns:
            带引号的标识符
        """
        if not name:
            return name
        return self.dialect.identifier_quote.format(name)

    def quote_table_column(self, table: str, column: str) -> Tuple[str, str]:
        """
        同时引用表名和列名

        Args:
            table: 表名
            column: 列名

        Returns:
            (引号后的表名, 引号后的列名)
        """
        return self.quote_identifier(table), self.quote_identifier(column)

    def quote_table_reference(self, table: str, schema: str = None) -> str:
        """
        生成完整的表引用（含 Schema）

        支持多种数据库的 schema 引用语法：
        - PostgreSQL/MySQL/SQLite/Trino: "schema"."table"
        - MSSQL: [schema].[table]
        - Oracle/DM: "schema"."table"

        Args:
            table: 表名（不带引号）
            schema: Schema 名（可选，为空时只返回带引号的表名）

        Returns:
            带引号的完整表引用，如 '"public"."users"' 或 '"users"'
        """
        quoted_table = self.quote_identifier(table)
        if schema and schema.strip():
            quoted_schema = self.quote_identifier(schema.strip())
            return f"{quoted_schema}.{quoted_table}"
        return quoted_table

    def adapt_condition_expr(self, condition: str, column: str) -> str:
        """
        适配条件表达式

        将 column 占位符替换为实际列名，并适配语法

        Args:
            condition: 原始条件表达式
            column: 实际列名

        Returns:
            适配后的条件表达式
        """
        if not condition:
            return ""

        # 替换 column 占位符
        quoted_col = self.quote_identifier(column)
        condition = re.sub(r'\bcolumn\b', quoted_col, condition, flags=re.IGNORECASE)

        return condition

    def adapt_regex(self, pattern: str, column: str) -> str:
        """
        适配正则表达式

        根据目标数据库转换正则表达式语法

        Args:
            pattern: 正则表达式模式
            column: 列名

        Returns:
            适配后的正则表达式
        """
        quoted_col = self.quote_identifier(column)

        if self.db_type == 'postgresql':
            return self.dialect.regex_match.format(quoted_col, pattern)
        elif self.db_type == 'mysql' or self.db_type == 'oceanbase':
            # OceanBase MySQL 模式与 MySQL 行为一致，复用同一处理方式
            return self.dialect.regex_match.format(quoted_col, pattern)
        elif self.db_type == 'mssql':
            # MSSQL 不支持正则，降级为 LIKE
            # 将正则转换为简单的 LIKE 模式
            like_pattern = self._regex_to_like(pattern)
            return f"{quoted_col} LIKE '{like_pattern}'"
        elif self.db_type == 'oracle' or self.db_type == 'dm':
            # 达梦 DM：与 Oracle 一致使用 REGEXP_LIKE 函数
            return self.dialect.regex_match.format(quoted_col, pattern)
        elif self.db_type == 'sqlite':
            # SQLite 不支持正则，降级为 LIKE
            like_pattern = self._regex_to_like(pattern)
            return f"{quoted_col} LIKE '{like_pattern}'"
        else:
            return self.dialect.regex_match.format(quoted_col, pattern)

    def _regex_to_like(self, pattern: str) -> str:
        """
        将正则表达式转换为 LIKE 模式

        注意：这是降级方案，只能处理简单的模式

        Args:
            pattern: 正则表达式

        Returns:
            LIKE 模式字符串
        """
        # 简单转换
        result = pattern
        # 移除正则特殊字符
        result = result.replace('.*', '%')
        result = result.replace('.', '_')
        result = result.replace('\\d', '[0-9]')
        result = result.replace('\\D', '[^0-9]')
        result = result.replace('\\w', '[a-zA-Z0-9_]')
        result = result.replace('\\W', '[^a-zA-Z0-9_]')
        result = result.replace('^', '')
        result = result.replace('$', '')
        return result

    def adapt_date_function(self, date_expr: str) -> str:
        """
        适配日期函数

        Args:
            date_expr: 日期表达式

        Returns:
            适配后的日期表达式
        """
        result = date_expr

        # NOW() -> 目标数据库的当前时间函数
        result = re.sub(r'\bNOW\(\)', self.dialect.date_now, result, flags=re.IGNORECASE)

        # CURRENT_DATE -> 目标数据库的当前日期函数
        result = re.sub(r'\bCURRENT_DATE\b', self.dialect.date_current_date, result, flags=re.IGNORECASE)

        # INTERVAL 'N days' 适配
        # PostgreSQL/MySQL: INTERVAL '7 days' 或 INTERVAL 7 DAY
        # MSSQL: DATEADD(day, 7, GETDATE())
        # Oracle: SYSDATE + 7
        # SQLite: datetime('now', '+7 days')

        def replace_interval(match):
            value = match.group(1)
            unit = match.group(2)
            return self.dialect.date_add.format(f"{value} {unit}")

        result = re.sub(r"INTERVAL\s+['\"]?(\d+)\s+(days?)['\"]?", replace_interval, result, flags=re.IGNORECASE)

        return result

    def adapt_string_length(self, column: str) -> str:
        """
        适配字符串长度函数

        Args:
            column: 列名

        Returns:
            适配后的长度函数调用
        """
        return self.dialect.string_length.format(self.quote_identifier(column))

    def empty_string_eq(self, column: str) -> str:
        """
        生成"列转为字符串后等于空串"的方言适配表达式

        用于基础空值检测中字符串列的空字符串判定，按目标数据库的 CAST 语法生成。

        Args:
            column: 列名（不带引号）

        Returns:
            完整表达式，例如：
            - PostgreSQL/SQLite:  CAST("col" AS TEXT) = ''
            - MySQL:             CAST(`col` AS CHAR) = ''
            - MSSQL:             CAST([col] AS VARCHAR(MAX)) = ''
            - Oracle:            CAST("COL" AS VARCHAR2(4000)) = ''
            - Trino:             CAST("col" AS VARCHAR) = ''
        """
        quoted = self.quote_identifier(column)
        cast_type = self.dialect.empty_string_cast
        return f"CAST({quoted} AS {cast_type}) = ''"

    def is_string_type(self, data_type: str) -> bool:
        """
        判定列类型是否为字符串类型（基础空值检测用）

        Args:
            data_type: 数据库 information_schema 返回的数据类型（如 'varchar'、'integer'、'text'）

        Returns:
            是否为字符串类型
        """
        if not data_type:
            return False
        dt = data_type.lower()
        return any(k in dt for k in (
            'char', 'text', 'varchar', 'nvarchar', 'nchar', 'clob', 'nclob',
        ))

    def build_sample_sql(
        self,
        table: str,
        columns: List[str],
        schema: str = None,
        limit: int = 100
    ) -> List[str]:
        """
        构建采样 SQL 列表（每个字段一个 SELECT DISTINCT 语句）

        用于数据卡片生成时的数据采样，采样结果供 AI 分析脱敏和字段特征。

        Args:
            table: 表名
            columns: 字段名列表
            schema: Schema 名（可选）
            limit: 每个字段最多采样的 distinct 值数量

        Returns:
            SQL 列表，每个元素是一条独立的采样 SQL

        示例：
            build_sample_sql("users", ["id", "name", "phone"], "public", 50)
            返回：
            [
                'SELECT DISTINCT "id" FROM "public"."users" LIMIT 50',
                'SELECT DISTINCT "name" FROM "public"."users" LIMIT 50',
                'SELECT DISTINCT "phone" FROM "public"."users" LIMIT 50'
            ]
        """
        quoted_table = self.quote_table_reference(table, schema)
        sqls = []

        for col in columns:
            quoted_col = self.quote_identifier(col)
            sql = f"SELECT DISTINCT {quoted_col} FROM {quoted_table} LIMIT {limit}"
            sqls.append(sql)

        return sqls

    def build_sample_sql_for_column(
        self,
        table: str,
        column: str,
        schema: str = None,
        limit: int = 100
    ) -> str:
        """
        构建单个字段的采样 SQL

        根据不同数据库类型适配 LIMIT 语法：
        - PostgreSQL/MySQL/SQLite/KingBase/OceanBase(MySQL)/Trino: SELECT DISTINCT col FROM table LIMIT N
        - SQL Server: SELECT DISTINCT TOP N col FROM table
        - Oracle/达梦: SELECT DISTINCT col FROM table FETCH FIRST N ROWS ONLY

        Args:
            table: 表名
            column: 字段名
            schema: Schema 名（可选）
            limit: 最多采样的 distinct 值数量

        Returns:
            采样 SQL 字符串
        """
        quoted_table = self.quote_table_reference(table, schema)
        quoted_col = self.quote_identifier(column)

        # 根据数据库类型选择合适的 LIMIT 语法
        if self.db_type == 'mssql':
            # SQL Server: TOP N 必须在 SELECT 之后、DISTINCT 之前
            return f"SELECT DISTINCT TOP {limit} {quoted_col} FROM {quoted_table}"
        elif self.db_type in ('oracle', 'dm'):
            # Oracle/达梦: FETCH FIRST N ROWS ONLY（Oracle 12c+ 兼容语法）
            return f"SELECT DISTINCT {quoted_col} FROM {quoted_table} FETCH FIRST {limit} ROWS ONLY"
        else:
            # PostgreSQL/MySQL/SQLite/KingBase/OceanBase/Trino: LIMIT N
            return f"SELECT DISTINCT {quoted_col} FROM {quoted_table} LIMIT {limit}"

    def build_statistics_sql(
        self,
        table: str,
        column: str,
        schema: str = None
    ) -> str:
        """
        构建数值字段统计 SQL

        用于获取数值字段的 min、max、avg 等统计信息。

        Args:
            table: 表名
            column: 字段名
            schema: Schema 名（可选）

        Returns:
            统计 SQL 字符串
        """
        quoted_table = self.quote_table_reference(table, schema)
        quoted_col = self.quote_identifier(column)

        return f"""
SELECT
    COUNT(*) as total_count,
    COUNT(DISTINCT {quoted_col}) as distinct_count,
    MIN({quoted_col}) as min_value,
    MAX({quoted_col}) as max_value,
    AVG({quoted_col}) as avg_value
FROM {quoted_table}
WHERE {quoted_col} IS NOT NULL
        """.strip()

    def build_date_range_sql(
        self,
        table: str,
        column: str,
        schema: str = None
    ) -> str:
        """
        构建日期字段范围查询 SQL

        用于获取日期字段的最小和最大日期。

        Args:
            table: 表名
            column: 字段名
            schema: Schema 名（可选）

        Returns:
            日期范围 SQL 字符串
        """
        quoted_table = self.quote_table_reference(table, schema)
        quoted_col = self.quote_identifier(column)

        return f"""
SELECT
    MIN({quoted_col}) as min_date,
    MAX({quoted_col}) as max_date
FROM {quoted_table}
WHERE {quoted_col} IS NOT NULL
        """.strip()

    def build_check_sql(
        self,
        table: str,
        column: str,
        condition: str,
        rule_type: str = 'custom_sql',
        schema: str = None
    ) -> str:
        """
        构建完整的检测 SQL

        核心逻辑（按优先级排序）：
        1. rule_type == 'unique' → 唯一性检测专用模板（优先级最高，即使传入了 condition 也走此分支）
        2. rule_type == 'consistency_check' → 一致性检测专用模板
        3. 有 condition_expr → 专家/模板模式：condition 是【业务条件】，SQL 用 NOT() 取反
        4. 无 condition_expr → 自动模式：根据 rule_type 生成默认条件

        Args:
            table: 表名
            column: 列名
            condition: 条件表达式
            rule_type: 规则类型
            schema: Schema 名（可选，为空时只引用表名）
        """
        quoted_table = self.quote_table_reference(table, schema)
        quoted_col = self.quote_identifier(column) if column else None

        # ============================================================
        # 优先级 1：唯一性检测（优先级最高，即使传入了 condition 也走此分支）
        # ============================================================
        if rule_type == 'unique':
            # 唯一性检测：检测字段值是否重复
            # 合规条件：值必须唯一（COUNT(DISTINCT) == COUNT）
            # 违规条件：COUNT(DISTINCT) < COUNT，即出现重复
            return f"""
SELECT
    COUNT(*) as total_count,
    COUNT({quoted_col}) as non_null_count,
    COUNT(DISTINCT {quoted_col}) as unique_count,
    COUNT(*) - COUNT(DISTINCT {quoted_col}) as duplicate_count
FROM {quoted_table}
WHERE {quoted_col} IS NOT NULL AND {quoted_col} != ''
            """.strip()

        # ============================================================
        # 优先级 2：一致性检测（需要特殊的违规条件，NULL 值会导致 NOT() 失效）
        # ============================================================
        if rule_type == 'consistency_check' and condition and condition.strip():
            match = re.search(r'(\w+)\s*=\s*(\w+)', condition.strip())
            if match:
                col1, col2 = match.group(1), match.group(2)
                # 合规条件：col1 = col2 OR (col1 IS NULL AND col2 IS NULL)
                # 违规条件：(col1 <> col2) OR (col1 IS NULL) <> (col2 IS NULL)
                violation_condition = f"({col1} <> {col2}) OR ({col1} IS NULL) <> ({col2} IS NULL)"
                return f"""
SELECT
    COUNT(*) as total_count,
    SUM(CASE WHEN {violation_condition} THEN 1 ELSE 0 END) as failed_count
FROM {quoted_table}
                """.strip()

        # ============================================================
        # 优先级 3：有 condition_expr → 专家/模板模式：NOT(业务条件) = 违规条件
        # ============================================================
        if condition and condition.strip():
            if column and quoted_col:
                adapted_condition = re.sub(
                    r'\bcolumn\b',
                    quoted_col,
                    condition.strip(),
                    flags=re.IGNORECASE
                )
            else:
                adapted_condition = condition.strip()

            return f"""
SELECT
    COUNT(*) as total_count,
    SUM(CASE WHEN NOT ({adapted_condition}) THEN 1 ELSE 0 END) as failed_count
FROM {quoted_table}
            """.strip()

        # ============================================================
        # 优先级 4：自动模式（无 condition），根据 rule_type 生成默认条件
        # ============================================================
        adapted_condition = self.adapt_condition_expr(condition, column)

        if rule_type == 'null_check':
            # 业务条件：字段必须有值；违规条件：NOT(IS NOT NULL AND != '')
            return f"""
SELECT
    COUNT(*) as total_count,
    SUM(CASE WHEN NOT ({quoted_col} IS NOT NULL AND {quoted_col} != '') THEN 1 ELSE 0 END) as failed_count
FROM {quoted_table}
            """.strip()

        elif rule_type in ('format', 'threshold', 'enum', 'custom_sql', 'length_check', 'range_check', 'date_check', 'freshness_check', 'value_distribution'):
            # 业务条件：adapted_condition；违规条件：NOT(adapted_condition)
            return f"""
SELECT
    COUNT(*) as total_count,
    SUM(CASE WHEN {quoted_col} IS NOT NULL AND NOT ({adapted_condition}) THEN 1 ELSE 0 END) as failed_count
FROM {quoted_table}
            """.strip()

        else:
            return f"""
SELECT COUNT(*) as total_count
FROM {quoted_table}
            """.strip()

    def build_multi_condition_sql(
        self,
        table: str,
        conditions: list,
        condition_mode: str = "AND",
        schema: str = None
    ) -> str:
        """
        构建多条件检测 SQL（复合规则）

        Args:
            table: 表名
            conditions: 条件列表，每个元素为 dict: {column, condition}
                       条件为【业务条件】（business conditions），
                       即用户描述中的"必须满足的条件"。
            condition_mode: 业务条件的关系 "AND" 或 "OR"
            schema: Schema 名（可选）

        Returns:
            多条件检测 SQL（先对每个业务条件取反，再按德摩根定律反向连接）

        示例（业务 AND）：
            业务条件: qty > 0, order_date >= '2025-09-01'
            condition_mode: AND
            违规条件: NOT(qty > 0) OR NOT(order_date >= '2025-09-01')
        示例（业务 OR）：
            业务条件: qty > 0, order_date >= '2025-09-01'
            condition_mode: OR
            违规条件: NOT(qty > 0) AND NOT(order_date >= '2025-09-01')
        """
        quoted_table = self.quote_table_reference(table, schema)

        # 构建 WHERE 子句：业务条件取反
        where_clauses = []
        for cond in conditions:
            column = cond.get('column', '')
            condition = cond.get('condition', '')

            if not column or not condition:
                continue

            quoted_col = self.quote_identifier(column)
            # 替换 column 占位符
            adapted_condition = re.sub(
                r'\bcolumn\b',
                quoted_col,
                condition.strip(),
                flags=re.IGNORECASE
            )
            # 业务条件取反，得到违规条件
            where_clauses.append(f"(NOT ({adapted_condition}))")

        if not where_clauses:
            return f"SELECT COUNT(*) as total_count FROM {quoted_table}"

        # De Morgan：业务 AND → 违规用 OR，业务 OR → 违规用 AND
        sql_mode = 'OR' if condition_mode == 'AND' else 'AND'
        where_clause = f"\n    {sql_mode} ".join(where_clauses)

        return f"""
SELECT
    COUNT(*) as total_count,
    SUM(CASE WHEN {where_clause} THEN 1 ELSE 0 END) as failed_count
FROM {quoted_table}
        """.strip()

    def build_table_check_sql(
        self,
        table: str,
        condition: str,
        rule_type: str,
        schema: str = None
    ) -> str:
        """
        构建表级检测 SQL（无列条件，用于全表扫描类规则）

        Args:
            table: 表名
            condition: 条件表达式
            rule_type: 规则类型
            schema: Schema 名（可选）

        Returns:
            表级检测 SQL
        """
        quoted_table = self.quote_table_reference(table, schema)

        # 适配条件表达式（表级规则中条件通常是完整的 WHERE 子句）
        adapted_condition = condition.strip() if condition else "1=1"

        if rule_type == 'table_stats':
            # 表级统计规则
            return f"""
SELECT
    COUNT(*) as total_count,
    0 as failed_count,
    COUNT(*) FILTER (WHERE {adapted_condition}) as matched_count
FROM {quoted_table}
            """.strip()

        elif rule_type in ('null_check', 'unique', 'format', 'threshold', 'enum',
                          'custom_sql', 'length_check', 'range_check', 'date_check',
                          'consistency_check', 'freshness_check', 'value_distribution'):
            # 通用规则：使用条件表达式过滤
            return f"""
SELECT
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE {adapted_condition}) as failed_count
FROM {quoted_table}
            """.strip()

        else:
            # 未知规则类型，只返回总行数
            return f"""
SELECT
    COUNT(*) as total_count,
    0 as failed_count
FROM {quoted_table}
            """.strip()

    def get_dialect_info(self) -> Dict[str, Any]:
        """
        获取方言信息（用于生成 Prompt）

        Returns:
            方言信息字典
        """
        return {
            'db_type': self.db_type,
            'name': self.dialect.name,
            'identifier_quote': self.dialect.identifier_quote.format('column'),
            'date_functions': self._get_date_functions_doc(),
            'string_functions': self._get_string_functions_doc(),
            'regex_syntax': self._get_regex_syntax_doc(),
            'null_check_syntax': self._get_null_check_doc()
        }

    def _get_date_functions_doc(self) -> str:
        """获取日期函数文档"""
        docs = {
            'postgresql': '''
- NOW(): 当前日期时间
- CURRENT_DATE: 当前日期
- CURRENT_TIMESTAMP: 当前时间戳
- INTERVAL 'N days': 日期加减（例: NOW() - INTERVAL '7 days'）
- DATE_TRUNC('day', col): 日期截断
- EXTRACT(YEAR FROM col): 提取年份
''',
            'mysql': '''
- NOW(): 当前日期时间
- CURDATE(): 当前日期
- CURRENT_DATE: 当前日期
- DATE_SUB(date, INTERVAL N DAY): 日期减法
- DATE_ADD(date, INTERVAL N DAY): 日期加法
- DATEDIFF(date1, date2): 日期差
- YEAR()/MONTH()/DAY(): 提取年月日
''',
            'mssql': '''
- GETDATE(): 当前日期时间
- GETUTCDATE(): UTC 时间
- DATEADD(day, N, date): 日期加减
- DATEDIFF(day, date1, date2): 日期差
- YEAR()/MONTH()/DAY(): 提取年月日
- CAST(GETDATE() AS DATE): 当前日期
''',
            'oracle': '''
- SYSDATE: 当前日期时间
- TRUNC(SYSDATE): 当前日期
- SYSDATE + N: 日期加法
- SYSDATE - N: 日期减法
- ADD_MONTHS(date, N): 月份加减
''',
            'sqlite': '''
- datetime('now'): 当前日期时间
- date('now'): 当前日期
- datetime('now', '+N days'): 日期加法
- datetime('now', '-N days'): 日期减法
- julianday(): 儒略日
''',
            'trino': '''
- NOW(): 当前日期时间
- CURRENT_DATE: 当前日期
- CURRENT_TIMESTAMP: 当前时间戳
- INTERVAL 'N days': 日期加减
- DATE_TRUNC('day', col): 日期截断
|''',
            # 达梦 DM：兼容 Oracle 的日期函数
            'dm': '''
|- SYSDATE: 当前日期时间
|- TRUNC(SYSDATE): 当前日期
|- SYSDATE + N: 日期加法
|- SYSDATE - N: 日期减法
|- ADD_MONTHS(date, N): 月份加减
|- EXTRACT(YEAR FROM col): 提取年份
'''
        }
        return docs.get(self.db_type, docs['postgresql'])

    def _get_string_functions_doc(self) -> str:
        """获取字符串函数文档"""
        docs = {
            'postgresql': '''
- CHAR_LENGTH(col): 字符串长度
- UPPER(col)/LOWER(col): 大小写转换
- TRIM(col): 去除首尾空格
- SUBSTRING(col, start, len): 字符串截取
- CONCAT(col1, col2): 字符串连接
''',
            'mysql': '''
- LENGTH(col): 字符串长度（字节）
- CHAR_LENGTH(col): 字符串长度（字符）
- UPPER(col)/LOWER(col): 大小写转换
- TRIM(col): 去除首尾空格
- SUBSTRING(col, start, len): 字符串截取
- CONCAT(col1, col2): 字符串连接
''',
            'mssql': '''
- LEN(col): 字符串长度（不包含尾部空格）
- UPPER(col)/LOWER(col): 大小写转换
- LTRIM(col)/RTRIM(col): 去除首/尾空格
- SUBSTRING(col, start, len): 字符串截取
- CONCAT(col1, col2): 字符串连接
''',
            'oracle': '''
- LENGTH(col): 字符串长度
- UPPER(col)/LOWER(col): 大小写转换
- TRIM(col): 去除首尾空格
- SUBSTR(col, start, len): 字符串截取
- CONCAT(col1, col2): 字符串连接
''',
            'sqlite': '''
- LENGTH(col): 字符串长度
- UPPER(col)/LOWER(col): 大小写转换
- TRIM(col): 去除首尾空格
- SUBSTR(col, start, len): 字符串截取
''',
            'trino': '''
- LENGTH(col): 字符串长度
- UPPER(col)/LOWER(col): 大小写转换
- TRIM(col): 去除首尾空格
- SUBSTRING(col, start, len): 字符串截取
- CONCAT(col1, col2): 字符串连接
|''',
            # 达梦 DM：兼容 Oracle 的字符串函数
            'dm': '''
|- LENGTH(col): 字符串长度
|- UPPER(col)/LOWER(col): 大小写转换
|- TRIM(col): 去除首尾空格
|- SUBSTR(col, start, len): 字符串截取
|- CONCAT(col1, col2): 字符串连接
|- TO_CHAR(col): 类型转换为字符串
|- INSTR(col, substr): 查找子串位置
'''
        }
        return docs.get(self.db_type, docs['postgresql'])

    def _get_regex_syntax_doc(self) -> str:
        """获取正则表达式语法文档"""
        docs = {
            'postgresql': '''
- 正则匹配: col ~* 'pattern'（不区分大小写）
- 正则匹配: col ~ 'pattern'（区分大小写）
- 不匹配: col !~* 'pattern'
- 示例: phone ~* '^1[3-9]\\d{9}$'
''',
            'mysql': '''
- 正则匹配: col REGEXP 'pattern'
- 不匹配: col NOT REGEXP 'pattern'
- 示例: phone REGEXP '^1[3-9]\\d{9}$'
''',
            'mssql': '''
- 不支持原生正则，使用 LIKE 替代
- LIKE '%pattern%': 模糊匹配
- 示例: phone LIKE '%[0-9]%'
''',
            'oracle': '''
- 正则匹配: REGEXP_LIKE(col, 'pattern')
- 不匹配: NOT REGEXP_LIKE(col, 'pattern')
- 示例: REGEXP_LIKE(phone, '^1[3-9]\\d{9}$')
''',
            'sqlite': '''
- 不支持原生正则，使用 LIKE 替代
- LIKE '%pattern%': 模糊匹配
''',
            'trino': '''
- 正则匹配: REGEXP_LIKE(col, 'pattern')
- 不匹配: NOT REGEXP_LIKE(col, 'pattern')
- 示例: REGEXP_LIKE(phone, '^1[3-9]\\d{9}$')
|''',
            # 达梦 DM：兼容 Oracle 的正则表达式
            'dm': '''
|- 正则匹配: REGEXP_LIKE(col, 'pattern')
|- 不匹配: NOT REGEXP_LIKE(col, 'pattern')
|- 示例: REGEXP_LIKE(phone, '^1[3-9]\\d{9}$')
'''
        }
        return docs.get(self.db_type, docs['postgresql'])

    def _get_null_check_doc(self) -> str:
        """获取空值判断语法文档"""
        docs = {
            'postgresql': '''
- IS NULL: 值为空
- IS NOT NULL: 值不为空
- = '': 为空字符串
- IS NULL OR col = '': 为空或空字符串
''',
            'mysql': '''
- IS NULL: 值为空
- IS NOT NULL: 值不为空
- = '': 为空字符串
- IS NULL OR col = '': 为空或空字符串
''',
            'mssql': '''
- IS NULL: 值为空
- IS NOT NULL: 值不为空
- = '': 为空字符串（注意：SQL Server 中 char 字段会填充空格）
''',
            'oracle': '''
- IS NULL: 值为空
- IS NOT NULL: 值不为空
- = '': 为空字符串（注意：Oracle 中空字符串等同于 NULL）
''',
            'sqlite': '''
- IS NULL: 值为空
- IS NOT NULL: 值不为空
- = '': 为空字符串
- IS NULL OR col = '': 为空或空字符串
''',
            'trino': '''
- IS NULL: 值为空
- IS NOT NULL: 值不为空
- = '': 为空字符串
|''',
            # 达梦 DM：兼容 Oracle 的空值行为——空字符串等同 NULL
            'dm': '''
|- IS NULL: 值为空
|- IS NOT NULL: 值不为空
|- = '': 为空字符串（注意：达梦沿用 Oracle 行为，空字符串等同于 NULL）
|- 数值/日期列的空字符串判定：先 TO_CHAR(col) = ''，再 IS NULL
'''
        }
        return docs.get(self.db_type, docs['postgresql'])


def adapt_sql_for_dialect(
    source_sql: str,
    target_db_type: str,
    column: str = 'column'
) -> Tuple[str, List[str]]:
    """
    便捷函数：将 SQL 适配到目标数据库

    Args:
        source_sql: 源 SQL（PostgreSQL 风格）
        target_db_type: 目标数据库类型
        column: 列名（用于替换 column 占位符）

    Returns:
        (适配后的 SQL, 警告列表)
    """
    adapter = DialectAdapter(target_db_type)

    # 替换 column 占位符
    sql = re.sub(r'\bcolumn\b', adapter.quote_identifier(column), source_sql, flags=re.IGNORECASE)

    # 适配日期函数
    sql = adapter.adapt_date_function(sql)

    warnings = []

    # 检查是否使用了不支持的功能
    if target_db_type in ('mssql', 'sqlite'):
        if re.search(r'~\*?', sql):
            warnings.append(f"{target_db_type} 不支持正则表达式，已降级为 LIKE 匹配")

    return sql, warnings


def get_dialect_prompt_context(db_type: str) -> Dict[str, str]:
    """
    获取方言相关的 Prompt 上下文

    用于生成 LLM 的提示词

    Args:
        db_type: 数据库类型

    Returns:
        包含方言上下文的字典
    """
    adapter = DialectAdapter(db_type)
    info = adapter.get_dialect_info()

    return {
        'db_type': info['db_type'],
        'identifier_quote': info['identifier_quote'],
        'date_functions': info['date_functions'],
        'string_functions': info['string_functions'],
        'regex_syntax': info['regex_syntax'],
        'null_check_syntax': info['null_check_syntax']
    }


def get_dialect_adaptation_prompt() -> str:
    """
    获取方言适配提示词（优先从数据库读取）

    Returns:
        方言适配提示词模板内容
    """
    # 优先从数据库加载
    try:
        from models.prompt_config import prompt_manager
        content = prompt_manager.get_prompt("dialect_adaptation_prompt.txt", use_cache=True)
        if content:
            return content
    except Exception as e:
        print(f"[WARN] 从数据库加载 dialect_adaptation_prompt.txt 失败: {str(e)}")

    # 回退到文件读取
    from pathlib import Path
    prompt_file = Path(__file__).resolve().parent.parent.parent / "libs" / "prompt" / "governance" / "dialect_adaptation_prompt.txt"
    if prompt_file.exists():
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()

    # 返回空字符串作为兜底
    return ""
