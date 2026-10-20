import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.application.deletions import cleanup_deletions
from test_accounts import accounts, project
from test_startup import database


@pytest.fixture
def isolated_accounts(database, monkeypatch, request):
    monkeypatch.setenv('TEST_DATABASE_URL', database.engine.url.render_as_string(hide_password=False))
    return request.getfixturevalue('accounts')


class Objects:
    def __init__(self):
        self.keys = set()
        self.fail = False
        self.deleted = []

    def _delete_report_temporary(self, key):
        if self.fail:
            raise OSError('local storage unavailable')
        self.keys.discard(key)
        self.deleted.append(key)


def test_management_api_contract():
    from app.main import create_app
    schema = create_app().openapi()
    for path in ('/projects/{identifier}', '/runs/{identifier}'):
        response = schema['paths'][path]['delete']['responses']['202']
        assert set(response['content']['application/json']['schema']['required']) == {'deletion_id', 'status'}
    status = schema['paths']['/deletions/{identifier}']['get']['responses']['200']
    assert status['content']['application/json']['schema']['properties']['status']['enum'] == ['cleaning', 'completed']
    role = schema['paths']['/projects/{project_id}/members/{user_id}']['patch']['requestBody']['content']['application/json']['schema']
    assert role['required'] == ['role']
    assert role['properties']['role']['enum'] == ['editor', 'viewer']
    assert role['additionalProperties'] is False


def photo(store, project_id, *, key=None, state='failed', predecessor=None):
    run, intent, artifact, input_id, call = [uuid4() for _ in range(5)]
    key = key or f'sha256/{uuid4().hex * 2}'
    request_key = str(uuid4())
    with store.engine.begin() as db:
        db.execute(text('''INSERT INTO analysis_runs(id,state,purpose,analysis_intent,request_context,retry_predecessor_id)
            VALUES (:run,:state,'ordinary','observation_only',CAST(:context AS jsonb),:parent)'''),
            {'run': run, 'state': state, 'context': json.dumps({'project_id': project_id}), 'parent': predecessor})
        db.execute(text("INSERT INTO submission_requests(idempotency_key,request_hash,state,project_id) VALUES (:key,'digest','publishing',:project)"), {'key': request_key, 'project': project_id})
        db.execute(text('''INSERT INTO publication_intents(id,run_id,idempotency_key,submission_key,media_type,state,sha256,size,final_key)
            VALUES (:intent,:run,:intent_key,:request,'image/jpeg','referenced',:sha,5,:key)'''),
            {'intent': intent, 'run': run, 'intent_key': str(intent), 'request': request_key, 'sha': key.rsplit('/',1)[1], 'key': key})
        db.execute(text('''INSERT INTO artifact_metadata(id,run_id,intent_id,key,sha256,size,media_type)
            VALUES (:artifact,:run,:intent,:key,:sha,5,'image/jpeg')'''),
            {'artifact': artifact, 'run': run, 'intent': intent, 'key': key, 'sha': key.rsplit('/',1)[1]})
        db.execute(text("INSERT INTO run_inputs(run_id,ordinal,input_id,sha256,size,context,artifact_id) VALUES (:run,0,:input,:sha,5,'{}',:artifact)"),
            {'run': run, 'input': input_id, 'sha': key.rsplit('/',1)[1], 'artifact': artifact})
        db.execute(text("INSERT INTO analysis_stages(run_id,ordinal,name,state) VALUES (:run,0,'assessment','failed')"), {'run': run})
        db.execute(text("INSERT INTO deepseek_calls(id,run_id,call_key,kind,input_id,context) VALUES (:id,:run,'frame:0','frame',:input,'{}')"), {'id': call, 'run': run, 'input': input_id})
        db.execute(text("INSERT INTO deepseek_results(call_id,result) VALUES (:id,CAST(:result AS jsonb))"), {'id': call, 'result': json.dumps({'saved': True})})
        db.execute(text("UPDATE submission_requests SET run_id=:run,state='accepted',intent_id=:intent WHERE idempotency_key=:key"), {'run': run, 'intent': intent, 'key': request_key})
    return SimpleNamespace(id=run, key=key, call=call, request_key=request_key, artifact=artifact, input_id=input_id)


