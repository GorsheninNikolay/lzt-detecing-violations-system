import base64
import io
import os
import secrets
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text, event
from sqlalchemy.engine import make_url

from app.adapters.postgres import PostgresStore
from app.adapters.artifacts import ArtifactStore
from app.config import Config
from app.application.engagement import router, validate_feedback
from app.application.site import router as site_router
from app.application.signals import router as signals_router
from app.application.admin_password import hash_password, verify_password


def image_data():
    output = io.BytesIO()
    Image.new('RGB',(8,8)).save(output,format='PNG')
    return base64.b64encode(output.getvalue()).decode()


def test_password_and_image_boundaries():
    secret = secrets.token_urlsafe(24)
    encoded = hash_password(secret)
    assert secret not in encoded and verify_password(secret, encoded)
    assert not verify_password(secrets.token_urlsafe(24), encoded)
    assert not verify_password(None, encoded)
    valid = {'category':'idea','message':' Useful ', 'attachments':[{'data':image_data()}]}
    assert validate_feedback(valid)[1] == 'Useful'
    for invalid in ({**valid,'message':' '}, {**valid,'message':'a'*5001}, {**valid,'attachments':[{'data':'broken'}]},
                    {**valid,'attachments':[{'data':image_data()}]*6}, {**valid,'context':{'pathname':'/x?private=1'}},
                    {**valid,'attachments':[{'data':base64.b64encode(b'not an image').decode()}]}):
        with pytest.raises(Exception):
            validate_feedback(invalid)


@pytest.fixture
def service():
    if not os.getenv('TEST_DATABASE_URL') or not os.getenv('TEST_S3_BUCKET'):
        pytest.fail('Explicit isolated TEST_DATABASE_URL and TEST_S3_BUCKET required')
    test_url = make_url(os.environ['TEST_DATABASE_URL'])
    app_url = make_url(os.environ['DATABASE_URL'])
    if (test_url.host,test_url.port,test_url.database) == (app_url.host,app_url.port,app_url.database):
        pytest.fail('Test and application database targets must differ')
    if os.environ['TEST_S3_BUCKET'] == os.environ['S3_BUCKET']:
        pytest.fail('Test and application buckets must differ')
    store = PostgresStore(os.environ['TEST_DATABASE_URL'])
    with store.engine.begin() as connection:
        connection.execute(text('TRUNCATE feedback_attachments,feedback,admin_sessions,admin_credentials,request_limits,activity_attribution,anonymous_events,anonymous_sessions,anonymous_browsers,project_requests'))
    app = FastAPI()
    app.include_router(router)
    app.include_router(site_router)
    app.include_router(signals_router)
    app.state.store = store
    app.state.artifacts = ArtifactStore(replace(Config.from_env(), database_url=os.environ["TEST_DATABASE_URL"], s3_bucket=os.environ["TEST_S3_BUCKET"]))
    app.state.readiness = type('Ready',(),{'ready':type('Event',(),{'is_set':lambda self:True})()})()
    with TestClient(app, base_url='https://testserver') as client:
        yield client, store
    store.close()


def login(client, store):
    secret = secrets.token_urlsafe(24)
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO admin_credentials VALUES ('gorshenin-nik',:hash)"), {'hash':hash_password(secret)})
    response = client.post('/admin/login',headers={'origin':'https://testserver'},json={'login':'gorshenin-nik','password':secret})
    assert response.status_code == 200, response.text
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    return secret, {'origin':'https://testserver','x-csrf-token':response.json()['csrf']}


