"""Opt-in differential checks against an isolated PostgreSQL 16 container.

Set ONTICARDS_TEST_POSTGRES=1 and pre-pull postgres:16 before running. Override
ONTICARDS_TEST_POSTGRES_IMAGE to check another installed PostgreSQL version. This suite
creates its own network-disabled container and synthetic fixtures; it never
accepts a production connection string or uses application configuration.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

import pytest


SPEC = importlib.util.spec_from_file_location(
    "_postgres_join_scope", Path(__file__).resolve().parents[1] / "controllers/query/sql_join_scope.py")
SCOPE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCOPE
SPEC.loader.exec_module(SCOPE)

pytestmark = pytest.mark.skipif(
    os.environ.get("ONTICARDS_TEST_POSTGRES") != "1",
    reason="Set ONTICARDS_TEST_POSTGRES=1 to use an isolated Docker PostgreSQL fixture",
)

CASES = [
    ("forward_join", False, "SELECT a.id FROM a JOIN b ON b.id=c.id JOIN c ON c.id=a.id"),
    ("valid_left_chain", True, "SELECT a.id FROM a LEFT JOIN b ON b.id=a.id LEFT JOIN c ON c.id=b.id"),
    ("five_table_wrong", False, "SELECT t2.id FROM a t2 LEFT JOIN b t4 ON t4.id=t2.id LEFT JOIN d t1 ON t1.id=t4.id LEFT JOIN e t5 ON t5.id=t3.id LEFT JOIN c t3 ON t3.id=t2.id"),
    ("five_table_correct", True, "SELECT t2.id FROM a t2 LEFT JOIN b t4 ON t4.id=t2.id LEFT JOIN c t3 ON t3.id=t2.id LEFT JOIN d t1 ON t1.id=t4.id LEFT JOIN e t5 ON t5.id=t3.id"),
    ("where_after_joins", True, "SELECT a.id FROM a JOIN b ON b.id=a.id JOIN c ON c.id=a.id WHERE c.id=1"),
    ("comma_previous_hidden", False, "SELECT a.id FROM a, b JOIN c ON c.id=a.id"),
    ("comma_current_visible", True, "SELECT a.id FROM a, b LEFT JOIN c ON c.id=b.id WHERE a.id=b.id"),
    ("parenthesized_visible", True, "SELECT a.id FROM (a LEFT JOIN b ON b.id=a.id) JOIN c ON c.id=b.id"),
    ("parenthesized_hidden", False, "SELECT c.id FROM (a JOIN b ON a.id=b.id) x JOIN c ON a.id=c.id"),
    ("nested_parenthesized", True, "SELECT 1 FROM ((a JOIN b ON a.id=b.id)) x"),
    ("nested_parenthesized_hidden", False, "SELECT c.id FROM ((a JOIN b ON a.id=b.id)) x JOIN c ON a.id=c.id"),
    ("derived_sibling_hidden", False, "SELECT a.id FROM a JOIN (SELECT a.id) x ON true"),
    ("lateral_prior", True, "SELECT a.id FROM a LEFT JOIN LATERAL (SELECT a.id) x ON true"),
    ("lateral_future", False, "SELECT a.id FROM a JOIN LATERAL (SELECT c.id) x ON true JOIN c ON c.id=a.id"),
    ("right_lateral_comma", True, "SELECT a.id FROM a, b RIGHT JOIN LATERAL (SELECT a.id) x ON true"),
    ("right_lateral_left", False, "SELECT a.id FROM a, b RIGHT JOIN LATERAL (SELECT b.id) x ON true"),
    ("correlated_outer", True, "SELECT a.id FROM a WHERE EXISTS (SELECT 1 FROM b JOIN c ON c.id=a.id)"),
    ("later_local_shadow", True, "SELECT t3.id FROM a t3 WHERE EXISTS (SELECT 1 FROM b JOIN c ON c.id=t3.id JOIN a t3 ON t3.id=b.id)"),
    ("grandparent", True, "SELECT a.id FROM a WHERE EXISTS (SELECT 1 FROM (SELECT a.id) x)"),
    ("cte_source", True, "WITH x AS (SELECT id FROM a) SELECT x.id FROM x JOIN b ON b.id=x.id"),
    ("cte_not_in_from", False, "WITH x AS (SELECT id FROM a) SELECT a.id FROM a JOIN b ON b.id=x.id"),
    ("cte_inner_alias", False, "WITH x AS (SELECT id FROM a) SELECT x.id FROM x JOIN b ON b.id=a.id"),
    ("cte_correlation", True, "SELECT a.id FROM a WHERE EXISTS (WITH x AS (SELECT a.id) SELECT x.id FROM x)"),
    ("quoted_exact", True, 'SELECT "A".id FROM a "A" JOIN b ON b.id="A".id'),
    ("quoted_wrong_case", False, 'SELECT "A".id FROM a "A" JOIN b ON b.id=a.id'),
    ("union_blocks", True, "SELECT a.id FROM a JOIN b ON b.id=a.id UNION ALL SELECT b.id FROM b JOIN c ON c.id=b.id"),
    ("union_alias_leak", False, "SELECT a.id FROM a JOIN b ON b.id=a.id UNION ALL SELECT c.id FROM c JOIN b ON b.id=a.id"),
    ("function_default_alias", True, "SELECT generate_series FROM generate_series(1,3)"),
    ("function_qualified_default", True, "SELECT generate_series.generate_series FROM generate_series(1,3)"),
    ("unnest_ordinality", True, "SELECT * FROM unnest(ARRAY[1,2]) WITH ORDINALITY"),
    ("explicit_lateral_function", True, "SELECT a.id FROM a CROSS JOIN LATERAL unnest(a.arr)"),
    ("implicit_lateral_ordinality", True, "SELECT a.id FROM a CROSS JOIN unnest(a.arr) WITH ORDINALITY AS u(value, ordinal)"),
    ("function_future", False, "SELECT a.id FROM a JOIN LATERAL unnest(c.arr) u ON true JOIN c ON c.id=a.id"),
    ("right_function_left", False, "SELECT a.id FROM a RIGHT JOIN LATERAL unnest(a.arr) u ON true"),
    ("sample_literal", True, "SELECT count(*) FROM a TABLESAMPLE SYSTEM (10)"),
    ("sample_repeatable", True, "SELECT count(*) FROM a TABLESAMPLE BERNOULLI (10) REPEATABLE (1)"),
    ("sample_self_hidden", False, "SELECT a.id FROM a TABLESAMPLE SYSTEM ((a.id))"),
    ("sample_join_sibling_hidden", False, "SELECT a.id FROM a JOIN b TABLESAMPLE SYSTEM ((a.id)) ON true"),
    ("sample_comma_sibling_hidden", False, "SELECT a.id FROM a, b TABLESAMPLE SYSTEM ((a.id))"),
    ("sample_outer_visible", True, "SELECT a.id FROM a WHERE EXISTS (SELECT 1 FROM b TABLESAMPLE SYSTEM ((a.id)))"),
    ("sample_repeatable_outer", True, "SELECT a.id FROM a WHERE EXISTS (SELECT 1 FROM b TABLESAMPLE SYSTEM (10) REPEATABLE ((a.id)))"),
]


@pytest.fixture(scope="module")
def postgres():
    if not shutil.which("docker"):
        pytest.fail("Docker is required when ONTICARDS_TEST_POSTGRES=1")
    name = "onticards-join-test-" + uuid.uuid4().hex[:12]
    image = os.environ.get("ONTICARDS_TEST_POSTGRES_IMAGE", "postgres:16")

    def psql(sql):
        return subprocess.run(
            ["docker", "exec", "-i", name, "psql", "-X", "-U", "postgres", "-d", "postgres",
             "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose", "-A", "-t"],
            input=sql, text=True, capture_output=True, timeout=20,
        )

    try:
        subprocess.run(
            ["docker", "run", "--pull=never", "--rm", "--detach", "--name", name,
             "--network", "none", "--memory", "256m", "--cpus", "1",
             "--tmpfs", "/var/lib/postgresql/data:rw", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
             image], check=True, text=True, capture_output=True, timeout=30,
        )
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            ready = subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres"],
                                   capture_output=True, timeout=5)
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            pytest.fail("Isolated PostgreSQL did not become ready")
        setup = "\n".join(
            f"CREATE TABLE {table}(id integer PRIMARY KEY, arr integer[]);\n"
            f"INSERT INTO {table} VALUES (1,ARRAY[1,2]);" for table in "abcde")
        setup += "\nINSERT INTO a VALUES (2,ARRAY[3]);"
        result = psql(setup)
        assert result.returncode == 0, result.stderr
        yield psql
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True, timeout=30)


@pytest.mark.parametrize("name,expected,sql", CASES, ids=[row[0] for row in CASES])
def test_visibility_matches_postgresql(postgres, name, expected, sql):
    try:
        SCOPE.validate_join_alias_scope(sql, "postgresql")
        accepted = True
    except SCOPE.JoinAliasScopeError:
        accepted = False
    result = postgres("BEGIN READ ONLY;\nEXPLAIN " + sql + ";\nROLLBACK;")
    assert (result.returncode == 0) == expected, result.stderr
    assert accepted == expected, f"{name}: validator disagrees with PostgreSQL"


def test_correct_left_join_retains_unmatched_record(postgres):
    sql = "SELECT a.id,b.id,c.id FROM a LEFT JOIN b ON b.id=a.id LEFT JOIN c ON c.id=b.id ORDER BY a.id"
    SCOPE.validate_join_alias_scope(sql, "postgresql")
    result = postgres(sql)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["1|1|1", "2||"]
