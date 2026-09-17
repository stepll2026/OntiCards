"""Synthetic wire contracts from official provider references; no live credentials.

See docs/mainstream-model-compatibility.md for scope and source links. Tests use
actual application callers as well as adapters; a green contract is not a live
account/region/model availability claim.
"""
import hashlib
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from .conftest import API_ROOT, load_functions
from controllers.model_config import model_endpoints as ep, model_protocols as mp
from controllers.model_config.model_native import viking_headers
from .test_model_configuration import caller_namespace, response


def config(protocol, kind='base', **options):
    return dict(url='https://proxy.example/v1', model_name='fixture-model', model_api_key='fixture-key',
                api_protocol=protocol, model_class=kind, **options)


CHAT = {
    'responses': {'id': 'r', 'status': 'completed', 'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [{'type': 'output_text', 'text': '你好'}]}], 'usage': {'input_tokens': 5, 'output_tokens': 3}},
    'anthropic': {'id': 'm', 'type': 'message', 'content': [{'type': 'thinking', 'thinking': 'private'}, {'type': 'text', 'text': '你好'}], 'stop_reason': 'end_turn', 'usage': {'input_tokens': 5, 'output_tokens': 3}},
    'gemini': {'candidates': [{'content': {'parts': [{'text': 'private', 'thought': True}, {'text': '你好'}]}, 'finishReason': 'STOP'}], 'usageMetadata': {'promptTokenCount': 5, 'candidatesTokenCount': 2, 'thoughtsTokenCount': 1, 'totalTokenCount': 8}},
    'ollama': {'model': 'fixture-model', 'message': {'role': 'assistant', 'content': '你好', 'thinking': 'private'}, 'done': True, 'prompt_eval_count': 5, 'eval_count': 3},
    'cohere': {'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': '你好'}]}, 'finish_reason': 'COMPLETE', 'usage': {'tokens': {'input_tokens': 5, 'output_tokens': 3}, 'billed_units': {'input_tokens': 2, 'output_tokens': 3}}},
}
STREAM = {
    'responses': [{'type': 'response.created'}, {'type': 'response.output_text.delta', 'delta': '你'}, {'type': 'response.output_text.delta', 'delta': '好'}, {'type': 'response.completed', 'response': CHAT['responses']}],
    'anthropic': [{'type': 'message_start', 'message': {'usage': {'input_tokens': 5, 'output_tokens': 0}}}, {'type': 'content_block_start', 'content_block': {'type': 'text', 'text': ''}}, {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': '你好'}}, {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 3}}, {'type': 'message_stop'}],
    'gemini': [{'candidates': [{'content': {'parts': [{'text': '你'}]}}]}, {'candidates': [{'content': {'parts': [{'text': '好'}]}, 'finishReason': 'STOP'}], 'usageMetadata': CHAT['gemini']['usageMetadata']}],
    'ollama': [{'message': {'role': 'assistant', 'content': '你'}, 'done': False}, {'message': {'role': 'assistant', 'content': '好'}, 'done': False}, {'message': {'content': ''}, 'done': True, 'prompt_eval_count': 5, 'eval_count': 3}],
    'cohere': [{'type': 'message-start'}, {'type': 'content-delta', 'delta': {'message': {'content': {'text': '你好'}}}}, {'type': 'message-end', 'delta': {'finish_reason': 'COMPLETE', 'usage': CHAT['cohere']['usage']}}],
}
EMBEDDINGS = {
    'openai': {'data': [{'index': 0, 'embedding': [0.1, 0.2, 0.3]}], 'usage': {'total_tokens': 3}},
    'dashscope': {'output': {'embeddings': [{'embedding': [0.1, 0.2, 0.3]}]}, 'usage': {'total_tokens': 3}},
    'ark': {'data': {'embedding': [0.1, 0.2, 0.3]}, 'usage': {'total_tokens': 3}},
    'gemini': {'embedding': {'values': [0.1, 0.2, 0.3]}},
    'ollama': {'embeddings': [[0.1, 0.2, 0.3]], 'prompt_eval_count': 3},
    'cohere': {'embeddings': {'float': [[0.1, 0.2, 0.3]]}, 'meta': {'billed_units': {'input_tokens': 3}}},
    'jina': {'data': [{'index': 0, 'embedding': [0.1, 0.2, 0.3]}], 'usage': {'total_tokens': 3}},
    'voyage': {'data': [{'index': 0, 'embedding': [0.1, 0.2, 0.3]}], 'usage': {'total_tokens': 3}},
    'azure': {'data': [{'index': 0, 'embedding': [0.1, 0.2, 0.3]}], 'usage': {'total_tokens': 3}},
}


def streaming_response(protocol, events=None):
    result = response({})
    lines = []
    for event in events if events is not None else STREAM[protocol]:
        encoded = json.dumps(event, ensure_ascii=False).encode()
        lines.extend([encoded] if protocol == 'ollama' else [b': keepalive', b'event: ignored', b'data: ' + encoded, b''])
    result.iter_lines.return_value = lines
    return result


@pytest.mark.parametrize('url,kind,model,protocol,suffix', [
    ('https://api.anthropic.com', 'base', 'claude-fixture', 'anthropic', '/v1/messages'),
    ('https://generativelanguage.googleapis.com', 'base', 'models/gemini-fixture', 'gemini', '/v1beta/models/gemini-fixture:generateContent'),
    ('https://generativelanguage.googleapis.com/v1beta', 'embedding', 'gemini-embedding-fixture', 'gemini', '/v1beta/models/gemini-embedding-fixture:embedContent'),
    ('http://localhost:11434/api', 'base', 'fixture', 'ollama', '/api/chat'),
    ('http://localhost:11434', 'embedding', 'fixture', 'ollama', '/api/embed'),
    ('https://api.cohere.com', 'base', 'command-fixture', 'cohere', '/v2/chat'),
    ('https://api.cohere.com/v2', 'embedding', 'embed-fixture', 'cohere', '/v2/embed'),
    ('https://api.cohere.com/v2', 'rerank', 'rerank-fixture', 'cohere', '/v2/rerank'),
    ('https://ark.cn-beijing.volces.com/api/v3', 'embedding', 'doubao-embedding-vision-fixture', 'ark', '/api/v3/embeddings/multimodal'),
    ('https://api-knowledgebase.mlp.cn-beijing.volces.com', 'rerank', 'Doubao-pro-4k-rerank', 'viking', '/api/knowledge/service/rerank'),
    ('https://api.jina.ai/v1', 'embedding', 'jina-embeddings-fixture', 'jina', '/v1/embeddings'),
    ('https://api.voyageai.com/v1', 'rerank', 'rerank-fixture', 'voyage', '/v1/rerank'),
    ('https://demo.openai.azure.com/openai/deployments/custom?api-version=2024-10-21', 'base', 'custom', 'azure', '/openai/deployments/custom/chat/completions'),
])
def test_native_endpoint_inference_and_resolution(url, kind, model, protocol, suffix):
    assert ep.detect_protocol(url, 'auto', model, kind) == protocol
    resolved = ep.resolve_api_url(url, kind, model)
    assert urlsplit(resolved).path == suffix
    assert urlsplit(resolved).query == urlsplit(url).query


@pytest.mark.parametrize('provider,base', [
    ('deepseek-chat', 'https://api.deepseek.com/v1'), ('doubao-seed-fixture', 'https://ark.cn-beijing.volces.com/api/v3'),
    ('glm-fixture', 'https://open.bigmodel.cn/api/paas/v4'), ('moonshot-fixture', 'https://api.moonshot.cn/v1'),
    ('Qwen/Qwen-fixture', 'https://api.siliconflow.cn/v1'), ('MiniMax-fixture', 'https://api.minimax.io/v1'),
    ('qwen-fixture', 'https://dashscope.aliyuncs.com/compatible-mode/v1'), ('local', 'http://localhost:1234/v1'),
    ('gemini-fixture', 'https://generativelanguage.googleapis.com/v1beta/openai'),
])
def test_compatible_provider_paths_keep_openai_contract(provider, base):
    cfg = config('auto'); cfg.update(url=base, model_name=provider)
    url, headers, body, protocol = mp.model_request(cfg, 'base', 'text')
    assert url == base + '/chat/completions' and protocol == 'openai'
    assert body == {'model': provider, 'messages': [{'role': 'user', 'content': 'text'}], 'stream': False}
    assert headers['Authorization'] == 'Bearer fixture-key'


@pytest.mark.parametrize('host', ['api.siliconflow.cn', 'api.siliconflow.com'])
@pytest.mark.parametrize('suffix', ['', '/rerank'])
def test_siliconflow_rerank_base_and_full_urls_are_flat(host, suffix):
    cfg = config('auto', 'rerank'); cfg['url'] = 'https://' + host + '/v1' + suffix
    url, _, body, wire = mp.model_request(cfg, 'rerank', 'hello', documents=['one'], top_n=1)
    assert url == 'https://' + host + '/v1/rerank' and wire == 'openai'
    assert body == {'model': 'fixture-model', 'query': 'hello', 'documents': ['one'], 'top_n': 1, 'return_documents': True}


@pytest.mark.parametrize('protocol', CHAT)
@pytest.mark.parametrize('stream', [False, True])
def test_real_chat_callers_and_connection_probe(monkeypatch, protocol, stream):
    cfg = config(protocol, api_options={'max_tokens': 8192})
    namespace = caller_namespace(SimpleNamespace(**cfg))
    if stream:
        reply = streaming_response(protocol)
        namespace['requests'].post.return_value = reply
        load_functions(API_ROOT / 'controllers/agents/qwen/QwenMaxLatest_stream.py', ['qian_wen_llm_stream'], namespace)
        events = list(namespace['qian_wen_llm_stream']('hello', True))
        assert ''.join(e['choices'][0]['delta']['content'] for e in events) == '你好'
        assert events[-1]['usage']['total_tokens'] == 8
        reply.close.assert_called_once()
        monkeypatch.setattr(mp.requests, 'post', Mock(return_value=streaming_response(protocol)))
    else:
        namespace['_request_with_timing'] = Mock(return_value=(CHAT[protocol], {'total_ms': 1, 'final_status_code': 200}))
        load_functions(API_ROOT / 'controllers/agents/qwen/QwenMaxLatest.py', ['qian_wen_llm'], namespace)
        for parallel in (None, cfg):
            output = namespace['qian_wen_llm']('hello', False, parallel)
            assert output['choices'][0]['message']['content'] == '你好' and output['usage']['total_tokens'] == 8
        monkeypatch.setattr(mp.requests, 'post', Mock(return_value=response(CHAT[protocol])))
    cfg['test_stream'] = stream
    assert mp.probe_model(cfg)['protocol'] == protocol


@pytest.mark.parametrize('protocol,auth', [('anthropic', 'x-api-key'), ('gemini', 'x-goog-api-key'), ('azure', 'api-key'), ('responses', 'Authorization'), ('cohere', 'Authorization')])
def test_native_auth_and_role_specific_request_fields(protocol, auth):
    cfg = config(protocol, api_options={'max_tokens': 512})
    url, headers, body, _ = mp.model_request(cfg, 'base', 'hello', stream=True, temperature=0.2)
    assert headers[auth] == ('Bearer fixture-key' if auth == 'Authorization' else 'fixture-key')
    if auth != 'Authorization':
        assert 'Authorization' not in headers
    if protocol == 'anthropic':
        assert headers['anthropic-version'] == '2023-06-01' and body['max_tokens'] == 512
    elif protocol == 'responses':
        assert body == {'model': 'fixture-model', 'input': 'hello', 'stream': True, 'store': False, 'temperature': 0.2, 'max_output_tokens': 512}
    elif protocol == 'gemini':
        assert url.endswith(':streamGenerateContent?alt=sse')
        assert body == {'contents': [{'role': 'user', 'parts': [{'text': 'hello'}]}], 'generationConfig': {'maxOutputTokens': 512, 'temperature': 0.2}}


@pytest.mark.parametrize('protocol', EMBEDDINGS)
@pytest.mark.parametrize('purpose', ['query', 'document'])
def test_actual_embedding_callers_and_dimensions(monkeypatch, protocol, purpose):
    cfg = config(protocol, 'embedding', embedding_dimensions=3)
    namespace = caller_namespace(SimpleNamespace(**cfg))
    namespace['requests'].post.return_value.json.return_value = EMBEDDINGS[protocol]
    load_functions(API_ROOT / 'controllers/agents/qwen_embedding/embedding_api.py', ['qwen_llm_embeddings_with_usage'], namespace)
    vector, usage = namespace['qwen_llm_embeddings_with_usage']('hello', purpose=purpose)
    assert vector == [0.1, 0.2, 0.3]
    assert usage['total_tokens'] == (0 if protocol == 'gemini' else 3)
    body = namespace['requests'].post.call_args.kwargs['json']
    if protocol == 'cohere':
        assert body['texts'] == ['hello'] and body['embedding_types'] == ['float'] and body['output_dimension'] == 3
        assert body['input_type'] == ('search_query' if purpose == 'query' else 'search_document')
    elif protocol == 'gemini':
        assert body['content']['parts'] == [{'text': 'hello'}] and body['outputDimensionality'] == 3
        assert body['taskType'] == ('RETRIEVAL_QUERY' if purpose == 'query' else 'RETRIEVAL_DOCUMENT')
    elif protocol == 'voyage':
        assert body['input_type'] == purpose and body['output_dimension'] == 3
    elif protocol == 'jina':
        assert body['task'] == ('retrieval.query' if purpose == 'query' else 'retrieval.passage')
    elif protocol == 'ark':
        assert body['input'] == [{'type': 'text', 'text': 'hello'}]
    monkeypatch.setattr(mp.requests, 'post', Mock(return_value=response(EMBEDDINGS[protocol])))
    assert mp.probe_model(cfg)['dimensions'] == 3
    with pytest.raises(mp.ModelServiceError, match='维'):
        mp.embedding_result(EMBEDDINGS[protocol], 4)


@pytest.mark.parametrize('protocol', ['openai', 'dashscope', 'cohere', 'jina', 'voyage', 'viking'])
def test_actual_rerank_callers_preserve_document_index_and_top_n(monkeypatch, protocol):
    cfg = config(protocol, 'rerank', api_options={'access_key_id': 'fixture-ak', 'region': 'cn-beijing'})
    ranked = [{'index': 1, 'relevance_score': 0.9}, {'index': 0, 'relevance_score': 0.1}]
    result = {'results': ranked, 'usage': {'total_tokens': 9}}
    if protocol == 'dashscope':
        result = {'output': {'results': ranked}, 'usage': {'total_tokens': 9}}
    elif protocol == 'viking':
        result = {'code': 0, 'data': {'scores': [0.1, 0.9], 'token_usage': 9}}
    namespace = caller_namespace(SimpleNamespace(**cfg))
    namespace['requests'].post.return_value.json.return_value = result
    load_functions(API_ROOT / 'controllers/agents/qwen_rerank/QwenRerank.py', ['QwenRerank_llm', 'QwenRerank_llm_with_usage'], namespace)
    actual, usage = namespace['QwenRerank_llm_with_usage']('hello', ['one', 'two'], 2)
    assert actual == ranked and usage['total_tokens'] == 9
    body = namespace['requests'].post.call_args.kwargs['json']
    if protocol == 'viking':
        assert body == {'rerank_model': 'fixture-model', 'datas': [{'query': 'hello', 'content': 'one', 'title': ''}, {'query': 'hello', 'content': 'two', 'title': ''}]}
        actual, _ = namespace['QwenRerank_llm_with_usage']('hello', ['one', 'two'], 1)
        assert actual == ranked[:1]
    elif protocol in {'cohere', 'voyage'}:
        assert body == {'model': 'fixture-model', 'query': 'hello', 'documents': ['one', 'two'], 'top_n': 2}
    monkeypatch.setattr(mp.requests, 'post', Mock(return_value=response(result)))
    assert mp.probe_model(cfg)['ranked_documents'] == 2


@pytest.mark.parametrize('protocol', CHAT)
def test_error_event_and_truncated_stream_never_report_success(monkeypatch, protocol):
    cfg = config(protocol, test_stream=True)
    events = STREAM[protocol][:-1]
    monkeypatch.setattr(mp.requests, 'post', Mock(return_value=streaming_response(protocol, events)))
    with pytest.raises(mp.ModelServiceError):
        mp.probe_model(cfg)
    events = STREAM[protocol][:-1] + [{'type': 'error', 'error': {'message': 'fixture-secret'}}]
    monkeypatch.setattr(mp.requests, 'post', Mock(return_value=streaming_response(protocol, events)))
    with pytest.raises(mp.ModelServiceError) as caught:
        mp.probe_model(cfg)
    assert 'fixture-secret' not in str(caught.value)


@pytest.mark.parametrize('protocol,kind', [('anthropic', 'embedding'), ('anthropic', 'rerank'), ('responses', 'rerank'), ('gemini', 'rerank'), ('ollama', 'rerank'), ('ark', 'base'), ('viking', 'base'), ('jina', 'base'), ('voyage', 'base')])
def test_unsupported_purpose_rejected_before_network(protocol, kind):
    with pytest.raises(ValueError, match='用途'):
        mp.model_request(config(protocol), kind, 'hello')


@pytest.mark.parametrize('protocol', CHAT)
def test_native_catalogs_and_pagination(monkeypatch, protocol):
    if protocol == 'gemini':
        replies = [{'models': [{'name': 'models/gemini-test', 'supportedGenerationMethods': ['generateContent']}], 'nextPageToken': 'page2'}, {'models': [{'name': 'models/embed-test', 'supportedGenerationMethods': ['embedContent']}]}]
        path = '/v1/models'
    elif protocol == 'cohere':
        replies = [{'models': [{'name': 'custom-a', 'endpoints': ['chat']}], 'next_page_token': 'page2'}, {'models': [{'name': 'custom-b', 'endpoints': ['embed']}]}]
        path = '/v1/models'
    elif protocol == 'ollama':
        replies = [{'models': [{'name': 'llama-fixture'}, {'name': 'unknown-private:latest'}]}]
        path = '/v1/api/tags'
    else:
        replies = [{'data': [{'id': 'one'}], 'has_more': True, 'last_id': 'one'}, {'data': [{'id': 'two'}]}]
        path = '/v1/models'
    get = Mock(side_effect=[response(reply) for reply in replies])
    monkeypatch.setattr(ep.requests, 'get', get)
    found = ep.discover_models('https://proxy.example/v1', 'fixture-key', protocol)
    assert len(found['models']) == 2 and not found['partial']
    assert urlsplit(get.call_args.args[0]).path == path
    if protocol in {'gemini', 'cohere'}:
        assert parse_qs(urlsplit(get.call_args.args[0]).query) == {'pageToken' if protocol == 'gemini' else 'page_token': ['page2']}
        assert {m['capability_source'] for m in found['models']} == {'metadata'}
    if protocol in {'gemini', 'anthropic'}:
        assert 'Authorization' not in get.call_args.kwargs['headers']


def test_complete_urls_overrides_and_legacy_cohere_ollama():
    url = 'https://proxy.example/tenant/inference?revision=1'
    for protocol in CHAT:
        cfg = config(protocol); cfg['url'] = url
        resolved, _, _, wire = mp.model_request(cfg, 'base', 'hello')
        assert resolved == url and wire == protocol
    cfg = config('openai'); cfg['url'] = 'https://api.anthropic.com/v1'
    assert mp.model_request(cfg, 'base', 'hello')[3] == 'openai'
    cfg = config('cohere'); cfg['url'] = 'https://api.cohere.com/v1/chat'
    assert mp.model_request(cfg, 'base', 'hello')[2] == {'model': 'fixture-model', 'message': 'hello', 'stream': False}
    assert mp.normalize_chat({'text': 'hello'}, 'cohere')['choices'][0]['message']['content'] == 'hello'
    cfg = config('ollama', 'embedding'); cfg['url'] = 'http://localhost:11434/api/embeddings'
    assert mp.model_request(cfg, 'embedding', 'hello')[2] == {'model': 'fixture-model', 'prompt': 'hello'}
    assert mp.embedding_result({'embedding': [1.0]})[0] == [1.0]
    with pytest.raises(mp.ModelServiceError):
        mp.normalize_chat({'choices': [], 'base_resp': {'status_code': 1004, 'status_msg': 'fixture-private'}}, 'openai')
    events = [{'event_type': 'text-generation', 'text': '你好'}, {'event_type': 'stream-end', 'response': {'meta': {'billed_units': {'input_tokens': 5, 'output_tokens': 3}}}}]
    wire = response({})
    wire.iter_lines.return_value = [json.dumps(event).encode() for event in events]
    normalized = list(mp.iter_chat_events(wire, 'cohere'))
    assert normalized[0]['choices'][0]['delta']['content'] == '你好' and normalized[-1]['usage']['total_tokens'] == 8


def test_viking_signature_uses_actual_wire_bytes_and_requires_credentials():
    url = 'https://api-knowledgebase.mlp.cn-beijing.volces.com/api/knowledge/service/rerank'
    body = {'datas': [{'query': '问题', 'content': '文本', 'title': ''}], 'rerank_model': 'Doubao-pro-4k-rerank'}
    headers = viking_headers(url, body, 'fixture-ak', 'fixture-sk', now=datetime(2026, 9, 16, tzinfo=timezone.utc))
    prepared = requests.Request('POST', url, json=body).prepare()
    assert headers['X-Content-Sha256'] == hashlib.sha256(prepared.body).hexdigest()
    assert headers['Authorization'].startswith('HMAC-SHA256 Credential=fixture-ak/20260916/cn-beijing/air/request, SignedHeaders=content-type;host;x-content-sha256;x-date, Signature=')
    # Golden signature independently generated with volcengine SDK 1.0.228.
    assert headers['Authorization'].endswith('Signature=baed6b3d7d646f4ec9607cf1ecd7b61da5100de4367c80972a1526fa36265ef5')
    assert 'fixture-sk' not in str(headers)
    with pytest.raises(ValueError, match='Access Key'):
        viking_headers(url, body, '', 'fixture-sk')


@pytest.mark.parametrize('options', [{'max_tokens': False}, {'max_tokens': -1}, {'max_tokens': '128'}, {'access_key_id': 'a\nb'}, {'region': 42}, {'secret_access_key': 'must-use-model-api-key'}, []])
def test_invalid_native_options_are_not_forwarded(options):
    with pytest.raises(ValueError):
        ep.validate_model_options('anthropic', None, options)


@pytest.fixture(scope='module')
def wire_server():
    state = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state['request'] = {'path': self.path, 'headers': dict(self.headers), 'body': json.loads(self.rfile.read(int(self.headers['Content-Length'])))}
            self.send_response(state.get('status', 200))
            self.send_header('Content-Type', state.get('content_type', 'application/json'))
            self.end_headers()
            self.wfile.write(state['reply'])

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield f'http://127.0.0.1:{server.server_port}/v1', state
    server.shutdown(); server.server_close(); worker.join(timeout=2)


@pytest.mark.parametrize('protocol,kind,stream', [(p, 'base', s) for p in CHAT for s in [False, True]] + [(p, 'embedding', False) for p in EMBEDDINGS] + [(p, 'rerank', False) for p in ['openai', 'dashscope', 'cohere', 'jina', 'voyage', 'viking']])
def test_real_http_transport_of_all_native_contracts(wire_server, protocol, kind, stream):
    url, state = wire_server
    state.clear()
    cfg = config(protocol, kind, test_stream=stream, api_options={'access_key_id': 'fixture-ak'})
    cfg['url'] = url
    if stream:
        state['reply'] = b'\n'.join(streaming_response(protocol).iter_lines()) + b'\n'
        state['content_type'] = 'application/x-ndjson' if protocol == 'ollama' else 'text/event-stream'
    else:
        if kind == 'base':
            reply = CHAT[protocol]
        elif kind == 'embedding':
            reply = EMBEDDINGS[protocol]
        elif protocol == 'viking':
            reply = {'code': 0, 'data': {'scores': [0.9, 0.1]}}
        else:
            reply = {'results': [{'index': 0, 'relevance_score': 0.9}, {'index': 1, 'relevance_score': 0.1}]}
        state['reply'] = json.dumps(reply, ensure_ascii=False).encode()
    result = mp.probe_model(cfg)
    assert result['success'] and result['protocol'] == protocol
    sent = state['request']
    headers = {k.lower(): v for k, v in sent['headers'].items()}
    assert headers['content-type'] == 'application/json'
    if protocol == 'viking':
        assert headers['authorization'].startswith('HMAC-SHA256 ')
        assert headers['x-content-sha256'] == hashlib.sha256(requests.Request('POST', url, json=sent['body']).prepare().body).hexdigest()
    else:
        key_name = {'anthropic': 'x-api-key', 'gemini': 'x-goog-api-key', 'azure': 'api-key'}.get(protocol, 'authorization')
        assert 'fixture-key' in headers[key_name]
    state['status'] = 401
    state['reply'] = b'{"error":"fixture-private-provider-error"}'
    with pytest.raises(mp.ModelServiceError, match='鉴权') as caught:
        mp.probe_model(cfg)
    assert 'fixture-private-provider-error' not in str(caught.value)
