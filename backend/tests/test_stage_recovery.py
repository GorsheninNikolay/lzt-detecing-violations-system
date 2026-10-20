import asyncio
import copy
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.adapters.postgres import AdmissionStoreError
from app.application import deepseek_runtime as runtime
from app.application.stage_recovery import retry_stage, retry_hints
from app.profiles import deepseek, hybrid
from app.shared.cloud import strict_json
from test_admission import isolated_admission_database
from test_deepseek import deepseek_service, queue_work, annotation, assessment, response
from test_startup import database, integration


@pytest.fixture(autouse=True)
def no_auth(monkeypatch):
    monkeypatch.setenv('AUTH_REQUIRED', 'false')


@pytest.mark.parametrize('text_value,accepted', [
    ('Одиночные кадры не позволяют установить рабочие действия, простой или длительность.', True),
    ('Техника простаивает', False),
    ('Кадры не позволяют оценить длительность, техника простаивает', False),
    ('Кадры не позволяют оценить длительность, но техника простаивает', False),
    ('Кадры не позволяют оценить длительность и техника простаивает', False),
    ('Длительность нельзя определить; техника простаивает', False),
])
def test_bounded_plural_negation(text_value, accepted):
    assert hybrid.asserts(text_value, r'простаива|простой') is not accepted


def test_truncation_is_distinct_and_partial_json_never_valid():
    raw = response(annotation())
    raw.update(status='incomplete', incomplete_details={'reason':'max_output_tokens'})
    raw['output'][0]['content'][0]['text'] = '{"objects":'
    with pytest.raises(ValueError, match='^response_output_truncated$'):
        deepseek.validate_response(raw, raw['model'], 'none')


def insufficient_activity(body):
    context = strict_json(body['input'][0]['content'][0]['text'].split(hybrid.ASSESSMENT_PROMPT, 1)[1])
    return [{'state':'insufficient_data','reason':'Недостаточно данных','uncertainty':'Один снимок',
             'frame_ids':[f['input_id']],'observation_ids':[], 'grounds':'insufficient_evidence','comparison':None}
            for f in context['frames']]


def setup_failed(service, monkeypatch, *, hybrid_mode=False, saved_revalidatable=False, fail_frame=None, context=None):
    store, artifacts, profile_id, profile, revision, runner = service
    if hybrid_mode:
        profile_id = runtime.provision(store, 'mock-folder', hybrid=True)
        profile, revision = store.require_authorized(profile_id)
        service = store, artifacts, profile_id, profile, revision, runner
        from app.profiles import yolo
        monkeypatch.setattr(yolo, 'detectors', lambda: type('D', (), {'detect': lambda self,*a: {'models':[], 'manifest': 'mock'}})())
    count = []
    def mocked(request, _):
        body = strict_json(request.data)
        kind = body['text']['format']['name']
        count.append(kind)
        if kind == 'frame':
            if fail_frame == len(count):
                raise TimeoutError()
            value = annotation()
            if hybrid_mode:
                value['objects'] = []
                value.update(frame_usability={'usable':True,'reason':'Видно'},
                             class_assessability={name:'assessable' for name in deepseek.EQUIPMENT},
                             detection_dispositions=[])
        else:
            value = assessment()
            if hybrid_mode:
                value.update(activity=insufficient_activity(body),stage_hypotheses=[])
            value['summary'] = ('Одиночные кадры не позволяют установить рабочие действия, простой или длительность.'
                                if saved_revalidatable else 'Техника простаивает')
        return response(value)
    monkeypatch.setattr(deepseek, '_read_json', mocked)
    if saved_revalidatable:
        original = hybrid.validate_assessment if hybrid_mode else deepseek.validate_assessment
        target = hybrid if hybrid_mode else deepseek
        def reject_old(value, context):
            if 'не позволяют' in value['summary']:
                raise ValueError('hybrid_idle_correspondence_unverified')
            return original(value, context)
        monkeypatch.setattr(target, 'validate_assessment', reject_old)
    # Always exercise a series, including partial frame failures.
    from app.application.submission import submit_series
    from test_deepseek import body
    request = body() | (context or {}); request['images_base64'] = [request.pop('image_base64')]*3
    _, run = submit_series(store, artifacts, str(uuid.uuid4()), request, profile_id, revision, profile)
    work = store.claim_ordinary(profile_id, revision, 30)
    asyncio.run(runner._execute(work,revision))
    if saved_revalidatable:
        monkeypatch.setattr(target,'validate_assessment',original)
    return service, run, count


