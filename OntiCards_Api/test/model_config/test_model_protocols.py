"""Protocol contracts, capability evidence, probes and persisted draft settings."""
import ast
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from flask import Flask, request
from flask_login import LoginManager, UserMixin, current_user, login_required
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from uuid import uuid4

from .conftest import API_ROOT, load_functions
from controllers.model_config import model_endpoints as ep, model_protocols as mp
from .test_model_configuration import response, caller_namespace


def config(protocol='auto', **values):
    return dict(url='https://service.example/v1', model_name='private-model', model_api_key='fixture-secret',
                model_class='base', api_protocol=protocol, **values)


@pytest.mark.parametrize('item,capabilities,source', [
    ({'id': 'private', 'capabilities': ['TG', 'embeddings']}, ['base', 'embedding'], 'metadata'),
    ({'id': 'gte-rerank-v2', 'capabilities': ['TR']}, ['rerank'], 'name'),
    ({'id': 'private-retrieval', 'capabilities': ['TR']}, [], 'unknown'),
    ({'id': 'private', 'capabilities': {'rerank': True, 'embedding': False}}, ['rerank'], 'metadata'),
    ({'id': 'embed-in-name', 'supported_endpoints': ['/v1/chat/completions']}, ['base'], 'metadata'),
    ({'model': 'private', 'pipeline_tag': 'feature-extraction'}, ['embedding'], 'metadata'),
    ({'id': 'image', 'capabilities': ['IG']}, ['other'], 'metadata'),
    ({'id': 'qwen3-rerank'}, ['rerank'], 'name'),
    ({'id': 'tenant/text-embedding-v3'}, ['embedding'], 'name'),
    ({'id': 'qwen-image-plus'}, ['other'], 'name'),
    ({'id': 'qwen-plus'}, ['base'], 'name'),
    ({'id': 'private-deployment-27'}, [], 'unknown'),
])
def test_capability_evidence(item, capabilities, source):
    result = ep.classify_model(item)
    assert result['capabilities'] == capabilities
    assert result['capability_source'] == source


@pytest.mark.parametrize('kind,suffix', [('base', 'chat/completions'), ('embedding', 'embeddings'), ('rerank', 'rerank')])
def test_openai_requests_do_not_include_native_fields(kind, suffix):
    cfg = config('openai', embedding_dimensions=768 if kind == 'embedding' else None)
    url, headers, body, protocol = mp.model_request(cfg, kind, 'hello', documents=['one'], top_n=1)
    assert url == f'https://service.example/v1/{suffix}' and protocol == 'openai'
    assert headers['Authorization'] == 'Bearer fixture-secret'
    assert 'parameters' not in body
    if kind == 'embedding':
        assert body == {'model': 'private-model', 'input': 'hello', 'encoding_format': 'float', 'dimensions': 768}
    if kind == 'rerank':
        assert body['query'] == 'hello' and body['top_n'] == 1


@pytest.mark.parametrize('kind', ['base', 'embedding', 'rerank'])
def test_native_requests_even_without_key(kind):
    cfg = config('dashscope', embedding_dimensions=256 if kind == 'embedding' else None)
    cfg.update(url='https://proxy.example/tenant/api/v1', model_api_key='')
    url, headers, body, protocol = mp.model_request(cfg, kind, 'hello', documents=['one'], top_n=1)
    assert url == 'https://proxy.example/tenant/api/v1/' + ep.NATIVE_PATHS[kind]
    assert 'Authorization' not in headers and protocol == 'dashscope'
    if kind == 'base':
        assert body['input']['messages'][0]['content'] == 'hello'
    elif kind == 'embedding':
        assert body['input']['texts'] == ['hello'] and body['parameters']['dimension'] == 256
    else:
        assert body['input']['query'] == 'hello' and body['parameters']['top_n'] == 1


def test_dimension_defaults_and_manual_full_endpoint_override():
    assert 'dimensions' not in mp.model_request(config('openai'), 'embedding', 'hello')[2]
    cfg = config('openai')
    cfg['url'] = 'https://proxy.example/custom/ranking?tenant=a'
    url, _, body, protocol = mp.model_request(cfg, 'rerank', 'hello', documents=['one'], top_n=1)
    assert url == cfg['url'] and protocol == 'openai' and body['query'] == 'hello'
    cfg['api_protocol'] = 'auto'
    assert mp.model_request(cfg, 'rerank', 'hello', documents=['one'], top_n=1)[2]['input']['query'] == 'hello'