def test_delete_photo_shared_content_lineage_immutable_receipts_and_retry_gc(accounts):
    make, store = accounts
    owner, _ = make()
    own = project(owner)
    first = photo(store, own['id'])
    second = photo(store, own['id'], key=first.key, predecessor=first.id)
    objects = Objects()
    objects.keys.add(first.key)
    with pytest.raises(DBAPIError), store.engine.begin() as db:
        db.execute(text('DELETE FROM deepseek_results WHERE call_id=:id'), {'id': first.call})
    with pytest.raises(DBAPIError), store.engine.begin() as db:
        db.execute(text("UPDATE deepseek_results SET result='{}' WHERE call_id=:id"), {'id': first.call})
    accepted = owner.delete(f'/runs/{first.id}')
    assert accepted.status_code == 202, accepted.text
    deletion = accepted.json()['deletion_id']
    assert owner.delete(f'/runs/{first.id}').json()['deletion_id'] == deletion
    assert owner.get(f'/runs/{first.id}').status_code == 404
    assert owner.get(f'/runs/{first.id}/artifacts/{first.artifact}').status_code == 404
    assert store.begin_submission(first.request_key, 'digest', 'image/jpeg')[0:4] == ('failed', None, None, 'resource_deleted')
    cleanup_deletions(store.engine, objects)
    assert first.key in objects.keys
    assert owner.get(f'/deletions/{deletion}').json()['status'] == 'completed'
    with store.engine.connect() as db:
        assert db.execute(text('SELECT result FROM deepseek_results WHERE call_id=:id'), {'id': second.call}).scalar_one() == {'saved': True}
        assert db.execute(text('SELECT retry_predecessor_id FROM analysis_runs WHERE id=:id'), {'id': second.id}).scalar_one() == first.id
    accepted = owner.delete(f'/runs/{second.id}')
    assert accepted.status_code == 202, accepted.text
    deletion = accepted.json()['deletion_id']
    objects.fail = True
    cleanup_deletions(store.engine, objects)
    assert owner.get(f'/deletions/{deletion}').json()['status'] == 'cleaning'
    objects.fail = False
    with store.engine.begin() as db:
        db.execute(text('UPDATE deletion_objects SET retry_after=clock_timestamp() WHERE deletion_id=:id'), {'id': deletion})
    cleanup_deletions(store.engine, objects)
    assert first.key not in objects.keys
    assert owner.get(f'/deletions/{deletion}').json()['status'] == 'completed'
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM deletion_row_authorizations')).scalar_one() == 0


def test_project_delete_authority_busy_and_no_request_resurrection(accounts):
    make, store = accounts
    owner, _ = make()
    editor, member = make()
    outsider, _ = make()
    request_key = str(uuid4())
    own = owner.post('/projects', json={'name': 'Delete entire project', 'timezone': 'UTC'}, headers={'Idempotency-Key': request_key}).json()
    invitation = owner.post(f'/projects/{own["id"]}/invitations', json={'email': member['email'], 'role': 'editor'}).json()
    assert editor.post('/invitations/accept', json={'token': invitation['token']}).status_code == 200
    assert editor.delete(f'/projects/{own["id"]}').status_code == 403
    assert outsider.delete(f'/projects/{own["id"]}').status_code == 404
    assert owner.delete(f'/projects/{own["id"]}', headers={'Origin':'http://evil.test'}).status_code == 403
    run = photo(store, own['id'], state='queued')
    assert owner.delete(f'/projects/{own["id"]}').status_code == 409
    assert owner.get(f'/projects/{own["id"]}/zones').status_code == 200
    with store.engine.begin() as db:
        db.execute(text("UPDATE analysis_runs SET state='failed' WHERE id=:id"), {'id': run.id})
    publishing = str(uuid4())
    assert store.begin_submission(publishing, 'publishing-hash', 'image/jpeg', own['id'])[0] == 'created'
    assert owner.delete(f'/projects/{own["id"]}').json()['detail'] == 'deletion_publishing_submission'
    store.fail_submission(publishing, 'interrupted')
    result = owner.delete(f'/projects/{own["id"]}')
    assert result.status_code == 202, result.text
    deletion = result.json()['deletion_id']
    assert editor.get(f'/deletions/{deletion}').status_code == 404
    assert outsider.delete(f'/projects/{own["id"]}').status_code == 404
    assert owner.delete(f'/projects/{own["id"]}').json()['deletion_id'] == deletion
    assert owner.get(f'/projects/{own["id"]}/zones').status_code == 404
    assert all(p['id'] != own['id'] for p in owner.get('/projects').json()['projects'])
    assert owner.post('/projects', json={'name': 'Delete entire project', 'timezone': 'UTC'}, headers={'Idempotency-Key': request_key}).status_code == 410
    cleanup_deletions(store.engine, Objects())
    assert owner.get(f'/deletions/{deletion}').json()['status'] == 'completed'