@pytest.mark.parametrize('hybrid_mode', [False, True])
def test_saved_raw_full_revalidation_same_run_zero_provider(deepseek_service, monkeypatch, hybrid_mode):
    service, run, calls = setup_failed(deepseek_service, monkeypatch, hybrid_mode=hybrid_mode, saved_revalidatable=True)
    store, artifacts, profile_id, profile, revision, runner = service
    before = store.read_ordinary(run)
    assert before['state'] == 'failed', before['error_code']
    source = before['ai_evidence'][-1]
    assert source['result']['valid'] is False
    stage = next(s['name'] for s in before['stages'] if s['state']=='failed')
    deepseek.DeepSeek(profile,'mock').revalidate('assessment',source['context'],source['result'])
    hints = retry_hints(store,before)
    assert next(s for s in hints['stages'] if s['name']==stage)['retry_cost'] is False
    key = uuid.uuid4()
    attempt = retry_stage(store,run,stage,key,artifacts,'mock-only')
    assert retry_stage(store,run,stage,key,artifacts,'mock-only') == attempt
    monkeypatch.setattr(deepseek,'_read_json',lambda *a: pytest.fail('revalidation called provider'))
    work = store.claim_ordinary(profile_id,revision,30)
    assert work['id'] == run and work['current_attempt_id'] == attempt
    asyncio.run(runner._execute(work,revision))
    result = store.read_ordinary(run)
    assert result['state']=='succeeded',result['error_code']
    assert len(calls)==4
    assert len(result['ai_evidence'])==5
    derived = result['ai_evidence'][-1]
    assert derived['source_call_id']==source['id'] and derived['validation_revision']==runtime.VALIDATION_REVISION
    assert derived['result']['receipt_kind']=='local_revalidation' and derived['result']['usage'] is None
    assert derived['context']==source['context'] and derived['result']['raw']==source['result']['raw']
    assert result['ai_evidence'][-2]['result']['valid'] is False
    assert retry_stage(store,run,stage,key,artifacts,'mock-only') == attempt
    with store.engine.connect() as db:
        assert db.execute(text('SELECT status FROM run_attempts WHERE id=:id'),{'id':attempt}).scalar()=='succeeded'
        assert db.execute(text('SELECT count(*) FROM analysis_runs')).scalar()==1
        assert db.execute(text('SELECT count(*) FROM detector_stage_outputs')).scalar()==(3 if hybrid_mode else 0)


@pytest.mark.parametrize('hybrid_mode', [False,True])
def test_failed_assessment_fresh_only_no_duplicate_frames(deepseek_service,monkeypatch,hybrid_mode):
    # Legacy validator accepts idle prose; force a fully invalid response for either contract.
    original = deepseek.validate_response
    invalid = {'enabled':True}
    def validate(raw,*args):
        if invalid['enabled'] and 'простаивает' in json.loads(raw['output'][0]['content'][0]['text']).get('summary',''):
            raise ValueError('response_text_invalid')
        return original(raw,*args)
    monkeypatch.setattr(deepseek,'validate_response',validate)
    service,run,calls = setup_failed(deepseek_service,monkeypatch,hybrid_mode=hybrid_mode)
    store,artifacts,profile_id,profile,revision,runner=service
    failed=store.read_ordinary(run)
    assert failed['state']=='failed'
    old=failed['ai_evidence'][-1]
    stage=next(s['name'] for s in failed['stages'] if s['state']=='failed')
    retry_stage(store,run,stage,uuid.uuid4(),artifacts,'mock-only')
    # Saved raw remains invalid; only a fresh assessment may succeed.
    calls.clear()
    def fresh(request,_):
        body=strict_json(request.data)
        kind=body['text']['format']['name'];calls.append(kind)
        assert kind=='assessment'
        assert old['context']['frames'][0]['input_id'] in body['input'][0]['content'][0]['text']
        value=assessment()
        if hybrid_mode:value.update(activity=insufficient_activity(body),stage_hypotheses=[])
        return response(value)
    monkeypatch.setattr(deepseek,'_read_json',fresh)
    asyncio.run(runner._execute(store.claim_ordinary(profile_id,revision,30),revision))
    result=store.read_ordinary(run)
    assert result['state']=='succeeded',result['error_code']
    assert calls==['assessment']
    assert result['ai_evidence'][-1]['source_call_id'] is None
    assert result['ai_evidence'][-1]['context']==old['context']


