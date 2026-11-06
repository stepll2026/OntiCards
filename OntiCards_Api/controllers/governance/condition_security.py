"""Restricted, side-effect-free SQL condition grammar for governance rules.

This is deliberately not a SQL statement parser. No subqueries, qualified
functions, comments, casts or arbitrary function calls are accepted.
"""
import re

_TOKEN = re.compile(
    r"\s+|'(?:''|[^'\\\x00])*'|\"(?:\"\"|[^\"\\\x00])*\"|"
    r"`(?:``|[^`\\\x00])*`|\[(?:\]\]|[^\]\\\x00])*\]|"
    r"\d+(?:\.\d+)?|(?:[^\W\d]|_)\w*|"
    r"<=|>=|<>|!=|!~\*?|~\*?|[=<>+*/%(),~-]", re.UNICODE)
_FUNCTIONS = frozenset("""
    LENGTH CHAR_LENGTH CHARACTER_LENGTH LEN TRIM LTRIM RTRIM LOWER UPPER
    ABS ROUND COALESCE NULLIF REGEXP_LIKE DATE_TRUNC NOW
""".split())
_RESERVED = frozenset("""
    SELECT FROM WHERE UNION INTERSECT EXCEPT WITH INSERT UPDATE DELETE DROP
    ALTER CREATE EXEC EXECUTE INTO OUTFILE LOAD COPY CALL DO GRANT REVOKE
    AS JOIN ON GROUP ORDER HAVING LIMIT OFFSET FETCH OVER FILTER RETURNING
    AND OR NOT IS NULL TRUE FALSE IN LIKE ILIKE BETWEEN REGEXP INTERVAL
    CURRENT_DATE CURRENT_TIMESTAMP
""".split())


def _tokens(expr):
    if not isinstance(expr, str) or len(expr) > 8192:
        raise ValueError("条件表达式过长或类型错误")
    # Reject comment delimiters outside literals during tokenization.
    result = []
    pos = 0
    while pos < len(expr):
        if expr.startswith(("--", "/*", "*/"), pos):
            raise ValueError("条件表达式不允许注释")
        match = _TOKEN.match(expr, pos)
        if not match:
            raise ValueError("条件表达式包含不支持的字符")
        token = match.group()
        pos = match.end()
        if not token.isspace():
            result.append(token)
    if len(result) > 512:
        raise ValueError("条件表达式过于复杂")
    return result


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def peek(self):
        return self.tokens[self.pos].upper() if self.pos < len(self.tokens) else ""

    def take(self, *choices):
        if self.peek() in choices:
            self.pos += 1
            return True
        return False

    def expect(self, *choices):
        if not self.take(*choices):
            raise ValueError("条件表达式语法错误")

    def expression(self):
        self.depth += 1
        if self.depth > 32:
            raise ValueError("条件表达式嵌套过深")
        self.conjunction()
        while self.take("OR"):
            self.conjunction()
        self.depth -= 1

    def conjunction(self):
        self.predicate()
        while self.take("AND"):
            self.predicate()

    def predicate(self):
        if self.take("NOT"):
            # Count NOT nesting too.
            self.expression_not()
            return
        self.arithmetic()
        if self.take("IS"):
            self.take("NOT")
            self.expect("NULL", "TRUE", "FALSE")
        elif self.take("=", "!=", "<>", "<", ">", "<=", ">=", "~", "~*", "!~", "!~*"):
            self.arithmetic()
        else:
            negated = self.take("NOT")
            if self.take("BETWEEN"):
                self.arithmetic()
                self.expect("AND")
                self.arithmetic()
            elif self.take("IN"):
                self.expect("(")
                self.arithmetic()
                while self.take(","):
                    self.arithmetic()
                self.expect(")")
            elif self.take("LIKE", "ILIKE", "REGEXP"):
                self.arithmetic()
            elif negated:
                raise ValueError("NOT 后缺少谓词")

    def expression_not(self):
        self.depth += 1
        if self.depth > 32:
            raise ValueError("条件表达式嵌套过深")
        self.predicate()
        self.depth -= 1

    def arithmetic(self):
        self.product()
        while self.take("+", "-"):
            self.product()

    def product(self):
        self.atom()
        while self.take("*", "/", "%"):
            self.atom()

    def atom(self):
        signs = 0
        while self.take("+", "-"):
            signs += 1
            if signs > 8:
                raise ValueError("过多一元运算符")
        if self.take("("):
            self.expression()
            self.expect(")")
            return
        token = self.peek()
        if not token:
            raise ValueError("缺少条件操作数")
        raw = self.tokens[self.pos]
        self.pos += 1
        if raw[0] in "'\"`[" or raw[0].isdigit():
            return
        if token in ("NULL", "TRUE", "FALSE", "CURRENT_DATE", "CURRENT_TIMESTAMP"):
            return
        if token == "INTERVAL":
            if not self.peek().startswith("'"):
                raise ValueError("INTERVAL 必须使用字符串常量")
            self.pos += 1
            return
        if self.take("("):
            if token not in _FUNCTIONS:
                raise ValueError("条件表达式不允许调用此函数")
            self.depth += 1
            if self.depth > 32:
                raise ValueError("条件表达式嵌套过深")
            if not self.take(")"):
                self.expression()
                while self.take(","):
                    self.expression()
                self.expect(")")
            self.depth -= 1
        elif token in _RESERVED or not (raw[0].isalpha() or raw[0] == "_"):
            raise ValueError("条件表达式不允许 SQL 语句")


def require_condition_expr(expr):
    """Raise ValueError before constructing SQL from an untrusted expression."""
    if expr is None or expr == "":
        return
    tokens = _tokens(expr)
    parser = _Parser(tokens)
    if not tokens:
        return
    parser.expression()
    if parser.pos != len(tokens):
        raise ValueError("条件表达式必须是一个完整表达式")


def validate_condition_expr(expr):
    try:
        require_condition_expr(expr)
        return True
    except (ValueError, TypeError, RecursionError):
        return False


def replace_column(expr, quoted_column):
    """Replace only bare placeholder tokens, preserving strings and identifiers."""
    require_condition_expr(expr)
    return _TOKEN.sub(
        lambda m: quoted_column if m.group().lower() == "column" else m.group(),
        expr or "")


def require_conditions_payload(data):
    """Validate explicit API inputs before mutating an ORM object."""
    if not isinstance(data, dict):
        raise ValueError("请求参数必须是对象")
    require_condition_expr(data.get("condition_expr"))
    conditions = data.get("conditions")
    if conditions is not None:
        if not isinstance(conditions, list):
            raise ValueError("conditions 必须是数组")
        for item in conditions:
            if not isinstance(item, dict):
                raise ValueError("条件必须是对象")
            require_condition_expr(item.get("condition"))
    if data.get("condition_mode", "AND") not in ("AND", "OR"):
        raise ValueError("condition_mode 必须是 AND 或 OR")