def test_authentication_csrf_expiry_revocation_and_throttle(service):
    client, store = service
    for path in ('/admin/overview','/admin/feedback',f'/admin/attachments/{uuid4()}','/admin/session'):
        assert client.get(path).status_code == 401
    for path in ('/admin/logout','/admin/password',f'/admin/feedback/{uuid4()}/open'):
        assert client.post(path).status_code == 401
    assert client.post('/admin/login',headers={'origin':'https://testserver'},json={}).status_code == 503
    secret, headers = login(client,store)
    assert client.get('/admin/session').status_code == 200
    assert client.post('/admin/logout').status_code == 403
    assert client.post('/admin/logout',headers={**headers,'origin':'https://evil.example'}).status_code == 403
    with store.engine.connect() as connection:
        original_hash = connection.execute(text('SELECT password_hash FROM admin_credentials')).scalar_one()
        original_sessions = connection.execute(text('SELECT token_hash FROM admin_sessions')).scalars().all()
    for value in ({'new_password': secrets.token_urlsafe(24)}, {'current_password': secrets.token_urlsafe(24), 'new_password':secrets.token_urlsafe(24)}):
        assert client.post('/admin/password',headers=headers,json=value).status_code == 401
        assert client.get('/admin/session').status_code == 200
        with store.engine.connect() as connection:
            assert connection.execute(text('SELECT password_hash FROM admin_credentials')).scalar_one() == original_hash
            assert connection.execute(text('SELECT token_hash FROM admin_sessions')).scalars().all() == original_sessions
    replacement = secrets.token_urlsafe(24)
    assert client.post('/admin/password',headers=headers,json={'current_password':secret,'new_password':replacement}).status_code == 200
    assert client.get('/admin/session').status_code == 401
    assert client.post('/admin/login',headers={'origin':'https://testserver'},json={'login':'gorshenin-nik','password':secret}).status_code == 401
    response = client.post('/admin/login',headers={'origin':'https://testserver'},json={'login':'gorshenin-nik','password':replacement})
    assert response.status_code == 200
    with store.engine.begin() as connection:
        connection.execute(text("UPDATE admin_sessions SET expires_at=clock_timestamp()-interval '1 second'"))
    assert client.get('/admin/session').status_code == 401
    for _ in range(12):
        response = client.post('/admin/login',headers={'origin':'https://testserver'},json={})
    assert response.status_code == 429
    with TestClient(client.app,base_url='http://testserver') as insecure:
        assert insecure.get('/admin/session').status_code == 403


def test_feedback_atomic_publication_retry_and_private_images(service, monkeypatch):
    client, store = service
    payload = {'category':'problem','message':'Frame issue', 'context':{'pathname':'/projects'},'attachments':[{'data':image_data()}]}
    key = str(uuid4())
    first = client.post('/feedback',headers={'idempotency-key':key},json=payload)
    assert first.status_code == 200, first.text
    assert first.json()['message'] == 'Спасибо, отзыв сохранён'
    assert client.post('/feedback',headers={'idempotency-key':key},json=payload).json() == first.json()
    assert client.post('/feedback',headers={'idempotency-key':key},json={**payload,'message':'different'}).status_code == 409
    _, headers = login(client,store)
    detail = client.post(f'/admin/feedback/{first.json()["id"]}/open',headers=headers)
    assert detail.status_code == 200 and detail.json()['read_at']
    image_id = detail.json()['attachments'][0]['id']
    image = client.get(f'/admin/attachments/{image_id}')
    assert image.content == base64.b64decode(image_data()) and image.headers['content-type'] == 'image/png'
    assert client.post('/admin/logout',headers=headers).status_code == 200
    assert client.get(f'/admin/attachments/{image_id}').status_code == 401
    original = client.app.state.artifacts.client.put_object
    monkeypatch.setattr(client.app.state.artifacts.client,'put_object',lambda **kwargs: (_ for _ in ()).throw(RuntimeError()))
    failure_key = str(uuid4())
    assert client.post('/feedback',headers={'idempotency-key':failure_key},json=payload).status_code == 503
    with store.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM feedback')).scalar_one() == 1
    monkeypatch.setattr(client.app.state.artifacts.client,'put_object',original)
    assert client.post('/feedback',headers={'idempotency-key':failure_key},json=payload).status_code == 200


