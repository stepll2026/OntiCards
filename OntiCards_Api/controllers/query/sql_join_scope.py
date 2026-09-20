"""Validate PostgreSQL relation visibility without rewriting generated SQL.

This is a relation-name guard, not a column/type resolver or a replacement for
the physical-table whitelist. In particular, JOIN's ON can see its two input
subtrees, not every table mentioned anywhere in the statement. Keep the parser
version pinned: comma joins and parenthesized joins have significant AST shapes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.dialects.postgres import Postgres
from sqlglot.errors import ErrorLevel, SqlglotError
from sqlglot.tokens import TokenType


_PG_TYPES = frozenset({"postgresql", "postgres", "pgsql", "kingbase", "kingbasees"})
Key = tuple[str, ...]


class _PostgresScopeDialect(Postgres):
    class Parser(Postgres.Parser):
        def _parse_table_sample(self, as_modifier: bool = False):
            # SQLGlot 30.18's generic parser restricts REPEATABLE to numbers.
            # PostgreSQL accepts expressions in both sampling arguments. Keep
            # them in the AST so the scope guard also checks their references.
            if not self._match(TokenType.TABLE_SAMPLE):
                return None
            method = self._parse_var(upper=True)
            if method is None:
                self.raise_error("Expected TABLESAMPLE method")
            percent = self._parse_wrapped(self._parse_expression)
            seed = (self._parse_wrapped(self._parse_expression)
                    if self._match_text_seq("REPEATABLE") else None)
            return self.expression(exp.TableSample(method=method,
                                                   percent=percent, seed=seed))


class JoinAliasScopeError(ValueError):
    """A safe, structured diagnostic; never includes SQL literals or SQL text."""

    def __init__(self, alias: str = "", current_join: str = "QUERY",
                 allowed_aliases: Iterable[str] = (), *,
                 code: str = "JOIN_ALIAS_OUT_OF_SCOPE"):
        self.code = code
        self.alias = alias
        self.current_join = current_join
        self.allowed_aliases = tuple(sorted(set(allowed_aliases)))
        message = (f"{code}: alias={alias or '<none>'}; context={current_join}; "
                   f"allowed_aliases={','.join(self.allowed_aliases) or '<none>'}")
        super().__init__(message)


@dataclass(frozen=True)
class _Binding:
    origin: Key | None
    explicit_alias: bool


Bindings = dict[Key, _Binding]


@dataclass(frozen=True)
class _Frame:
    bindings: Bindings
    # A RIGHT/FULL JOIN input is present but unavailable to a lateral reference.
    # It must not accidentally resolve to an ancestor with the same name.
    blocked: frozenset[Key] = frozenset()


Frames = tuple[_Frame, ...]


def _ident(node: exp.Expression) -> str:
    if not isinstance(node, exp.Identifier):
        raise JoinAliasScopeError(code="JOIN_SCOPE_UNSUPPORTED")
    value = node.name
    return value if node.args.get("quoted") else value.lower()


def _allowed(frames: Frames) -> tuple[str, ...]:
    seen: set[Key] = set()
    result: set[str] = set()
    for frame in frames:
        for key in frame.bindings:
            if key not in seen:
                result.add(".".join(key))
        seen.update(frame.bindings)
        seen.update(frame.blocked)
    return tuple(sorted(result))


def _unsupported(context: str) -> None:
    raise JoinAliasScopeError(current_join=context, code="JOIN_SCOPE_UNSUPPORTED")


def _check_args(node: exp.Expression, supported: set[str], context: str) -> None:
    if any(value for key, value in node.args.items() if key not in supported):
        _unsupported(context)


def _alias_binding(node: exp.Expression) -> Bindings | None:
    alias = node.args.get("alias")
    if alias is None:
        return None
    if not isinstance(alias, exp.TableAlias) or alias.this is None:
        _unsupported("RELATION ALIAS")
    return {(_ident(alias.this),): _Binding(None, True)}


def _merge(left: Bindings, right: Bindings, context: str) -> Bindings:
    for key in left.keys() & right.keys():
        a, b = left[key], right[key]
        # PostgreSQL permits unaliased same-named tables in different schemas.
        # Their qualified names remain usable; column ambiguity is checked by PG.
        if (a.explicit_alias or b.explicit_alias or a.origin is None
                or b.origin is None or a.origin == b.origin):
            raise JoinAliasScopeError(".".join(key), context,
                                      (".".join(k) for k in left),
                                      code="JOIN_SCOPE_DUPLICATE_ALIAS")
    return {**left, **right}


def _label(node: exp.Expression) -> str:
    aliases = _alias_binding(node)
    if aliases:
        return next(iter(aliases))[0]
    if isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier):
        return _ident(node.this)
    return "<derived>"


def _walk(node: exp.Expression, frames: Frames, context: str) -> None:
    if isinstance(node, (exp.Select, exp.SetOperation, exp.Subquery, exp.Values)):
        _query(node, frames, context)
        return
    if isinstance(node, exp.Column) and node.args.get("table"):
        key = tuple(_ident(node.args[k]) for k in ("catalog", "db", "table")
                    if node.args.get(k) is not None)
        for frame in frames:
            if key in frame.blocked:
                break
            if key in frame.bindings:
                return
        raise JoinAliasScopeError(".".join(key), context, _allowed(frames))
    # Unexpected relational nodes must not get treated as ordinary expressions.
    if isinstance(node, (exp.Table, exp.Join, exp.Lateral, exp.CTE, exp.From)):
        _unsupported(context)
    for child in node.iter_expressions():
        _walk(child, frames, context)


def _walk_args(node: exp.Expression, frames: Frames, context: str,
               exclude: set[str]) -> None:
    for key, value in node.args.items():
        if key in exclude:
            continue
        if isinstance(value, exp.Expression):
            _walk(value, frames, context)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, exp.Expression):
                    _walk(child, frames, context)


def _record_function_names(statement: exp.Expression, sql: str) -> None:
    """Keep the input spelling when SQLGlot canonicalizes a function name.

    For example, PostgreSQL's generate_series is an ExplodingGenerateSeries
    node. Its implicit relation name is still generate_series. Parser token
    locations let us retain that identifier without serializing/reformatting SQL.
    """
    for function in statement.find_all(exp.Func):
        start, end = function.meta.get("start"), function.meta.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        name = sql[start:end + 1]
        if name.startswith('"') and name.endswith('"'):
            function.meta["pg_range_name"] = name[1:-1].replace('""', '"')
        elif name.replace("$", "_").isidentifier():
            function.meta["pg_range_name"] = name.lower()


def _function_relation(node: exp.Expression, lateral: Frames, context: str,
                       aliases: Bindings | None = None) -> Bindings:
    # An explicit LATERAL schema.function(...) is represented as a Dot, while
    # an implicit one is a Table with a separate db argument.
    if isinstance(node, exp.Dot) and isinstance(node.expression, exp.Func):
        qualifier = node.this
        while isinstance(qualifier, exp.Dot):
            _ident(qualifier.expression)
            qualifier = qualifier.this
        _ident(qualifier)
        node = node.expression
    if not isinstance(node, exp.Func):
        _unsupported(context)
    aliases = aliases or _alias_binding(node)
    if isinstance(node, exp.Unnest):
        _check_args(node, {"expressions", "alias", "offset"}, context)
        # offset is an output column name/bool for WITH ORDINALITY, not an
        # input expression or an extra relation visible to later JOINs.
        offset = node.args.get("offset")
        if offset is not None and not isinstance(offset, (bool, exp.Identifier)):
            _unsupported(context)
        _walk_args(node, lateral, context, {"alias", "offset"})
        name = "unnest"
    else:
        _walk_args(node, lateral, context, {"alias"})
        name = node.meta.get("pg_range_name")
        if not name and isinstance(node, exp.Anonymous):
            name = (_ident(node.this) if isinstance(node.this, exp.Identifier)
                    else node.name.lower())
    if aliases is not None:
        return aliases
    if not name:
        _unsupported(context)
    return {(name,): _Binding(None, False)}


def _table_sample(node: exp.Expression, outers: Frames, context: str) -> None:
    if not isinstance(node, exp.TableSample):
        _unsupported(context)
    _check_args(node, {"method", "percent", "size", "seed"}, context)
    # TABLESAMPLE arguments can capture an outer query, but unlike table
    # functions they are not implicitly LATERAL to sibling FROM items.
    _walk_args(node, outers, context, {"method"})


def _relation(node: exp.Expression, outers: Frames, lateral: Frames,
              context: str) -> Bindings:
    """Return names exported by one FROM item, validating its nested scopes."""
    aliases = _alias_binding(node)
    if isinstance(node, exp.Lateral):
        _check_args(node, {"this", "alias", "ordinality"}, context)
        inner = node.this
        if isinstance(inner, (exp.Select, exp.SetOperation, exp.Subquery, exp.Values)):
            _query(inner, lateral, context)
        elif isinstance(inner, (exp.Func, exp.Dot)):
            return _function_relation(inner, lateral, context, aliases)
        else:
            _unsupported(context)
        if aliases is None:
            aliases = _alias_binding(inner)
        if aliases is None:
            _unsupported(context)
        return aliases

    if isinstance(node, exp.Subquery):
        _check_args(node, {"this", "alias", "joins"}, context)
        inner = node.this
        if isinstance(inner, (exp.Select, exp.SetOperation, exp.Values)):
            # Ordinary derived tables cannot capture sibling FROM items.
            _query(inner, outers, context)
            result = aliases or {}
        elif isinstance(inner, (exp.Table, exp.Subquery)):
            # Parenthesized JOINs are range subtrees, not correlated subqueries.
            inside = _relation(inner, outers, lateral, context)
            result = aliases if aliases is not None else inside
        else:
            _unsupported(context)
        return _joins(result, node.args.get("joins") or [], outers, lateral, context)

    if isinstance(node, exp.Table):
        _check_args(node, {"this", "db", "catalog", "alias", "joins", "only",
                           "ordinality", "sample"}, context)
        if isinstance(node.this, exp.Identifier):
            origin = tuple(_ident(node.args[k]) for k in ("catalog", "db", "this")
                           if node.args.get(k) is not None)
            if aliases is not None:
                result = aliases
            else:
                binding = _Binding(origin, False)
                result = {origin[-1:]: binding, origin: binding}
        elif isinstance(node.this, exp.Func):
            # PostgreSQL FROM functions are implicitly LATERAL.
            result = _function_relation(node.this, lateral, context, aliases)
        else:
            _unsupported(context)
        if node.args.get("sample") is not None:
            _table_sample(node.args["sample"], outers, context)
        return _joins(result, node.args.get("joins") or [], outers, lateral, context)

    if isinstance(node, exp.Values):
        _check_args(node, {"expressions", "alias"}, context)
        _walk_args(node, outers, context, {"alias"})
        return aliases or {}

    if isinstance(node, exp.Unnest):
        return _function_relation(node, lateral, context, aliases)

    _unsupported(context)


def _joins(first: Bindings, joins: list[exp.Join], outers: Frames,
           lateral_prefix: Frames, context: str) -> Bindings:
    # 'all_items' is visible after FROM, while 'term' is the left subtree of
    # the next explicit JOIN. A comma starts a new term (JOIN binds tighter).
    all_items = first
    term = first
    for join in joins:
        if not isinstance(join, exp.Join):
            _unsupported(context)
        _check_args(join, {"this", "on", "using", "side", "kind", "method"}, context)
        side, kind, method = join.side.upper(), join.kind.upper(), join.method.upper()
        if side not in ("", "LEFT", "RIGHT", "FULL") or kind not in ("", "INNER", "OUTER", "CROSS"):
            _unsupported(context)
        if method not in ("", "NATURAL"):
            _unsupported(context)
        current = "JOIN " + _label(join.this)
        comma = not any(join.args.get(k) for k in ("side", "kind", "method", "on", "using"))
        blocked = frozenset(term) if side in ("RIGHT", "FULL") else frozenset()
        lateral_bindings = {k: v for k, v in all_items.items() if k not in blocked}
        # Prefix frames carry preceding enclosing FROM items for LATERAL only;
        # they must never leak into a parenthesized inner JOIN's ON condition.
        lateral = (_Frame(lateral_bindings, blocked),) + lateral_prefix
        right = _relation(join.this, outers, lateral, current)
        combined = _merge(term, right, current) if not comma else right
        if join.args.get("on") is not None:
            _walk(join.args["on"], (_Frame(combined),) + outers, current)
        all_items = _merge(all_items, right, current)
        term = combined
    return all_items


def _query(node: exp.Expression, outers: Frames, context: str) -> None:
    if isinstance(node, exp.Subquery):
        _check_args(node, {"this", "alias"}, context)
        _query(node.this, outers, context)
        return
    if isinstance(node, exp.Values):
        _check_args(node, {"expressions", "alias"}, context)
        _walk_args(node, outers, context, {"alias"})
        return
    if not isinstance(node, (exp.Select, exp.SetOperation)):
        _unsupported(context)
    with_clause = node.args.get("with_")
    if with_clause:
        _check_args(with_clause, {"expressions", "recursive"}, "WITH")
        for cte in with_clause.expressions:
            if not isinstance(cte, exp.CTE):
                _unsupported("WITH")
            _check_args(cte, {"this", "alias", "materialized"}, "WITH")
            # CTE bodies do not inherit the main query's FROM aliases. A CTE
            # becomes a visible relation only when referenced in FROM/JOIN.
            _query(cte.this, outers, "CTE " + _label(cte))
    if isinstance(node, exp.SetOperation):
        _check_args(node, {"this", "expression", "distinct", "with_", "order", "limit", "offset"}, context)
        _query(node.this, outers, context)
        _query(node.expression, outers, context)
        _walk_args(node, outers, context, {"this", "expression", "with_"})
        return
    _check_args(node, {"expressions", "from_", "joins", "with_", "distinct",
                       "where", "group", "having", "windows", "order", "limit", "offset"}, context)
    from_clause = node.args.get("from_")
    bindings: Bindings = {}
    if from_clause is not None:
        _check_args(from_clause, {"this"}, context)
        bindings = _relation(from_clause.this, outers, outers, context)
    bindings = _joins(bindings, node.args.get("joins") or [], outers, outers, context)
    _walk_args(node, (_Frame(bindings),) + outers, context, {"from_", "joins", "with_"})


def validate_join_alias_scope(sql: str, db_type: str | None) -> None:
    """Validate PG/Kingbase SELECT relation scopes; leave other dialects alone.

    No statement is executed, normalized or transpiled. Parser diagnostics are
    intentionally replaced so literal credentials/customer values cannot leak.
    Unsupported constructs are rejected explicitly, never silently skipped.
    """
    if (db_type or "").strip().lower() not in _PG_TYPES:
        return
    try:
        statements = sqlglot.parse(sql, read=_PostgresScopeDialect,
                                  error_level=ErrorLevel.RAISE)
    except (SqlglotError, ValueError, TypeError, RecursionError):
        raise JoinAliasScopeError(code="JOIN_SCOPE_PARSE_ERROR") from None
    if len(statements) != 1 or statements[0] is None:
        raise JoinAliasScopeError(code="JOIN_SCOPE_PARSE_ERROR")
    try:
        _record_function_names(statements[0], sql)
        _query(statements[0], (), "QUERY")
    except RecursionError:
        raise JoinAliasScopeError(code="JOIN_SCOPE_UNSUPPORTED") from None