def test_video_delete_scopes_files_and_blocks_replay(accounts):
    make, store = accounts
    owner, _ = make()
    own = project(owner)
    identifier = uuid4()
    request_key = str(uuid4())
    keys = [f'video/sha256/{uuid4().hex}' for _ in range(3)]
    with store.engine.begin() as db:
        db.execute(text('''INSERT INTO video_jobs(id,project_id,zone_id,request_key,request_hash,source_key,source_sha256,source_size,
            context,profile_snapshot,state,metadata,result)
            VALUES (:id,:project,:zone,:request,'digest',:source,'hash',5,'{}','{}','failed','{}',CAST(:result AS jsonb))'''),
            {'id': identifier, 'project': own['id'], 'zone': own['default_zone_id'], 'request': request_key, 'source': keys[0],
             'result': json.dumps({'artifact_key': keys[1], 'selected_frames': [{'artifact_key': keys[2]}]})})
        db.execute(text("INSERT INTO video_calls(job_id,call_key,context,result) VALUES (:id,'frame:0','{}','{}')"), {'id': identifier})
    result = owner.delete(f'/runs/{identifier}')
    assert result.status_code == 202, result.text
    assert owner.get(f'/video-runs/{identifier}').status_code == 404
    objects = Objects()
    objects.keys.update(keys)
    cleanup_deletions(store.engine, objects)
    assert not objects.keys
    assert set(keys) <= set(objects.deleted)
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM video_calls WHERE job_id=:id'), {'id': identifier}).scalar_one() == 0
        assert db.execute(text("SELECT 1 FROM deleted_request_keys WHERE kind='video' AND request_key=:key"), {'key': own['id']+':'+request_key}).scalar_one() == 1


def test_slow_object_cleanup_does_not_block_other_run_lease_or_settlement(accounts):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    import time
    from app.application import deepseek_runtime as runtime
    make, store = accounts
    owner, _ = make()
    own, foreign = project(owner), project(owner)
    doomed = photo(store, own['id'])
    assert owner.delete(f'/runs/{doomed.id}').status_code == 202
    profile_id = runtime.provision(store, 'mock-folder')
    profile, revision = store.require_authorized(profile_id)
    running, call = uuid4(), uuid4()
    with store.engine.begin() as db:
        db.execute(text('''INSERT INTO analysis_runs(id,state,purpose,analysis_intent,request_context,profile_snapshot,
            profile_id,authorization_revision,lease_owner,lease_expires_at)
            VALUES (:run,'running','ordinary','observation_only',CAST(:context AS jsonb),CAST(:profile AS jsonb),
                :profile_id,:revision,'worker',clock_timestamp()+interval '30 seconds')'''),
            {'run': running, 'context': json.dumps({'project_id': foreign['id'], 'cloud_processing_consent': True}),
             'profile': json.dumps(profile), 'profile_id': profile_id, 'revision': revision})
        db.execute(text("INSERT INTO deepseek_calls(id,run_id,call_key,kind,context) VALUES (:id,:run,'assessment','assessment','{}')"), {'id': call, 'run': running})
    entered, release = Event(), Event()
    class SlowObjects(Objects):
        def _delete_report_temporary(self, key):
            entered.set()
            assert release.wait(15)
            super()._delete_report_temporary(key)
    with ThreadPoolExecutor() as pool:
        cleanup = pool.submit(cleanup_deletions, store.engine, SlowObjects())
        assert entered.wait(3)
        try:
            # Exceed the database lock timeout while object storage remains blocked.
            time.sleep(5.2)
            started = time.monotonic()
            store.renew_ordinary(running, 'worker', revision, 30)
            runtime.save_result(store, {'id': running, 'owner': 'worker'}, call, {'valid': True})
            assert time.monotonic() - started < 2
            assert not cleanup.done()
        finally:
            release.set()
        cleanup.result(timeout=3)
    with store.engine.connect() as db:
        assert db.execute(text('SELECT result FROM deepseek_results WHERE call_id=:id'), {'id': call}).scalar_one() == {'valid': True}


