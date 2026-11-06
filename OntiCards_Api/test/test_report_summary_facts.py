"""Deterministic summary regressions; no database, credentials or model calls.

Run: python -m unittest discover -s OntiCards_Api/test -p test_report_summary_facts.py -v
"""
import importlib.util
import copy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import contextmanager


# The production module only uses these ORM classes as type annotations.
_models = {}
for _name, _class in [('governance_report', 'GovernanceReport'),
                      ('rule_execution_result', 'RuleExecutionResult')]:
    _module = ModuleType('models.' + _name)
    setattr(_module, _class, object)
    _models[_module.__name__] = _module
_path = Path(__file__).resolve().parents[1] / 'controllers/governance/report_summary_llm.py'
_spec = importlib.util.spec_from_file_location('summary_under_test', _path)
summary = importlib.util.module_from_spec(_spec)
with patch.dict(sys.modules, _models):
    _spec.loader.exec_module(summary)


def table(rows=(3, 3, 3), schema='public', database='db'):
    return dict(db_type='sqlite', database=database, schema=schema, table='orders',
                report=[dict(column_name=str(i), total_rows=n, null_count=0,
                             empty_str_count=0, missing_count=0, missing_pct=0)
                        for i, n in enumerate(rows)])


@contextmanager
def provider_capture():
    """Replace only the external provider, exercising the real report helpers."""
    provider = ModuleType('controllers.agents.qwen.QwenMaxLatest')
    calls = []
    def capture(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return prompt, {}
    provider.qian_wen_llm_with_usage = capture
    with patch.dict(sys.modules, {provider.__name__: provider}):
        yield calls


class SummaryFactsTests(unittest.TestCase):
    def test_healthy_runtime6_identities_reach_current_and_legacy_overall_prompts(self):
        response = json.loads((Path(__file__).parent / 'fixtures/report_runtime6_governance.json').read_text(encoding='utf-8'))['data']
        before = copy.deepcopy(response)
        templates = [summary._load_prompt_template('report_overall_summary_chunk.txt', force_file=True),
                     (Path(__file__).parent / 'fixtures/report_overall_summary_legacy.txt').read_text(encoding='utf-8')]
        for template in templates:
            with self.subTest(template=template[:30]):
                prompt = self.prompt_for(response, template)
                basic, _ = json.JSONDecoder().raw_decode(prompt[prompt.index('{'):])
                self.assertIn('inspected_tables', basic)
                self.assertEqual(len(basic['inspected_tables']), 1)
                identity = basic['inspected_tables'][0]
                self.assertEqual(identity['table'], 'maintenance_orders')
                self.assertEqual(identity['columns'], ['amount', 'order_id', 'region'])
                self.assertIsNone(identity['schema'])
                self.assertEqual(basic['top_problems'], [])
                self.assertEqual((basic['total_rows'], basic['field_observations']), (3, 9))
        self.assertEqual(response, before)

    def test_inspected_and_problem_identities_keep_same_names_in_distinct_scopes(self):
        tables = [table(), table(schema='other'), table(database='other'), table()]
        tables[-1]['datasource_id'] = 'second-source'
        for t in tables:
            t['report'][0].update(missing_pct=33.33, missing_count=1)
        facts = self.basic(*tables)
        self.assertIn('inspected_tables', facts)
        expected = [(None, 'db', 'public'), (None, 'db', 'other'),
                    (None, 'other', 'public'), ('second-source', 'db', 'public')]
        for collection in ['inspected_tables', 'top_problems']:
            with self.subTest(collection=collection):
                self.assertEqual([(x['datasource_id'], x['database'], x['schema']) for x in facts[collection]], expected)
                self.assertTrue(all(x['table'] == 'orders' and x['db_type'] == 'sqlite' for x in facts[collection]))
        self.assertEqual(facts['tables_count'], 4)
        self.assertEqual(facts['total_rows'], 12)

    def test_identity_inventory_preserves_partial_unknown_and_empty_inputs(self):
        known = table((0,))
        del known['report'][0]['column_name']
        unknown = {'report': [{'column_name': 'known_column', 'total_rows': 3}]}
        facts = self.basic(known, unknown)
        self.assertIn('inspected_tables', facts)
        self.assertEqual(facts['inspected_tables'][0]['columns'], [None])
        self.assertEqual(facts['inspected_tables'][0]['table'], 'orders')
        self.assertIsNone(facts['inspected_tables'][1]['table'])
        self.assertEqual(facts['inspected_tables'][1]['columns'], ['known_column'])
        self.assertIsNone(facts['total_rows'])
        self.assertEqual(self.basic()['inspected_tables'], [])
        self.assertEqual(self.basic(table(()))['inspected_tables'][0]['columns'], [])
        missing = json.loads(summary._build_summary_json_for_module({}, 'basic_audit'))
        self.assertNotIn('inspected_tables', missing)
        self.assertIsNone(missing['status'])

    def basic(self, *tables):
        return json.loads(summary._build_summary_json_for_module(
            {'tables': list(tables)}, 'basic_audit'))

    def test_three_rows_are_not_nine_records(self):
        data = table()
        data['report'][0].update(missing_count=1, null_count=1, missing_pct=33.33)
        facts = self.basic(data)
        self.assertEqual(facts['total_rows'], 3)
        self.assertEqual(facts['field_observations'], 9)
        self.assertEqual(facts['missing_pct'], 11.11)

    def test_table_identity_includes_schema_and_database(self):
        facts = self.basic(table(), table((2, 2), schema='other'),
                           table((4,), database='other'))
        self.assertEqual(facts['total_rows'], 9)
        self.assertEqual(facts['tables_count'], 3)

    def test_repeated_table_does_not_duplicate_rows(self):
        self.assertEqual(self.basic(table(), table())['total_rows'], 3)

    def test_unknown_or_conflicting_rows_are_not_guessed(self):
        for rows in [(3, 4), (3, None), (), (-1,), (True,), ('3',)]:
            with self.subTest(rows=rows):
                self.assertIsNone(self.basic(table(rows))['total_rows'])

    def test_zero_rows_are_known_and_do_not_divide_by_zero(self):
        facts = self.basic(table((0, 0)))
        self.assertEqual(facts['total_rows'], 0)
        self.assertEqual(facts['missing_pct'], 0)

    def test_missing_column_count_keeps_rate_unknown(self):
        data = table()
        del data['report'][0]['total_rows']
        facts = self.basic(data)
        self.assertIsNone(facts['total_rows'])
        self.assertIsNone(facts['missing_pct'])

    def test_actual_prompt_carries_authoritative_score_even_with_legacy_template(self):
        # Database templates can lag behind file updates.
        for score in [100.0, 0.0, None]:
            with self.subTest(score=score):
                report = SimpleNamespace(quality_score=score, grade='优秀' if score == 100 else None)
                prompts = []
                def capture(prompt):
                    prompts.append(prompt)
                    return '分析建议'
                with patch.object(summary, '_call_qwen_llm', side_effect=capture), \
                     patch.object(summary, '_load_prompt_template', return_value='{basic_audit_summary}'):
                    self.assertEqual(summary.generate_overall_summary(report, {'basic_audit': {'tables': [table()]}}), '分析建议')
                prompt = prompts[0]
                self.assertIn('"quality_score": ' + json.dumps(score), prompt)
                self.assertIn('"total_rows": 3', prompt)
                self.assertIn('不得重新评分', prompt)
                self.assertIn('未知', prompt)

    def test_file_template_formats_with_report_facts(self):
        template = summary._load_prompt_template('report_overall_summary_chunk.txt', force_file=True)
        with patch.object(summary, '_load_prompt_template', return_value=template), \
             patch.object(summary, '_call_qwen_llm', side_effect=lambda prompt: prompt):
            prompt = summary.generate_overall_summary(SimpleNamespace(quality_score=100.0, grade='优秀'), {})
        self.assertIn('"quality_score": 100.0', prompt)
        self.assertIn('"grade": "优秀"', prompt)

    def prompt_for(self, response, template=None):
        if template is None:
            template = summary._load_prompt_template('report_overall_summary_chunk.txt', force_file=True)
        with patch.object(summary, '_load_prompt_template', return_value=template), \
             provider_capture():
            return summary.generate_overall_summary(SimpleNamespace(quality_score=100, grade='优秀'), response)

    def test_missing_modules_do_not_claim_not_executed(self):
        prompt = self.prompt_for({})
        self.assertNotIn('未执行该模块', prompt)
        self.assertNotIn('用户本次未选择', prompt)
        self.assertIn('没有可用结果', prompt)
        self.assertIn('"status": null', prompt)

    def test_empty_module_results_preserve_unknown_execution_status(self):
        response = {'basic_audit': {'tables': []}, 'quality_audit': {'results': []},
                    'relation_discovery': {}}
        prompt = self.prompt_for(response)
        self.assertNotIn('未执行该模块', prompt)
        self.assertIn('"rules_count": 0', prompt)
        self.assertIn('"pass_rate": null', prompt)
        self.assertIn('"status": null', prompt)

    def test_completed_zero_relationships_are_available_results(self):
        data = {'status': 'completed', 'relationships_count': 0, 'relationships': [],
                'tables_count': 1, 'cards_count': 0}
        prompt = self.prompt_for({'relation_discovery': data})
        self.assertIn('"relationships_count": 0', prompt)
        self.assertIn('"status": "completed"', prompt)
        self.assertNotIn('未执行该模块', prompt)

    def test_full_legacy_database_template_has_no_conflicting_instructions(self):
        template = (Path(__file__).parent / 'fixtures/report_overall_summary_legacy.txt').read_text(encoding='utf-8')
        prompt = self.prompt_for({}, template)
        self.assertNotIn('未执行该模块', prompt)
        self.assertNotIn('用户本次未选择', prompt)
        self.assertNotIn('给出整体质量评分', prompt)
        self.assertIn('"quality_score": 100.0', prompt)
        self.assertIn('没有可用结果', prompt)

    def test_current_and_saved_templates_do_not_require_unsupported_diagnoses(self):
        templates = [summary._load_prompt_template('report_overall_summary_chunk.txt', force_file=True),
                     (Path(__file__).parent / 'fixtures/report_overall_summary_legacy.txt').read_text(encoding='utf-8')]
        for template in templates:
            with self.subTest(template=template[:30]):
                prompt = self.prompt_for({'basic_audit': {'tables': [table()]}}, template)
                self.assertNotIn('- 分析问题的共性原因（系统层面/业务层面）', prompt)
                self.assertNotIn('- 评估问题的严重程度和影响范围', prompt)
                self.assertNotIn('最突出的 3-5 个关键问题', prompt)
                self.assertIn('不凑足条数', prompt)
                self.assertIn('原因未知', prompt)
                self.assertIn('待核查方向', prompt)

    def test_unknown_causes_and_advisory_severity_are_explicit_in_actual_prompt(self):
        for response in [{}, {'quality_audit': {}},
                         {'quality_audit': {'status': 'error'}},
                         {'quality_audit': {'status': 'completed', 'results': []}}]:
            with self.subTest(response=response):
                prompt = self.prompt_for(response)
                self.assertIn('缺少结果或仅有 status 不能证明原因', prompt)
                self.assertIn('不得据此断言配置、执行链路或结果采集发生故障', prompt)
                self.assertIn('标明为建议或推断', prompt)
                self.assertIn('不得写成已观察到的故障或严重级别', prompt)

    def test_custom_template_content_survives_with_final_evidence_constraints(self):
        custom = ('企业附录：保留责任人表格及季度计划。\n{quality_audit_summary}\n'
                  '企业分析要求：分析所有缺失结果的原因与严重程度。')
        prompt = self.prompt_for({}, custom)
        self.assertIn('企业附录：保留责任人表格及季度计划。', prompt)
        self.assertIn('企业分析要求：分析所有缺失结果的原因与严重程度。', prompt)
        boundary = '证据与建议边界（优先于模板中的原因分析、严重程度和建议要求）'
        self.assertIn(boundary, prompt)
        self.assertGreater(prompt.index(boundary), prompt.index('企业分析要求'))
        self.assertIn('原因未知', prompt)
        self.assertIn('标明为建议或推断', prompt)

    def test_preceding_database_template_cannot_treat_status_as_cause_evidence(self):
        # This clause was shipped after the original saved legacy fixture.
        # Preserve unrelated database customizations while upgrading the known clause.
        old_clause = '- 如果某个模块缺少结果，说明没有可用结果；仅在明确的执行状态支持时说明原因'
        template = '{quality_audit_summary}\n' + old_clause + '\n企业附录：保留审批流程。'
        prompt = self.prompt_for({'quality_audit': {'status': 'error'}}, template)
        self.assertNotIn(old_clause, prompt)
        self.assertIn('不能从 status 单独推断', prompt)
        self.assertIn('企业附录：保留审批流程。', prompt)
        self.assertIn('"status": "error"', prompt)
        self.assertIn('原因未知', prompt)

    def test_observed_critical_failures_are_not_suppressed_by_unknown_cause_policy(self):
        response = {'quality_audit': {'status': 'completed', 'results': [
            {'status': 'failed', 'rule_name': 'amount_nonnegative', 'table_name': 'orders',
             'column_name': 'amount', 'severity': 'critical', 'failed_count': 7, 'failed_rate': 70},
            {'status': 'error', 'rule_name': 'region_check'},
            {'status': 'passed', 'rule_name': 'order_id_check'},
        ]}}
        before = json.dumps(response, sort_keys=True)
        prompt = self.prompt_for(response, '{quality_audit_summary}')
        facts, _ = json.JSONDecoder().raw_decode(prompt)
        self.assertEqual(facts['failed_count'], 1)
        self.assertEqual(facts['error_count'], 1)
        self.assertEqual(facts['critical_count'], 1)
        self.assertEqual(facts['total_failed_rows'], 7)
        self.assertEqual(facts['top_failures'][0]['severity'], 'critical')
        self.assertEqual(facts['top_failures'][0]['rule_name'], 'amount_nonnegative')
        self.assertIn('实际失败、错误、severity、critical_count 和影响行数须如实引用', prompt)
        self.assertIn('不得因原因未知而淡化已有检测事实', prompt)
        self.assertEqual(json.dumps(response, sort_keys=True), before)


class SharedReportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.report = SimpleNamespace(id=1, quality_score=100, grade='优秀',
                                      datasource_id=1, report_name='回归报告',
                                      execution_time=None, scope_tables=[], details={})
        self.response = {'basic_audit': {'tables': [table()]}}

    def assert_boundary(self, prompt):
        self.assertEqual(prompt.count('## 证据与建议边界'), 1)
        self.assertIn('零缺失、零失败或执行成功不能证明已有预防机制', prompt)
        self.assertIn('非空约束（NOT NULL）、默认值、录入校验、初始化或清洗流程', prompt)
        self.assertIn('输入未提供不等于底层不存在', prompt)
        self.assertIn('仅在输入明确提供时引用已有机制', prompt)
        self.assertIn('原因未知', prompt)
        self.assertIn('条件建议', prompt)
        self.assertIn('实际失败、错误、severity、critical_count 和影响行数须如实引用', prompt)

    def test_parallel_basic_chunk_reaches_provider_with_boundary_and_config(self):
        config = {'model_name': 'offline-test', 'timeout': 17}
        with provider_capture() as calls, patch.object(summary, '_get_model_config_dict', return_value=config):
            result = summary.generate_report_chunks(self.report, self.response)
        self.assertEqual(len(calls), 1)
        prompt, kwargs = calls[0]
        self.assertEqual(result['basic_audit'], prompt.strip())
        self.assertEqual(kwargs, {'stream_type': False, 'model_config_dict': config})
        self.assertIn('"missing_count":0', prompt)
        self.assert_boundary(prompt)

    def test_overall_and_dynamic_reach_provider_with_boundary(self):
        for generate in [summary.generate_overall_summary, summary.generate_report_summary_from_response]:
            with self.subTest(generate=generate.__name__), provider_capture() as calls:
                generate(self.report, self.response)
                self.assertEqual(len(calls), 1)
                self.assert_boundary(calls[0][0])

    def test_legacy_entry_reaches_same_provider_boundary(self):
        with provider_capture() as calls:
            summary.ReportSummaryLLM().generate_summary(self.report, [])
        self.assertEqual(len(calls), 1)
        self.assert_boundary(calls[0][0])

    def test_database_custom_templates_are_loaded_and_constrained(self):
        flask = ModuleType('flask')
        flask.has_app_context = lambda: True
        db = ModuleType('models.prompt_config')
        templates = {
            'report_basic_audit_chunk.txt': '企业自定义附录\n{basic_audit_data}\n- 如果没有缺失问题，分析数据完整性好的原因',
            'report_overall_summary_chunk.txt': '企业自定义附录\n{basic_audit_summary}',
            'report_dynamic_prompt.txt': '企业自定义附录\n{EXECUTION_RESPONSE_JSON}',
            'report_summary_prompt.txt': '企业自定义附录\n{null_check_section}',
        }
        db.prompt_manager = SimpleNamespace(get_prompt=lambda name, **kwargs: templates[name])
        with patch.dict(sys.modules, {'flask': flask, 'models.prompt_config': db}):
            for generate in [lambda: summary._generate_basic_audit_chunk(self.response['basic_audit']),
                             lambda: summary.generate_overall_summary(self.report, self.response),
                             lambda: summary.generate_report_summary_from_response(self.report, self.response),
                             lambda: summary.ReportSummaryLLM().generate_summary(self.report, [])]:
                with provider_capture() as calls:
                    generate()
                    self.assertEqual(len(calls), 1)
                    prompt = calls[0][0]
                    self.assertIn('企业自定义附录', prompt)
                    self.assert_boundary(prompt)
                    self.assertGreater(prompt.index('## 证据与建议边界'), prompt.index('企业自定义附录'))
                    self.assertNotIn('- 如果没有缺失问题，分析数据完整性好的原因', prompt)

    def test_direct_chunks_preserve_explicit_controls_and_critical_failures(self):
        data = {'tables': [table()], 'controls': {'nullable': False, 'default': 0},
                'results': [{'severity': 'critical', 'failed_count': 7}],
                'relationships_count': 1}
        before = json.dumps(data, sort_keys=True)
        for generate in [summary._generate_basic_audit_chunk, summary._generate_quality_audit_chunk,
                         summary._generate_relation_chunk]:
            with self.subTest(generate=generate.__name__), provider_capture() as calls:
                generate(data)
                self.assertEqual(len(calls), 1)
                prompt = calls[0][0]
                self.assertIn('"nullable":false', prompt)
                self.assertIn('"default":0', prompt)
                self.assertIn('"severity":"critical","failed_count":7', prompt)
                self.assert_boundary(prompt)
        self.assertEqual(json.dumps(data, sort_keys=True), before)

    def test_shared_helper_keeps_provider_output_and_empty_response_behavior(self):
        provider = ModuleType('controllers.agents.qwen.QwenMaxLatest')
        for content in ['  原始模型结果  ', '']:
            provider.qian_wen_llm_with_usage = lambda *args, **kwargs: (content, {})
            with patch.dict(sys.modules, {provider.__name__: provider}):
                for call in [summary._call_qwen_llm, summary.ReportSummaryLLM()._call_llm]:
                    if content:
                        self.assertEqual(call('输入'), '原始模型结果')
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'LLM 返回内容为空'):
                            call('输入')


if __name__ == '__main__':
    unittest.main()
