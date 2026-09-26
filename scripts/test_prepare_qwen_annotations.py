"""Offline checks: schema safety, shared spending and unknown-outcome fencing."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import prepare_qwen_annotations as q


def annotation():
    return {'equipment': {name: 'absent' for name in q.EQUIPMENT}, 'objects': [],
            'scenes': {name: 'absent' for name in q.SCENES}, 'stage': 'unknown',
            'stage_reason': 'No supported visible activity.'}


class AnnotationTests(unittest.TestCase):
    def test_exact_classes_and_presence_boxes(self):
        value = annotation()
        self.assertEqual(q.validate_annotation(value), value)
        value['equipment']['excavator'] = 'present'
        with self.assertRaises(q.AnnotationError):
            q.validate_annotation(value)
        value['objects'] = [{'class_name': 'excavator', 'box': [0, .2, .8, 1]}]
        q.validate_annotation(value)
        for box in ([True, .2, .8, 1], [0, .2, float('nan'), 1], [0, .2, .8, .1]):
            broken = deepcopy(value)
            broken['objects'][0]['box'] = box
            with self.assertRaises(q.AnnotationError):
                q.validate_annotation(broken)
        value['equipment']['truck'] = 'present'
        with self.assertRaises(q.AnnotationError):
            q.validate_annotation(value)

    def test_duplicate_keys_and_confidence_rejected(self):
        with self.assertRaises(q.AnnotationError):
            q.strict_json('{"x":1,"x":2}')
        value = annotation()
        value['confidence'] = .9
        with self.assertRaises(q.AnnotationError):
            q.validate_annotation(value)

    def test_model_status_refusal_and_malformed_output(self):
        response = {'id': 'resp-test', 'model': 'exact-model', 'status': 'completed', 'output': [
            {'type': 'message', 'role': 'assistant', 'content': [
                {'type': 'output_text', 'text': json.dumps(annotation())}]}]}
        q.validate_response(response, 'exact-model')
        for key, value in [('model', 'different'), ('status', 'incomplete'), ('error', {'code': 'x'})]:
            invalid = {**response, key: value}
            with self.assertRaises(q.AnnotationError):
                q.validate_response(invalid, 'exact-model')
        response['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'No'}]
        with self.assertRaises(q.AnnotationError):
            q.validate_response(response, 'exact-model')

    def test_concurrent_budget_cannot_overspend(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'budget.sqlite'
            def reserve(index):
                budget = q.Budget(path, '0', 'fixed')
                try:
                    return budget.reserve(str(index))
                except q.AnnotationError as exc:
                    self.assertEqual(str(exc), 'budget_exhausted')
                    return False
                finally:
                    budget.db.close()
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(reserve, range(25)))
            self.assertEqual(sum(outcomes), q.TOTAL_MICRO // q.RESERVE_MICRO)
            budget = q.Budget(path, '0', 'fixed')
            self.assertLessEqual(sum(c['amount_micro_rub'] for c in budget.summary()['calls']), q.TOTAL_MICRO)
            budget.db.close()

    def test_unknown_retained_invalid_json_charged_and_no_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'budget.sqlite'
            budget = q.Budget(path, '0', 'fixed')
            with self.assertRaises(q.AnnotationError):
                budget.settle('unreserved', {'usage': {'input_tokens': 1, 'output_tokens': 1}})
            self.assertTrue(budget.reserve('unknown'))
            self.assertFalse(budget.settle('unknown', {}))
            self.assertTrue(budget.reserve('invalid-output'))
            response = {'usage': {'input_tokens': 3000, 'output_tokens': 500}, 'output': 'bad'}
            self.assertTrue(budget.settle('invalid-output', response))
            with self.assertRaises(q.AnnotationError):
                q.validate_response(response, 'model')
            calls = {c['id']: c for c in budget.summary()['calls']}
            self.assertEqual(calls['unknown']['amount_micro_rub'], q.RESERVE_MICRO)
            self.assertEqual(calls['invalid-output']['amount_micro_rub'], 750000)
            budget.db.close()
            resumed = q.Budget(path, '0', 'fixed')
            self.assertFalse(resumed.reserve('unknown'))
            self.assertFalse(resumed.reserve('invalid-output'))
            resumed.db.close()
            with self.assertRaises(q.AnnotationError):
                q.Budget(path, '1', 'fixed')
            with self.assertRaises(q.AnnotationError):
                q.Budget(path, '0', 'new-binding')

    def test_experiments_share_ledger_without_reset_or_parameter_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'budget.sqlite'
            original = q.Budget(path, '0', 'legacy-binding')
            original.reserve('image')
            original.settle('image', {'usage': {'input_tokens': 3000, 'output_tokens': 100}})
            original.db.close()
            upgraded = q.Budget(path, '0', 'legacy-binding')
            upgraded.bind_experiment('v2', 'medium+prompt-v2')
            self.assertFalse(upgraded.reserve('image'))
            self.assertTrue(upgraded.reserve('v2/image'))
            self.assertFalse(upgraded.reserve('v2/image'))
            self.assertEqual(sum(c['amount_micro_rub'] for c in upgraded.summary()['calls']),
                             630000 + q.RESERVE_MICRO)
            with self.assertRaises(q.AnnotationError):
                upgraded.bind_experiment('v2', 'changed-prompt')
            self.assertEqual(upgraded.db.execute('SELECT binding FROM meta').fetchone()[0], 'legacy-binding')
            upgraded.db.close()

    def test_usage_bound_violation_charged_then_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            budget = q.Budget(Path(directory) / 'budget.sqlite', '0', 'fixed')
            budget.reserve('oversize')
            with self.assertRaises(q.AnnotationError):
                budget.settle('oversize', {'usage': {'input_tokens': q.MAX_INPUT + 1, 'output_tokens': q.MAX_OUTPUT}})
            self.assertGreater(budget.summary()['calls'][0]['amount_micro_rub'], q.RESERVE_MICRO)
            with self.assertRaises(q.AnnotationError):
                budget.reserve('another')
            budget.db.close()


if __name__ == '__main__':
    unittest.main()
