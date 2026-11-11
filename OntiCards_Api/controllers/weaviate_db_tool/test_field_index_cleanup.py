"""Isolated production-function regressions; no app startup or real database."""
import ast
from contextlib import contextmanager, redirect_stdout
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class FieldIndexCleanupTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name('weaviate_api.py')
        tree = ast.parse(path.read_text(encoding='utf-8'))
        names = {'delete_field_index_by_datasource', '_field_index_class_name',
                 '_require_user_class_name', '_normalize_class_name'}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.rows = []
        self.queries = []
        self.attempted = []
        self.deleted = []
        self.failures = {}
        self.fail_offset = None
        self.exists = True
        self.page_cap = 1000
        self.classes = []
        self.closed = 0
        self.events = []
        self.repeat_page = False

        class Filter:
            @staticmethod
            def by_property(name):
                return SimpleNamespace(equal=lambda value: (name, value))

        patcher = patch.dict(sys.modules, {'weaviate.classes.query': SimpleNamespace(Filter=Filter)})
        patcher.start()
        self.addCleanup(patcher.stop)

        def fetch_objects(*, filters, limit, offset=0):
            self.queries.append((filters, limit, offset))
            self.events.append('query')
            if offset == self.fail_offset:
                raise RuntimeError('query failed')
            rows = [r for r in self.rows if r.datasource_id == filters[1]]
            if self.repeat_page and offset:
                offset = 0
                self.repeat_page = False
            return SimpleNamespace(objects=rows[offset:offset + min(limit, self.page_cap)])

        def delete_by_id(uid):
            self.events.append('delete')
            self.attempted.append(uid)
            outcome = self.failures.get(uid, True)
            if isinstance(outcome, Exception):
                raise outcome
            if outcome:
                self.deleted.append(uid)
                self.rows = [r for r in self.rows if r.uuid != uid]
            return outcome

        collection = SimpleNamespace(query=SimpleNamespace(fetch_objects=fetch_objects),
                                     data=SimpleNamespace(delete_by_id=delete_by_id))
        def get(name):
            self.classes.append(name)
            return collection
        client = SimpleNamespace(collections=SimpleNamespace(exists=lambda _: self.exists, get=get))

        @contextmanager
        def connect():
            try:
                yield client
            finally:
                self.closed += 1

        self.ns = {'weaviate_client': connect, 'FIELD_INDEX_SUFFIX': '_FieldIndex'}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), self.ns)
        output = redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def run_cleanup(self, datasource='ds', user='user-space'):
        return self.ns['delete_field_index_by_datasource'](datasource, user)

    def seed(self, count, datasource='ds'):
        self.rows += [SimpleNamespace(uuid=f'{datasource}-{i}', datasource_id=datasource) for i in range(count)]

    def test_more_than_1000_all_enumerated_before_deletion(self):
        self.seed(2501)
        self.seed(3, 'other')
        self.assertEqual(self.run_cleanup(), 2501)
        self.assertEqual(len(self.deleted), 2501)
        self.assertEqual([q[2] for q in self.queries], [0, 1000, 2000, 2501])
        self.assertNotIn('query', self.events[self.events.index('delete'):])
        self.assertEqual(len(self.rows), 3)
        self.assertEqual(self.classes, ['user_space_FieldIndex'])
        self.assertEqual(self.closed, 1)

    def test_short_server_pages_do_not_truncate(self):
        self.seed(7)
        self.page_cap = 3
        self.assertEqual(self.run_cleanup(), 7)
        self.assertEqual([q[2] for q in self.queries], [0, 3, 6, 7])

    def test_sdk_false_raises_after_attempting_remaining_ids(self):
        self.seed(3)
        self.failures['ds-1'] = False
        with self.assertRaises(RuntimeError):
            self.run_cleanup()
        self.assertEqual(self.attempted, ['ds-0', 'ds-1', 'ds-2'])
        self.assertEqual(self.deleted, ['ds-0', 'ds-2'])

    def test_exception_raises_after_attempting_remaining_ids(self):
        self.seed(3)
        self.failures['ds-0'] = TimeoutError('test timeout')
        with self.assertRaises(RuntimeError):
            self.run_cleanup()
        self.assertEqual(self.attempted, ['ds-0', 'ds-1', 'ds-2'])
        self.assertEqual(self.closed, 1)

    def test_later_query_failure_deletes_nothing(self):
        self.seed(1001)
        self.fail_offset = 1000
        with self.assertRaises(RuntimeError):
            self.run_cleanup()
        self.assertEqual(self.attempted, [])

    def test_empty_scope_is_rejected(self):
        for datasource, user in [('', 'user'), (None, 'user'), (' ', 'user'), ('ds', ''), ('ds', None)]:
            with self.subTest(datasource=datasource, user=user):
                with self.assertRaises(ValueError):
                    self.run_cleanup(datasource, user)
        self.assertEqual(self.queries, [])

    def test_duplicate_page_fails_before_deletion(self):
        self.seed(1001)
        self.repeat_page = True
        with self.assertRaisesRegex(RuntimeError, 'duplicate UUIDs'):
            self.run_cleanup()
        self.assertEqual(self.attempted, [])

    def test_missing_collection_is_empty_success(self):
        self.exists = False
        self.assertEqual(self.run_cleanup(), 0)
        self.assertEqual(self.queries, [])

    def test_no_matching_records_is_empty_success(self):
        self.seed(2, 'other')
        self.assertEqual(self.run_cleanup(), 0)
        self.assertEqual(self.deleted, [])


if __name__ == '__main__':
    unittest.main()
