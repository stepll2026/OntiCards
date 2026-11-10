"""Validate governance predicates with the pinned SQLGlot AST, not SQL text regexes.

Keep the original SQL spelling: dialect functions/regex literals must not be
silently transpiled. Read-only subqueries remain supported (reference template).
Full queries share the built-in expression allowlist and are checked at API and execution boundaries.
"""
import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import TokenType

_DIALECTS = {
    "postgresql": "postgres", "kingbase": "postgres", "mssql": "tsql",
    "dm": "oracle", "mariadb": "mysql", "oceanbase": "mysql",
}
# Explicit AST allowlist. Unknown functions/statements fail closed, including
# schema-qualified calls, external table functions, variables and user casts.
_NODES = frozenset("""
    Column Identifier Literal RawString Boolean Null Star Paren Tuple And Or Not
    EQ NEQ LT LTE GT GTE Is In Between Like ILike Escape Add Sub Mul Div Mod Neg
    Case If Interval Var DataType DataTypeParam
    Select Subquery Exists From Table Where Join Group Having Order Ordered
    Limit Offset Distinct Window WindowSpec
    Cast TryCast Length Trim Lower Upper Abs Round Coalesce Nullif
    RegexpLike RegexpILike RegexpReplace RegexpExtract Substring Concat
    CurrentDate CurrentTimestamp CurrentTime DateTrunc TimestampTrunc Extract
    DateAdd DateSub DateDiff TimestampAdd TimestampSub TimestampDiff AddMonths
    TimeStrToTime StrToTime TsOrDsToDate TsOrDsToTimestamp TimeToStr
    Year Month Day Date Datetime JulianDay ToNumber StrToDate ToChar StrPosition
    Count Sum Avg Min Max
    Array Bracket Any ArrayContainsAll ArrayContainedBy ArrayOverlaps ArraySize
    ByteString National
""".split())
_ANONYMOUS = {
    "postgres": frozenset({"NOW"}),
    "mysql": frozenset({"NOW", "CURDATE"}),
    "tsql": frozenset({"GETDATE", "GETUTCDATE"}),
    "sqlite": frozenset({"DATETIME", "DATE", "JULIANDAY"}),
    "oracle": frozenset({"TO_NUMBER", "TO_DATE", "TO_CHAR"}),
    "trino": frozenset({"NOW"}),
}
# 只读的比较量词（ANY/ALL/ARRAY[...] 等由 SQLGlot 记为函数名节点）。
_SHARED_ANONYMOUS = frozenset({"ALL"})
_TYPES = frozenset("""
    BOOLEAN TINYINT SMALLINT INT BIGINT UINT UBIGINT FLOAT DOUBLE DECIMAL
    CHAR NCHAR VARCHAR NVARCHAR TEXT DATE TIME TIMESTAMP TIMESTAMPTZ DATETIME
""".split())
_SELECT_ARGS = frozenset("""
    expressions from_ where joins distinct group having order limit offset
""".split())
_PREFIX = "SELECT 1 FROM __governance_target WHERE ("


def _dialect(db_type):
    name = (db_type or "postgresql").lower()
    return _DIALECTS.get(name, name)


def _parse(expr, db_type=None):
    if not isinstance(expr, str) or len(expr) > 8192 or "\x00" in expr:
        raise ValueError("条件表达式过长或类型错误")
    dialect = _dialect(db_type)
    try:
        tokens = sqlglot.Dialect.get_or_raise(dialect).tokenize(expr)
        if len(tokens) > 512:
            raise ValueError("条件表达式过于复杂")
        depth = 0
        for index, token in enumerate(tokens):
            # SQLGlot can normalize "ABS"(x) to Abs(x), but PostgreSQL keeps
            # quoted case and may call a different user-defined function.
            # Our predicates support bare built-in calls, not quoted calls.
            if (token.token_type == TokenType.IDENTIFIER
                    and index + 1 < len(tokens)
                    and tokens[index + 1].token_type == TokenType.L_PAREN):
                raise ValueError("条件表达式不允许引用函数名")
            if token.comments or token.token_type == TokenType.SEMICOLON:
                raise ValueError("条件表达式不允许注释或多条语句")
            if token.token_type == TokenType.L_PAREN:
                depth += 1
                if depth > 32:
                    raise ValueError("条件表达式嵌套过深")
            elif token.token_type == TokenType.R_PAREN:
                depth -= 1
                if depth < 0:
                    raise ValueError("条件表达式括号不匹配")
        if depth:
            raise ValueError("条件表达式括号不匹配")
        if not tokens:
            return None
        statements = sqlglot.parse(_PREFIX + expr + ")", read=dialect)
        if len(statements) != 1 or type(statements[0]) is not exp.Select:
            raise ValueError("条件表达式必须是单一谓词")
        wrapper = statements[0]
        if (any(value and key not in {"expressions", "from_", "where"} for key, value in wrapper.args.items())
                or wrapper.expressions != [exp.Literal.number(1)]
                or wrapper.args["from_"].this != exp.to_table("__governance_target")
                or not isinstance(wrapper.args.get("where"), exp.Where)
                or type(wrapper.args["where"].this) is not exp.Paren):
            raise ValueError("条件表达式不能改变查询结构")
        condition = wrapper.args["where"].this.this
        for node in condition.walk():
            name = type(node).__name__
            if name == "Anonymous":
                if (node.name.upper() not in _ANONYMOUS.get(dialect, ())
                        and node.name.upper() not in _SHARED_ANONYMOUS):
                    raise ValueError("条件表达式不允许调用此函数")
            elif name not in _NODES:
                raise ValueError("条件表达式包含不支持的结构")
            if isinstance(node, exp.Select):
                if any(v and k not in _SELECT_ARGS for k, v in node.args.items()):
                    raise ValueError("子查询必须只读取数据")
            if isinstance(node, exp.Table) and not isinstance(node.this, exp.Identifier):
                raise ValueError("不允许外部表函数")
            if isinstance(node, exp.DataType) and node.this.name not in _TYPES:
                raise ValueError("不支持此类型转换")
            if isinstance(node, exp.In) and not node.expressions and not node.args.get("query"):
                raise ValueError("IN 列表不能为空")
        return condition
    except (SqlglotError, RecursionError, KeyError) as error:
        raise ValueError("条件表达式语法不受支持") from error


