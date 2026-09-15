"""Exercise each actual request handler with isolated authentication/storage/model IO."""
import ast
import copy
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conftest import API_ROOT, load_functions
from test_completeness import contract, payload
from controllers.query.query_validation import QueryValidationError


@pytest.mark.parametrize('case', ['verified', 'incomplete', 'empty', 'multiple_sources', 'trino_incomplete'])
def test_request_response_and_logging_agree(endpoint, case):
    filename = endpoint['run_sql_safe_new'].__code__.co_filename.replace('\\', '/').rsplit('/', 1)[-1]
    plugin = 'plugin' in filename
    tree = ast.parse((API_ROOT / 'controllers/query' / filename).read_text(encoding='utf-8'))
    resource = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    post = copy.deepcopy(next(node for node in resource.body if isinstance(node, ast.FunctionDef) and node.name == 'post'))
    post.decorator_list = []  # Authentication is mocked; handler logic is unchanged.
    exec(compile(ast.Module(body=[post], type_ignores=[]), filename, 'exec'), endpoint)
    log_name = '_log_query_plugin' if plugin else '_log_query'
    load_functions(filename, [log_name, 'format_response', '_should_use_llm_fusion', '_filter_clusters_by_question'], endpoint)
    endpoint['defaultdict'] = defaultdict
    load_functions('sql_join_utils.py', ['build_clusters'], endpoint)

    class Query:
        def __init__(self, factory):
            self.factory = factory
        def filter_by(self, **values):
            return SimpleNamespace(first=lambda: self.factory(values))

    question = contract()['original_question']
    body = {'query': question, 'enable_term_rewrite': False}
    logger = SimpleNamespace(log_success=Mock(), log_error=Mock())
    source = lambda values: SimpleNamespace(id=values.get('connect_name', 'fixture'), schema_name=None, database_name='fixture', connect_name='fixture')
    schema = lambda values: SimpleNamespace(id=values['id'], table_name='projects', database_name='fixture')
    cards = [] if case == 'empty' else [{'DocInfo': {'connect_name': 'trino-fixture' if case == 'trino_incomplete' else 'fixture'}}]
    if case == 'multiple_sources':
        cards.append({'DocInfo': {'connect_name': 'second'}})
    retrieval = {'doc_ids': [str(i) for i in range(len(cards))], 'data_card_results': cards}
    execution = Mock()
    def execute(**kwargs):
        assert kwargs['tables'][0]['_query_contract']['original_question'] == question
        execution()
        result = payload()['clusters'][0]
        result['rows'] = payload()['final_rows']
        if case == 'incomplete':
            result['validation'] = {'status': 'incomplete', 'issues': ['缺少姓名条件']}
            result['error'] = '缺少姓名条件'
        return result
    endpoint.update(
        request=SimpleNamespace(get_json=lambda: body),
        flask_login=SimpleNamespace(current_user=SimpleNamespace(id='owner', weaviate_class_name='fixture')),
        _require_api_key_user_id=lambda: ('owner', None, 'fixture-key-id'),
        User=SimpleNamespace(query=Query(lambda values: SimpleNamespace(weaviate_class_name='fixture'))),
        UserDatasourceSchema=SimpleNamespace(query=Query(schema)),
        DatasourceInfo=SimpleNamespace(query=Query(source)),
        QueryLogger=logger, db=SimpleNamespace(session=Mock()),
        _base_format_response=lambda data, code, msg: ({'code': code, 'data': data, 'msg': msg}, code),
        _infer_strategy=lambda question: 'AND', plan_query=lambda *a: contract(),
        recall_requirements=lambda *a, **k: retrieval, get_data_card_json=None,
        expand_owned_dependencies=lambda result, *a: result,
        qian_wen_llm_with_usage=None,
        map_connect_name_to_connect_info=lambda name, *a, **k: name,
        card_to_table_obj=lambda row, card, conn, **k: {
            'table_name': 'projects', 'connect_name': conn, 'connect_info': conn,
            'db_type': 'sqlite', 'columns': [{'name': 'name'}]},
        infer_entity_key_from_cards=lambda tables: 'id',
        fetch_relationship_cards=lambda **k: {}, merge_relationship_data=lambda *a: {'cards': {}, 'join_suggestions': []},
        _exec_cluster=execute,
        _exec_trino_unified=Mock(side_effect=QueryValidationError(['缺少行业条件'])),
    )
    response, status = endpoint['post'](None)
    assert status == (200 if case == 'verified' else 422)
    assert response['code'] == status
    if case == 'verified':
        assert response['data']['validation']['status'] == 'verified'
        assert response['data']['final_rows'] == payload()['final_rows']
        logger.log_success.assert_called_once()
        logger.log_error.assert_not_called()
    else:
        assert response['data']['validation']['status'] != 'verified'
        assert response['data']['final_rows'] == []
        logger.log_success.assert_not_called()
        logger.log_error.assert_called_once()
    if case in {'empty', 'multiple_sources', 'trino_incomplete'}:
        execution.assert_not_called()
