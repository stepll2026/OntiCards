"""Regression coverage for JOIN visibility, without app/DB initialization."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


_PATH = Path(__file__).resolve().parents[1] / "controllers/query/sql_join_scope.py"
_SPEC = importlib.util.spec_from_file_location("_test_sql_join_scope", _PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
validate_join_alias_scope = _MODULE.validate_join_alias_scope
JoinAliasScopeError = _MODULE.JoinAliasScopeError


@pytest.mark.parametrize("sql", [
    # The customer dependency chain: t3 must exist before t5's ON.
    "SELECT t2.id FROM a t2 LEFT JOIN b t4 ON t2.id=t4.id "
    "LEFT JOIN c t3 ON t4.id=t3.id LEFT JOIN d t1 ON t1.id=t2.id "
    "LEFT JOIN e t5 ON t5.id=t3.id",
    "SELECT a.id FROM a JOIN b ON a.id=b.id",
    "SELECT a.id FROM a FULL OUTER JOIN b ON a.id=b.id",
    "SELECT a.id FROM a RIGHT JOIN b ON a.id=b.id",
    "SELECT a.id FROM a NATURAL LEFT JOIN b",
    "SELECT a.id FROM a JOIN b USING(id)",
    "SELECT a.id FROM a, b JOIN c ON b.id=c.id WHERE a.id=c.id",
    "SELECT a.id FROM a CROSS JOIN b JOIN c ON a.id=c.id",
    "SELECT a.id FROM a LEFT JOIN (b JOIN c ON b.id=c.id) ON a.id=b.id",
    "SELECT x.id FROM (a JOIN b ON a.id=b.id) x JOIN c ON x.id=c.id",
    "WITH x AS (SELECT a.id FROM a JOIN b ON a.id=b.id) "
    "SELECT x.id FROM x JOIN c ON x.id=c.id",
    "WITH x AS (SELECT a.id FROM a), y AS (SELECT x.id FROM x) "
    "SELECT y.id FROM y JOIN c ON y.id=c.id",
    "WITH RECURSIVE x(id) AS (SELECT 1 UNION ALL SELECT x.id+1 FROM x WHERE x.id<3) "
    "SELECT x.id FROM x JOIN a ON x.id=a.id",
    "SELECT x.id FROM (SELECT a.id FROM a) x JOIN b ON x.id=b.id",
    "SELECT a.id FROM a JOIN b ON EXISTS (SELECT 1 FROM c WHERE c.id=a.id AND c.id=b.id)",
    "SELECT a.id FROM a WHERE EXISTS (SELECT 1 FROM b JOIN c ON c.id=a.id)",
    "SELECT t3.id FROM a t3 WHERE EXISTS (SELECT 1 FROM b JOIN c ON c.id=t3.id "
    "JOIN a t3 ON t3.id=b.id)",
    "SELECT x.id FROM a x WHERE EXISTS (SELECT 1 FROM b x JOIN c ON x.id=c.id)",
    "SELECT a.id FROM a JOIN LATERAL (SELECT a.id) x ON x.id=a.id",
    "SELECT a.id FROM a, LATERAL (SELECT a.id) x JOIN b ON x.id=b.id",
    "SELECT a.id FROM a LEFT JOIN LATERAL (SELECT a.id) x ON true",
    "SELECT a.id FROM a, b RIGHT JOIN LATERAL (SELECT a.id) x ON true",
    "SELECT a.id FROM a RIGHT JOIN LATERAL (SELECT 1 AS id) x ON true",
    "SELECT a.id FROM a, unnest(a.arr) u",
    "SELECT a.id FROM a JOIN generate_series(1,a.id) AS g ON true",
    'SELECT "T".id FROM a AS "T" JOIN b ON "T".id=b.id',
    'SELECT t.id FROM a AS T JOIN b ON t.id=b.id',
    "SELECT public.a.id FROM public.a JOIN public.b ON public.a.id=public.b.id",
    "SELECT s1.a.id FROM s1.a JOIN s2.a ON s1.a.id=s2.a.id",
    "SELECT a.id FROM a JOIN b ON b.id=a.id AND 't9.id secret'='t9.id secret'",
    "SELECT x.id FROM (VALUES(1)) x(id) JOIN a ON x.id=a.id",
    "SELECT a.id FROM a UNION ALL SELECT b.id FROM b",
    "SELECT a.id FROM a WHERE EXISTS (SELECT x.id FROM (SELECT a.id) x)",
    "SELECT a.id FROM a WHERE EXISTS (WITH x AS (SELECT a.id) SELECT x.id FROM x)",
    "SELECT generate_series.generate_series FROM generate_series(1,3)",
    "SELECT generate_series.generate_series FROM pg_catalog.generate_series(1,3)",
    "SELECT lower.lower FROM lower('ABC')",
    'SELECT "MyFunc".id FROM "MyFunc"(1)',
    "SELECT a.id, json_each.key FROM a CROSS JOIN json_each(a.data)",
    "SELECT a.id FROM a CROSS JOIN LATERAL unnest(a.arr)",
    "SELECT a.id FROM a CROSS JOIN LATERAL pg_catalog.generate_series(1,a.id)",
    "SELECT generate_series.ordinality FROM generate_series(1,3) WITH ORDINALITY",
    "SELECT unnest.ordinality FROM unnest(ARRAY[1,2]) WITH ORDINALITY",
    "SELECT a.id, u.ordinal FROM a CROSS JOIN unnest(a.arr) "
    "WITH ORDINALITY AS u(value, ordinal)",
    "SELECT a.id, u.ordinal FROM a CROSS JOIN LATERAL unnest(a.arr) "
    "WITH ORDINALITY AS u(value, ordinal)",
    "SELECT a.id, g.ordinal FROM a CROSS JOIN LATERAL generate_series(1,a.id) "
    "WITH ORDINALITY AS g(value, ordinal)",
    "SELECT a.id FROM a TABLESAMPLE SYSTEM (10) REPEATABLE (1)",
    "SELECT a.id FROM a WHERE EXISTS (SELECT b.id FROM b "
    "TABLESAMPLE SYSTEM ((a.id)))",
    "SELECT a.id FROM a WHERE EXISTS (SELECT b.id FROM b "
    "TABLESAMPLE SYSTEM (10) REPEATABLE ((a.id)))",
    "SELECT a.id FROM a WHERE EXISTS (SELECT b.id FROM b "
    "TABLESAMPLE SYSTEM (a.id) REPEATABLE (a.id + 1))",
    "SELECT a.id FROM ((a JOIN b ON a.id=b.id)) JOIN c ON a.id=c.id",
    "SELECT x.id FROM ((a JOIN b ON a.id=b.id)) x JOIN c ON x.id=c.id",
    "SELECT x.id FROM ((SELECT a.id FROM a)) x JOIN c ON x.id=c.id",
    "SELECT x.id FROM ((SELECT a.id FROM a) x) JOIN c ON x.id=c.id",
])
def test_legal_scopes(sql):
    assert validate_join_alias_scope(sql, "postgresql") is None


@pytest.mark.parametrize("sql, bad_alias", [
    ("SELECT t2.id FROM a t2 LEFT JOIN e t5 ON t5.id=t3.id LEFT JOIN c t3 ON t3.id=t2.id", "t3"),
    ("SELECT a.id FROM a JOIN b ON b.id=c.id JOIN c ON c.id=a.id", "c"),
    ("SELECT a.id FROM a JOIN b ON missing.id=b.id", "missing"),
    ("SELECT a.id FROM a, b JOIN c ON a.id=c.id", "a"),
    ("SELECT a.id FROM a, b LEFT JOIN c ON a.id=c.id", "a"),
    ("SELECT a.id FROM a JOIN (b JOIN c ON a.id=c.id) ON a.id=b.id", "a"),
    ("SELECT x.id FROM (a JOIN b ON a.id=b.id) x JOIN c ON a.id=c.id", "a"),
    ("WITH x AS (SELECT a.id FROM a) SELECT x.id FROM x JOIN b ON a.id=b.id", "a"),
    ("WITH x AS (SELECT b.id FROM b JOIN c ON a.id=c.id) SELECT a.id FROM a JOIN x ON a.id=x.id", "a"),
    ("WITH x AS (SELECT a.id FROM a) SELECT b.id FROM b JOIN c ON x.id=c.id", "x"),
    ("SELECT x.id FROM (SELECT a.id FROM a) x JOIN b ON a.id=b.id", "a"),
    ("SELECT a.id FROM a JOIN (SELECT a.id) x ON true", "a"),
    ("SELECT a.id FROM a JOIN b ON EXISTS (SELECT 1 FROM c WHERE c.id=d.id) JOIN d ON true", "d"),
    ("SELECT a.id FROM a JOIN LATERAL (SELECT b.id) x ON true JOIN b ON true", "b"),
    ("SELECT a.id FROM a RIGHT JOIN LATERAL (SELECT a.id) x ON true", "a"),
    ("SELECT a.id FROM a FULL JOIN LATERAL (SELECT a.id) x ON true", "a"),
    ("SELECT a.id FROM a, b RIGHT JOIN LATERAL (SELECT b.id) x ON true", "b"),
    ('SELECT "T".id FROM a AS "T" JOIN b ON t.id=b.id', "t"),
    ("SELECT x.id FROM public.a x JOIN b ON public.a.id=b.id", "public.a"),
    ("SELECT a.id FROM a UNION ALL SELECT b.id FROM b JOIN c ON a.id=c.id", "a"),
    ("SELECT a.id FROM a JOIN unnest(z.arr) u ON true", "z"),
    ("SELECT a.id FROM a CROSS JOIN generate_series(1,b.id) JOIN b ON true", "b"),
    ("SELECT a.id FROM a CROSS JOIN LATERAL pg_catalog.generate_series(1,b.id) "
     "JOIN b ON true", "b"),
    ("SELECT a.id FROM a CROSS JOIN json_each(b.data) JOIN b ON true", "b"),
    ("SELECT a.id FROM a CROSS JOIN unnest(b.arr) WITH ORDINALITY "
     "JOIN b ON true", "b"),
    ("SELECT a.id FROM a CROSS JOIN LATERAL unnest(b.arr) WITH ORDINALITY "
     "JOIN b ON true", "b"),
    ("SELECT a.id FROM a RIGHT JOIN LATERAL unnest(a.arr) ON true", "a"),
    ("SELECT a.id FROM a FULL JOIN generate_series(1,a.id) ON true", "a"),
    ("SELECT ordinality.id FROM unnest(ARRAY[1,2]) WITH ORDINALITY", "ordinality"),
    ("SELECT generate_series.id FROM generate_series(1,3) g", "generate_series"),
    ("SELECT a.id FROM a TABLESAMPLE SYSTEM ((a.id))", "a"),
    ("SELECT a.id FROM a JOIN b TABLESAMPLE SYSTEM ((a.id)) ON true", "a"),
    ("SELECT a.id FROM a, b TABLESAMPLE SYSTEM ((a.id))", "a"),
    ("SELECT a.id FROM a JOIN b TABLESAMPLE SYSTEM (a.id) ON true", "a"),
    ("SELECT a.id FROM a JOIN b TABLESAMPLE SYSTEM (10) REPEATABLE ((a.id)) "
     "ON true", "a"),
    ("SELECT a.id FROM a JOIN d ON EXISTS (SELECT b.id FROM b TABLESAMPLE "
     "SYSTEM ((c.id))) JOIN c ON true", "c"),
    ("SELECT a.id FROM a JOIN ((b JOIN c ON a.id=c.id)) ON a.id=b.id", "a"),
    ("SELECT a.id FROM ((a JOIN b ON a.id=b.id)) x JOIN c ON x.id=c.id", "a"),
    ("SELECT a.id FROM a JOIN ((SELECT a.id)) x ON true", "a"),
])
def test_invalid_scopes(sql, bad_alias):
    with pytest.raises(JoinAliasScopeError) as caught:
        validate_join_alias_scope(sql, "postgresql")
    assert caught.value.code == "JOIN_ALIAS_OUT_OF_SCOPE"
    assert caught.value.alias == bad_alias
    assert isinstance(caught.value.allowed_aliases, tuple)


@pytest.mark.parametrize("db_type", ["postgresql", "POSTGRES", " pgsql ", "kingbase", "kingbasees"])
def test_pg_aliases_are_enabled(db_type):
    with pytest.raises(JoinAliasScopeError):
        validate_join_alias_scope("SELECT a.id FROM a JOIN b ON c.id=b.id", db_type)


@pytest.mark.parametrize("db_type", [None, "", "mysql", "trino", "oracle", "dm", "mssql", "sqlite"])
def test_other_dialects_keep_existing_behavior(db_type):
    assert validate_join_alias_scope("not even SQL", db_type) is None


@pytest.mark.parametrize("sql", ["", "SELECT 1; SELECT 2", "SELECT a.id FROM a JOIN b ON ("])
def test_parse_failure_is_structured(sql):
    with pytest.raises(JoinAliasScopeError) as caught:
        validate_join_alias_scope(sql, "postgresql")
    assert caught.value.code == "JOIN_SCOPE_PARSE_ERROR"


@pytest.mark.parametrize("sql", [
    "SELECT x.id FROM a x JOIN b x ON x.id=x.id",
    "SELECT 1 FROM generate_series(1,3), generate_series(1,3)",
    "SELECT 1 FROM generate_series, generate_series(1,3)",
    "SELECT 1 FROM unnest(ARRAY[1,2]), unnest(ARRAY[1,2])",
])
def test_duplicate_alias_is_not_overwritten(sql):
    with pytest.raises(JoinAliasScopeError) as caught:
        validate_join_alias_scope(sql, "postgresql")
    assert caught.value.code == "JOIN_SCOPE_DUPLICATE_ALIAS"


@pytest.mark.parametrize("sql", [
    "SELECT a.id FROM a SEMI JOIN b ON a.id=b.id",
    "SELECT a.id INTO new_table FROM a",
])
def test_unsupported_structures_are_explicit(sql):
    with pytest.raises(JoinAliasScopeError) as caught:
        validate_join_alias_scope(sql, "postgresql")
    assert caught.value.code == "JOIN_SCOPE_UNSUPPORTED"


def test_diagnostics_exclude_literals_and_original_sql():
    secret = "private-token-must-not-appear"
    sql = f"SELECT a.id FROM a JOIN b ON z.id=b.id AND '{secret}'='x'"
    with pytest.raises(JoinAliasScopeError) as caught:
        validate_join_alias_scope(sql, "postgresql")
    assert secret not in str(caught.value)
    assert sql not in str(caught.value)
    assert caught.value.current_join == "JOIN b"
    assert set(caught.value.allowed_aliases) == {"a", "b"}
    with pytest.raises(JoinAliasScopeError) as parse_error:
        validate_join_alias_scope(f"SELECT '{secret}' FROM (", "postgresql")
    assert secret not in str(parse_error.value)


def test_validation_never_executes_or_serializes_sql(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The scope guard must not transpile SQL")
    monkeypatch.setattr(_MODULE.sqlglot, "transpile", forbidden)
    monkeypatch.setattr(_MODULE.exp.Expression, "sql", forbidden)
    sql = 'SELECT "a".id FROM a AS "a" LEFT JOIN b ON b.id="a".id'
    before = sql
    validate_join_alias_scope(sql, "postgresql")
    assert sql == before