def test_sessions_dedup_project_attribution_and_statistics(service):
    client, store = service
    browser = str(uuid4())
    event = {'browser_id':browser,'event_id':str(uuid4()),'kind':'visit'}
    assert client.post('/analytics/events',json=event).status_code == 200
    client.post('/analytics/events',json=event)
    client.post('/analytics/events',json={**event,'event_id':str(uuid4())})
    with store.engine.begin() as connection:
        assert connection.execute(text('SELECT count(*) FROM anonymous_sessions')).scalar_one() == 1
        assert connection.execute(text('SELECT count(*) FROM anonymous_events')).scalar_one() == 2
        connection.execute(text("UPDATE anonymous_browsers SET last_at=clock_timestamp()-interval '30 minutes'"))
    client.post('/analytics/events',json=event)
    with store.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM anonymous_sessions')).scalar_one() == 1
    client.post('/analytics/events',json={**event,'event_id':str(uuid4())})
    key = str(uuid4())
    payload = {'name': 'Analytics fixture', 'timezone':'Europe/Moscow'}
    created = client.post('/projects',headers={'idempotency-key':key,'x-browser-id':browser},json=payload)
    replay = client.post('/projects',headers={'idempotency-key':key,'x-browser-id':str(uuid4())},json=payload)
    assert created.json() == replay.json()
    assert client.post('/projects',headers={'idempotency-key':key},json={**payload,'name':'Different'}).status_code == 409
    _, headers = login(client,store)
    overview = client.get('/admin/overview?period=all')
    assert overview.status_code == 200, overview.text
    data = overview.json()
    assert data['cards']['visits'] == 2 and data['cards']['visitors'] == 1
    assert data['funnel']['created_project'] == 1
    assert client.get('/admin/overview?period=bad').status_code == 400
    assert len(data['daily']) >= 1
    with store.engine.connect() as connection:
        owner = connection.execute(text("SELECT browser_id FROM activity_attribution WHERE object_id=:id"), {'id':created.json()['id']}).scalar_one()
        assert str(owner) == browser


def test_decoded_image_limits_and_corruption():
    raw = base64.b64decode(image_data())
    exact = base64.b64encode(raw + b'\0' * (5_000_000 - len(raw))).decode()
    payload = {'category':'other','message':'Image boundary','attachments':[{'data':exact}]*3}
    assert len(validate_feedback(payload)[3]) == 3
    for invalid in ({**payload,'attachments':[{'data':exact}]*4},
                    {**payload,'attachments':[{'data':base64.b64encode(raw+b'\0'*(5_000_001-len(raw))).decode()}]},
                    {**payload,'category':[]}, {**payload,'context':[]}, {**payload,'attachments':{}},
                    {**payload,'attachments':[None]}):
        with pytest.raises(Exception):
            validate_feedback(invalid)
    output = io.BytesIO()
    Image.new('RGB',(64,64)).save(output,format='JPEG')
    with pytest.raises(Exception):
        validate_feedback({**payload,'attachments':[{'data':base64.b64encode(output.getvalue()[:-16]).decode()}]})


def test_authoritative_historical_counts_and_moscow_dates(service):
    client, store = service
    login(client,store)
    before = client.get('/admin/overview?period=all').json()
    with store.engine.begin() as connection:
        for created,state,purpose in [('2026-09-25T20:59:00Z','succeeded','ordinary'),
                                      ('2026-09-25T21:01:00Z','failed','ordinary'),
                                      (None,'succeeded','ordinary'),
                                      ('2026-09-25T21:02:00Z','succeeded','profile_admission')]:
            connection.execute(text('''INSERT INTO analysis_runs(id,state,purpose,analysis_intent,created_at)
                VALUES (:id,:state,:purpose,'observation_only',:created)'''),
                {'id':uuid4(),'state':state,'purpose':purpose,'created':created})
    after = client.get('/admin/overview?period=all').json()
    assert after['cards']['launched'] - before['cards']['launched'] == 3
    assert after['cards']['succeeded'] - before['cards']['succeeded'] == 2
    assert after['cards']['failed'] - before['cards']['failed'] == 1
    assert after['cards']['unknown_dates'] - before['cards']['unknown_dates'] == 1
    previous = {row['day']:row['analyses'] for row in before['daily']}
    actual = {row['day']:row['analyses'] for row in after['daily']}
    assert actual['2026-09-25'] - previous.get('2026-09-25',0) == 1
    assert actual['2026-09-26'] - previous.get('2026-09-26',0) == 1
    assert after['funnel'] == before['funnel']
    assert client.get('/admin/overview?period=7').json()['cards']['unknown_dates'] == 0