def test_known_native_auto_and_generic_api_v1_are_distinct():
    assert '/services/aigc/' in ep.resolve_api_url('https://dashscope.aliyuncs.com/api/v1')
    assert ep.resolve_api_url('https://proxy.example/api/v1') == 'https://proxy.example/api/v1/chat/completions'
    assert ep.resolve_api_url('https://dashscope.aliyuncs.com/compatible-mode/v1', 'rerank', 'qwen3-rerank', 'dashscope').endswith('/compatible-api/v1/reranks')
    assert ep.model_catalog_url('https://proxy.example/tenant/api/v1/services/aigc/text-generation/generation', 'dashscope') == 'https://proxy.example/tenant/api/v1/models'
    cfg = config()
    cfg['url'] = 'https://proxy.example/services/chat/completions'
    url, _, body, protocol = mp.model_request(cfg, 'base', 'hello')
    assert url == cfg['url'] and protocol == 'openai' and 'messages' in body


@pytest.mark.parametrize('protocol,dimensions', [('anthropic', None), ('auto', True), ('openai', 0), ('auto', -1), ('auto', 1.5), ('auto', '1024'), ('auto', 65537)])
def test_invalid_options_rejected_before_network(protocol, dimensions):
    with pytest.raises(ValueError):
        mp.model_request(config(protocol, embedding_dimensions=dimensions), 'embedding', 'hi')


def test_native_chat_usage_and_multimodal_text_response():
    result = mp.normalize_chat({'request_id': 'x', 'output': {'choices': [{'message': {'content': [{'text': '你'}, {'text': '好'}]}, 'finish_reason': 'stop'}]},
                                'usage': {'input_tokens': 3, 'output_tokens': 2}}, 'dashscope')
    assert result['choices'][0]['message']['content'] == '你好'
    assert result['usage']['total_tokens'] == 5 and result['usage']['prompt_tokens'] == 3
    assert mp.normalize_chat({'output': {'text': 'old result'}}, 'dashscope')['choices'][0]['message']['content'] == 'old result'


def test_native_stream_request_and_events():
    _, headers, payload, _ = mp.model_request(config('dashscope'), 'base', 'hi', stream=True)
    assert headers['X-DashScope-SSE'] == 'enable'
    assert payload['parameters']['incremental_output'] is True and 'stream' not in payload
    event = {'output': {'choices': [{'message': {'content': '你好'}, 'finish_reason': 'null'}]}, 'usage': {'input_tokens': 2}}
    stream = Mock()
    stream.iter_lines.return_value = [b': keepalive', b'event: result', ('data: ' + json.dumps(event)).encode(), b'', b'data: [DONE]', b'']
    result = list(mp.iter_chat_events(stream, 'dashscope'))
    assert result[0]['choices'][0]['delta']['content'] == '你好'
    assert 'message' not in result[0]['choices'][0]


@pytest.mark.parametrize('payload', [{'error': {'message': 'fixture-secret'}}, {'code': 'InvalidApiKey', 'message': 'fixture-secret'}, [], None])
def test_provider_error_body_is_not_exposed(payload):
    with pytest.raises(mp.ModelServiceError) as caught:
        mp.normalize_chat(payload, 'dashscope')
    assert 'fixture-secret' not in str(caught.value)


@pytest.mark.parametrize('vector', [[], [True], ['0.1'], [float('nan')], [float('inf')], None])
def test_embedding_malformed_vectors_fail(vector):
    with pytest.raises(mp.ModelServiceError):
        mp.embedding_result({'data': [{'embedding': vector}]})


def test_native_vector_and_dimension_mismatch():
    payload = {'output': {'embeddings': [{'embedding': [0.1, 0.2], 'text_index': 0}]}, 'usage': {'total_tokens': 8}}
    vector, usage = mp.embedding_result(payload, 2)
    assert len(vector) == 2 and usage['total_tokens'] == 8
    with pytest.raises(mp.ModelServiceError, match='不一致'):
        mp.embedding_result(payload, 1024)


@pytest.mark.parametrize('rows', [[{'index': 2, 'relevance_score': 0.5}], [{'index': 0, 'relevance_score': 'high'}],
                                [{'index': 0, 'relevance_score': float('nan')}], [{'index': 0, 'relevance_score': 1}] * 2])