def test_versioned_objects_are_physically_absent_after_cleanup(accounts):
    from dataclasses import replace
    from app.adapters.artifacts import ArtifactStore
    from app.config import Config
    make, store = accounts
    owner, _ = make()
    own = project(owner)
    run = photo(store, own['id'])
    bucket = 'lzt-deletion-' + uuid4().hex
    artifacts = ArtifactStore(replace(Config.from_env(), s3_bucket=bucket))
    artifacts.client.create_bucket(Bucket=bucket)
    artifacts.client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={'Status': 'Enabled'})
    for body in (b'first version', b'second version'):
        artifacts.client.put_object(Bucket=bucket, Key=run.key, Body=body)
    artifacts.client.put_object(Bucket=bucket, Key='tmp/' + str(uuid4()), Body=b'other content')
    result = owner.delete(f'/runs/{run.id}')
    assert result.status_code == 202, result.text
    cleanup_deletions(store.engine, artifacts)
    assert artifacts._health_versions(run.key) == []
    assert owner.get(f'/deletions/{result.json()["deletion_id"]}').json()['status'] == 'completed'
    remaining = artifacts.client.list_objects_v2(Bucket=bucket).get('Contents', [])
    assert len(remaining) == 1
    artifacts._delete_report_temporary(remaining[0]['Key'])
    artifacts.client.delete_bucket(Bucket=bucket)


def test_project_graph_with_trial_plan_annotations_and_notifications_is_removed(accounts):
    make, store = accounts
    owner, _ = make()
    recipient, member = make()
    trial_key = str(uuid4())
    imported = owner.post('/trial/import', headers={'Idempotency-Key': trial_key})
    assert imported.status_code == 200, imported.text
    project_id = imported.json()['project_id']
    owner.post(f'/projects/{project_id}/invitations', json={'email': member['email'], 'role': 'editor'})
    run = photo(store, project_id)
    proposal, version = uuid4(), uuid4()
    with store.engine.begin() as db:
        plan = db.execute(text('''SELECT r.id,z.id AS zone,e.id AS entry FROM zone_plan_revisions r
            JOIN site_zones z ON z.id=r.zone_id JOIN zone_plan_entries e ON e.revision_id=r.id
            WHERE z.project_id=:p LIMIT 1'''), {'p': project_id}).first()
        db.execute(text('INSERT INTO run_plan_bindings(run_id,zone_id,revision_id,frame_times) VALUES (:run,:zone,:revision,\'[]\')'),
            {'run': run.id, 'zone': plan.zone, 'revision': plan.id})
        db.execute(text('''INSERT INTO site_signals(id,fingerprint,run_id,zone_id,revision_id,work_entry_id,kind,basis)
            VALUES (:id,:fingerprint,:run,:zone,:revision,:entry,'plan','{}')'''),
            {'id': uuid4(), 'fingerprint': str(uuid4()), 'run': run.id, 'zone': plan.zone, 'revision': plan.id, 'entry': plan.entry})
        db.execute(text('''INSERT INTO annotation_proposals(id,request_key,body_sha256,run_id,input_id,input_sha256,artifact_id,profile_snapshot,original_objects)
            VALUES (:id,:key,'digest',:run,:input,'hash',:artifact,'{}','[]')'''),
            {'id': proposal, 'key': uuid4(), 'run': run.id, 'input': run.input_id, 'artifact': run.artifact})
        db.execute(text("""INSERT INTO annotation_versions(id,proposal_id,revision,objects,status,request_key,body_sha256)
            VALUES (:id,:proposal,1,'[]','pending',:key,'digest')"""), {'id': version, 'proposal': proposal, 'key': uuid4()})
    assert len(recipient.get('/notifications').json()['notifications']) == 1
    result = owner.delete(f'/projects/{project_id}')
    assert result.status_code == 202, result.text
    assert recipient.get('/notifications').json()['notifications'] == []
    assert owner.post('/trial/import', headers={'Idempotency-Key': trial_key}).status_code == 410
    cleanup_deletions(store.engine, Objects())
    with store.engine.connect() as db:
        for table, field, identifier in (('annotation_versions','id',version), ('annotation_proposals','id',proposal),
                ('run_plan_bindings','run_id',run.id), ('zone_plan_revisions','id',plan.id), ('zone_plan_entries','id',plan.entry)):
            assert db.execute(text(f'SELECT count(*) FROM {table} WHERE {field}=:id'), {'id': identifier}).scalar_one() == 0