@pytest.mark.parametrize('key', ['project_id','analysis_id'])
@pytest.mark.parametrize('value', [{}, [], None, '', 0, False, 'not-a-uuid'])
def test_every_supplied_context_identifier_is_validated(key, value):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as rejected:
        validate_feedback({'category':'idea','message':'Context','context':{key:value}})
    assert rejected.value.status_code == 400


def test_acceptance_before_visit_has_ownership_and_replays_never_reassign(service):
    from app.application import submission
    client, store = service
    browser, other = str(uuid4()), str(uuid4())
    project = client.post('/projects',headers={'x-browser-id':browser},json={'name':'First action','timezone':'UTC'}).json()
    from app.application.deepseek_runtime import provision
    profile = provision(store, 'test-folder')
    profile_snapshot, _ = store.require_authorized(profile)
    image = io.BytesIO(); Image.new('RGB',(8,8)).save(image,format='JPEG')
    encoded = base64.b64encode(image.getvalue()).decode()
    body = {'cloud_processing_consent':True,'intent':'observation_only','scenario':'ownership','observation_area':'Основной участок','period':'2026-09-26T12:00:00+03:00','project_id':project['id'],'zone_id':project['default_zone_id'],'capture_times':['2026-09-26T12:00:00+03:00'],'image_base64':encoded}
    key = str(uuid4())
    artifacts = client.app.state.artifacts
    _, single = submission.submit(store,artifacts,key,body,profile,1,profile_snapshot,browser_id=browser)
    assert submission.submit(store,artifacts,key,body,profile,1,profile_snapshot,browser_id=other)[1] == single
    with store.engine.begin() as connection:
        connection.execute(text("UPDATE analysis_runs SET state='failed' WHERE id=:id"),{'id':single})
    successor = store.retry_ordinary(single,profile,1,profile_snapshot,artifacts,browser_id=browser)
    assert store.retry_ordinary(single,profile,1,profile_snapshot,artifacts,browser_id=other) == successor
    series_body = {**body,'images_base64':[encoded,encoded],'capture_times':body['capture_times']*2}
    del series_body['image_base64']
    _, series = submission.submit_series(store,artifacts,str(uuid4()),series_body,profile,1,profile_snapshot,browser_id=other)
    with store.engine.begin() as connection:
        owners = dict(connection.execute(text("SELECT object_id,browser_id FROM activity_attribution WHERE kind='run' AND object_id=ANY(:ids)"),{'ids':[single,successor,series]}).all())
        assert str(owners[single]) == str(owners[successor]) == browser
        assert str(owners[series]) == other
        connection.execute(text("UPDATE analysis_runs SET state='succeeded' WHERE id=:id"),{'id':successor})
        assert connection.execute(text('SELECT count(*) FROM anonymous_sessions')).scalar_one() == 2
    client.post('/analytics/events',json={'browser_id':browser,'event_id':str(uuid4()),'kind':'visit'})
    login(client,store)
    data = client.get('/admin/overview?period=all').json()
    assert data['funnel'] == {'visited':2,'created_project':1,'succeeded':1}
    assert data['cards']['visits'] == 2

    def fail_attribution(_connection, cursor, statement, _parameters, _context, _many):
        if 'INSERT INTO activity_attribution' in statement:
            cursor.execute('SELECT * FROM missing_attribution_fault_fixture')
    event.listen(store.engine, 'before_cursor_execute', fail_attribution)
    try:
        _, accepted = submission.submit(store, artifacts, str(uuid4()), body, profile, 1, profile_snapshot, browser_id=str(uuid4()))
    finally:
        event.remove(store.engine, 'before_cursor_execute', fail_attribution)
    with store.engine.connect() as connection:
        assert connection.execute(text("SELECT state FROM analysis_runs WHERE id=:id"), {'id': accepted}).scalar_one() == 'queued'
        assert connection.execute(text("SELECT state FROM submission_requests WHERE run_id=:id"), {'id': accepted}).scalar_one() == 'accepted'
        assert connection.execute(text("SELECT count(*) FROM activity_attribution WHERE kind='run' AND object_id=:id"), {'id': accepted}).scalar_one() == 0


