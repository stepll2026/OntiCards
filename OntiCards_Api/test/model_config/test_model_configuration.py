"""Base URLs, actual callers and the authenticated model catalog HTTP route."""
import ast
import json
import logging
import time
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from flask import Flask, current_app, request
from flask_login import LoginManager, UserMixin, current_user, login_required
from flask_restful import Api, Resource

from .conftest import API_ROOT, load_functions
from controllers.model_config import model_endpoints as endpoints
from controllers.model_config import model_protocols as protocols


@pytest.mark.parametrize('url,kind,model,expected', [
    (' https://proxy.example/v1/ ', 'base', '', 'https://proxy.example/v1/chat/completions'),
    ('https://proxy.example/gateway/v2?tenant=1', 'base', '', 'https://proxy.example/gateway/v2/chat/completions?tenant=1'),
    ('http://localhost:11434/v1', 'embedding', '', 'http://localhost:11434/v1/embeddings'),
    ('https://proxy.example', 'base', '', 'https://proxy.example/chat/completions'),
    ('https://proxy.example/v1', 'rerank', '', 'https://proxy.example/v1/rerank'),
    ('https://dashscope.aliyuncs.com/compatible-mode/v1', 'base', 'qwen3.7-max', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'),
    ('https://dashscope.aliyuncs.com/compatible-mode/v1', 'embedding', '', 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings'),
    ('https://dashscope.aliyuncs.com/compatible-mode/v1', 'rerank', 'gte-rerank-v2', 'https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank'),
    ('https://dashscope.aliyuncs.com/compatible-mode/v1', 'rerank', 'qwen3-rerank', 'https://dashscope.aliyuncs.com/compatible-api/v1/reranks'),
    ('https://proxy.example/v1/chat/completions', 'base', '', 'https://proxy.example/v1/chat/completions'),
    ('https://proxy.example/custom/endpoint/?version=1', 'base', '', 'https://proxy.example/custom/endpoint/?version=1'),
])
def test_endpoint_resolution(url, kind, model, expected):
    assert endpoints.resolve_api_url(url, kind, model) == expected


@pytest.mark.parametrize('url', ['', None, 'file:///tmp/key', 'https://user:secret@example.com/v1', 'https://example.com/v1#fragment', 'https://example.com:wrong/v1'])
def test_invalid_endpoint_is_rejected(url):
    with pytest.raises(ValueError):
        endpoints.resolve_api_url(url)


@pytest.mark.parametrize('url,expected', [
    ('https://proxy.example/v1', 'https://proxy.example/v1/models'),
    ('https://proxy.example/gateway/v1/chat/completions?tenant=a', 'https://proxy.example/gateway/v1/models?tenant=a'),
    ('https://proxy.example/v1/embeddings', 'https://proxy.example/v1/models'),
    ('https://proxy.example/v1/rerank', 'https://proxy.example/v1/models'),
    ('https://proxy.example/v1/models', 'https://proxy.example/v1/models'),
    ('https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank', 'https://dashscope.aliyuncs.com/api/v1/models'),
])
def test_catalog_url_from_base_or_full_endpoint(url, expected):
    assert endpoints.model_catalog_url(url) == expected


def response(payload, status=200):
    result = MagicMock()
    result.__enter__.return_value = result
    result.status_code = status
    result.iter_content.return_value = [json.dumps(payload).encode()]
    return result


def test_discovery_paginates_deduplicates_and_keeps_credentials_out_of_result(monkeypatch):
    get = Mock(side_effect=[response({'data': [{'id': 'b'}, {'id': 'a'}], 'has_more': True, 'last_id': 'a'}),
                            response({'data': [{'id': 'a'}, {'id': 'c'}, {}, None], 'has_more': False})])
    monkeypatch.setattr(endpoints.requests, 'get', get)
    result = endpoints.discover_models('https://proxy.example/v1?tenant=1', 'secret-fixture')
    assert [item['id'] for item in result['models']] == ['a', 'b', 'c']
    assert not result['partial'] and not result['message']
    assert parse_qs(urlsplit(get.call_args.args[0]).query) == {'tenant': ['1'], 'after': ['a']}
    assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer secret-fixture'
    assert get.call_args.kwargs['allow_redirects'] is False
    assert 'secret-fixture' not in json.dumps(result)


def test_native_catalog_pages_and_no_key_local_models(monkeypatch):
    get = Mock(side_effect=[response({'output': {'models': [{'model': 'first'}], 'total': 2, 'page_size': 1}}),
                            response({'output': {'models': [{'model': 'second'}], 'total': 2, 'page_size': 1}})])
    monkeypatch.setattr(endpoints.requests, 'get', get)
    assert len(endpoints.discover_models('http://localhost:8080/api/v1/models')['models']) == 2
    assert parse_qs(urlsplit(get.call_args.args[0]).query) == {'page_no': ['2'], 'page_size': ['1']}
    assert 'Authorization' not in get.call_args.kwargs['headers']


@pytest.mark.parametrize('status', [401, 403, 404, 302, 429, 500])
def test_provider_errors_are_safe_and_do_not_redirect(monkeypatch, status):
    get = Mock(return_value=response({'error': 'secret-fixture'}, status))
    monkeypatch.setattr(endpoints.requests, 'get', get)
    with pytest.raises(endpoints.ModelDiscoveryError) as caught:
        endpoints.discover_models('https://proxy.example/v1', 'secret-fixture')
    assert 'secret-fixture' not in str(caught.value)
    get.assert_called_once()


@pytest.mark.parametrize('payload', [None, {}, {'data': 'wrong'}, []])
def test_malformed_catalog_is_not_reported_as_success(monkeypatch, payload):
    monkeypatch.setattr(endpoints.requests, 'get', Mock(return_value=response(payload)))
    with pytest.raises(endpoints.ModelDiscoveryError):
        endpoints.discover_models('https://proxy.example/v1')


def test_empty_catalog_and_repeated_page_allow_manual_entry(monkeypatch):
    get = Mock(return_value=response({'data': []}))
    monkeypatch.setattr(endpoints.requests, 'get', get)
    assert endpoints.discover_models('https://proxy.example/v1')['message']
    get.return_value = response({'data': [{'id': 'one'}], 'has_more': True, 'last_id': 'one'})
    result = endpoints.discover_models('https://proxy.example/v1')
    assert [item['id'] for item in result['models']] == ['one'] and result['partial']


@pytest.mark.parametrize('role,status', [(None, 401), ('normal', 403), ('admin', 200)])
def test_catalog_http_route_is_admin_only(role, status):
    app = Flask('catalog-test')
    app.secret_key = 'test-only'
    login = LoginManager(app)
    class User(UserMixin):
        id = 'fixture'
    user = User()
    user.role = role
    login.user_loader(lambda identifier: user)
    login.unauthorized_handler(lambda: ({'code': 401}, 401))
    discover = Mock(return_value={'models': [{'id': 'remote-model'}], 'partial': False, 'message': ''})
    namespace = dict(Resource=Resource, login_required=login_required, current_user=current_user, request=request,
                     resp=lambda code=200, msg='success', data=None, http_status=200: ({'code': code, 'msg': msg, 'data': data}, http_status),
                     discover_models=discover, ModelDiscoveryError=endpoints.ModelDiscoveryError)
    path = API_ROOT / 'controllers/model_config/model_config_api.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ModelCatalogAPI')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    Api(app).add_resource(namespace['ModelCatalogAPI'], '/model_config/models')
    client = app.test_client()
    if role:
        with client.session_transaction() as session:
            session['_user_id'] = user.id
    result = client.post('/model_config/models', json={'url': 'https://example.com/v1', 'model_api_key': 'fixture-key'})
    assert result.status_code == status
    if status == 200:
        assert result.json['data']['models'] == [{'id': 'remote-model'}]
        assert 'fixture-key' not in result.get_data(as_text=True)
    else:
        discover.assert_not_called()


def caller_namespace(config):
    app = SimpleNamespace(app_context=nullcontext)
    query = SimpleNamespace(filter_by=lambda **kwargs: SimpleNamespace(first=lambda: config))
    return dict(resolve_api_url=endpoints.resolve_api_url, rerank_uses_flat_payload=endpoints.rerank_uses_flat_payload,
                model_request=protocols.model_request, normalize_chat=protocols.normalize_chat, ModelServiceError=protocols.ModelServiceError,
                embedding_result=protocols.embedding_result, rerank_result=protocols.rerank_result, iter_chat_events=protocols.iter_chat_events,
                Model_configuration=SimpleNamespace(query=query), current_app=SimpleNamespace(_get_current_object=lambda: app),
                db=SimpleNamespace(session=SimpleNamespace(query=lambda model: query)), json=json, time=time,
                logger=logging.getLogger('test'), requests=MagicMock())


@pytest.mark.parametrize('thread_config', [False, True])
def test_main_caller_normalizes_db_and_parallel_configs(thread_config):
    config = SimpleNamespace(url='https://example.com/v1', model_api_key='fixture-key', model_name='chosen-model')
    namespace = caller_namespace(config)
    send = Mock(return_value=({'choices': []}, {'total_ms': 0, 'final_status_code': 200}))
    namespace['_request_with_timing'] = send
    load_functions(API_ROOT / 'controllers/agents/qwen/QwenMaxLatest.py', ['qian_wen_llm'], namespace)
    override = dict(api_url=config.url, api_key=config.model_api_key, model_name=config.model_name) if thread_config else None
    namespace['qian_wen_llm']('test', False, override)
    assert send.call_args.args[1] == 'https://example.com/v1/chat/completions'
    assert send.call_args.kwargs['json']['model'] == 'chosen-model'


@pytest.mark.parametrize('kind', ['stream', 'utility', 'embedding', 'rerank', 'native_rerank', 'legacy_rerank'])
def test_other_actual_callers_use_resolved_endpoints(kind, capsys):
    host = 'dashscope.aliyuncs.com/compatible-mode' if kind == 'native_rerank' else 'example.com'
    config = SimpleNamespace(url=f'https://{host}/v1', model_api_key='fixture-key', model_name='chosen-model')
    if kind == 'legacy_rerank':
        config.url += '/rerank'
    namespace = caller_namespace(config)
    send = namespace['requests'].post
    send.return_value.json.return_value = {'choices': [{'message': {'content': 'ok'}}], 'data': [{'embedding': [0.1]}], 'usage': {}}
    send.return_value.iter_lines.return_value = [b'data: {"ok": true}']
    if kind == 'stream':
        path, function, args = 'qwen/QwenMaxLatest_stream.py', 'qian_wen_llm_stream', ('test', True)
    elif kind == 'utility':
        path, function, args = 'qwen/llm_utils.py', 'llm_call', ('test',)
    elif kind == 'embedding':
        path, function, args = 'qwen_embedding/embedding_api.py', 'qwen_llm_embeddings_with_usage', ('test',)
    else:
        path, function, args = 'qwen_rerank/QwenRerank.py', 'QwenRerank_llm', ('test', ['one'], 1)
    load_functions(API_ROOT / 'controllers/agents' / path, [function], namespace)
    result = namespace[function](*args)
    if kind == 'stream':
        list(result)
    suffix = 'embeddings' if kind == 'embedding' else 'rerank' if kind in {'rerank', 'legacy_rerank'} else 'chat/completions'
    expected = f'https://{host}/v1/{suffix}' if kind != 'native_rerank' else 'https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank'
    assert send.call_args.args[0] == expected
    if kind == 'rerank':
        assert send.call_args.kwargs['json']['query'] == 'test'
    if kind in {'native_rerank', 'legacy_rerank'}:
        assert send.call_args.kwargs['json']['input']['query'] == 'test'
    assert 'fixture-key' not in capsys.readouterr().out
