"""The paid runner must fail before transport and retain rejected paid outputs."""
import importlib.util
import json
from pathlib import Path

import pytest

from app.application import hybrid_readiness
from app.profiles import deepseek
from test_hybrid_readiness import qualified


def runner(monkeypatch, tmp_path):
    path = Path(__file__).resolve().parents[2] / 'evaluation/hybrid/run_control.py'
    spec = importlib.util.spec_from_file_location('hybrid_control_runner', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(hybrid_readiness, 'SOURCE_MANIFEST_HASHES', dict(hybrid_readiness.SOURCE_MANIFEST_HASHES))
    return module


def test_unapproved_control_cannot_construct_a_paid_observer(monkeypatch, tmp_path):
    module = runner(monkeypatch, tmp_path)
    root = tmp_path / 'output'; root.mkdir()
    profile, report = qualified(root)
    report['runs'] = []
    (root / 'profile.json').write_text(json.dumps(profile))
    review = json.loads((root / 'review.json').read_text()); review['actor_type']='machine'
    (root / 'review.json').write_text(json.dumps(review))
    report['human_review']['sha256'] = module.digest((root / 'review.json').read_bytes())
    (root / 'report.json').write_text(json.dumps(report))
    def forbidden(*args):
        pytest.fail('Paid observer accessed before source acceptance')
    monkeypatch.setattr(module, 'DeepSeek', forbidden)
    with pytest.raises(ValueError, match='human_adjudication'):
        module.run(root/'report.json', root/'profile.json', root/'budget.json')


def test_rejected_paid_result_is_saved_and_never_replayed(monkeypatch, tmp_path):
    module = runner(monkeypatch, tmp_path)
    root = tmp_path / 'output'; root.mkdir()
    profile, report = qualified(root)
    (root/'profile.json').write_text(json.dumps(profile))
    first = json.loads((root / report['runs'][0]['result']['path']).read_text())
    detection = first['component_evidence']['frames'][0]['detectors']
    report['runs'] = []
    (root/'report.json').write_text(json.dumps(report))
    monkeypatch.setattr(module, 'Detectors', lambda: type('FakeDetector', (), {'manifest':detection['manifest'], 'detect': lambda self,*args:detection})())
    calls=[]
    def rejected(request, timeout):
        calls.append(request)
        return {'id':'rejected-paid', 'model':'wrong-model', 'usage':{'input_tokens':1000,'output_tokens':1000}}
    monkeypatch.setattr(deepseek, '_read_json', rejected)
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY','test-key-never-sent')
    assert module.run(root/'report.json',root/'profile.json',root/'budget.json') == 1
    assert len(calls)==1
    directory=next(root.glob('control-*'))
    if directory.is_file():
        directory=next(p for p in root.glob('control-*') if p.is_dir())
    checkpoint=json.loads((directory/'checkpoint.json').read_text())
    assert checkpoint['status']=='blocked' and checkpoint['runs']==0
    frame=json.loads(next(directory.glob('*-frame-0.json')).read_text())
    assert frame['deepseek']['raw']['id']=='rejected-paid' and frame['deepseek']['valid'] is False
    ledger=json.loads((root/'budget.json').read_text())
    assert ledger['calls'][-1]['response_id']=='rejected-paid'


def test_missing_history_and_missing_references_fail_before_paid_calls(monkeypatch, tmp_path):
    module = runner(monkeypatch, tmp_path)
    root = tmp_path / 'output'; root.mkdir()
    profile, report = qualified(root)
    report['runs']=[]
    (root/'profile.json').write_text(json.dumps(profile)); (root/'report.json').write_text(json.dumps(report))
    (root/'empty-budget.json').write_text(json.dumps({'limit_rub':1000,'calls':[]}))
    def forbidden(*args):
        pytest.fail('Paid observer constructed with incomplete approval inputs')
    monkeypatch.setattr(module,'DeepSeek',forbidden)
    with pytest.raises(ValueError,match='historical_budget_exposure_missing'):
        module.run(root/'report.json',root/'profile.json',root/'empty-budget.json')
    annotation=json.loads((root/'annotations.json').read_text())
    annotation['0'].pop('component_reference')
    (root/'annotations.json').write_text(json.dumps(annotation))
    report['annotations']['sha256']=module.digest((root/'annotations.json').read_bytes())
    review=json.loads((root/'review.json').read_text());review['annotations_sha256']=report['annotations']['sha256']
    (root/'review.json').write_text(json.dumps(review));report['human_review']['sha256']=module.digest((root/'review.json').read_bytes())
    (root/'report.json').write_text(json.dumps(report))
    from app.profiles.yolo import manifest
    monkeypatch.setattr(module,'Detectors',lambda:type('Detector',(),{'manifest':manifest()})())
    with pytest.raises(KeyError,match='component_reference'):
        module.run(root/'report.json',root/'profile.json',root/'budget.json')


def test_resume_complete_report_never_repeats_paid_calls(monkeypatch,tmp_path):
    module=runner(monkeypatch,tmp_path)
    root=tmp_path/'output';root.mkdir()
    profile,report=qualified(root)
    (root/'profile.json').write_text(json.dumps(profile));(root/'report.json').write_text(json.dumps(report))
    def forbidden(*args):
        pytest.fail('Already qualified execution replayed')
    monkeypatch.setattr(module,'DeepSeek',forbidden)
    with pytest.raises(ValueError,match='prior_runs'):
        module.run(root/'report.json',root/'profile.json',root/'budget.json')
    assert module.run(root/'report.json',root/'profile.json',root/'budget.json',resume=True)==0
