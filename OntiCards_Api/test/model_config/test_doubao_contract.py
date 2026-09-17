"""Offline Ark protocol checks; all credentials, responses and endpoint IDs are fixtures.

Reference: volcengine/volcengine-python-sdk, revision
3b116781c5b8bb648f215b29587f2ec74d9e5d02, volcenginesdkarkruntime:
  resources/chat/completions.py, resources/embeddings.py,
  resources/multimodal_embeddings.py, types/chat/chat_completion_chunk.py,
  types/multimodal_embedding/embedding_response.py.

These tests do not establish account permissions, current model availability,
catalog endpoint availability, inference quality, or provider latency.
Viking rerank reference: volcengine/volc-sdk-python,
volcengine/viking_knowledgebase/VikingKnowledgeBaseService.py (2026-09-16).
Native requests and responses are covered without expected-failure exemptions.
"""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from .conftest import API_ROOT, load_functions
from controllers.model_config import model_endpoints as ep, model_protocols as mp
from .test_model_configuration import caller_namespace, response


BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'
CHAT_MODEL = 'doubao-seed-2-0-lite-260215'
ENDPOINT_ID = 'ep-fixture-chat'
FIXTURE_KEY = 'fixture-ark-key'


def config(protocol='auto', **overrides):
    return dict(dict(url=BASE_URL, model_name=CHAT_MODEL, model_api_key=FIXTURE_KEY,
                     model_class='base', api_protocol=protocol), **overrides)


def chat_response():
    return {'id': 'fixture-chat', 'object': 'chat.completion', 'created': 0,
            'model': CHAT_MODEL, 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': 'OK', 'reasoning_content': 'fixture reasoning'}}],
            'usage': {'prompt_tokens': 4, 'completion_tokens': 6, 'total_tokens': 10,
                      'completion_tokens_details': {'reasoning_tokens': 5}}}


