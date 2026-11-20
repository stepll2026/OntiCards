"""Run real cleanup methods with synthetic persistence boundaries, never app startup."""
import ast
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock
import uuid

HERE = Path(__file__).parent

def method(file, cls, name, ns):
    tree = ast.parse((HERE / file).read_text())
    node = next(n for c in tree.body if isinstance(c, ast.ClassDef) and c.name == cls
                for n in c.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), ns)
    return ns[name]

class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.batch = MagicMock(return_value=True)
        self.index = MagicMock(return_value=3)
        self.ds_id = str(uuid.uuid4())
        self.record = NS(id=self.ds_id, user_id='owner', connect_info_hash='hash', db_type='mysql', schema_name=None)
        self.models = {n: MagicMock(name=n) for n in ('DatasourceInfo', 'UserDatasourceSchema', 'DataCardDataSource',
                       'DatasourceTermLibrary', 'TargetInventoryJob', 'TargetInventoryJobResult',
                       'TableRelationship', 'TableRelationshipCard', 'FieldMapping', 'User')}
        self.relationship_uuid = str(uuid.uuid4())
        self.schema = NS(id=str(uuid.uuid4()))
        self.card = NS(w_uuid=str(uuid.uuid4()))
        def query(entity):
            q = MagicMock()
            q.filter.return_value = q
            q.filter_by.return_value = q
            q.one_or_none.return_value = self.record
            q.first.return_value = self.record
            q.delete.return_value = 1
            if entity is self.models['UserDatasourceSchema'].id:
                q.all.return_value = [(self.schema.id,)]
            elif entity is self.models['DataCardDataSource'].w_uuid:
                q.all.return_value = [(self.card.w_uuid,)]
            elif entity is self.models['TableRelationshipCard'].w_uuid:
                q.all.return_value = [(self.relationship_uuid,)]
            elif entity is self.models['UserDatasourceSchema']:
                q.all.return_value = [self.schema]
            elif entity is self.models['DataCardDataSource']:
                q.all.return_value = [self.card]
            else:
                q.all.return_value = []
            return q
        self.session.query.side_effect = query
        self.ns = dict(self.models, uuid=uuid, Optional=object, db=NS(session=self.session),
            current_user=NS(id='owner', weaviate_class_name='user_space'),
            _must_uuid=uuid.UUID, _ensure_owner=lambda *a: None, _add_schema_filter=lambda q,*a:q,
            SQLAlchemyError=RuntimeError, batch_delete_by_uuids=self.batch,
            delete_field_index_by_datasource=self.index,
            format_response=lambda data,code,msg:({'data':data,'code':code,'msg':msg},code))
        self.cancel_ns = dict(self.ns, request=NS(get_json=lambda:{'request_id':'request','config':{'dbType':'mysql'}}),
            request_status_manager=MagicMock(), flask_login=NS(current_user=self.ns['current_user']),
            build_db_url_from_json=lambda c:'synthetic', _to_raw_conn_str=lambda x:x,
            _resolve_schema_name=lambda *a:None, get_connect_info_hash=lambda c:'hash', _has_schema_dim=lambda x:False)
        self.models['User'].query.filter_by.return_value.first.return_value = self.ns['current_user']
        self.out = contextlib.redirect_stdout(io.StringIO())
        self.out.__enter__()
        self.addCleanup(self.out.__exit__, None,None,None)

    def delete(self):
        return method('datasource_tool.py','DatasourceToolAPI','delete',self.ns)(None,self.ds_id)

    def cancel(self):
        return method('database_schema_extractor.py','CancelExtractSchemaAPI','post',self.cancel_ns)(None)

    def refresh_cleanup(self):
        # Execute the exact Step 4 statements, excluding DB introspection/LLM rebuild.
        tree = ast.parse((HERE / 'datasource_tool.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DatasourceToolAPI')
        post = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'post')
        outer = next(n for n in post.body if isinstance(n, ast.Try) and n.finalbody)
        nodes = outer.body
        start = next(i for i,n in enumerate(nodes) if isinstance(n, ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id == 'schemas_deleted')
        end = next(i for i,n in enumerate(nodes[start:],start) if isinstance(n, ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id == 'to_refresh_tables')
        fn = ast.parse('def cleanup():\n    pass').body[0]
        fn.body = nodes[start:end] + ast.parse('return weaviate_deleted').body
        self.ns.update(old_map={'old':{'id':self.schema.id}},removed={'old'},changed=[],ds_id=self.ds_id)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])), 'refresh_step4','exec'),self.ns)
        return self.ns['cleanup']()

    def test_refresh_false_stops_before_removing_metadata(self):
        self.batch.return_value=False
        result=self.refresh_cleanup()
        self.assertIsInstance(result,tuple)
        self.assertEqual(result[1],502)
        self.session.commit.assert_not_called()

    def test_refresh_exception_stops_before_removing_metadata(self):
        self.batch.side_effect=TimeoutError()
        result=self.refresh_cleanup()
        self.assertIsInstance(result,tuple)
        self.assertEqual(result[1],502)
        self.session.commit.assert_not_called()

    def test_refresh_success_counts_only_confirmed_deletions(self):
        self.assertEqual(self.refresh_cleanup(),1)
        self.session.commit.assert_called_once()

    def test_delete_includes_relationship_vectors(self):
        body,status=self.delete()
        self.assertEqual(status,200)
        self.assertIn(self.relationship_uuid, self.batch.call_args.args[0])

    def test_delete_partial_failure_does_not_commit_or_report_success(self):
        self.batch.return_value = False
        body,status = self.delete()
        self.assertEqual(status,502)
        self.assertFalse(body['data']['cleanup_complete'])
        self.session.commit.assert_not_called()

    def test_delete_field_index_failure_preserves_source(self):
        self.index.side_effect = RuntimeError('field index unavailable')
        body,status = self.delete()
        self.assertEqual(status,502)
        self.session.commit.assert_not_called()

    def test_delete_success_cleans_vectors_before_commit(self):
        events=[]
        self.batch.side_effect=lambda *a,**k:events.append('vectors') or True
        self.index.side_effect=lambda **k:events.append('index') or 3
        self.session.commit.side_effect=lambda:events.append('commit')
        body,status=self.delete()
        self.assertEqual(status,200)
        self.assertEqual(events,['vectors','index','commit'])

    def test_cancel_partial_failure_rolls_back_and_reports_cleanup_failed(self):
        self.batch.return_value=False
        body,status=self.cancel()
        self.assertEqual(status,502)
        self.assertFalse(body['data']['cleanup_complete'])
        self.session.commit.assert_not_called()
        self.session.rollback.assert_called()

    def test_cancel_exception_does_not_claim_cleanup_success(self):
        self.batch.side_effect=TimeoutError('synthetic timeout')
        body,status=self.cancel()
        self.assertEqual(status,502)
        self.session.commit.assert_not_called()

    def test_cancel_invalid_uuid_does_not_silently_skip_vector(self):
        self.card.w_uuid='invalid-uuid'
        body,status=self.cancel()
        self.assertNotEqual(status,200)
        self.session.commit.assert_not_called()

    def test_cancel_invalid_config_does_not_claim_all_data_cleaned(self):
        self.cancel_ns['build_db_url_from_json']=lambda c: (_ for _ in ()).throw(ValueError('bad config'))
        body,status=self.cancel()
        self.assertNotEqual(status,200)
        self.session.commit.assert_not_called()

    def test_cancel_success_reports_confirmed_count(self):
        body,status=self.cancel()
        self.assertEqual(status,200)
        self.assertEqual(body['data']['deleted_weaviate'],1)

if __name__ == '__main__': unittest.main()
