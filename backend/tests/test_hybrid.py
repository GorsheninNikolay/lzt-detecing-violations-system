import copy
from datetime import datetime, timezone
import json

import pytest

from app.profiles import deepseek, hybrid
from app.profiles.yolo import manifest
from app.application.deepseek_runtime import class_state, observation_context
from app.domain.site_analysis import compare_equipment
from test_deepseek import annotation, assessment, response, photo


def frame_value():
    value = annotation()
    value['objects'] = [{**value['objects'][0], 'type_ru': 'экскаватор', 'type_en': 'excavator',
        'catalog_class': 'excavator', 'box': [.1, .2, .5, .8], 'missing_localization_reason': None,
        'detection_ids': ['f/apoce/0'], 'disagreements': [], 'visual_action': 'digging',
        'action_evidence': 'Грунт падает из ковша', 'idle_indicator': 'none'}]
    value['detection_dispositions'] = [{'detection_id': 'f/apoce/0', 'status': 'accepted', 'reason': 'Совпадает объект'}]
    value.update(frame_usability={'usable': True, 'reason': 'Участок виден'},
                 class_assessability={name: 'assessable' for name in deepseek.EQUIPMENT})
    return value


def context_frame(key='f', sha='a', time='2026-01-02T12:00:00Z'):
    frame = observation_context({'input_id': key, 'ordinal': 0, 'sha256': sha, 'artifact_id': 'artifact'}, {'value': frame_value()})
    frame['captured_at'] = time
    return frame


def context():
    return {'frames': [context_frame()], 'zone_id': 'zone', 'plan': None, 'comparison_method': 'individual_frames_only', 'rule_results': []}


def hybrid_assessment(ctx):
    frame = ctx['frames'][0]
    return {**assessment(), 'activity': [{'state': 'working_signs', 'reason': 'Видно копание', 'uncertainty': 'Один снимок',
                'frame_ids': [frame['input_id']], 'observation_ids': [frame['observations'][0]['id']],
                'grounds': 'visible_work_action', 'comparison': None}], 'stage_hypotheses': []}


def test_manifest_keeps_original_ambiguous_classes_unmapped():
    data = manifest()
    assert {m['id'] for m in data['models']} == {'apoce', 'kaggle'}
    assert data['settings']['device'] == 'cpu'
    apoce = data['models'][0]
    assert apoce['mapping']['lifting-equipment'] is None
    assert apoce['mapping']['tower-crane'] is None
    assert len(apoce['sha256']) == 64
    assert hybrid.snapshot('folder') != deepseek.snapshot('folder')


def test_reconciliation_retains_provenance_and_rejects_duplicate_detection_use():
    value = frame_value()
    detectors = {'detectors': {'models': [{'detections': [{'id': 'f/apoce/0'}]}]}}
    assert hybrid.validate_frame(value, detectors) == value
    value['objects'].append({**value['objects'][0], 'box': [.6, .2, .9, .8]})
    with pytest.raises(ValueError, match='detection_reference'):
        hybrid.validate_frame(value, detectors)


def test_unusable_and_uncertain_frames_never_become_missing_equipment_evidence():
    value = frame_value()
    value['objects'][0]['status'] = 'uncertain'
    assert class_state(value, 'excavator') == 'insufficient_data'
    value['objects'] = []
    value['frame_usability']['usable'] = False
    assert class_state(value, 'excavator') == 'insufficient_data'
    value['frame_usability']['usable'] = True
    value['class_assessability']['excavator'] = 'uncertain'
    assert class_state(value, 'excavator') == 'insufficient_data'


def test_activity_requires_action_and_usable_evidence():
    ctx = context()
    value = hybrid_assessment(ctx)
    assert hybrid.validate_assessment(value, ctx)
    ctx['frames'][0]['observations'][0]['visual_action'] = 'no_visible_action'
    with pytest.raises(ValueError, match='work_action'):
        hybrid.validate_assessment(value, ctx)
    ctx['frames'][0]['frame_usability']['usable'] = False
    with pytest.raises(ValueError, match='usable_evidence'):
        hybrid.validate_assessment(value, ctx)


