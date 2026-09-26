import asyncio
import base64
import copy
import io
import json
import os
import uuid
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.profiles import deepseek
from app.shared.cloud import strict_json
from app.application import deepseek_runtime as runtime
from app.application.submission import validate_request, SubmissionError, submit_series
from app.application.executor import ClaimLoop
from app.adapters.postgres import PostgresStore, AdmissionStoreError
from app.adapters.artifacts import ArtifactStore
from app.config import Config
from test_admission import isolated_admission_database
from test_startup import database, integration


def photo(format='PNG', orientation=1):
    output = io.BytesIO()
    exif = Image.Exif()
    exif[274] = orientation
    Image.new('RGB', (40, 20), 'white').save(output, format=format, exif=exif)
    return output.getvalue()


def annotation():
    return {'objects': [{'type_ru': 'буровая установка', 'type_en': 'drilling rig',
            'catalog_class': None, 'status': 'identified', 'evidence': 'Видна вертикальная мачта',
            'box': None, 'missing_localization_reason': 'Перекрыта краем кадра'}],
            'scenes': {s: 'uncertain' for s in deepseek.SCENES}, 'stage': 'unknown', 'stage_reason': 'Недостаточно данных'}


def assessment():
    return {'summary': 'Наблюдение площадки', 'stage_hypothesis': {'stage': 'unknown', 'reason': 'Мало данных'},
            'risks': [], 'recommendations': ['Проверить на месте'], 'limitations': ['Только видимые признаки']}