def require_condition_expr(expr, db_type=None):
    if expr is None or expr == "":
        return
    _parse(expr, db_type)


def validate_condition_expr(expr, db_type=None):
    try:
        require_condition_expr(expr, db_type)
        return True
    except (ValueError, TypeError):
        return False


def replace_column(expr, quoted_column, db_type=None):
    """Use AST source spans to replace bare column references only."""
    if not expr:
        return ""
    condition = _parse(expr, db_type)
    spans = []
    if condition is not None:
        for column in condition.find_all(exp.Column):
            identifier = column.this
            if (column.name.lower() == "column" and not column.table
                    and isinstance(identifier, exp.Identifier) and not identifier.quoted):
                spans.append((identifier.meta["start"] - len(_PREFIX),
                              identifier.meta["end"] + 1 - len(_PREFIX)))
    result = expr
    for start, end in sorted(set(spans), reverse=True):
        result = result[:start] + quoted_column + result[end:]
    require_condition_expr(result, db_type)
    return result


_QUERY_NODES = _NODES | frozenset("""
    Alias TableAlias With CTE Union Intersect Except Filter Qualify Fetch Placeholder
    RowNumber Rank DenseRank Lag Lead FirstValue LastValue NthValue
""".split())
_QUERY_SELECT_ARGS = _SELECT_ARGS | {"with_", "qualify"}


def require_read_only_sql(sql, db_type=None):
    """Accept one supported read query without rewriting its dialect spelling."""
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 65536 or "\x00" in sql:
        raise ValueError("完整 SQL 不能为空、类型错误或过长")
    dialect = _dialect(db_type)
    try:
        tokens = sqlglot.Dialect.get_or_raise(dialect).tokenize(sql)
        if len(tokens) > 4096:
            raise ValueError("查询过于复杂")
        quoted_calls = []
        depth = 0
        for index, token in enumerate(tokens):
            if token.comments:
                raise ValueError("不支持注释或查询提示")
            if token.token_type == TokenType.SEMICOLON and index != len(tokens) - 1:
                raise ValueError("只允许一条查询及可选的结尾分号")
            if (token.token_type == TokenType.IDENTIFIER
                    and index + 1 < len(tokens)
                    and tokens[index + 1].token_type == TokenType.L_PAREN):
                quoted_calls.append(token.start)
            if token.token_type == TokenType.L_PAREN:
                depth += 1
                if depth > 64:
                    raise ValueError("查询嵌套过深")
            elif token.token_type == TokenType.R_PAREN:
                depth -= 1
        statements = sqlglot.parse(sql, read=dialect)
        if len(statements) != 1 or not isinstance(
                statements[0], (exp.Select, exp.SetOperation, exp.Subquery)):
            raise ValueError("仅允许单条只读 SELECT 查询")
        # SQLGlot normalizes quoted built-ins, but quoted CTE/table aliases
        # followed by a column list are declarations, not function calls.
        alias_starts = {
            node.this.meta.get("start")
            for node in statements[0].find_all(exp.TableAlias)
            if isinstance(node.this, exp.Identifier)
        }
        if any(start not in alias_starts for start in quoted_calls):
            raise ValueError("不允许引用函数名")
        for node in statements[0].walk():
            name = type(node).__name__
            if name == "Anonymous":
                if (node.name.upper() not in _ANONYMOUS.get(dialect, ())
                        and node.name.upper() not in _SHARED_ANONYMOUS):
                    raise ValueError("不允许调用此函数")
            elif name not in _QUERY_NODES:
                raise ValueError("包含不支持的结构: " + name)
            if isinstance(node, exp.Select):
                if any(v and k not in _QUERY_SELECT_ARGS for k, v in node.args.items()):
                    raise ValueError("查询不能写入、加锁或改变数据库状态")
            if isinstance(node, exp.Table) and not isinstance(node.this, exp.Identifier):
                raise ValueError("不允许外部表函数")
            if isinstance(node, exp.DataType) and node.this.name not in _TYPES:
                raise ValueError("不支持此类型转换")
    except (SqlglotError, RecursionError, KeyError, ValueError) as error:
        raise ValueError("完整 SQL 必须是受支持的单条只读查询：" + str(error)) from error


def require_conditions_payload(data, db_type=None):
    if not isinstance(data, dict):
        raise ValueError("请求参数必须是对象")
    for field in ("sql_text", "sql_preview"):
        value = data.get(field)
        if value is not None and value != "":
            require_read_only_sql(value, db_type)
    require_condition_expr(data.get("condition_expr"), db_type)
    conditions = data.get("conditions")
    if conditions is not None:
        if not isinstance(conditions, list):
            raise ValueError("conditions 必须是数组")
        for item in conditions:
            if not isinstance(item, dict):
                raise ValueError("条件必须是对象")
            require_condition_expr(item.get("condition"), db_type)
    if data.get("condition_mode", "AND") not in ("AND", "OR"):
        raise ValueError("condition_mode 必须是 AND 或 OR")