def stream_response(reasoning_only=False):
    # Ark's SDK permits optional reasoning_content and usage-only chunks.
    chunks = [
        {'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}}]},
        {'choices': [{'index': 0, 'delta': {'content': None, 'reasoning_content': 'fixture reasoning'}}]},
    ]
    if not reasoning_only:
        chunks.extend({'choices': [{'index': 0, 'delta': {'content': part}}]} for part in ['O', 'K'])
    chunks.extend([
        {'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
        {'choices': [], 'usage': {'prompt_tokens': 4, 'completion_tokens': 6, 'total_tokens': 10}},
    ])
    wire = [b': keepalive', b'']
    for chunk in chunks:
        wire.extend([('data: ' + json.dumps(dict(id='fixture-stream', object='chat.completion.chunk',
                                               created=0, model=CHAT_MODEL, **chunk))).encode(), b''])
    wire.extend([b'data: [DONE]', b''])
    result = response({})
    result.iter_lines.return_value = wire
    return result


@pytest.mark.parametrize('protocol', ['auto', 'openai'])
@pytest.mark.parametrize('full_url', [False, True])
@pytest.mark.parametrize('model', [CHAT_MODEL, ENDPOINT_ID])
def test_ark_chat_request_matches_official_contract(protocol, full_url, model):
    cfg = config(protocol, model_name=model, url=BASE_URL + ('/chat/completions' if full_url else ''))
    url, headers, body, wire = mp.model_request(cfg, 'base', '你好')
    assert url == BASE_URL + '/chat/completions'
    assert headers == {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + FIXTURE_KEY}
    assert body == {'model': model, 'messages': [{'role': 'user', 'content': '你好'}], 'stream': False}
    assert wire == 'openai'


@pytest.mark.parametrize('protocol', ['auto', 'openai'])
@pytest.mark.parametrize('parallel_config', [False, True])
def test_ark_chat_actual_caller_preserves_text_and_usage(protocol, parallel_config):
    cfg = config(protocol, model_name=ENDPOINT_ID)
    namespace = caller_namespace(SimpleNamespace(**cfg))
    namespace['_request_with_timing'] = Mock(return_value=(chat_response(), {'total_ms': 1, 'final_status_code': 200}))
    load_functions(API_ROOT / 'controllers/agents/qwen/QwenMaxLatest.py', ['qian_wen_llm'], namespace)
    result = namespace['qian_wen_llm']('hello', False, cfg if parallel_config else None)
    assert result['choices'][0]['message']['content'] == 'OK'
    assert result['usage']['total_tokens'] == 10
    assert result['usage']['completion_tokens_details']['reasoning_tokens'] == 5
    assert namespace['_request_with_timing'].call_args.kwargs['json']['model'] == ENDPOINT_ID


@pytest.mark.parametrize('protocol', ['auto', 'openai'])
def test_ark_actual_stream_caller_accepts_reasoning_and_usage_chunks(protocol):
    namespace = caller_namespace(SimpleNamespace(**config(protocol)))
    reply = stream_response()
    namespace['requests'].post.return_value = reply
    load_functions(API_ROOT / 'controllers/agents/qwen/QwenMaxLatest_stream.py', ['qian_wen_llm_stream'], namespace)
    chunks = list(namespace['qian_wen_llm_stream']('hello', True))
    answer = ''.join(choice['delta'].get('content') or '' for chunk in chunks for choice in chunk['choices'])
    assert answer == 'OK' and chunks[-1]['usage']['total_tokens'] == 10
    assert namespace['requests'].post.call_args.args[0] == BASE_URL + '/chat/completions'
    assert namespace['requests'].post.call_args.kwargs['json']['stream'] is True
    reply.close.assert_called_once()


@pytest.mark.parametrize('protocol', ['auto', 'openai'])
@pytest.mark.parametrize('streaming', [False, True])
def test_ark_chat_connection_probe_with_official_response_shape(monkeypatch, protocol, streaming):
    post = Mock(return_value=stream_response() if streaming else response(chat_response()))
    monkeypatch.setattr(mp.requests, 'post', post)
    result = mp.probe_model(config(protocol, test_stream=streaming))
    assert result['success'] and result['protocol'] == 'openai'
    assert result.get('stream', False) is streaming
    assert FIXTURE_KEY not in json.dumps(result)


def test_ark_reasoning_only_stream_is_not_a_successful_text_answer(monkeypatch):
    monkeypatch.setattr(mp.requests, 'post', Mock(return_value=stream_response(reasoning_only=True)))
    with pytest.raises(mp.ModelServiceError, match='未收到对话文本流'):
        mp.probe_model(config(test_stream=True))


@pytest.mark.parametrize('protocol', ['auto', 'openai'])
@pytest.mark.parametrize('full_url', [False, True])
@pytest.mark.parametrize('dimensions', [None, 3])
def test_ark_text_embedding_actual_caller(protocol, full_url, dimensions):
    # Three synthetic values verify the dimension contract, not any model's supported sizes.
    cfg = config(protocol, model_class='embedding', model_name='ep-fixture-text-embedding',
                 embedding_dimensions=dimensions, url=BASE_URL + ('/embeddings' if full_url else ''))
    namespace = caller_namespace(SimpleNamespace(**cfg))
    namespace['requests'].post.return_value.json.return_value = {
        'id': 'fixture-embedding', 'created': 0, 'model': cfg['model_name'], 'object': 'list',
        'data': [{'index': 0, 'object': 'embedding', 'embedding': [0.1, -0.2, 0.3]}],
        'usage': {'prompt_tokens': 3, 'total_tokens': 3},
    }
    load_functions(API_ROOT / 'controllers/agents/qwen_embedding/embedding_api.py', ['qwen_llm_embeddings_with_usage'], namespace)
    vector, usage = namespace['qwen_llm_embeddings_with_usage']('测试文本')
    assert vector == [0.1, -0.2, 0.3] and usage['total_tokens'] == 3
    request = namespace['requests'].post.call_args
    assert request.args[0] == BASE_URL + '/embeddings'
    expected = {'model': cfg['model_name'], 'input': '测试文本', 'encoding_format': 'float'}
    if dimensions is not None:
        expected['dimensions'] = dimensions
    assert request.kwargs['json'] == expected


@pytest.mark.parametrize('status', [401, 403, 404, 429])
def test_ark_upstream_failure_cannot_pass_connection_test(monkeypatch, status):
    monkeypatch.setattr(mp.requests, 'post', Mock(return_value=response(
        {'error': {'code': 'FixtureUpstreamFailure', 'message': FIXTURE_KEY, 'type': 'invalid_request_error'}}, status)))
    with pytest.raises(mp.ModelServiceError) as caught:
        mp.probe_model(config(model_name=ENDPOINT_ID))
    assert FIXTURE_KEY not in str(caught.value)


@pytest.mark.parametrize('source_url', [BASE_URL, BASE_URL + '/chat/completions', BASE_URL + '/embeddings'])
def test_ark_shaped_base_url_uses_standard_catalog_contract_only(monkeypatch, source_url):
    # Conditional compatibility: this does NOT claim Ark exposes GET /api/v3/models.
    get = Mock(return_value=response({'object': 'list', 'data': [{'id': ENDPOINT_ID}]}))
    monkeypatch.setattr(ep.requests, 'get', get)
    result = ep.discover_models(source_url, FIXTURE_KEY)
    assert get.call_args.args[0] == BASE_URL + '/models'
    assert result['models'] == [{'id': ENDPOINT_ID, 'capabilities': [], 'capability_source': 'unknown'}]


def test_catalog_unavailable_reports_manual_configuration_fallback(monkeypatch):
    monkeypatch.setattr(ep.requests, 'get', Mock(return_value=response({}, 404)))
    with pytest.raises(ep.ModelDiscoveryError, match='手动填写'):
        ep.discover_models(BASE_URL, FIXTURE_KEY)
    assert mp.model_request(config(model_name=ENDPOINT_ID), 'base', 'hello')[2]['model'] == ENDPOINT_ID


def test_opaque_endpoint_and_unrecognised_doubao_name_do_not_fake_purpose_evidence():
    assert ep.classify_model({'id': ENDPOINT_ID}) == {'id': ENDPOINT_ID, 'capabilities': [], 'capability_source': 'unknown'}
    assert ep.classify_model({'id': CHAT_MODEL})['capability_source'] == 'name'
    assert ep.classify_model({'id': ENDPOINT_ID, 'supported_endpoints': ['chat/completions']})['capabilities'] == ['base']


def test_gap_ark_multimodal_embedding_request():
    cfg = config(model_class='embedding', model_name='doubao-embedding-vision-250615',
                 url=BASE_URL + '/embeddings/multimodal')
    url, _, body, _ = mp.model_request(cfg, 'embedding', '测试文本')
    assert url == BASE_URL + '/embeddings/multimodal'
    assert body['input'] == [{'type': 'text', 'text': '测试文本'}]


def test_gap_ark_multimodal_embedding_response():
    fixture = {'id': 'fixture-multimodal', 'created': 0, 'model': 'doubao-embedding-vision-250615',
               'object': 'list', 'data': {'object': 'embedding', 'embedding': [0.1, 0.2, 0.3]},
               'usage': {'prompt_tokens': 3, 'total_tokens': 3}}
    vector, usage = mp.embedding_result(fixture)
    assert vector == [0.1, 0.2, 0.3] and usage['total_tokens'] == 3


@pytest.mark.parametrize('protocol', ['auto', 'viking'])
def test_gap_viking_native_doubao_rerank_request(protocol):
    cfg = config(protocol, model_class='rerank', model_name='Doubao-pro-4k-rerank',
                 api_options={'access_key_id': 'fixture-ak'},
                 url='https://api-knowledgebase.mlp.cn-beijing.volces.com/api/knowledge/service/rerank')
    _, _, body, _ = mp.model_request(cfg, 'rerank', '问题', documents=['候选文本'], top_n=1)
    assert 'datas' in body
    assert body['rerank_model'] == cfg['model_name']
