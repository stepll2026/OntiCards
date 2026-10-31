"""Deterministic summary regressions; no database, credentials or model calls.

Run: python -m unittest discover -s OntiCards_Api/test -p test_report_summary_facts.py -v
"""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


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


class SummaryFactsTests(unittest.TestCase):
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
             patch.object(summary, '_call_qwen_llm', side_effect=lambda prompt: prompt):
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


if __name__ == '__main__':
    unittest.main()