def test_partial_frames_uncertainty_and_competing_keys(deepseek_service,monkeypatch):
    service,run,calls=setup_failed(deepseek_service,monkeypatch,fail_frame=2)
    store,artifacts,profile_id,profile,revision,runner=service
    failed=store.read_ordinary(run)
    assert failed['state']=='failed' and [c['state'] for c in failed['ai_evidence']]==['completed','uncertain']
    stage=next(s['name'] for s in failed['stages'] if s['state']=='failed')
    key=uuid.uuid4()
    def accept(_):
        return retry_stage(store,run,stage,key,artifacts,'mock-only')
    with ThreadPoolExecutor(2) as pool:
        attempts=list(pool.map(accept,range(2)))
    assert attempts[0]==attempts[1]
    with pytest.raises(AdmissionStoreError,match='retry_ineligible'):
        retry_stage(store,run,stage,uuid.uuid4(),artifacts,'mock-only')
    calls.clear()
    monkeypatch.setattr(deepseek,'_read_json',lambda req,_: (calls.append(strict_json(req.data)['text']['format']['name']) or response(annotation() if calls[-1]=='frame' else assessment())))
    work=store.claim_ordinary(profile_id,revision,30)
    stale={**work,'current_attempt_id':run}
    with pytest.raises(ValueError,match='ordinary_lease_rejected'):
        runtime.reserve(store,stale,'assessment',{})
    asyncio.run(runner._execute(work,revision))
    assert store.read_ordinary(run)['state']=='succeeded'
    assert calls==['frame','frame','assessment']
    with store.engine.begin() as db:
        with pytest.raises(DatabaseError):
            db.execute(text("UPDATE attempt_call_refs SET call_key='changed' WHERE attempt_id=:id"),{'id':attempts[0]})


@pytest.mark.parametrize('phase', ['rule_evaluation','result_projection'])
def test_downstream_failure_recovery_has_no_cloud_calls(deepseek_service,monkeypatch,phase):
    store,artifacts,profile_id,profile,revision,runner=deepseek_service
    work=queue_work(deepseek_service)
    target='validate_downstream' if phase=='rule_evaluation' else 'complete'
    original=getattr(runtime,target)
    monkeypatch.setattr(runtime,target,lambda *args: (_ for _ in ()).throw(ValueError('forced_projection_failure')))
    asyncio.run(runner._execute(work,revision))
    failed=store.read_ordinary(work['id'])
    assert failed['state']=='failed'
    assert next(s['name'] for s in failed['stages'] if s['state']=='failed')==phase
    assert all(c['effective'] for c in failed['ai_evidence'])
    monkeypatch.setattr(runtime,target,original)
    retry_stage(store,work['id'],phase,uuid.uuid4(),artifacts,'mock')
    monkeypatch.setattr(deepseek,'_read_json',lambda *args: pytest.fail('downstream recovery called provider'))
    asyncio.run(runner._execute(store.claim_ordinary(profile_id,revision,30),revision))
    result=store.read_ordinary(work['id'])
    assert result['state']=='succeeded',result['error_code']
    assert len(result['ai_evidence'])==2


def test_crash_recovery_and_revocation_terminalize_attempts(deepseek_service,monkeypatch):
    service,run,_=setup_failed(deepseek_service,monkeypatch,fail_frame=2)
    store,artifacts,profile_id,profile,revision,runner=service
    failed=store.read_ordinary(run)
    stage=next(s['name'] for s in failed['stages'] if s['state']=='failed')
    first=retry_stage(store,run,stage,uuid.uuid4(),artifacts,'mock')
    work=store.claim_ordinary(profile_id,revision,30)
    with store.engine.begin() as db:
        db.execute(text("UPDATE analysis_runs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=:id"),{'id':run})
    assert store.recover()==1
    with store.engine.connect() as db:
        assert db.execute(text('SELECT status FROM run_attempts WHERE id=:id'),{'id':first}).scalar()=='failed'
    failed=store.read_ordinary(run);stage=next(s['name'] for s in failed['stages'] if s['state']=='failed')
    second=retry_stage(store,run,stage,uuid.uuid4(),artifacts,'mock')
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET state='revoked' WHERE profile_id=:id"),{'id':profile_id})
    store.fail_unauthorized_queued()
    assert store.claim_ordinary(profile_id,revision,30) is None
    with store.engine.connect() as db:
        assert db.execute(text('SELECT status FROM run_attempts WHERE id=:id'),{'id':second}).scalar()=='failed'