def response(value):
    return {'id': 'mock-response', 'model': 'gpt://mock-folder/' + deepseek.MODEL,
            'status': 'completed', 'reasoning': {'effort': 'none'},
            'usage': {'input_tokens': 20, 'output_tokens': 10, 'total_tokens': 30},
            'output': [{'type': 'message', 'role': 'assistant', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


def body():
    return {'intent': 'observation_only', 'scenario': 'test', 'observation_area': 'north',
            'period': '2026-09-26T12:00:00+03:00', 'cloud_processing_consent': True,
            'image_base64': base64.b64encode(photo()).decode()}


def test_consent_and_orientation():
    request = body()
    del request['cloud_processing_consent']
    with pytest.raises(SubmissionError, match='cloud_consent_required'):
        validate_request(request)
    payload, mime, dimensions = deepseek.oriented_image(photo('JPEG', 6))
    assert mime == 'image/jpeg' and dimensions == [20, 40]
    assert Image.open(io.BytesIO(payload)).getexif().get(274, 1) == 1
    assert deepseek.oriented_image(photo())[1] == 'image/png'


def test_retired_admission_rejects_before_inputs_or_credentials(monkeypatch):
    from app.application import admission
    def forbidden(*args, **kwargs):
        pytest.fail('retired admission accessed inputs or credentials')
    monkeypatch.setattr(admission, 'validate_manifest', forbidden)
    monkeypatch.setattr(admission.Config, 'from_env', forbidden)
    with pytest.raises(ValueError, match='^profile_retired$'):
        admission.admit(None, None, None, None, 60)
    with pytest.raises(ValueError, match='^profile_retired$'):
        admission.admit_cloud(None, None, None, 60)


@pytest.mark.parametrize('change', [
    lambda r: r.update(model='wrong'), lambda r: r.update(status='incomplete'),
    lambda r: r.update(reasoning={'effort': 'high'}), lambda r: r['usage'].update(input_tokens=True),
    lambda r: r['usage'].update(total_tokens=1), lambda r: r.update(incomplete_details={}),
    lambda r: r['output'][0]['content'][0].update(text='{"objects":[]'),
    lambda r: r['output'][0]['content'][0].update(text='{"a":1,"a":2}'),
    lambda r: r['output'][0]['content'][0].update(text='{"a":NaN}'),
])
def test_reject_invalid_response(change):
    raw = response(annotation())
    change(raw)
    with pytest.raises(ValueError):
        deepseek.validate_response(raw, 'gpt://mock-folder/' + deepseek.MODEL, 'none')


def test_objects_and_risk_references():
    value = deepseek.validate_annotation(annotation())
    assert value['objects'][0]['catalog_class'] is None and 'score' not in value['objects'][0]
    value['objects'][0]['box'] = [0, 0, 2, 1]
    with pytest.raises(ValueError):
        deepseek.validate_annotation(value)
    context = {'frames': [{'input_id': 'f', 'observations': [{'id': 'o', 'visible': True}]}], 'plan': None}
    value = assessment()
    value['risks'] = [{'category': 'safety', 'text': 'Требует осмотра', 'frame_ids': ['f'], 'observation_ids': ['wrong']}]
    with pytest.raises(ValueError, match='reference'):
        deepseek.validate_assessment(value, context)
    value['risks'][0]['observation_ids'] = ['o']
    assert deepseek.validate_assessment(value, context)
    value['risks'][0]['category'] = 'plan'
    with pytest.raises(ValueError, match='plan_missing'):
        deepseek.validate_assessment(value, context)


@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='isolated PostgreSQL and private S3 required')
def test_deepseek_persisted_run_and_uncertain_no_replay(monkeypatch, isolated_admission_database):
    from alembic.config import Config as AlembicConfig
    from alembic import command
    monkeypatch.setenv('DATABASE_URL', isolated_admission_database)
    monkeypatch.setenv('S3_BUCKET', os.environ['TEST_S3_BUCKET'])
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY', 'mock-only-never-sent')
    config = AlembicConfig(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
    command.upgrade(config, 'head')
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(Config.from_env())
    profile_id = runtime.provision(store, 'mock-folder')
    profile, revision = store.require_authorized(profile_id)
    calls = []
    def mocked(http_request, seconds):
        request = strict_json(http_request.data)
        calls.append(request)
        progress = store.read_ordinary(run_id)['stages']
        running_stage = 2 if request['text']['format']['name'] == 'frame' else 3
        assert progress[running_stage]['state'] == 'running'
        assert request['store'] is False and request['reasoning'] == {'effort': 'none'}
        assert request['max_output_tokens'] == 8192 and request['temperature'] == 0
        assert http_request.get_header('X-data-logging-enabled') == 'false'
        return response(annotation() if request['text']['format']['name'] == 'frame' else assessment())
    monkeypatch.setattr(deepseek, '_read_json', mocked)
    request = body()
    request['images_base64'] = [request.pop('image_base64')] * 2
    _, run_id = submit_series(store, artifacts, str(uuid.uuid4()), request, profile_id, revision, profile)
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, artifacts
    work = store.claim_ordinary(profile_id, revision, 30)
    assert work['id'] == run_id
    asyncio.run(runner._execute(work, revision))
    result = store.read_ordinary(run_id)
    assert result['state'] == 'succeeded', result['error_code']
    assert len(calls) == 3 and len(result['ai_evidence']) == 3
    assert result['ai_assessment']['summary'] == 'Наблюдение площадки'
    assert result['objects'][0]['class_name'] == 'unknown' and result['objects'][0]['score'] is None
    assert result['objects'][0]['box'] is None
    frozen = result['ai_evidence'][-1]['context']
    assert frozen['history'] == [] and frozen['plan'] is None
    with pytest.raises(DatabaseError), store.engine.begin() as db:
        db.execute(text('UPDATE deepseek_results SET result=\'{}\' WHERE call_id=:id'), {'id': result['ai_evidence'][0]['id']})
    _, failed = submit_series(store, artifacts, str(uuid.uuid4()), request, profile_id, revision, profile)
    work = store.claim_ordinary(profile_id, revision, 30)
    def uncertain(*args):
        raise TimeoutError()
    monkeypatch.setattr(deepseek, '_read_json', uncertain)
    asyncio.run(runner._execute(work, revision))
    result = store.read_ordinary(failed)
    assert result['state'] == 'failed' and result['result_projection'] is None
    assert result['ai_evidence'][0]['state'] == 'uncertain'
    with pytest.raises(AdmissionStoreError, match='provider_call_not_replayable'):
        store.retry_ordinary(failed, profile_id, revision, profile, artifacts)
    assert store.claim_ordinary(profile_id, revision, 30) is None
    store.close()


@pytest.fixture
def deepseek_service(isolated_admission_database, monkeypatch):
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY', 'mock-only-never-sent')
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(Config.from_env())
    profile_id = runtime.provision(store, 'mock-folder')
    profile, revision = store.require_authorized(profile_id)
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, artifacts
    monkeypatch.setattr(deepseek, '_read_json', lambda request, _: response(
        annotation() if strict_json(request.data)['text']['format']['name'] == 'frame' else assessment()))
    yield store, artifacts, profile_id, profile, revision, runner
    store.close()


def queue_work(service, context=None):
    from app.application.submission import submit
    store, artifacts, profile_id, profile, revision, runner = service
    request = body() | (context or {})
    _, run_id = submit(store, artifacts, str(uuid.uuid4()), request, profile_id, revision, profile)
    work = store.claim_ordinary(profile_id, revision, 30)
    assert work['id'] == run_id
    return work


def test_runtime_consent_lease_and_retirement_fences(deepseek_service):
    store, artifacts, profile_id, profile, revision, runner = deepseek_service
    work = queue_work(deepseek_service)
    frame = work['frames'][0]
    with store.engine.begin() as db:
        db.execute(text("UPDATE analysis_runs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=:id"), {'id':work['id']})
    with pytest.raises(ValueError, match='ordinary_lease_rejected'):
        runtime.reserve(store, work, 'frame', {}, frame)
    assert store.recover() == 1
    assert store.read_ordinary(work['id'])['state'] == 'failed'
    with pytest.raises(AdmissionStoreError, match='profile_retired'):
        store.reserve_ordinary(work['id'], work['owner'], revision, frame['sha256'])
    # An old run with absent consent cannot invoke the new adapter through an internal call.
    no_consent = uuid.uuid4()
    with store.engine.begin() as db:
        db.execute(text('''INSERT INTO analysis_runs(id,state,purpose,profile_id,authorization_revision,
            profile_snapshot,request_context,lease_owner,lease_expires_at)
            VALUES (:id,'running','ordinary',:profile,1,CAST(:snapshot AS jsonb),'{}','owner',clock_timestamp()+interval '30 seconds')'''),
            {'id':no_consent,'profile':profile_id,'snapshot':json.dumps(profile)})
    with pytest.raises(ValueError, match='cloud_consent_required'):
        runtime.reserve(store, {'id':no_consent,'owner':'owner'}, 'assessment', {})
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM deepseek_calls')).scalar_one() == 0


def test_renewal_failure_during_provider_prevents_later_calls(deepseek_service, monkeypatch):
    import threading
    store, _, _, _, revision, runner = deepseek_service
    work = queue_work(deepseek_service)
    entered, failed = threading.Event(), threading.Event()
    async def renewal(*_):
        await asyncio.to_thread(entered.wait, 2)
        failed.set()
        raise RuntimeError('renewal_failed')
    calls = []
    def provider(request, seconds):
        calls.append(request)
        entered.set()
        assert failed.wait(2)
        return response(annotation())
    monkeypatch.setattr(runner, '_renew', renewal)
    monkeypatch.setattr(deepseek, '_read_json', provider)
    asyncio.run(runner._execute(work, revision))
    result = store.read_ordinary(work['id'])
    assert result['state'] == 'failed' and len(calls) == 1
    assert len(result['ai_evidence']) == 1 and result['ai_evidence'][0]['result'] is None
    assert result['result_projection'] is None


def test_expired_lease_fences_completion_during_recovery(deepseek_service, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import event
    from app.adapters.postgres import RecoveryGateError

    store, _, _, _, revision, runner = deepseek_service
    work = queue_work(deepseek_service)
    pending = []
    with monkeypatch.context() as patch:
        patch.setattr(runtime, 'complete', lambda *args: pending.append(args))
        asyncio.run(runner._execute(work, revision))
    assert len(pending) == 1
    with store.engine.begin() as db:
        db.execute(text("UPDATE analysis_runs SET lease_expires_at=clock_timestamp()+interval '2 seconds' WHERE id=:id"),
                   {'id': work['id']})

    locked, release = threading.Event(), threading.Event()
    lock_error_states = []

    def hold_completion_after_lock(_conn, _cursor, statement, _params, _context, _many):
        if 'FOR UPDATE OF r,a' in statement:
            locked.set()
            assert release.wait(10), 'completion lock was not released'

    def capture_recovery_error(context):
        if context.statement and 'FOR UPDATE NOWAIT' in context.statement:
            lock_error_states.append(getattr(context.original_exception, 'sqlstate', None))

    event.listen(store.engine, 'after_cursor_execute', hold_completion_after_lock)
    event.listen(store.engine, 'handle_error', capture_recovery_error)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            completion = pool.submit(runtime.complete, *pending[0])
            try:
                assert locked.wait(5), 'completion did not acquire the run lock'
                with store.engine.connect() as db:
                    assert db.execute(text('SELECT lease_expires_at>clock_timestamp() FROM analysis_runs WHERE id=:id'),
                                      {'id': work['id']}).scalar_one()
                deadline = time.monotonic() + 5
                while True:
                    with store.engine.connect() as db:
                        expired = db.execute(text('SELECT lease_expires_at<=clock_timestamp() FROM analysis_runs WHERE id=:id'),
                                             {'id': work['id']}).scalar_one()
                    if expired:
                        break
                    assert time.monotonic() < deadline, 'lease did not expire'
                    time.sleep(0.02)
                with pytest.raises(RecoveryGateError, match='recovery_gate_failed'):
                    store.recover()
                assert lock_error_states == ['55P03']
            finally:
                release.set()
            with pytest.raises(ValueError, match='ordinary_lease_rejected'):
                completion.result(timeout=10)
    finally:
        release.set()
        event.remove(store.engine, 'after_cursor_execute', hold_completion_after_lock)
        event.remove(store.engine, 'handle_error', capture_recovery_error)

    with pytest.raises(AdmissionStoreError, match='ordinary_lease_rejected'):
        store.renew_ordinary(work['id'], work['owner'], revision, 30)
    assert store.recover() == 1
    result = store.read_ordinary(work['id'])
    assert result['state'] == 'failed' and result['error_code'] == 'executor_interrupted'
    assert result['result_projection'] is None and result['objects'] == []
    assert len(result['ai_evidence']) == 2
    assert all(call['result'] is not None for call in result['ai_evidence'])
    with store.engine.connect() as db:
        for table in ('result_projections', 'detected_objects', 'observations', 'observer_invocations'):
            assert db.execute(text(f'SELECT count(*) FROM {table} WHERE run_id=:id'),
                              {'id': work['id']}).scalar_one() == 0


def test_history_is_same_zone_strictly_earlier_and_limited(deepseek_service):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.application.site import router
    store, _, _, _, revision, runner = deepseek_service
    app = FastAPI()
    app.state.store = store
    app.state.readiness = type('Ready', (), {'ready':type('Event', (), {'is_set':lambda _: True})()})()
    app.include_router(router)
    client = TestClient(app)
    project = client.post('/projects', json={'name':'History test','timezone':'UTC'}).json()
    zone = project['default_zone_id']
    other = client.post(f"/projects/{project['id']}/zones", json={'name':'Other'}).json()['id']
    def context(day, zone_id=zone):
        return {'project_id':project['id'],'zone_id':zone_id,'capture_times':[f'2026-09-{day:02}T12:00:00+00:00']}
    prior = []
    for day, zone_id in [(1,zone),(2,zone),(3,zone),(4,zone),(5,other),(20,zone)]:
        work = queue_work(deepseek_service, context(day,zone_id))
        asyncio.run(runner._execute(work,revision))
        assert store.read_ordinary(work['id'])['state'] == 'succeeded'
        if day <= 4:
            prior.append(str(work['id']))
    work = queue_work(deepseek_service, context(10))
    asyncio.run(runner._execute(work,revision))
    result = store.read_ordinary(work['id'])
    frozen = next(call['context'] for call in result['ai_evidence'] if call['kind']=='assessment')
    assert [item['run_id'] for item in frozen['history']] == list(reversed(prior[1:]))
    work = queue_work(deepseek_service)
    asyncio.run(runner._execute(work,revision))
    frozen = next(call['context'] for call in store.read_ordinary(work['id'])['ai_evidence'] if call['kind']=='assessment')
    assert frozen['history'] == []


def test_documentation_direct_and_proxy_schema(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    monkeypatch.setenv('API_ROOT_PATH', '/api')
    client = TestClient(create_app())
    for prefix in ('', '/api'):
        assert client.get(prefix + '/docs').status_code == 200
        assert './openapi.json' in client.get(prefix + '/redoc').text
        schema = client.get(prefix + '/openapi.json').json()
        assert schema['servers'] == [{'url':'/api','description':'Настроенный root_path'}, {'url':'/','description':'Прямой backend'}]
        request = schema['paths']['/runs/single-image']['post']['requestBody']['content']['application/json']['schema']
        assert 'cloud_processing_consent' in request['required']
        assert schema['paths']['/admin/session']['get']['responses']['200']['content']['application/json']['schema']['required'] == ['csrf']
        assert schema['paths']['/runs/{run_id}']['get']['responses']['200']['content']['application/json']['schema']['properties']['ai_assessment']['anyOf'][0]['properties']['risks']


def test_prefixed_series_dispatch_and_admin_cache(monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setenv('API_ROOT_PATH', '/api')
    app = main.create_app()
    app.state.readiness.ready.set()
    run_id = uuid.uuid4()
    app.state.claim_loop = SimpleNamespace(runtime_binding=(uuid.uuid4(), 1))
    app.state.store = SimpleNamespace(require_authorized=lambda *args: (deepseek.snapshot('mock-folder'), 1),
                                     read_ordinary=lambda *args: {'state':'queued'})
    app.state.artifacts = None
    submitted = []
    def series(*args, **kwargs):
        submitted.append(args[3])
        return 'queued', run_id
    monkeypatch.setattr(main, 'submit_series', series)
    monkeypatch.setattr(main, 'submit', lambda *args, **kwargs: pytest.fail('series dispatched as single image'))
    client = TestClient(app)
    for prefix in ('', '/api'):
        response = client.post(prefix+'/runs/series', headers={'Idempotency-Key':'synthetic'},
                               json={'images_base64':['synthetic-a','synthetic-b']})
        assert response.status_code == 202
        assert response.json()['run_id'] == str(run_id)
        response = client.get(prefix+'/admin/session')
        assert response.status_code == 403
        assert response.headers['Cache-Control'] == 'no-store'
    assert len(submitted) == 2


@pytest.mark.parametrize('kind,expected_calls', [('frame',1),('assessment',2)])
def test_invalid_raw_is_immutable_failed_and_not_replayed(deepseek_service, monkeypatch, kind, expected_calls):
    store, artifacts, profile_id, profile, revision, runner = deepseek_service
    work = queue_work(deepseek_service)
    calls, invalid = [], response(annotation() if kind=='frame' else assessment())
    invalid.update(status='incomplete', model=17, usage='bad')
    def provider(request, _):
        actual = strict_json(request.data)['text']['format']['name']
        calls.append(actual)
        return invalid if actual==kind else response(annotation())
    monkeypatch.setattr(deepseek, '_read_json', provider)
    asyncio.run(runner._execute(work,revision))
    result = store.read_ordinary(work['id'])
    assert result['state']=='failed' and result['ai_assessment'] is None and result['result_projection'] is None
    assert len(calls)==expected_calls
    evidence = result['ai_evidence'][-1]
    assert evidence['state']=='invalid' and evidence['result']['raw']==invalid
    assert evidence['result']['value'] is None and evidence['result']['usage'] is None and evidence['result']['model'] is None
    with pytest.raises(AdmissionStoreError,match='provider_call_not_replayable'):
        store.retry_ordinary(work['id'],profile_id,revision,profile,artifacts)
    with pytest.raises(DatabaseError), store.engine.begin() as db:
        db.execute(text("UPDATE deepseek_results SET result='{}' WHERE call_id=:id"), {'id':evidence['id']})


@pytest.mark.parametrize('statement,accepted', [
    ('Без плана невозможно оценить отставание',True),
    ('Данных об отставании нет.',True),
    ('Площадка отстаёт на три дня.',False),
    ('Без плана невозможно оценить отставание, но задержка составляет три дня.',False),
])
def test_no_plan_affirmative_claim_and_insufficiency(statement,accepted):
    value=assessment();value['summary']=statement
    context={'frames':[],'plan':None}
    if accepted:
        assert deepseek.validate_assessment(value,context)['summary']==statement
    else:
        with pytest.raises(ValueError,match='delay_claim_without_plan'):
            deepseek.validate_assessment(value,context)


@pytest.mark.parametrize('visible,statement,accepted', [
    (False,'Проверить взаимное расположение людей и техники',False),
    (True,'Проверить взаимное расположение людей и техники',True),
    (True,'Расстояние составляет 2 метра',False),
    (True,'Нарушение норм безопасности',False),
    (True,'Нарушения норм не подтверждены, требуется осмотр',True),
    (True,'Расстояние невозможно подтвердить по фотографии',True),
])
def test_safety_claims_require_visible_evidence_and_no_verified_assertion(visible,statement,accepted):
    value=assessment();value['risks']=[{'category':'safety','text':statement,'frame_ids':['f'],'observation_ids':['o']}]
    context={'frames':[{'input_id':'f','observations':[{'id':'o','visible':visible}]}],'plan':None}
    if accepted:
        assert deepseek.validate_assessment(value,context)
    else:
        with pytest.raises(ValueError,match='assessment_(visible_evidence_required|safety_claim_unverified)'):
            deepseek.validate_assessment(value,context)


def test_declared_context_and_unsorted_times_are_preserved(deepseek_service):
    store,artifacts,profile_id,profile,revision,runner=deepseek_service
    from app.application.submission import submit_series
    project,zone=uuid.uuid4(),uuid.uuid4()
    with store.engine.begin() as db:
        db.execute(text("INSERT INTO site_projects(id,name,timezone) VALUES (:id,'Context','UTC')"),{'id':project})
        db.execute(text("INSERT INTO site_zones(id,project_id,name) VALUES (:id,:project,'North')"),{'id':zone,'project':project})
    request=body();request['images_base64']=[request.pop('image_base64')]*2
    request.update(project_id=str(project),zone_id=str(zone),stage='excavation',
                   capture_times=['2026-09-26T14:00:00+03:00','2026-09-26T12:00:00+03:00'])
    _,run=submit_series(store,artifacts,str(uuid.uuid4()),request,profile_id,revision,profile)
    work=store.claim_ordinary(profile_id,revision,30)
    asyncio.run(runner._execute(work,revision))
    result=store.read_ordinary(run)
    assert result['state']=='succeeded',result['error_code']
    frozen=result['ai_evidence'][-1]['context']
    assert frozen['history']==[] and frozen['history_eligible'] is False
    assert [frame['captured_at'] for frame in frozen['frames']]==request['capture_times']
    for field in ('scenario','observation_area','period','stage'):
        assert frozen['declared_context'][field]==request[field]


def test_uncertain_detection_and_bound_plan_revision_survive_later_revision(deepseek_service,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.application.site import router
    store,artifacts,profile_id,profile,revision,runner=deepseek_service
    app=FastAPI();app.state.store=store
    app.state.readiness=type('Ready',(),{'ready':type('Event',(),{'is_set':lambda _:True})()})()
    app.include_router(router);client=TestClient(app)
    project=client.post('/projects',json={'name':'Frozen plan','timezone':'UTC'}).json()
    zone=project['default_zone_id'];work_id=client.get('/catalog/works').json()['works'][0]['id']
    entry={'catalog_work_id':work_id,'start_at':'2026-09-01T00:00:00Z','end_at':'2026-10-01T00:00:00Z',
           'state':'active','stage_key':'excavation','expected_equipment':['excavator','dump_truck'],
           'allowed_equipment':[],'excluded_equipment':[]}
    plan_a=client.put(f'/zones/{zone}/plan',json={'expected_revision':0,'entries':[entry]}).json()
    request=body();request['images_base64']=[request.pop('image_base64')]*3
    request.update(project_id=project['id'],zone_id=zone,plan_revision_id=plan_a['revision_id'],
                   capture_times=['2026-09-26T12:00:00Z']*3)
    _,run=submit_series(store,artifacts,str(uuid.uuid4()),request,profile_id,revision,profile)
    plan_b=client.put(f'/zones/{zone}/plan',json={'expected_revision':1,'entries':[{**entry,'expected_equipment':[]}]}).json()
    value=annotation();value['objects']=[{**value['objects'][0],'type_ru':'экскаватор','type_en':'excavator','catalog_class':'excavator','status':'uncertain'}]
    monkeypatch.setattr(deepseek,'_read_json',lambda request,_: response(value if strict_json(request.data)['text']['format']['name']=='frame' else assessment()))
    work=store.claim_ordinary(profile_id,revision,30);asyncio.run(runner._execute(work,revision))
    result=store.read_ordinary(run)
    assert result['state']=='succeeded',result['error_code']
    assert all(o['state']=='insufficient_data' for o in result['observations'] if o['class_name']=='excavator')
    assert result['objects'][0]['details']['status']=='uncertain'
    assert result['result_projection']['plan_revision_id']==plan_a['revision_id']!=plan_b['revision_id']
    assert [s['kind'] for s in result['result_projection']['rule_results']]==['insufficient_observations']
    with store.engine.connect() as db:
        signal=db.execute(text('SELECT revision_id,basis FROM site_signals WHERE run_id=:id'),{'id':run}).one()
        assert str(signal.revision_id)==plan_a['revision_id']
        assert len(signal.basis['observations'])==6 and signal.basis['supporting_input_ids']
        assert len(signal.basis['frames'])==3


def test_enabled_retired_queue_is_terminalized(deepseek_service):
    store,_,profile_id,_,_,_=deepseek_service
    run=uuid.uuid4()
    with store.engine.begin() as db:
        db.execute(text('''INSERT INTO analysis_runs(id,state,purpose,profile_id,authorization_revision,profile_snapshot)
            VALUES (:id,'queued','ordinary',:profile,1,'{"kind":"cloud_api"}')'''),{'id':run,'profile':profile_id})
        db.execute(text("INSERT INTO analysis_stages(run_id,ordinal,name,state) VALUES (:id,0,'input_registration','pending'),(:id,1,'frame_usability','pending')"),{'id':run})
    store.fail_unauthorized_queued()
    result=store.read_ordinary(run)
    assert result['state']=='failed' and result['error_code']=='profile_retired'
    assert result['stages'][0]['state']=='failed' and result['stages'][1]['state']=='skipped'


def test_actual_shared_transport_size_and_deadline(monkeypatch):
    from app.shared import cloud
    class Response(io.BytesIO):
        def __enter__(self):return self
        def __exit__(self,*_):self.close()
    class Opener:
        def open(self,*_,**__):return Response(b'x'*(cloud.MAX_RESPONSE_BYTES+1))
    monkeypatch.setattr(cloud.request,'build_opener',lambda *_:Opener())
    with pytest.raises(cloud.CloudObserverError,match='response_too_large'):
        cloud._read_json(cloud.request.Request('https://example.invalid'),1)
    ticks=iter([0,2])
    monkeypatch.setattr(cloud.time,'monotonic',lambda:next(ticks))
    with pytest.raises(cloud.CloudObserverError,match='observer_timeout'):
        cloud._read_json(cloud.request.Request('https://example.invalid'),1)


def test_actual_shared_transport_does_not_follow_redirects():
    import threading
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from app.shared import cloud
    paths=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            paths.append(self.path)
            self.send_response(302);self.send_header('Location','/must-not-receive-credentials');self.end_headers()
        def log_message(self,*_):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with pytest.raises(cloud.CloudObserverError,match='redirect_rejected'):
            cloud._read_json(cloud.request.Request(f'http://127.0.0.1:{server.server_port}/start',headers={'Authorization':'Api-Key synthetic'}),2)
        assert paths==['/start']
    finally:
        server.shutdown();server.server_close();thread.join()