def test_possible_idle_requires_independence_and_visible_object_correspondence():
    ctx = context()
    ctx['frames'].append(context_frame('g', 'b', '2026-01-02T12:10:00Z'))
    ctx['comparison_method'] = 'same_zone_independent_timed_frames'
    refs = [f['observations'][0]['id'] for f in ctx['frames']]
    for f in ctx['frames']:
        f['observations'][0].update(visual_action='no_visible_action', idle_indicator='stowed_work_attachment')
    value = hybrid_assessment(ctx)
    value['activity'] = [{'state': 'possible_idle', 'reason': 'Возможный простой; нужна проверка', 'uncertainty': 'Нельзя установить длительность',
        'frame_ids': ['f', 'g'], 'observation_ids': refs, 'grounds': 'comparable_series_without_work_signs',
        'comparison': {'same_view': True, 'view_reason': 'Совпадает неподвижный фон', 'object_observation_ids': refs,
                       'identity_reason': 'Та же машина у ограждения', 'non_work_evidence': 'Рабочее оборудование сложено'}}]
    assert hybrid.validate_assessment(value, ctx)
    ctx['frames'][1]['sha256'] = 'a'
    with pytest.raises(ValueError, match='independent_frames'):
        hybrid.validate_assessment(value, ctx)
    ctx['frames'][1]['sha256'] = 'b'
    ctx['frames'][1]['observations'][0]['idle_indicator'] = 'none'
    with pytest.raises(ValueError, match='idle_correspondence'):
        hybrid.validate_assessment(value, ctx)


def test_risks_require_zone_references_and_applicable_work():
    ctx = context()
    value = hybrid_assessment(ctx)
    value['risks'] = [{'category': 'process', 'cause': 'visible_process_risk', 'text': 'Проверить организацию работ',
        'frame_ids': ['f'], 'observation_ids': [ctx['frames'][0]['observations'][0]['id']], 'work_entry_id': None,
        'impact': 'Возможное затруднение проезда', 'recommended_check': 'Осмотреть площадку', 'limitations': ['По фотографии']}]
    assert hybrid.validate_assessment(value, ctx)
    ctx['zone_id'] = None
    with pytest.raises(ValueError, match='usable_zone'):
        hybrid.validate_assessment(value, ctx)
    ctx['zone_id'] = 'zone'
    value['risks'][0]['work_entry_id'] = 'foreign'
    with pytest.raises(ValueError, match='work_reference'):
        hybrid.validate_assessment(value, ctx)


def test_both_call_types_receive_photos_and_frame_context(monkeypatch):
    requests = []
    ctx = context()
    frame_context = {'input_id': 'f', 'detectors': {'models': [{'detections': [{'id': 'f/apoce/0'}]}]}}
    def provider(request, timeout):
        body = json.loads(request.data)
        requests.append(body)
        return response(frame_value() if body['text']['format']['name'] == 'frame' else hybrid_assessment(ctx))
    monkeypatch.setattr(deepseek, '_read_json', provider)
    observer = deepseek.DeepSeek(hybrid.snapshot('mock-folder'), 'mock-only')
    assert observer.call('frame', frame_context, photo())['valid']
    assert observer.call('assessment', ctx, images=[('f', photo())])['valid']
    assert all(any(c['type'] == 'input_image' for c in r['input'][0]['content']) for r in requests)
    assert 'f/apoce/0' in requests[0]['input'][0]['content'][0]['text']


def test_invalid_hybrid_keeps_raw_rejection(monkeypatch):
    raw = response({'wrong': 'shape'})
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: raw)
    result = deepseek.DeepSeek(hybrid.snapshot('mock-folder'), 'mock-only').call('frame', {}, photo())
    assert result['raw'] == raw and not result['valid'] and result['value'] is None
    assert result['rejection'] == 'hybrid_schema_invalid'


def test_boundary_crossing_compares_each_entry_and_duplicate_hashes_do_not_count():
    frames = [{'input_id': str(i), 'sha256': str(i), 'captured_at': f'2026-01-0{day}T12:00:00Z'}
              for i, day in enumerate([1, 2, 3, 4, 5, 6])]
    entries = [{'id': key, 'state': 'active', 'starts_at': datetime(2026, 1, start, tzinfo=timezone.utc),
                'ends_at': datetime(2026, 1, end, 23, tzinfo=timezone.utc), 'expected_equipment': ['excavator'],
                'allowed_equipment': [], 'excluded_equipment': []} for key, start, end in [('a', 1, 3), ('b', 4, 6)]]
    obs = [{'input_id': f['input_id'], 'class_name': 'excavator', 'state': 'not_detected_in_frame'} for f in frames]
    def compare():
        return compare_equipment(entries, [f['captured_at'] for f in frames], obs, [f['input_id'] for f in frames], {'excavator'}, frames=frames)
    assert [s['supporting_input_ids'] for s in compare()] == [['0', '1', '2'], ['3', '4', '5']]
    for f in frames: f['sha256'] = 'same'
    assert [s['kind'] for s in compare()] == ['insufficient_observations', 'insufficient_observations']


