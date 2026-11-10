"""Isolated regression tests: python controllers/weaviate_db_tool/test_doc_id_cleanup.py.

Compile the unchanged production functions; replace only the database boundary.
No application startup, embedding calls or credentials are required.
"""
import ast
from contextlib import contextmanager, redirect_stdout
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import sys


class DocIdCleanupTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name("weaviate_api.py")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {"get_records_by_doc_id", "delete_relationship_card_vector",
                 "batch_delete_by_uuids", "_require_user_class_name",
                 "_normalize_class_name", "_require_collection_exists"}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.rows = []
        self.calls = []
        self.deleted = []
        self.fail_offset = None
        self.exists = True
        self.collection_names = []
        self.closed = 0
        self.page_cap = 1000
        self.delete_failures = {}
        self.delete_results = {}
        self.attempted = []

        class Filter:
            @staticmethod
            def by_property(name):
                return SimpleNamespace(equal=lambda value: (name, value))

        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {"weaviate.classes.query": SimpleNamespace(Filter=Filter)}).start()

        def fetch_objects(*, filters, limit, offset=0):
            self.calls.append((filters, limit, offset))
            if offset == self.fail_offset:
                raise RuntimeError("query failed")
            rows = [r for r in self.rows if r.properties["doc_id"] == filters[1]]
            return SimpleNamespace(objects=rows[offset:offset + min(limit, self.page_cap)])

        def delete_by_id(uuid):
            self.attempted.append(uuid)
            if uuid in self.delete_failures:
                raise self.delete_failures[uuid]
            result = self.delete_results.get(uuid, True)
            if result:
                self.deleted.append(uuid)
            return result

        collection = SimpleNamespace(
            query=SimpleNamespace(fetch_objects=fetch_objects),
            data=SimpleNamespace(delete_by_id=delete_by_id))
        def get(name):
            self.collection_names.append(name)
            return collection
        client = SimpleNamespace(collections=SimpleNamespace(
            exists=lambda name: self.exists, get=get))

        @contextmanager
        def connect():
            try:
                yield client
            finally:
                self.closed += 1

        self.ns = {"weaviate_client": connect, "WeaviateClient": object}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), self.ns)
        self.output = redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_batch_partial_failure_continues_and_returns_false(self):
        self.delete_failures["bad"] = RuntimeError("service refused deletion")
        with redirect_stdout(io.StringIO()) as output:
            result = self.ns["batch_delete_by_uuids"](["ok", "bad", "later"], "user-space")
        self.assertIs(result, False)
        self.assertEqual(self.attempted, ["ok", "bad", "later"])
        self.assertEqual(self.deleted, ["ok", "later"])
        self.assertIn("bad", output.getvalue())
        self.assertIn("service refused deletion", output.getvalue())
        self.assertIn("success=2 failed=1", output.getvalue())
        self.assertEqual(self.closed, 1)

    def test_batch_false_response_is_failure(self):
        self.delete_results["missing"] = False
        with redirect_stdout(io.StringIO()) as output:
            result = self.ns["batch_delete_by_uuids"](["missing", "later"], "user")
        self.assertIs(result, False)
        self.assertEqual(self.attempted, ["missing", "later"])
        self.assertIn("missing", output.getvalue())
        self.assertIn("success=1 failed=1", output.getvalue())

    def test_batch_all_failed_returns_false(self):
        self.delete_failures["bad"] = TimeoutError("timeout")
        self.delete_results["missing"] = False
        self.assertIs(self.ns["batch_delete_by_uuids"](["bad", "missing"], "user"), False)
        self.assertEqual(self.attempted, ["bad", "missing"])
        self.assertEqual(self.deleted, [])

    def test_batch_success_preserves_bool_contract(self):
        self.assertIs(self.ns["batch_delete_by_uuids"](["a", "b"], "user-space"), True)
        self.assertEqual(self.deleted, ["a", "b"])
        self.assertEqual(self.collection_names, ["user_space"])

    def test_relationship_cleanup_propagates_batch_failure(self):
        self.populate(3)
        self.delete_failures["id-1"] = RuntimeError("refused")
        self.assertIs(self.ns["delete_relationship_card_vector"]("target", "user"), False)
        self.assertEqual(self.attempted, ["id-0", "id-1", "id-2"])

    def test_batch_empty_and_missing_collection_remain_errors(self):
        with self.assertRaises(ValueError):
            self.ns["batch_delete_by_uuids"]([], "user")
        self.exists = False
        with self.assertRaises(RuntimeError):
            self.ns["batch_delete_by_uuids"](["a"], "user")
        self.assertEqual(self.attempted, [])

    def populate(self, count):
        self.rows = [SimpleNamespace(
            uuid=f"id-{i}", properties={"doc_id": "target", "abstract": f"text-{i}"},
            metadata=SimpleNamespace(creation_time_unix=123, last_update_time_unix=456))
            for i in range(count)]
        self.rows.append(SimpleNamespace(uuid="keep", properties={"doc_id": "other"}))

    def test_lookup_returns_all_pages_and_preserves_record_shape(self):
        self.populate(2505)
        records = self.ns["get_records_by_doc_id"]("target", "user-space")
        self.assertEqual([r["uuid"] for r in records], [f"id-{i}" for i in range(2505)])
        self.assertEqual(records[-1], dict(uuid="id-2504", doc_id="target",
                         abstract="text-2504", creation_time=123, last_update_time=456))
        self.assertTrue(all(c[0] == ("doc_id", "target") for c in self.calls))
        self.assertEqual(set(self.collection_names), {"user_space"})
        self.assertEqual(self.closed, 1)

    def test_cleanup_deletes_every_match_without_touching_other_docs(self):
        self.populate(2505)
        self.assertTrue(self.ns["delete_relationship_card_vector"]("target", "user-space"))
        self.assertEqual(self.deleted, [f"id-{i}" for i in range(2505)])

    def test_empty_small_and_exact_page_boundary(self):
        for count in (0, 1, 1000, 2000):
            with self.subTest(count=count):
                self.populate(count)
                self.deleted.clear()
                self.assertTrue(self.ns["delete_relationship_card_vector"]("target", "user-space"))
                self.assertEqual(self.deleted, [f"id-{i}" for i in range(count)])

    def test_short_server_pages_are_not_treated_as_end(self):
        self.populate(1010)
        self.page_cap = 300
        self.assertEqual(len(self.ns["get_records_by_doc_id"]("target", "user-space")), 1010)

    def test_later_page_failure_does_not_delete_partial_results(self):
        self.populate(1001)
        self.fail_offset = 1000
        with self.assertRaisesRegex(RuntimeError, "query failed"):
            self.ns["delete_relationship_card_vector"]("target", "user-space")
        self.assertEqual(self.deleted, [])
        self.assertEqual(self.closed, 1)

    def test_missing_collection_and_empty_identifiers_remain_errors(self):
        for doc_id, class_name in (("", "user"), ("target", "")):
            with self.assertRaises(ValueError):
                self.ns["get_records_by_doc_id"](doc_id, class_name)
        self.exists = False
        with self.assertRaises(RuntimeError):
            self.ns["get_records_by_doc_id"]("target", "user")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.deleted, [])


if __name__ == "__main__":
    unittest.main()