def test_invalid_rerank_indices_and_scores_fail(rows):
    with pytest.raises(mp.ModelServiceError):
        mp.rerank_result({'results': rows}, 2)


@pytest.mark.parametrize('protocol', ['openai', 'dashscope'])
@pytest.mark.parametrize('kind', ['base', 'embedding', 'rerank'])
def test_probe_real_adapter_validates_role_response(monkeypatch, protocol, kind):
    cfg = config(protocol)
    cfg['model_class'] = kind
    if kind == 'base':
        inner = {'choices': [{'message': {'content': 'OK'}}]}
    elif kind == 'embedding':
        inner = {'embeddings': [{'embedding': [1.0, 0.2]}]} if protocol == 'dashscope' else {'data': [{'embedding': [1.0, 0.2]}]}
    else:
        inner = {'results': [{'index': 1, 'relevance_score': 0.9}, {'index': 0, 'relevance_score': 0.1}]}
    payload = {'output': inner} if protocol == 'dashscope' else inner
    post = Mock(return_value=response(payload))
    monkeypatch.setattr(mp.requests, 'post', post)
    result = mp.probe_model(cfg)
    assert result['success'] and result['model_class'] == kind and result['protocol'] == protocol
    assert post.call_args.kwargs['allow_redirects'] is False
    assert 'fixture-secret' not in json.dumps(result)


@pytest.mark.parametrize('status', [401, 403, 404, 302, 429, 500])
def test_probe_http_failure_is_safe(monkeypatch, status):
    post = Mock(return_value=response({'error': 'fixture-secret'}, status))
    monkeypatch.setattr(mp.requests, 'post', post)
    with pytest.raises(mp.ModelServiceError) as caught:
        mp.probe_model(config())
    assert 'fixture-secret' not in str(caught.value)
    post.assert_called_once()


def test_probe_wrong_type_empty_stream_timeout_and_dimension(monkeypatch):
    post = Mock(return_value=response({'data': [{'embedding': [0.1]}]}))
    monkeypatch.setattr(mp.requests, 'post', post)
    with pytest.raises(mp.ModelServiceError, match='对话'):
        mp.probe_model(config())
    post.return_value.iter_lines.return_value = [b'data: [DONE]', b'']
    with pytest.raises(mp.ModelServiceError, match='文本流'):
        mp.probe_model(config(test_stream=True))
    cfg = config(embedding_dimensions=3)
    cfg['model_class'] = 'embedding'
    with pytest.raises(mp.ModelServiceError, match='不一致'):
        mp.probe_model(cfg)
    post.side_effect = requests.Timeout('fixture-secret')
    with pytest.raises(mp.ModelServiceError, match='超时') as caught:
        mp.probe_model(config())
    assert 'fixture-secret' not in str(caught.value)


@pytest.mark.parametrize('thread_config', [False, True])
def test_main_native_caller_converts_response_and_propagates_protocol(thread_config):
    cfg = SimpleNamespace(**config('dashscope'))
    namespace = caller_namespace(cfg)
    send = Mock(return_value=({'output': {'choices': [{'message': {'content': '正常'}}]}, 'usage': {'input_tokens': 4, 'output_tokens': 2}}, {'total_ms': 1, 'final_status_code': 200}))
    namespace['_request_with_timing'] = send
    load_functions(API_ROOT / 'controllers/agents/qwen/QwenMaxLatest.py', ['qian_wen_llm'], namespace)
    result = namespace['qian_wen_llm']('question', False, vars(cfg) if thread_config else None)
    assert result['choices'][0]['message']['content'] == '正常'
    assert result['usage']['total_tokens'] == 6
    assert send.call_args.kwargs['json']['input']['messages'][0]['content'] == 'question'