@pytest.mark.parametrize('risk_kind', ['visible_process_risk', 'stage_plan_mismatch'])
def test_hybrid_persists_planless_signals_once_and_does_not_reopen_closed(monkeypatch, isolated_admission_database, risk_kind):
    import asyncio
    import base64
    import os
    import uuid
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from app.adapters.postgres import PostgresStore
    from app.adapters.artifacts import ArtifactStore
    from app.config import Config
    from app.application import deepseek_runtime as runtime
    from app.application.executor import ClaimLoop
    from app.application.submission import submit_series
    from app.application.site import router as site_router
    from app.application.signals import router as signal_router
    from app.profiles import yolo
    from test_deepseek import body
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY', 'mock-only')
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(Config.from_env())
    profile_id = runtime.provision(store, 'mock-folder', hybrid=True)
    profile, revision = store.require_authorized(profile_id)
    detected_frames = []
    class Detector:
        def detect(self, payload, input_id):
            assert store.read_ordinary(run)['stages'][1]['state'] == 'running'
            detected_frames.append(input_id)
            return {'manifest': manifest(), 'models': [{'model_id': 'apoce', 'detections': [{'id': f'{input_id}/apoce/0'}]},
                                                       {'model_id': 'kaggle', 'detections': []}]}
    monkeypatch.setattr(yolo, 'detectors', lambda: Detector())
    app = FastAPI(); app.state.store = store
    app.state.readiness = type('Ready', (), {'ready': type('Event', (), {'is_set': lambda _: True})()})()
    app.include_router(site_router); app.include_router(signal_router)
    client = TestClient(app)
    project = client.post('/projects', json={'name': 'Hybrid signals', 'timezone': 'UTC'}).json()
    zone = project['default_zone_id']
    request = {**body(), 'project_id': project['id'], 'zone_id': zone, 'capture_times': ['2035-01-02T12:00:00Z']}
    plan_revision = work_entry = None
    if risk_kind == 'stage_plan_mismatch':
        catalog_work = client.get('/catalog/works').json()['works'][0]['id']
        saved = client.put(f'/zones/{zone}/plan', json={'expected_revision': 0, 'entries': [{
            'catalog_work_id': catalog_work, 'start_at': '2035-01-01T00:00:00Z', 'end_at': '2035-01-03T00:00:00Z',
            'state': 'active', 'stage_key': 'roadwork', 'expected_equipment': ['road_roller'],
            'allowed_equipment': [], 'excluded_equipment': []}]})
        assert saved.status_code == 200, saved.text
        plan = client.get(f'/zones/{zone}/plan').json()
        plan_revision, work_entry = plan['revision_id'], plan['entries'][0]['id']
        request['plan_revision_id'] = plan_revision
    request['images_base64'] = [request.pop('image_base64')] * 2
    request['capture_times'] *= 2
    actual_call = deepseek.DeepSeek.call
    def call(self, kind, ctx, image=None, timeout=120, images=None):
        if kind == 'frame':
            assert len(detected_frames) == (attempt + 1) * 2
            assert ctx['instruction_version'] == profile['instruction_version']
            assert ctx['schema_version'] == profile['schema_version']
            assert store.read_ordinary(run)['stages'][1]['state'] == 'succeeded'
            value = frame_value()
            identity = ctx['detectors']['models'][0]['detections'][0]['id']
            value['objects'][0]['detection_ids'] = [identity]
            value['detection_dispositions'][0]['detection_id'] = identity
            if risk_kind == 'stage_plan_mismatch':
                value['stage'] = 'excavation'
                value['stage_reason'] = 'Виден котлован'
                value['scenes']['excavation_or_trench'] = 'present'
            if attempt:
                value['objects'][0]['box'] = [.11, .21, .51, .81]
        else:
            assert images and len(images) == 2
            value = hybrid_assessment(ctx)
            value['risks'] = [{'category': 'process', 'cause': 'visible_process_risk', 'text': 'Проверить путь проезда',
                'frame_ids': [ctx['frames'][0]['input_id']], 'observation_ids': [ctx['frames'][0]['observations'][0]['id']],
                'work_entry_id': None, 'impact': 'Может мешать проезду', 'recommended_check': 'Осмотреть участок', 'limitations': ['Один снимок']}]
            if risk_kind == 'stage_plan_mismatch':
                frame = ctx['frames'][0]
                risk = value['risks'][0]
                risk.update(category='plan', cause=risk_kind, work_entry_id=work_entry, text='Видимый этап расходится с планом')
                value['stage_hypothesis'] = {'stage': 'excavation', 'reason': 'Виден котлован'}
                value['stage_hypotheses'] = [{'stage': 'excavation', 'reason': 'Виден котлован',
                    'frame_ids': [frame['input_id']], 'observation_ids': list(risk['observation_ids']), 'work_entry_id': None}]
                if attempt:
                    risk['observation_ids'].append(next(o['id'] for o in frame['observations'] if o.get('name') == 'excavation_or_trench'))
        with monkeypatch.context() as patch:
            patch.setattr(deepseek, '_read_json', lambda *args: response(value))
            return actual_call(self, kind, ctx, image, timeout, images)
    monkeypatch.setattr(deepseek.DeepSeek, 'call', call)
    runner = ClaimLoop(); runner.store = store; runner.artifacts = artifacts
    runner.bind_runtime(store, profile_id)
    ids = []
    original_basis = None
    for attempt in range(2):
        _, run = submit_series(store, artifacts, str(uuid.uuid4()), request, profile_id, revision, profile)
        work = store.claim_ordinary(profile_id, revision, 60)
        asyncio.run(runner._execute(work, revision))
        result = store.read_ordinary(run)
        assert result['state'] == 'succeeded', result['error_code']
        assert result['stages'][1]['name'] == 'yolo_detection'
        frozen_frame = result['result_projection']['hybrid_frames'][0]
        assert frozen_frame['detectors']['models'][1]['model_id'] == 'kaggle'
        assert frozen_frame['detection_dispositions'][0]['detection_id'] == frozen_frame['input_id'] + '/apoce/0'
        signals = [signal for signal in result['result_projection']['created_signals'] if signal['kind'] == risk_kind]
        assert len(signals) == 1
        ids.append(signals[0]['id'])
        stored_signals = client.get('/signals', params={'project_id': project['id']}).json()['signals']
        stored = [signal for signal in stored_signals if signal['kind'] == risk_kind]
        assert len(stored) == 1
        if attempt == 0:
            original_basis = copy.deepcopy(stored[0]['basis'])
            assert client.patch('/signals/' + ids[0], json={'state': 'closed', 'comment': 'Checked'}).status_code == 200
        else:
            assert signals[0]['state'] == stored[0]['state'] == 'closed'
            assert stored[0]['basis'] == original_basis
            assert frozen_frame['observations'][0]['box'] != original_basis['frames'][0]['observations'][0]['box']
            if risk_kind == 'stage_plan_mismatch':
                assert len(result['ai_assessment']['risks'][0]['observation_ids']) == 2
                assert len(original_basis['risk']['observation_ids']) == 1
    assert ids[0] == ids[1]
    response_body = client.get('/signals', params={'project_id': project['id']}).json()
    matching = [signal for signal in response_body['signals'] if signal['kind'] == risk_kind]
    assert len(matching) == 1
    assert matching[0]['revision_id'] == plan_revision
    assert matching[0]['work_entry_id'] == work_entry
    assert matching[0]['basis'] == original_basis
    assert matching[0]['basis']['frames'][0]['observations'][0]['visual_action'] == 'digging'
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM site_signals WHERE zone_id=:zone AND kind=:kind'),
                          {'zone': zone, 'kind': risk_kind}).scalar_one() == 1
    store.close()


