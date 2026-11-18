"""Unit tests for the D7 ontology acceptance scoring helpers."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from acceptance import ontology  # noqa: E402


class PayloadTests(unittest.TestCase):
    def test_mcp_envelope_is_unwrapped_to_the_issue_payload(self):
        inner = {
            'error': 'invalid_input',
            'detail': 'preview contains unresolved issues',
            'issues': [{
                'code': 'ontology.conversion_failed',
                'reason': '值无法按目标类型转换',
            }],
        }
        envelope = {
            'content': [{'type': 'text', 'text': json.dumps(inner, ensure_ascii=False)}],
            'isError': True,
        }
        payload = ontology._payload(AssertionError(envelope))
        self.assertEqual(payload, inner)
        self.assertEqual(
            ontology._issue_reasons(payload),
            ['ontology.conversion_failed 值无法按目标类型转换'],
        )

    def test_issue_list_from_a_failed_result_is_kept(self):
        issues = [{'code': 'ontology.evidence_missing', 'reason': '值没有来源定位'}]
        payload = ontology._payload(AssertionError(issues))
        self.assertEqual(payload['issues'], issues)

    def test_raw_envelope_has_no_issue_reasons(self):
        # Negative case: without unwrapping content[0].text the transport
        # frame carries no issues, which is exactly the E3 defect.
        envelope = {
            'content': [{'type': 'text', 'text': json.dumps({'issues': [
                {'code': 'ontology.conversion_failed', 'reason': '值无法按目标类型转换'},
            ]}, ensure_ascii=False)}],
            'isError': True,
        }
        self.assertEqual(ontology._issue_reasons(envelope), [])

    def test_unknown_issue_code_never_copies_the_raw_exception(self):
        payload = {'issues': [{
            'code': 'custom.unmapped_issue',
            'reason': 'Traceback (most recent call last): ValueError: bad value',
            'detail': 'Traceback (most recent call last): ValueError: bad value',
        }]}
        reasons = ontology._issue_reasons(payload)
        text = ' '.join(reasons)
        self.assertIn('custom.unmapped_issue', text)
        self.assertNotIn('Traceback', text)
        self.assertNotIn('bad value', text)

    def test_known_issue_uses_the_workbench_reason(self):
        payload = {'issues': [{
            'code': 'ontology.conversion_failed',
            'reason': '值无法按目标类型转换',
            'detail': 'ValueError: raw text',
        }]}
        self.assertEqual(
            ontology._issue_reasons(payload),
            ['ontology.conversion_failed 值无法按目标类型转换'],
        )


class QueryComparisonTests(unittest.TestCase):
    def test_date_and_midnight_datetime_compare_equal(self):
        self.assertTrue(ontology._entry_matches(
            {'when': '2026-03-02'}, {'when': '2026-03-02T00:00:00'}))
        self.assertTrue(ontology._entry_matches(
            {'when': '2026-03-02T00:00:00'}, {'when': '2026-03-02'}))

    def test_real_time_part_still_differs(self):
        self.assertFalse(ontology._entry_matches(
            {'when': '2026-03-02T01:00:00'}, {'when': '2026-03-02'}))

    def test_filter_echo_must_match_and_every_row_must_obey(self):
        page = {
            'filters': [{'property': 'grade', 'op': 'eq', 'value': 'A'}],
            'items': [{'values': {'grade': 'A'}}],
        }
        self.assertTrue(ontology._filter_echo_ok(
            page, [{'property': 'grade', 'op': 'eq', 'value': 'A'}]))
        self.assertFalse(ontology._filter_echo_ok(
            page, [{'property': 'grade', 'op': 'eq', 'value': 'B'}]))
        ignored = {'filters': [], 'items': page['items']}
        self.assertFalse(ontology._filter_echo_ok(
            ignored, [{'property': 'grade', 'op': 'eq', 'value': 'A'}]))


class QueryScoringTests(unittest.TestCase):
    def _flow(self, filters):
        flow = object.__new__(ontology.Flow)
        flow.gold = {'query_expectations': {'Q1 test': [
            {'grade': 'A', 'amount': '10'}]}}
        flow.art = {'query': {'C1_filters': filters}}
        flow.results = ontology.Results()
        flow._concept_evidence = lambda key: (
            {'properties': {'grade': {'column': 'grade'},
                            'amount': {'column': 'amount'}}}, None)
        return flow

    @staticmethod
    def _filtered(total=1):
        return {
            'where': [{'property': 'grade', 'op': 'eq', 'value': 'A'}],
            'page': {
                'filters': [{'property': 'grade', 'op': 'eq', 'value': 'A'}],
                'total': total,
                'items': [{'values': {'grade': 'A', 'amount': '10'}}],
            },
        }

    def test_q1_passes_only_through_a_matching_attribute_filter(self):
        flow = self._flow([self._filtered()])
        flow._score_query()
        self.assertEqual(flow.results.rows['Q1']['status'], 'pass')

    def test_q1_fails_without_an_attribute_filter(self):
        flow = self._flow([])
        flow._score_query()
        self.assertEqual(flow.results.rows['Q1']['status'], 'fail')
        self.assertIn('没有下发属性过滤条件', flow.results.rows['Q1']['reason'])

    def test_q1_fails_when_the_tool_ignores_the_filter(self):
        entry = self._filtered()
        entry['page']['filters'] = []
        flow = self._flow([entry])
        flow._score_query()
        self.assertEqual(flow.results.rows['Q1']['status'], 'fail')


class SourceChangeTests(unittest.TestCase):
    def test_source_snapshot_change_is_recognised(self):
        self.assertTrue(ontology._is_source_change_rejection(
            {'error': 'invalid_input', 'detail': 'source snapshot changed; discover again'}))

    def test_other_refusals_are_not_accepted(self):
        self.assertFalse(ontology._is_source_change_rejection(
            {'error': 'version_conflict', 'detail': 'candidate expired; reload'}))
        self.assertFalse(ontology._is_source_change_rejection(
            {'error': 'invalid_input', 'detail': 'task changed; reload'}))


class TypeComparisonTests(unittest.TestCase):
    def test_date_to_datetime_is_a_recorded_deviation_not_a_failure(self):
        failures, deviations = ontology._compare_value_types(
            [{'name': 'day', 'value_type': 'date'}],
            {'day': 'day'},
            {'day': {'value_type': 'datetime'}},
        )
        self.assertEqual(failures, [])
        self.assertEqual(deviations, 1)

    def test_other_type_mismatch_still_fails(self):
        failures, deviations = ontology._compare_value_types(
            [{'name': 'amount', 'value_type': 'decimal'}],
            {'amount': 'amount'},
            {'amount': {'value_type': 'string'}},
        )
        self.assertEqual(failures, ['decimal->string'])
        self.assertEqual(deviations, 0)


class RelationTests(unittest.TestCase):
    def _specs(self, entries):
        relations = {name: {'subject_concept': subject, 'object_concept': obj}
                     for name, subject, obj, _ in entries}
        evidence = {name: {'evidence_id': 'link-' + name, 'source_columns': pairs[0],
                           'target_columns': pairs[1]}
                    for name, _, _, pairs in entries}
        links = {'link-' + name: {'id': 'link-' + name, 'matched_rows': 16,
                                  'checked_rows': 20, 'matched_distinct_keys': 12}
                 for name, _, _, _ in entries}
        return ontology._relation_specs(relations, evidence, links)

    @staticmethod
    def _gold(*joins):
        return [{'from': 'C2 detail', 'to': 'C1 standard', 'join': [list(pair) for pair in join]}
                for join in joins]

    def test_all_gold_relations_match(self):
        join = [('a', 'a'), ('b', 'b'), ('c', 'c')]
        checks = ontology._relation_checks(
            self._specs([('Relation1', 'Detail', 'Standard', (['a', 'b', 'c'], ['a', 'b', 'c']))]),
            self._gold(join), 'Standard', 'Detail')
        self.assertTrue(all(item[0] for item in checks.values()), checks)

    def test_every_gold_relation_is_required(self):
        first = [('a', 'a'), ('b', 'b'), ('c', 'c')]
        second = [('x', 'x'), ('y', 'y'), ('z', 'z')]
        checks = ontology._relation_checks(
            self._specs([
                ('Relation1', 'Detail', 'Standard', (['a', 'b', 'c'], ['a', 'b', 'c'])),
                ('Relation2', 'Detail', 'Standard', (['x', 'y', 'z'], ['x', 'y', 'z'])),
            ]),
            self._gold(first, second), 'Standard', 'Detail')
        self.assertTrue(all(item[0] for item in checks.values()), checks)
        missing = ontology._relation_checks(
            self._specs([('Relation1', 'Detail', 'Standard',
                          (['a', 'b', 'c'], ['a', 'b', 'c']))]),
            self._gold(first, second), 'Standard', 'Detail')
        self.assertFalse(missing['R1'][0])
        self.assertFalse(missing['R1.join'][0])

    def test_extra_relation_fails(self):
        checks = ontology._relation_checks(
            self._specs([
                ('Relation1', 'Detail', 'Standard', (['a', 'b', 'c'], ['a', 'b', 'c'])),
                ('Relation2', 'Detail', 'Standard', (['x', 'y', 'z'], ['x', 'y', 'z'])),
            ]),
            self._gold([('a', 'a'), ('b', 'b'), ('c', 'c')]), 'Standard', 'Detail')
        self.assertFalse(checks['R1'][0])
        self.assertFalse(checks['R1.join'][0])
        self.assertFalse(checks['R1.forbidden'][0])
        self.assertIn('多出', checks['R1.forbidden'][1])

    def test_wrong_join_or_direction_fails(self):
        wrong_join = ontology._relation_checks(
            self._specs([('Relation1', 'Detail', 'Standard',
                          (['a', 'b', 'x'], ['a', 'b', 'c']))]),
            self._gold([('a', 'a'), ('b', 'b'), ('c', 'c')]), 'Standard', 'Detail')
        self.assertFalse(wrong_join['R1.join'][0])
        reversed_direction = ontology._relation_checks(
            self._specs([('Relation1', 'Standard', 'Detail',
                          (['a', 'b', 'c'], ['a', 'b', 'c']))]),
            self._gold([('a', 'a'), ('b', 'b'), ('c', 'c')]), 'Standard', 'Detail')
        self.assertFalse(reversed_direction['R1'][0])
        self.assertFalse(reversed_direction['R1.forbidden'][0])


if __name__ == '__main__':
    unittest.main()
