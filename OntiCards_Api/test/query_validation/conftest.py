"""Load pure query checks without starting Flask or seeding a database."""
import ast
import sys
import types
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[2]
for name, directory in (("controllers", API_ROOT / "controllers"),
                        ("controllers.query", API_ROOT / "controllers/query")):
    package = types.ModuleType(name)
    package.__path__ = [str(directory)]
    sys.modules[name] = package


def load_functions(filename, names, namespace):
    """Exercise the real legacy endpoint functions without their startup side effects."""
    path = API_ROOT / "controllers/query" / filename
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in functions} == set(names)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


@pytest.fixture(params=["query_by_datacards_agg.py", "query_by_datacards_agg_plugin.py"])
def endpoint(request):
    return endpoint_namespace(request.param)


def endpoint_namespace(filename):
    import re
    import time
    from typing import Any, List, Optional, Set, Tuple, Dict
    from datetime import datetime, date, time as datetime_time, timedelta
    from decimal import Decimal
    from uuid import UUID
    from sqlalchemy import text
    from controllers.query import query_validation as validation

    namespace = dict(locals())
    namespace.update(vars(validation))
    namespace["time_module"] = time
    return load_functions(filename, ["run_sql_safe_new", "_strip_code_fences", "_norm_ident",
                          "_make_json_serializable", "_strip_nolock"], namespace)