def test_accepted_replay_survives_retirement_and_missing_source(deepseek_service,monkeypatch):
    service,run,_=setup_failed(deepseek_service,monkeypatch,fail_frame=2)
    store,artifacts,profile_id,profile,revision,runner=service
    failed=store.read_ordinary(run);stage=next(s['name'] for s in failed['stages'] if s['state']=='failed')
    key=uuid.uuid4();attempt=retry_stage(store,run,stage,key,artifacts,'mock')
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET state='revoked' WHERE profile_id=:id"),{'id':profile_id})
    monkeypatch.setattr(artifacts,'read_verified',lambda *a:pytest.fail('accepted replay read sources'))
    assert retry_stage(store,run,stage,key,artifacts,None,ready=False)==attempt
    with pytest.raises(AdmissionStoreError,match='idempotency_conflict'):
        retry_stage(store,run,'other',key,artifacts,None,ready=False)


def test_compact_schema_preserves_snapshot_and_complete_references():
    from app.shared.cloud import digest,canonical_bytes
    profile=hybrid.snapshot('mock-folder')
    assert profile['instruction_sha256']==digest((hybrid.FRAME_PROMPT+hybrid.ASSESSMENT_PROMPT).encode())
    observer=deepseek.DeepSeek(copy.deepcopy(profile),'mock')
    compact=deepseek.compact_output_schema(hybrid.FRAME_SCHEMA)
    assert hybrid.FRAME_SCHEMA['properties']['objects']['maxItems']==compact['properties']['objects']['maxItems']
    assert compact['properties']['objects']['items']['properties']['detection_ids']==hybrid.FRAME_SCHEMA['properties']['objects']['items']['properties']['detection_ids']
    assert compact['properties']['stage_reason']['maxLength']==240
    assert hybrid.FRAME_SCHEMA['properties']['stage_reason']['maxLength']==1000
    assert observer.profile==profile


@pytest.fixture
def recovery_accounts(isolated_admission_database,monkeypatch):
    from test_accounts import accounts
    monkeypatch.setenv('TEST_DATABASE_URL',isolated_admission_database)
    yield from accounts.__wrapped__(monkeypatch)


def test_authenticated_api_roles_replay_and_hard_delete(recovery_accounts,monkeypatch):
    from app.adapters.artifacts import ArtifactStore
    from app.config import Config
    from app.application.executor import ClaimLoop
    from test_accounts import project
    make,store=recovery_accounts
    owner,_=make();editor,member=make();viewer,readonly=make();outsider,_=make()
    own=project(owner)
    for client,user,role in ((editor,member,'editor'),(viewer,readonly,'viewer')):
        invitation=owner.post(f"/projects/{own['id']}/invitations",json={'email':user['email'],'role':role}).json()
        assert client.post('/invitations/accept',json={'token':invitation['token']}).status_code==200
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY','mock-only')
    artifacts=ArtifactStore(Config.from_env())
    profile_id=runtime.provision(store,'mock-folder');profile,revision=store.require_authorized(profile_id)
    runner=ClaimLoop();runner.store,runner.artifacts=store,artifacts
    service,run,calls=setup_failed((store,artifacts,profile_id,profile,revision,runner),monkeypatch,
        hybrid_mode=True,fail_frame=2,context={'project_id':own['id'],'zone_id':own['default_zone_id'],'capture_times':['2026-09-26T12:00:00Z']*3})
    store,artifacts,profile_id,profile,revision,runner=service
    owner.app.state.artifacts=artifacts
    owner.app.state.claim_loop.runtime_binding=(profile_id,revision)
    current=owner.get(f'/runs/{run}')
    assert current.status_code==200,current.text
    payload=current.json();assert payload['current_attempt_id']==str(run)
    other_profile = runtime.provision(store, 'another-folder', hybrid=True)
    owner.app.state.claim_loop.runtime_binding = (other_profile, 1)
    different_binding = owner.get(f'/runs/{run}').json()
    assert different_binding['retry_eligible'] is True
    assert not any(s['retryable'] for s in different_binding['stages'])
    owner.app.state.claim_loop.runtime_binding = (profile_id, revision)
    stage=next(s['name'] for s in payload['stages'] if s['state']=='failed')
    assert next(s for s in payload['stages'] if s['name']==stage)['retryable'] is True
    path=f'/runs/{run}/stages/{stage}/retry';headers={'Idempotency-Key':str(uuid.uuid4())}
    assert outsider.post(path,headers=headers).status_code==404
    assert viewer.post(path,headers=headers).status_code==403
    assert editor.post(path).status_code==400
    accepted=editor.post(path,headers=headers)
    assert accepted.status_code==202,accepted.text
    assert accepted.json()['run_id']==str(run)
    assert editor.post(path,headers=headers).json()==accepted.json()
    assert owner.delete(f'/runs/{run}').status_code==409
    assert owner.patch(f"/projects/{own['id']}/members/{member['id']}",json={'role':'viewer'}).status_code==200
    assert editor.post(path,headers=headers).status_code==403
    def fresh(request,_):
        body=strict_json(request.data);kind=body['text']['format']['name']
        if kind=='frame':
            value=annotation();value['objects']=[]
            value.update(frame_usability={'usable':True,'reason':'Видно'},class_assessability={n:'assessable' for n in deepseek.EQUIPMENT},detection_dispositions=[])
        else:
            value=assessment();value.update(activity=insufficient_activity(body),stage_hypotheses=[])
        return response(value)
    monkeypatch.setattr(deepseek,'_read_json',fresh)
    asyncio.run(runner._execute(store.claim_ordinary(profile_id,revision,30),revision))
    assert store.read_ordinary(run)['state']=='succeeded'
    result=owner.delete(f'/runs/{run}')
    assert result.status_code==202,result.text
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM run_attempts WHERE run_id=:run'),{'run':run}).scalar()==0
        assert db.execute(text('SELECT count(*) FROM detector_stage_outputs WHERE run_id=:run'),{'run':run}).scalar()==0
        assert db.execute(text('SELECT count(*) FROM deepseek_calls WHERE run_id=:run'),{'run':run}).scalar()==0
        assert db.execute(text('SELECT count(*) FROM attempt_call_refs')).scalar()==0