@pytest.mark.parametrize('role,status', [(None, 401), ('normal', 403), ('admin', 200)])
def test_probe_http_route_permissions_and_payload(role, status):
    app = Flask('probe-test')
    app.secret_key = 'fixture'
    login = LoginManager(app)
    class User(UserMixin):
        id = 'fixture'
    user = User()
    user.role = role
    login.user_loader(lambda _: user)
    login.unauthorized_handler(lambda: ({'code': 401}, 401))
    probe = Mock(return_value={'success': True, 'model_class': 'embedding', 'dimensions': 1024})
    namespace = dict(Resource=Resource, login_required=login_required, current_user=current_user, request=request,
                     resp=lambda code=200, msg='success', data=None, http_status=200: ({'code': code, 'msg': msg, 'data': data}, http_status),
                     probe_model=probe, ModelServiceError=mp.ModelServiceError)
    path = API_ROOT / 'controllers/model_config/model_config_api.py'
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.ClassDef) and n.name == 'ModelProbeAPI')
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    Api(app).add_resource(namespace['ModelProbeAPI'], '/model_config/test')
    client = app.test_client()
    if role:
        with client.session_transaction() as session:
            session['_user_id'] = user.id
    draft = config('openai', embedding_dimensions=1024)
    draft['model_class'] = 'embedding'
    result = client.post('/model_config/test', json=draft)
    assert result.status_code == status
    if status == 200:
        probe.assert_called_once_with(draft)
        probe.side_effect = mp.ModelServiceError('服务商鉴权失败')
        assert client.post('/model_config/test', json=draft).status_code == 502
        probe.side_effect = ValueError('配置无效')
        assert client.post('/model_config/test', json=draft).status_code == 400
    else:
        probe.assert_not_called()


def test_config_crud_persists_new_options_and_preserves_legacy_defaults():
    app = Flask('config-persistence')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    db = SQLAlchemy(app)
    namespace = dict(db=db, UUID=UUID(as_uuid=False), func=func, Resource=Resource, request=request,
                     validate_model_options=ep.validate_model_options,
                     resp=lambda code=200, msg='success', data=None, http_status=200: ({'code': code, 'msg': msg, 'data': data}, http_status))
    for relative, classname in [('models/model_config.py', 'Model_configuration'), ('controllers/model_config/model_config_api.py', 'ModelConfigAPI')]:
        path = API_ROOT / relative
        node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.ClassDef) and n.name == classname)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    model = namespace['Model_configuration']
    # SQLite test fixture supplies the UUID normally supplied by PostgreSQL.
    model.__table__.c.id.server_default = None
    event.listen(model, 'before_insert', lambda mapper, connection, target: setattr(target, 'id', target.id or str(uuid4())))
    Api(app).add_resource(namespace['ModelConfigAPI'], '/model_config')
    with app.app_context():
        db.create_all()
    client = app.test_client()
    legacy = dict(model_name='private-legacy', model_type='custom', model_api_key='', model_class='embedding', url='https://example.com/v1')
    assert client.post('/model_config', json=legacy).status_code == 200
    record = client.get('/model_config').json['data'][0]
    assert record['api_protocol'] == 'auto' and record['embedding_dimensions'] is None
    for opts in [{'api_protocol': 'dashscope', 'embedding_dimensions': 1024}, {'api_protocol': 'openai', 'embedding_dimensions': None}]:
        assert client.put('/model_config', json={'id': record['id'], **opts}).status_code == 200
        result = client.get('/model_config').json['data'][0]
        assert result['api_protocol'] == opts['api_protocol'] and result['embedding_dimensions'] == opts['embedding_dimensions']
    # Old clients may omit both options during edits; preserve saved values.
    assert client.put('/model_config', json={'id': record['id'], 'model_type': 'updated note'}).status_code == 200
    assert client.get('/model_config').json['data'][0]['api_protocol'] == 'openai'
    native_options = {'max_tokens': 8192, 'access_key_id': 'fixture-ak', 'region': 'cn-beijing', 'endpoint_id': 'ep-fixture'}
    assert client.put('/model_config', json={'id': record['id'], 'api_options': native_options}).status_code == 200
    assert client.get('/model_config').json['data'][0]['api_options'] == native_options
    assert client.put('/model_config', json={'id': record['id'], 'model_type': 'keep native options'}).status_code == 200
    assert client.get('/model_config', query_string={'id': record['id']}).json['data']['api_options'] == native_options
    assert client.put('/model_config', json={'id': record['id'], 'api_options': {'max_tokens': 0}}).status_code == 400
    bad = {**legacy, 'model_name': 'bad', 'api_protocol': 'unknown-protocol'}
    assert client.post('/model_config', json=bad).status_code == 400
    assert len(client.get('/model_config').json['data']) == 1