def test_interrupted_video_admission_is_busy_until_terminal_then_files_are_deleted(isolated_accounts):
    make, store = isolated_accounts
    owner, _ = make()
    own = project(owner)
    request_key, source = str(uuid4()), 'video/sha256/'+uuid4().hex
    with store.engine.begin() as db:
        db.execute(text("""INSERT INTO video_admissions(project_id,request_key,request_hash,source_key,state)
            VALUES (:project,:key,'digest',:source,'publishing')"""), {'project': own['id'], 'key': request_key, 'source': source})
    assert owner.delete(f'/projects/{own["id"]}').json()['detail'] == 'deletion_publishing_submission'
    store.recover()
    with store.engine.connect() as db:
        assert db.execute(text('SELECT state FROM video_admissions WHERE project_id=:project'), {'project': own['id']}).scalar_one() == 'publishing'
    assert owner.delete(f'/projects/{own["id"]}').json()['detail'] == 'deletion_publishing_submission'
    store.recover_interrupted_video_admissions()
    with store.engine.connect() as db:
        assert db.execute(text('SELECT state FROM video_admissions WHERE project_id=:project'), {'project': own['id']}).scalar_one() == 'failed'
    result = owner.delete(f'/projects/{own["id"]}')
    assert result.status_code == 202, result.text
    objects = Objects()
    objects.keys.add(source)
    cleanup_deletions(store.engine, objects)
    assert source in objects.deleted and not objects.keys
    with store.engine.connect() as db:
        assert db.execute(text("SELECT 1 FROM deleted_request_keys WHERE kind='video' AND request_key=:key"), {'key': own['id']+':'+request_key}).scalar_one() == 1


def test_video_cleanup_ignores_model_paths_and_keeps_only_authoritative_shared_references(accounts):
    make, store = accounts
    owner, _ = make()
    own = project(owner)
    first, second = uuid4(), uuid4()
    source, other_source, output, detections, frame = [f'video/sha256/{uuid4().hex}' for _ in range(5)]
    unrelated = f'tmp/{uuid4()}'
    with store.engine.begin() as db:
        for identifier, source_key, result, context in (
            (first, source, {'artifact_key': output, 'detections_artifact_key': detections,
                'selected_frames': [{'artifact_key': frame}],
                'assessment': {'raw': unrelated, 'value': {'artifact_key': unrelated}}}, {'notes': unrelated}),
            (second, other_source, {'artifact_key': output,
                'assessment': {'raw': source, 'value': {'artifact_key': source}}}, {'notes': source}),
        ):
            db.execute(text('''INSERT INTO video_jobs(id,project_id,zone_id,request_key,request_hash,source_key,
                source_sha256,source_size,context,profile_snapshot,state,metadata,result)
                VALUES (:id,:project,:zone,:request,'digest',:source,'hash',5,CAST(:context AS jsonb),
                    '{}','failed','{}',CAST(:result AS jsonb))'''),
                {'id': identifier, 'project': own['id'], 'zone': own['default_zone_id'],
                 'request': str(uuid4()), 'source': source_key, 'context': json.dumps(context), 'result': json.dumps(result)})
            db.execute(text('''INSERT INTO video_calls(job_id,call_key,context,result)
                VALUES (:id,'assessment',CAST(:context AS jsonb),CAST(:result AS jsonb))'''),
                {'id': identifier, 'context': json.dumps({'notes': unrelated if identifier == first else source}),
                 'result': json.dumps({'raw': unrelated if identifier == first else source,
                    'value': {'artifact_key': unrelated if identifier == first else source}})})
    objects = Objects()
    objects.keys.update((source, other_source, output, detections, frame, unrelated))
    accepted = owner.delete(f'/runs/{first}')
    assert accepted.status_code == 202, accepted.text
    with store.engine.connect() as db:
        queued = set(db.execute(text('SELECT object_key FROM deletion_objects WHERE deletion_id=:id'),
            {'id': accepted.json()['deletion_id']}).scalars())
    assert queued == {source, output, detections, frame}
    cleanup_deletions(store.engine, objects)
    assert objects.keys == {other_source, output, unrelated}
    assert owner.delete(f'/runs/{second}').status_code == 202
    cleanup_deletions(store.engine, objects)
    assert objects.keys == {unrelated}
    assert unrelated not in objects.deleted


