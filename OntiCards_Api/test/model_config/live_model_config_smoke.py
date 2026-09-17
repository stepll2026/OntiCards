"""Opt-in check of configured providers using base URLs; no configuration writes."""
import ast
import json
import logging
import math
import sys
import time
from types import SimpleNamespace

import requests
from flask import Flask, current_app
from requests.adapters import HTTPAdapter
from sqlalchemy import create_engine, text
from urllib3.util.retry import Retry

from conftest import API_ROOT
from controllers.model_config import model_protocols
from controllers.model_config.model_endpoints import (
    discover_models, model_catalog_url, resolve_api_url, rerank_uses_flat_payload,
)


def main():
    if sys.argv[1:] != ['--server-config']:
        raise SystemExit('Run explicitly with --server-config inside the test API container.')
    sys.path.append('/onticards_api')
    from config import Config
    engine = create_engine(Config().SQLALCHEMY_DATABASE_URI)
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        settings = {row['model_class']: SimpleNamespace(**dict(row)) for row in connection.execute(text(
            "SELECT model_class, model_name, model_api_key, url FROM model_config WHERE model_class IN ('base', 'embedding', 'rerank')"
        )).mappings()}
    engine.dispose()
    original_base_url = settings['base'].url
    # Use in-memory copies only; the live database configuration remains untouched.
    from urllib.parse import urlsplit, urlunsplit
    for setting in settings.values():
        parts = urlsplit(setting.url)
        setting.url = urlunsplit(parts._replace(path='/compatible-mode/v1', query='', fragment=''))
        setting.api_protocol = 'auto'
        setting.embedding_dimensions = None
    started = time.monotonic()
    catalogs = [discover_models(url, settings['base'].model_api_key) for url in (settings['base'].url, original_base_url)]
    assert all(any(item['id'] == settings['base'].model_name for item in catalog['models']) for catalog in catalogs)
    print(json.dumps({'status': 'passed', 'check': 'model_catalog_base_and_full_url',
                      'counts': [len(catalog['models']) for catalog in catalogs],
                      'configured_model_found': True}, ensure_ascii=False), flush=True)
    class ConfigQuery:
        def filter_by(self, **values):
            return SimpleNamespace(first=lambda: settings[values['model_class']])
    namespace = dict(requests=requests, HTTPAdapter=HTTPAdapter, Retry=Retry, time=time,
                     current_app=current_app, Model_configuration=SimpleNamespace(query=ConfigQuery()),
                     resolve_api_url=resolve_api_url, rerank_uses_flat_payload=rerank_uses_flat_payload,
                     logger=logging.getLogger('live-config-test'), _http_session=None,
                     print=lambda *args, **kwargs: None)
    for helper in ['model_request', 'normalize_chat', 'ModelServiceError', 'embedding_result', 'rerank_result', 'iter_chat_events']:
        namespace[helper] = getattr(model_protocols, helper)
    for path in ['qwen/QwenMaxLatest_stream.py', 'qwen/QwenMaxLatest.py', 'qwen_embedding/embedding_api.py', 'qwen_rerank/QwenRerank.py']:
        source = API_ROOT / 'controllers/agents' / path
        nodes = [node for node in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(node, ast.FunctionDef)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    app = Flask('isolated-model-config-test')
    with app.app_context():
        base = settings['base']
        answer = namespace['qian_wen_llm']('Reply with exactly OK.', False, dict(
            api_url=base.url, api_key=base.model_api_key, model_name=base.model_name, api_protocol=base.api_protocol, timeout=45))
        reply = answer['choices'][0]['message']['content'].strip()
        if reply != 'OK':
            safe_reply = reply
            for setting in settings.values():
                if setting.model_api_key:
                    safe_reply = safe_reply.replace(setting.model_api_key, '[redacted]')
            print(json.dumps({'check': 'chat_response', 'has_error': bool(answer.get('error')), 'reply': safe_reply[:200]}, ensure_ascii=False), flush=True)
        assert reply == 'OK'
        vector, _ = namespace['qwen_llm_embeddings_with_usage']('仪器商品的仓库库存')
        assert len(vector) == 1024 and all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector)
        ranking, _ = namespace['QwenRerank_llm_with_usage']('仪器商品的仓库库存', ['员工考勤排班与请假记录', '仪器商品库存数量及仓库区域'], 1)
        assert len(ranking) == 1 and ranking[0]['index'] == 1
    print(json.dumps({'status': 'passed', 'check': 'actual_callers_with_compatible_base_urls',
                      'models': {kind: setting.model_name for kind, setting in settings.items()},
                      'embedding_dimensions': len(vector), 'rerank_correct': True}, ensure_ascii=False), flush=True)
    # Exercise both protocols via the actual streaming and non-streaming entry points.
    with app.app_context():
        for protocol in ['auto', 'dashscope']:
            for setting in settings.values():
                setting.api_protocol = protocol
                if protocol == 'dashscope':
                    parts = urlsplit(setting.url)
                    setting.url = urlunsplit(parts._replace(path='/api/v1'))
            if protocol == 'dashscope':
                answer = namespace['qian_wen_llm']('Reply with exactly OK.', False)
                assert not answer.get('error') and answer['choices'][0]['message']['content'].strip()
                vector, _ = namespace['qwen_llm_embeddings_with_usage']('模型连接测试')
                assert len(vector) == 1024
                ranking, _ = namespace['QwenRerank_llm_with_usage']('仪器商品的仓库库存', ['员工考勤排班与请假记录', '仪器商品库存数量及仓库区域'], 1)
                assert ranking[0]['index'] == 1
            chunks = list(namespace['qian_wen_llm_stream']('Reply with exactly OK.', True))
            content = ''.join(choice.get('delta', {}).get('content') or '' for chunk in chunks for choice in chunk.get('choices', []))
            assert content.strip()
            print(json.dumps({'status': 'passed', 'check': 'actual_chat_stream_and_role_callers', 'protocol': protocol}, ensure_ascii=False), flush=True)
            for kind, setting in settings.items():
                result = model_protocols.probe_model(vars(setting))
                assert result['success']
                print(json.dumps({'check': 'configuration_probe', **result}, ensure_ascii=False), flush=True)
            sized = dict(vars(settings['embedding']), embedding_dimensions=256)
            result = model_protocols.probe_model(sized)
            assert result['dimensions'] == 256
            print(json.dumps({'check': 'explicit_embedding_dimensions', **result}, ensure_ascii=False), flush=True)
            result = model_protocols.probe_model(dict(vars(settings['base']), test_stream=True))
            assert result['stream']
            print(json.dumps({'check': 'stream_probe', **result}, ensure_ascii=False), flush=True)
        # Explicit compatible rerank uses its own supported model and payload convention.
        compatible_rank = dict(vars(settings['rerank']))
        parts = urlsplit(compatible_rank['url'])
        compatible_rank.update(api_protocol='openai', model_name='qwen3-rerank',
                               url=urlunsplit(parts._replace(path='/compatible-api/v1/reranks')))
        result = model_protocols.probe_model(compatible_rank)
        print(json.dumps({'check': 'compatible_rerank_probe', **result}, ensure_ascii=False), flush=True)
    # Verify migration against a session-local shadow table, never the installed table.
    engine = create_engine(Config().SQLALCHEMY_DATABASE_URI)
    with engine.connect() as connection:
        connection.execute(text('CREATE TEMP TABLE model_config (model_name text, url text, model_api_key text)'))
        assert connection.execute(text("SELECT relpersistence FROM pg_class WHERE oid = 'model_config'::regclass")).scalar_one() == 't'
        connection.execute(text("INSERT INTO model_config VALUES ('fixture', 'https://example.com/v1', 'fixture-key')"))
        migration = (API_ROOT / 'scripts/migrations/20260916_model_protocol.sql').read_text(encoding='utf-8')
        connection.execute(text(migration))
        connection.execute(text(migration))
        row = connection.execute(text('SELECT * FROM model_config')).mappings().one()
        assert row['api_protocol'] == 'auto' and row['embedding_dimensions'] is None
        assert row['model_name'] == 'fixture' and row['model_api_key'] == 'fixture-key'
        connection.rollback()
    engine.dispose()
    print(json.dumps({'status': 'passed', 'check': 'idempotent_migration_on_temporary_table',
                      'elapsed_seconds': round(time.monotonic() - started, 2)}, ensure_ascii=False), flush=True)
    namespace['reset_session']()


if __name__ == '__main__':
    main()