from test_admission import isolated_admission_database
from test_startup import database, integration


def test_every_raw_detection_needs_explicit_disposition():
    value = frame_value()
    detectors = {'detectors': {'models': [{'detections': [{'id': 'f/apoce/0'}, {'id': 'f/kaggle/0'}]}]}}
    with pytest.raises(ValueError, match='disposition_incomplete'):
        hybrid.validate_frame(value, detectors)
    value['detection_dispositions'].append({'detection_id': 'f/kaggle/0', 'status': 'dismissed', 'reason': 'Фон, не машина'})
    assert hybrid.validate_frame(value, detectors)


def test_plan_risk_cannot_use_process_category_or_outside_interval():
    ctx = context()
    ctx['plan'] = {'entries': [{'id': 'work', 'state': 'active', 'stage_key': 'excavation',
                               'starts_at': '2026-01-01T00:00:00Z', 'ends_at': '2026-01-03T00:00:00Z'}]}
    value = hybrid_assessment(ctx)
    value['risks'] = [{'category': 'process', 'cause': 'expected_equipment_missing', 'text': 'Проверить технику',
        'frame_ids': ['f'], 'observation_ids': [ctx['frames'][0]['observations'][0]['id']], 'work_entry_id': 'work',
        'impact': 'Возможное затруднение', 'recommended_check': 'Осмотреть участок', 'limitations': ['Фотография']}]
    with pytest.raises(ValueError, match='category_conflict'):
        hybrid.validate_assessment(value, ctx)
    value['risks'][0].update(category='plan', cause='stage_plan_mismatch')
    ctx['plan']['entries'][0]['ends_at'] = '2026-01-01T23:59:59Z'
    with pytest.raises(ValueError, match='work_reference'):
        hybrid.validate_assessment(value, ctx)


