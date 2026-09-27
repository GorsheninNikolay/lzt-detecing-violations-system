import json
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from app.shared import quality_budget as budget


def ledger(tmp_path):
    path = tmp_path / 'budget.json'
    path.write_bytes(budget.BASELINE_PATH.read_bytes())
    return path


def test_clean_checkout_uses_pinned_tracked_baseline(tmp_path):
    source = tmp_path / 'backend/app/shared/quality_budget.py'
    source.parent.mkdir(parents=True)
    source.write_bytes(Path(budget.__file__).read_bytes())
    baseline = tmp_path / 'evaluation/hybrid/budget.json'
    baseline.parent.mkdir(parents=True)
    baseline.write_bytes(budget.BASELINE_PATH.read_bytes())
    spec = importlib.util.spec_from_file_location('clean_checkout_budget', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.BASELINE_PATH == baseline
    module.verify_history(json.loads(baseline.read_text()))
    baseline.write_text('{}')
    with pytest.raises(ValueError, match='quality_budget_history_invalid'):
        module.verify_history({'calls': []})


def test_concurrent_reservations_cannot_exceed_cap(tmp_path):
    path = ledger(tmp_path)
    def reserve(_):
        try:
            return budget.reserve(path, 'test', 'hash')
        except ValueError as error:
            assert str(error) == 'quality_budget_exhausted'
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = [value for value in pool.map(reserve, range(8)) if value]
    assert len(ids) == 2
    assert Decimal(budget.status(path)['exposure_rub']) == Decimal('696.1221')
    assert budget.status(path)['can_reserve'] is False


def test_unknown_outcome_retains_upper_and_valid_usage_settles_once(tmp_path):
    path = ledger(tmp_path)
    identity = budget.reserve(path, 'test', 'hash')
    assert budget.status(path)['exposure_rub'] == '377.4533'
    with pytest.raises(ValueError):
        budget.settle(path, identity, {'input_tokens': -1, 'output_tokens': 1})
    assert budget.status(path)['exposure_rub'] == '377.4533'
    budget.settle(path, identity, {'input_tokens': 1000, 'output_tokens': 2000})
    assert budget.status(path)['exposure_rub'] == '60.0845'
    with pytest.raises(ValueError):
        budget.settle(path, identity, {'input_tokens': 0, 'output_tokens': 0})


def test_invalid_ledger_never_releases_money(tmp_path):
    path = ledger(tmp_path)
    data = json.loads(path.read_text()); data['calls'][0]['actual_estimate_rub']='NaN'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        budget.reserve(path, 'test', 'hash')


def test_deepseek_reserves_before_http_and_keeps_uncertain_cost(tmp_path, monkeypatch):
    from app.profiles import deepseek
    path = ledger(tmp_path)
    monkeypatch.setenv('HYBRID_BUDGET_LEDGER', str(path))
    seen = []
    def unavailable(*args):
        seen.append(budget.status(path)['exposure_rub'])
        raise TimeoutError('uncertain')
    monkeypatch.setattr(deepseek, '_read_json', unavailable)
    observer = deepseek.DeepSeek(deepseek.snapshot('mock-folder'), 'not-a-real-key')
    with pytest.raises(TimeoutError):
        observer.call('assessment', {'frames': [], 'plan': None})
    assert seen == ['377.4533']
    assert budget.status(path)['exposure_rub'] == '377.4533'


def test_paid_invalid_assessment_still_settles_valid_usage(tmp_path, monkeypatch):
    from app.profiles import deepseek
    path = ledger(tmp_path)
    monkeypatch.setenv('HYBRID_BUDGET_LEDGER', str(path))
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: {
        'model': 'wrong-model', 'usage': {'input_tokens': 1000, 'output_tokens': 2000}})
    observer = deepseek.DeepSeek(deepseek.snapshot('mock-folder'), 'not-a-real-key')
    result = observer.call('assessment', {'frames': [], 'plan': None})
    assert result['valid'] is False
    assert budget.status(path)['exposure_rub'] == '60.0845'


def test_settlement_failure_preserves_raw_and_full_reserve(tmp_path,monkeypatch):
    from app.profiles import deepseek
    path=ledger(tmp_path)
    monkeypatch.setenv('HYBRID_BUDGET_LEDGER',str(path))
    raw={'id':'paid-response','model':'wrong-model','usage':{'input_tokens':10,'output_tokens':10}}
    monkeypatch.setattr(deepseek,'_read_json',lambda *args:raw)
    def unavailable(*args):raise OSError('disk unavailable')
    monkeypatch.setattr(budget,'settle',unavailable)
    result=deepseek.DeepSeek(deepseek.snapshot('mock-folder'),'test-key').call('assessment',{'frames':[],'plan':None})
    assert result['raw']==raw and result['rejection']=='quality_budget_settlement_failed'
    assert result['valid'] is False and budget.status(path)['exposure_rub']=='377.4533'


def test_non_object_paid_response_is_retained_as_uncertain(tmp_path,monkeypatch):
    from app.profiles import deepseek
    path=ledger(tmp_path)
    monkeypatch.setenv('HYBRID_BUDGET_LEDGER',str(path))
    monkeypatch.setattr(deepseek,'_read_json',lambda *args:[])
    result=deepseek.DeepSeek(deepseek.snapshot('mock-folder'),'test-key').call('assessment',{'frames':[],'plan':None})
    assert result['raw']==[] and result['valid'] is False
    assert budget.status(path)['exposure_rub']=='377.4533'
