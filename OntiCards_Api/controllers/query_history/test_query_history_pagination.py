"""Standalone handler regression tests; no Flask app or database is started.

Run: python controllers/query_history/test_query_history_pagination.py
The complete list handler is compiled from source, with request/query boundaries
replaced by fakes. This tests parsing, validation, response and OFFSET/LIMIT;
it does not claim Flask routing or PostgreSQL integration coverage.
"""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Tuple
import unittest
from uuid import UUID


class Column:
    def __eq__(self, other):
        return ("eq", other)

    def desc(self):
        return self


class Query:
    def __init__(self):
        self.filters = []
        self.offset_value = None
        self.limit_value = None

    def filter(self, condition):
        self.filters.append(condition)
        return self

    def count(self):
        return 205

    def order_by(self, *args):
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return []


def load_handler():
    path = Path(__file__).with_name("query_history_api.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = [node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                and node.name in {"resp", "_is_uuid", "QueryHistoryListResource"}]
    assert len(selected) == 3
    namespace = dict(datetime=datetime, UUID=UUID, Any=Any, Dict=Dict,
                     Tuple=Tuple, Resource=object)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"),
         namespace)
    return namespace


class PaginationTest(unittest.TestCase):
    def setUp(self):
        self.namespace = load_handler()
        self.query = Query()
        self.namespace["QueryLog"] = SimpleNamespace(
            query=self.query, user_id=Column(), created_at=Column())

    def request(self, **args):
        params = {"user_id": "00000000-0000-0000-0000-000000000001"}
        params.update(args)
        self.namespace["request"] = SimpleNamespace(args=params)
        return self.namespace["QueryHistoryListResource"]().get()

    def check_page(self, args, page, size):
        body, status = self.request(**args)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["data"]["page"], page)
        self.assertEqual(body["data"]["page_size"], size)
        self.assertEqual(body["data"]["total_pages"], (205 + size - 1) // size)
        self.assertEqual(self.query.offset_value, (page - 1) * size)
        self.assertEqual(self.query.limit_value, size)
        self.assertEqual(self.query.filters,
                         [("eq", "00000000-0000-0000-0000-000000000001")])

    def test_missing_defaults(self):
        self.check_page({}, 1, 20)

    def test_valid_pages_and_sizes(self):
        for page, size in [(1, 1), (2, 20), (3, 50), (2, 100)]:
            with self.subTest(page=page, size=size):
                self.setUp()
                self.check_page({"page": str(page), "page_size": str(size)},
                                page, size)

    def test_invalid_page_falls_back_without_resetting_size(self):
        for value in ["abc", "", "1.5", "NaN", None, "9" * 5000]:
            with self.subTest(value=str(value)[:20]):
                self.setUp()
                self.check_page({"page": value, "page_size": "50"}, 1, 50)

    def test_invalid_size_falls_back_without_resetting_page(self):
        for value in ["abc", "", "1.5", "NaN", None, "9" * 5000]:
            with self.subTest(value=str(value)[:20]):
                self.setUp()
                self.check_page({"page": "3", "page_size": value}, 3, 20)

    def test_nonpositive_page(self):
        for value in ["0", "-2"]:
            with self.subTest(value=value):
                self.setUp()
                self.check_page({"page": value}, 1, 20)

    def test_out_of_range_size_preserves_existing_default(self):
        for value in ["0", "-2", "101", "200", "201", "999"]:
            with self.subTest(value=value):
                self.setUp()
                self.check_page({"page": "2", "page_size": value}, 2, 20)

    def test_invalid_both(self):
        self.check_page({"page": "abc", "page_size": "abc"}, 1, 20)

    def test_user_validation_still_applies(self):
        for value in ["", "bad-uuid"]:
            with self.subTest(value=value):
                body, status = self.request(user_id=value, page="abc")
                self.assertEqual(status, 400, body)
                self.assertIsNone(self.query.offset_value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