def test_current_quality_report_is_blocked_when_absent_stale_or_incomplete(tmp_path):
    from app.application.hybrid_readiness import read_report
    from app.shared.cloud import canonical_bytes, digest
    profile = hybrid.snapshot('folder')
    path = tmp_path / 'readiness.json'
    assert read_report(profile, path)['code'] == 'missing_current_report'
    path.write_text(json.dumps({'status': 'pass', 'profile_sha256': 'wrong'}))
    assert read_report(profile, path)['code'] == 'current_report_stale'
    report = {'status': 'pass', 'profile_sha256': digest(canonical_bytes(profile)),
              'detector_manifest_sha256': profile['detector_manifest_sha256']}
    path.write_text(json.dumps(report))
    assert read_report(profile, path)['status'] == 'blocked'
    report.update(criteria={'independently_reviewed': True, 'required_cases_complete': True, 'zero_false_warnings': True})
    path.write_text(json.dumps(report))
    assert read_report(profile, path)['status'] == 'blocked'
    assert read_report(profile, path)['code'] == 'reviewed_evidence_incomplete'


def test_unresolved_detector_evidence_cannot_turn_into_absence():
    value = frame_value()
    value['objects'] = []
    value['detection_dispositions'] = [{'detection_id': 'raw', 'status': 'unresolved', 'reason': 'Неясный тип'}]
    detectors = {'models': [{'detections': [{'id': 'raw', 'catalog_class': 'excavator'}]}]}
    assert class_state(value, 'excavator', detectors) == 'insufficient_data'
    assert class_state(value, 'dump_truck', detectors) == 'not_detected_in_frame'
    detectors['models'][0]['detections'][0]['catalog_class'] = None
    assert class_state(value, 'dump_truck', detectors) == 'insufficient_data'


def test_working_action_must_support_every_cited_frame_and_unusable_stage_is_unknown():
    ctx = context()
    ctx['frames'].append(context_frame('g', 'b', '2026-01-02T12:10:00Z'))
    value = hybrid_assessment(ctx)
    value['activity'][0]['frame_ids'].append('g')
    value['activity'][0]['observation_ids'].append(ctx['frames'][1]['observations'][0]['id'])
    ctx['frames'][1]['observations'][0]['visual_action'] = 'unknown'
    with pytest.raises(ValueError, match='work_action_required'):
        hybrid.validate_assessment(value, ctx)
    value['activity'] = [{'state': 'insufficient_data', 'reason': 'Недостаточно данных', 'uncertainty': 'Не видно',
                         'frame_ids': ['g'], 'observation_ids': [], 'grounds': 'insufficient_evidence', 'comparison': None}]
    ctx['frames'][1]['frame_usability']['usable'] = False
    value['stage_hypotheses'] = [{'frame_ids':['g'], 'observation_ids':[ctx['frames'][1]['observations'][0]['id']],
                                 'stage':'excavation','reason':'Котлован','work_entry_id':None}]
    with pytest.raises(ValueError, match='unusable_stage'):
        hybrid.validate_assessment(value, ctx)
    frame = frame_value(); frame['stage'] = 'excavation'; frame['frame_usability']['usable'] = False
    with pytest.raises(ValueError, match='unusable_stage'):
        hybrid.validate_frame(frame, {'detectors': {'models': []}})
    assert hybrid.distinct_instants([{'captured_at':'2026-01-02T12:00:00Z'}, {'captured_at':'2026-01-02T15:00:00+03:00'}]) == 1