def test_concurrent_cleanup_serializes_last_objects_and_completes_operation(accounts):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    make, store = accounts
    make()
    operation = uuid4()
    keys = [f'tmp/{uuid4()}' for _ in range(2)]
    with store.engine.begin() as db:
        db.execute(text("INSERT INTO deletion_operations(id,target_kind,target_id,state) VALUES (:id,'run',:id,'cleaning')"), {'id': operation})
        for key in keys:
            db.execute(text('INSERT INTO deletion_objects(deletion_id,object_key) VALUES (:id,:key)'), {'id': operation, 'key': key})
    entered, release = Event(), Event()
    class PausedObjects(Objects):
        def _delete_report_temporary(self, key):
            if key in keys and not entered.is_set():
                entered.set()
                assert release.wait(5)
            super()._delete_report_temporary(key)
    objects = PausedObjects()
    with ThreadPoolExecutor() as pool:
        first = pool.submit(cleanup_deletions, store.engine, objects)
        assert entered.wait(3)
        second = pool.submit(cleanup_deletions, store.engine, objects)
        try:
            second.result(timeout=3)
            assert not any(key in objects.deleted for key in keys)
        finally:
            release.set()
        first.result(timeout=3)
    with store.engine.connect() as db:
        assert db.execute(text('SELECT state FROM deletion_operations WHERE id=:id'), {'id': operation}).scalar_one() == 'completed'
        assert db.execute(text('SELECT count(*) FROM deletion_objects WHERE deletion_id=:id'), {'id': operation}).scalar_one() == 0


def test_poison_object_is_scheduled_and_does_not_block_healthy_cleanup(accounts):
    _, store = accounts
    operation, other = uuid4(), uuid4()
    poison, healthy, unrelated = [f'tmp/{uuid4()}' for _ in range(3)]
    class PoisonObjects(Objects):
        def _delete_report_temporary(self, key):
            if key == poison:
                raise OSError('single object unavailable')
            super()._delete_report_temporary(key)
    objects = PoisonObjects()
    with store.engine.begin() as db:
        for identifier in (operation, other):
            db.execute(text("INSERT INTO deletion_operations(id,target_kind,target_id,state) VALUES (:id,'run',:id,'cleaning')"), {'id': identifier})
        for identifier, key in ((operation, poison), (operation, healthy), (other, unrelated)):
            db.execute(text('INSERT INTO deletion_objects(deletion_id,object_key) VALUES (:id,:key)'), {'id': identifier, 'key': key})
    cleanup_deletions(store.engine, objects)
    assert healthy in objects.deleted and unrelated in objects.deleted
    with store.engine.connect() as db:
        assert db.execute(text('SELECT retry_after>clock_timestamp() FROM deletion_objects WHERE deletion_id=:id'), {'id': operation}).scalar_one()
        assert db.execute(text('SELECT state FROM deletion_operations WHERE id=:id'), {'id': other}).scalar_one() == 'completed'
    with store.engine.begin() as db:
        db.execute(text('UPDATE deletion_objects SET retry_after=clock_timestamp() WHERE deletion_id=:id'), {'id': operation})
    cleanup_deletions(store.engine, Objects())


def test_cleanup_completes_preexisting_empty_operation(accounts):
    _, store = accounts
    operation = uuid4()
    with store.engine.begin() as db:
        db.execute(text("INSERT INTO deletion_operations(id,target_kind,target_id,state) VALUES (:id,'run',:id,'cleaning')"), {'id': operation})
    cleanup_deletions(store.engine, Objects())
    with store.engine.connect() as db:
        assert db.execute(text('SELECT state FROM deletion_operations WHERE id=:id'), {'id': operation}).scalar_one() == 'completed'
