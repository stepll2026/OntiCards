"""Real Flask routes and SQLite queries, isolated from application startup/services."""
import ast
from datetime import datetime, timezone, timedelta
import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Tuple
from uuid import UUID

from flask import Flask, Blueprint, request
from flask_login import LoginManager, UserMixin, current_user, login_required
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
OWN_LOG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_LOG = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture()
def history():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-only", SQLALCHEMY_DATABASE_URI="sqlite://")
    database = SQLAlchemy(app)
    columns = {
        '__tablename__': 'query_logs', 'id': database.Column(database.String, primary_key=True),
        'user_id': database.Column(database.String), 'created_at': database.Column(database.DateTime),
    }
    for name in ('api_key_id question processed_question sql status error_message fusion_strategy').split():
        columns[name] = database.Column(database.String)
    for name in ('term_rewrite_info cluster_sqls source_datasource_ids source_datasource_names '
                 'datasource_ids datasource_names table_names full_response_result').split():
        columns[name] = database.Column(database.JSON)
    for name in ('total_duration_ms vector_search_ms rerank_ms llm_gen_sql_ms sql_execution_ms fusion_ms '
                 'embedding_tokens rerank_tokens llm_prompt_tokens llm_completion_tokens total_tokens '
                 'result_count cards_recalled cards_reranked cards_selected top1_rerank_score avg_rerank_score').split():
        columns[name] = database.Column(database.Integer)
    record = type('QueryLog', (database.Model,), columns)
    login = LoginManager(app)

    @login.request_loader
    def load(req):
        identity = req.headers.get('Authorization')
        if identity in (OWNER, OTHER):
            user = UserMixin()
            user.id = identity
            return user
        return None

    spec = importlib.util.spec_from_file_location('history_sanitizer', ROOT / 'core/log_sanitizer.py')
    sanitizer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sanitizer)
    path = ROOT / 'controllers/query_history/query_history_api.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]

    def delete(item):
        database.session.delete(item)
        database.session.commit()
        return True

    namespace = dict(__name__='history_under_test', datetime=datetime, timezone=timezone, timedelta=timedelta,
                     logging=logging, UUID=UUID, Any=Any, Dict=Dict, Tuple=Tuple, Blueprint=Blueprint,
                     request=request, Api=Api, Resource=Resource, JSONB=JSONB, db=database, QueryLog=record,
                     QueryLogger=SimpleNamespace(delete_with_cascade=delete), current_user=current_user,
                     login_required=login_required, sanitize_log_text=sanitizer.sanitize_log_text,
                     sanitize_log_value=sanitizer.sanitize_log_value)
    exec(compile(tree, str(path), 'exec'), namespace)
    app.register_blueprint(namespace['query_history_api'], url_prefix='/query_history')
    with app.app_context():
        database.create_all()
        database.session.add_all([
            record(id=OWN_LOG, user_id=OWNER, question='own query', sql='SELECT 1', status='error',
                   error_message='JOIN_ALIAS_OUT_OF_SCOPE password=private-password', total_tokens=42,
                   created_at=datetime(2026, 9, 21, 8), cluster_sqls=[{
                       'sql': 'SELECT 1', 'db_type': 'postgresql', 'retry_count': 1,
                       'attempts': [{'attempt': 0, 'stage': 'validation', 'status': 'error',
                                     'error_code': 'JOIN_ALIAS_OUT_OF_SCOPE', 'message': 'password=private-password',
                                     'connect_info': 'private-dsn'}],
                   }]),
            record(id=OTHER_LOG, user_id=OTHER, question='other user secret', status='success',
                   created_at=datetime(2026, 9, 21, 9)),
        ])
        database.session.commit()
        yield app.test_client(), record, database, namespace
        database.session.remove()
        database.drop_all()


@pytest.mark.parametrize('method,path', [
    ('get', '/list'), ('get', '/' + OWN_LOG), ('get', '/stats'),
    ('delete', '/' + OWN_LOG + '/delete'), ('delete', '/batch/delete?keep_days=1'),
])
def test_history_requires_authentication(history, method, path):
    client, *_ = history
    assert getattr(client, method)('/query_history' + path).status_code == 401


@pytest.mark.parametrize('method,path', [
    ('get', '/list'), ('get', '/' + OTHER_LOG), ('get', '/stats'),
    ('delete', '/' + OTHER_LOG + '/delete'), ('delete', '/batch/delete'),
])
def test_supplied_user_id_cannot_change_ownership(history, method, path):
    client, record, *_ = history
    response = getattr(client, method)('/query_history' + path + '?user_id=' + OTHER,
                                       headers={'Authorization': OWNER})
    assert response.status_code == 403
    assert record.query.count() == 2


@pytest.mark.parametrize('suffix,method', [('', 'get'), ('/delete', 'delete')])
def test_other_users_log_is_inaccessible_even_without_user_parameter(history, suffix, method):
    client, record, *_ = history
    response = getattr(client, method)('/query_history/' + OTHER_LOG + suffix, headers={'Authorization': OWNER})
    assert response.status_code == 404
    assert record.query.count() == 2


def test_list_search_and_detail_expose_only_owned_redacted_diagnostics(history):
    client, *_ = history
    response = client.get('/query_history/list?keyword=JOIN_ALIAS', headers={'Authorization': OWNER})
    assert response.status_code == 200
    items = response.json['data']['items']
    assert [row['id'] for row in items] == [OWN_LOG]
    assert items[0]['retry_count'] == 1
    assert 'private-password' not in items[0]['error_message']
    detail = client.get('/query_history/' + OWN_LOG, headers={'Authorization': OWNER}).json['data']
    assert detail['tokens']['total_tokens'] == 42
    assert detail['execution_logs'][0]['retry_count'] == 1
    assert 'private' not in str(detail['execution_logs'])
    assert 'connect_info' not in detail['execution_logs'][0]['attempts'][0]


def test_old_records_have_empty_diagnostic_list(history):
    client, *_ = history
    response = client.get('/query_history/' + OTHER_LOG, headers={'Authorization': OTHER})
    assert response.status_code == 200
    assert response.json['data']['execution_logs'] == []
    listing = client.get('/query_history/list', headers={'Authorization': OTHER})
    assert listing.json['data']['items'][0]['retry_count'] is None


@pytest.mark.parametrize('params', ['page=not-a-number', 'status=invalid', 'start_date=invalid'])
def test_invalid_filters_return_400(history, params):
    client, *_ = history
    assert client.get('/query_history/list?' + params, headers={'Authorization': OWNER}).status_code == 400