def test_real_safe_assessment_advice_is_not_a_duration_assertion():
    from pathlib import Path
    case = json.loads((Path(__file__).parent / 'fixtures/hybrid-real-safe-assessment.json').read_text())
    assert hybrid.validate_assessment(case['value'], case['context'])


@pytest.mark.parametrize('field', ['summary', 'uncertainty', 'impact', 'action', 'hypothesis', 'recommendation', 'limitation'])
@pytest.mark.parametrize('claim', ['Простой длится 45 минут', 'Длительность работы 500 минут'])
def test_asserted_duration_is_rejected_in_every_published_explanation(field, claim):
    ctx = context(); ctx['comparison_method'] = 'same_zone_independent_timed_frames'
    value = hybrid_assessment(ctx)
    if field == 'summary': value['summary'] = claim
    elif field == 'uncertainty': value['activity'][0]['uncertainty'] = claim
    elif field == 'hypothesis': value['stage_hypothesis']['reason'] = claim
    elif field == 'recommendation': value['recommendations'] = [claim]
    elif field == 'limitation': value['limitations'] = [claim]
    elif field == 'action':
        frame = frame_value(); frame['objects'][0]['action_evidence'] = claim
        with pytest.raises(ValueError, match='duration_unverified'):
            hybrid.validate_frame(frame, {'detectors':{'models':[{'detections':[{'id':'f/apoce/0'}]}]}})
        return
    else:
        value['risks'] = [{'category':'process','cause':'visible_process_risk','text':'Проверить проезд',
            'frame_ids':['f'],'observation_ids':[ctx['frames'][0]['observations'][0]['id']], 'work_entry_id':None,
            'impact':claim,'recommended_check':'Осмотреть','limitations':['Фотография']}]
    with pytest.raises(ValueError, match='duration_unverified'):
        hybrid.validate_assessment(value, ctx)


@pytest.mark.parametrize('problem', ['corrupt', 'classes', 'dependency'])
def test_detector_real_integrity_guards_precede_inference(tmp_path, monkeypatch, problem):
    import sys
    from types import SimpleNamespace
    from app.profiles import yolo
    from app.shared.cloud import digest
    payload = b'controlled-checkpoint'
    (tmp_path / 'test.pt').write_bytes(payload if problem != 'corrupt' else b'corrupt')
    config = {'dependencies': {'torch':'test-pin'}, 'models':[{'id':'test','filename':'test.pt',
              'sha256':digest(payload),'classes':['excavator'],'mapping':{'excavator':'excavator'}}]}
    monkeypatch.setenv('YOLO_MODELS_DIR', str(tmp_path))
    monkeypatch.setattr(yolo, 'manifest', lambda: config)
    monkeypatch.setattr(yolo, 'version', lambda _: 'wrong-pin' if problem == 'dependency' else 'test-pin')
    loads = []
    def loader(path, task):
        loads.append(path)
        return SimpleNamespace(names={0:'wrong-class'}, to=lambda device: None)
    monkeypatch.setitem(sys.modules, 'ultralytics', SimpleNamespace(YOLO=loader))
    with pytest.raises(ValueError, match={'corrupt':'weights_invalid','classes':'classes_mismatch','dependency':'dependency_mismatch'}[problem]):
        yolo.Detectors()
    assert bool(loads) == (problem == 'classes')