@pytest.mark.parametrize('rejection',['quality_budget_settlement_failed','accounting_incomplete',None])
def test_administrative_rejection_cannot_be_revalidated(deepseek_service,monkeypatch,rejection):
    store,artifacts,profile_id,profile,revision,runner=deepseek_service
    work=queue_work(deepseek_service)
    asyncio.run(runner._execute(work,revision))
    saved=store.read_ordinary(work['id'])['ai_evidence'][-1]
    rejected={**saved['result'],'valid':False,'rejection':rejection}
    with pytest.raises(ValueError,match='revalidation_administrative_rejection'):
        deepseek.DeepSeek(profile,'mock').revalidate('assessment',saved['context'],rejected)


def test_admission_rejects_wrong_stage_revocation_and_corrupted_source(deepseek_service,monkeypatch):
    from app.adapters.artifacts import ArtifactGateError
    service,run,_=setup_failed(deepseek_service,monkeypatch,fail_frame=2)
    store,artifacts,profile_id,profile,revision,runner=service
    failed=store.read_ordinary(run);stage=next(s['name'] for s in failed['stages'] if s['state']=='failed')
    for wrong in ('input_registration','series_aggregation','result_projection','not_a_stage'):
        with pytest.raises(AdmissionStoreError,match='retry_ineligible'):
            retry_stage(store,run,wrong,uuid.uuid4(),artifacts,'mock')
    def corrupt(*args):raise ArtifactGateError('artifact_integrity_failed')
    monkeypatch.setattr(artifacts,'read_verified',corrupt)
    with pytest.raises(AdmissionStoreError,match='retry_source_unavailable'):
        retry_stage(store,run,stage,uuid.uuid4(),artifacts,'mock')
    with store.engine.begin() as db:
        db.execute(text("UPDATE profile_authorizations SET state='revoked' WHERE profile_id=:id"),{'id':profile_id})
    with pytest.raises(AdmissionStoreError,match='profile_unauthorized'):
        retry_stage(store,run,stage,uuid.uuid4(),artifacts,'mock')
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM run_attempts WHERE run_id=:id'),{'id':run}).scalar()==1


def test_admission_rejects_unsupported_profile_and_absent_consent(deepseek_service):
    store,artifacts,profile_id,profile,revision,_=deepseek_service
    for snapshot,context,code in ((profile,{},'cloud_consent_required'),({'kind':'cloud_api'},{},'profile_retired')):
        run=uuid.uuid4()
        with store.engine.begin() as db:
            db.execute(text('''INSERT INTO analysis_runs(id,state,purpose,profile_id,authorization_revision,profile_snapshot,request_context)
                VALUES (:id,'failed','ordinary',:profile,1,CAST(:snapshot AS jsonb),CAST(:context AS jsonb))'''),
                {'id':run,'profile':profile_id,'snapshot':json.dumps(snapshot),'context':json.dumps(context)})
        with pytest.raises((ValueError,AdmissionStoreError),match=code):
            retry_stage(store,run,'series_aggregation',uuid.uuid4(),artifacts,'mock')