def test_real_attribution_sql_failure_does_not_abort_project_commit(service):
    client,store=service
    browser=str(uuid4())
    def fail(_connection,cursor,statement,_parameters,_context,_many):
        if 'INSERT INTO activity_attribution' in statement:
            cursor.execute('SELECT * FROM missing_attribution_fault_fixture')
    event.listen(store.engine,'before_cursor_execute',fail)
    try:
        response=client.post('/projects',headers={'x-browser-id':browser},json={'name':'Survives analytics fault','timezone':'UTC'})
    finally:
        event.remove(store.engine,'before_cursor_execute',fail)
    assert response.status_code == 201, response.text
    with store.engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM site_projects WHERE id=:id'),{'id':response.json()['id']}).scalar_one() == 1
        assert connection.execute(text('SELECT count(*) FROM anonymous_browsers WHERE id=:id'),{'id':browser}).scalar_one() == 0


def test_latest_project_activity_includes_plan_confirmation_and_signal_updates(service):
    client,store=service
    login(client,store)
    project=client.post('/projects',json={'name':'Activity timeline','timezone':'UTC'}).json()
    revision,run,signal=uuid4(),uuid4(),uuid4()
    def latest():
        return next(item['latest_activity'] for item in client.get('/admin/overview').json()['projects'] if item['id']==project['id'])
    with store.engine.begin() as connection:
        connection.execute(text("UPDATE site_projects SET created_at='2026-01-01T00:00:00Z' WHERE id=:id"),{'id':project['id']})
        connection.execute(text("INSERT INTO zone_plan_revisions(id,zone_id,revision_number,created_at) VALUES (:id,:zone,1,'2026-01-02T00:00:00Z')"),{'id':revision,'zone':project['default_zone_id']})
    assert latest().startswith('2026-01-02')
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs(id,state,purpose,analysis_intent,request_context,created_at) VALUES (:id,'succeeded','ordinary','observation_only',jsonb_build_object('project_id',CAST(:project AS text)),NULL)"),{'id':run,'project':project['id']})
        connection.execute(text("INSERT INTO stage_confirmations(run_id,stage,created_at) VALUES (:run,'excavation','2026-01-03T00:00:00Z')"),{'run':run})
    assert latest().startswith('2026-01-03')
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO site_signals(id,fingerprint,zone_id,revision_id,kind,basis,created_at) VALUES (:id,:fingerprint,:zone,:revision,'test','{}','2026-01-04T00:00:00Z')"),{'id':signal,'fingerprint':str(signal),'zone':project['default_zone_id'],'revision':revision})
    assert latest().startswith('2026-01-04')
    assert client.patch(f'/signals/{signal}',json={'state':'in_progress','comment':'Checked'}).status_code==200
    with store.engine.connect() as connection:
        updated=connection.execute(text('SELECT updated_at FROM site_signals WHERE id=:id'),{'id':signal}).scalar_one()
    assert latest()==updated.isoformat()