def test_rejected_detector_startup_never_becomes_ready(monkeypatch):
    import asyncio
    import uuid
    from types import SimpleNamespace
    from unittest.mock import Mock
    from app import main
    from app.profiles import yolo
    profile = hybrid.snapshot('mock-folder')
    store = Mock(); store.require_authorized.return_value = (profile, 1)
    monkeypatch.setattr(main, 'PostgresStore', lambda _: store)
    monkeypatch.setattr(main, 'ArtifactStore', lambda _: Mock())
    monkeypatch.setattr(main.Config, 'from_env', lambda: SimpleNamespace(database_url='unused', cloud_api_key='mock-only'))
    monkeypatch.setenv('OBSERVER_PROFILE_ID', str(uuid.uuid4()))
    def rejected(): raise ValueError('detector_weights_invalid')
    monkeypatch.setattr(yolo, 'detectors', rejected)
    async def check():
        app = main.create_app()
        async with app.router.lifespan_context(app):
            await app.state.startup_task
            assert not app.state.readiness.ready.is_set()
            assert app.state.readiness.code == 'observer_snapshot_invalid'
            assert app.state.claim_loop.task is None
    asyncio.run(check())


def test_actual_plan_disclaimers_do_not_assert_delay():
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent / 'fixtures/hybrid-real-plan-disclaimer.json').read_text())
    assert hybrid.validate_assessment(fixture['assessment'], fixture['context'])
    assert not hybrid.asserts('Выводы об отставаниях невозможны.', r'отстав')
    assert not hybrid.asserts('Выводы о графике и отставаниях не делаются.', r'отстав')


def test_single_frame_request_cannot_offer_idle_risk_without_temporal_evidence():
    ctx = context()
    schema = hybrid.assessment_schema(ctx)
    assert 'possible_idle' not in schema['properties']['activity']['items']['properties']['state']['enum']
    assert 'possible_idle' not in schema['properties']['risks']['items']['properties']['cause']['enum']
    assert 'possible_idle' in hybrid.ASSESSMENT_SCHEMA['properties']['risks']['items']['properties']['cause']['enum']
    ctx['frames'].append(context_frame('g', 'b', '2026-01-02T12:01:00Z'))
    ctx['comparison_method'] = 'same_zone_independent_timed_frames'
    assert 'possible_idle' in hybrid.assessment_schema(ctx)['properties']['activity']['items']['properties']['state']['enum']


def test_unusable_or_unassigned_request_offers_no_signal_risks():
    ctx = context()
    ctx['frames'][0]['frame_usability']['usable'] = False
    assert hybrid.assessment_schema(ctx)['properties']['risks']['maxItems'] == 0
    ctx = context()
    ctx['zone_id'] = None
    assert hybrid.assessment_schema(ctx)['properties']['risks']['maxItems'] == 0


def test_request_only_offers_plan_risks_supported_by_frozen_rules():
    ctx = context()
    schema = hybrid.assessment_schema(ctx)
    causes = schema['properties']['risks']['items']['properties']['cause']['enum']
    assert 'expected_equipment_missing' not in causes and 'equipment_not_planned' not in causes
    assert 'stage_plan_mismatch' not in causes
    assert schema['properties']['risks']['items']['properties']['work_entry_id']['enum'] == [None]
    ctx['plan'] = {'entries': [{'id': 'bound-work'}]}
    ctx['rule_results'] = [{'kind': 'expected_equipment_missing'}]
    schema = hybrid.assessment_schema(ctx)
    causes = schema['properties']['risks']['items']['properties']['cause']['enum']
    assert 'expected_equipment_missing' in causes and 'stage_plan_mismatch' in causes
    assert 'equipment_not_planned' not in causes
    assert schema['properties']['risks']['items']['properties']['work_entry_id']['enum'] == ['bound-work', None]


def test_unknown_stage_can_identify_the_applicable_work_without_confirming_it():
    ctx = context()
    ctx['plan'] = {'entries': [{'id': 'work', 'state': 'active', 'stage_key': 'roadwork',
                              'starts_at': '2026-01-02T11:00:00Z', 'ends_at': '2026-01-02T13:00:00Z'}]}
    value = hybrid_assessment(ctx)
    value['stage_hypotheses'] = [{'stage': 'unknown', 'reason': 'Стадия работы не подтверждена',
                                 'frame_ids': ['f'], 'observation_ids': [ctx['frames'][0]['observations'][0]['id']],
                                 'work_entry_id': 'work'}]
    assert hybrid.validate_assessment(value, ctx)
    value['stage_hypotheses'][0]['stage'] = 'concreting'
    with pytest.raises(ValueError, match='work_reference'):
        hybrid.validate_assessment(value, ctx)
