import argparse
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import prepare_deepseek_annotations as deepseek
import prepare_qwen_annotations as shared


class DeepseekTests(unittest.TestCase):
    def budget(self, path):
        return shared.Budget(path, '0', 'binding', total_micro=deepseek.TOTAL_MICRO,
                             max_input=deepseek.MAX_INPUT, input_rate=300, output_rate=500)

    def test_rate_and_maximum_reservation(self):
        with TemporaryDirectory() as directory:
            budget = self.budget(Path(directory) / 'budget.sqlite')
            self.assertTrue(budget.reserve('none/image'))
            self.assertEqual(budget.summary()['calls'][0]['amount_micro_rub'], 316_620_800)
            budget.settle('none/image', {'usage': {'input_tokens': 1000, 'output_tokens': 200}, 'id': 'r1'})
            self.assertEqual(budget.summary()['calls'][0]['amount_micro_rub'], 400_000)
            self.assertTrue(budget.reserve('low/image'))
            budget.db.close()

    def test_concurrent_unknown_calls_cannot_exceed_budget(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'budget.sqlite'
            def reserve(call):
                budget = self.budget(path)
                try:
                    return budget.reserve(call)
                except shared.AnnotationError as exc:
                    return str(exc)
                finally:
                    budget.db.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(reserve, ('none/a', 'low/b')))
            self.assertCountEqual(results, [True, 'budget_exhausted'])

    def test_http_error_retains_reservation_and_never_retries(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            args = argparse.Namespace(allow_cloud_upload=True, limit=1, ids=['a'],
                                      manifest=Path('manifest'), archive=Path('archive'), reasoning='none')
            error = HTTPError('https://example.org', 403, 'Forbidden', {},
                              BytesIO(b'{"error":{"message":"subscription required SECRET"}}'))
            with patch.dict('os.environ', YANDEX_API_KEY='SECRET', YANDEX_FOLDER_ID='folder'), \
                 patch.object(deepseek, 'OUTPUT', output), \
                 patch.object(deepseek, 'LEDGER', output / 'budget.sqlite'), \
                 patch.object(shared, 'verified_sources', return_value=({'images': []}, 'hash', {'a': b'png'})), \
                 patch.object(shared, 'cloud_request', side_effect=error) as cloud:
                with self.assertRaisesRegex(shared.AnnotationError, 'subscription_required_or_restricted'):
                    deepseek.run(args)
                deepseek.run(args)
                self.assertEqual(cloud.call_count, 1)
            saved = (output / 'none/errors/a.json').read_text()
            self.assertNotIn('SECRET', saved)
            self.assertEqual(json.loads(saved)['http_status'], 403)
            manifest = json.loads((output / 'none/draft-annotations.json').read_text())
            self.assertEqual(manifest['model'], 'deepseek-v4.1-flash')


if __name__ == '__main__':
    unittest.main()
