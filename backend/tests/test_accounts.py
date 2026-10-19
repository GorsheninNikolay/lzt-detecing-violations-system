import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.postgres import PostgresStore
from app.application.accounts import router, authorize_request
from app.application.site import router as site_router
from app.application.signals import router as signals_router
from app.application.annotations import router as annotations_router


@pytest.fixture
def accounts(monkeypatch):
    if not os.getenv('TEST_DATABASE_URL'):
        pytest.skip('isolated PostgreSQL required')
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    store = PostgresStore(os.environ['TEST_DATABASE_URL'])
    from app.main import create_app
    app = create_app()
    app.state.store = store
    app.state.claim_loop = SimpleNamespace(runtime_binding=None)
    app.state.readiness = SimpleNamespace(ready=SimpleNamespace(is_set=lambda: True))
    clients = []

    def make():
        client = TestClient(app, headers={'Origin': 'http://testserver'})
        address = f'{uuid4()}@example.test'
        register = client.post('/account/register', json={'email': address, 'name': 'Tester', 'password': 'safe password 123'})
        assert register.status_code == 200, register.text
        assert register.json()['verification_required'] is False
        assert 'recovery_code' not in register.json()
        logged = client.post('/account/login', json={'email': address, 'password': 'safe password 123'})
        assert logged.status_code == 200, logged.text
        clients.append(client)
        return client, logged.json()['user']

    yield make, store
    for client in clients:
        client.close()
    store.close()


def project(client):
    result = client.post('/projects', json={'name': f'Private {uuid4()}', 'timezone': 'Europe/Moscow'})
    assert result.status_code == 201, result.text
    return result.json()


def test_private_projects_roles_invites_and_replay(accounts):
    make, store = accounts
    owner, user = make()
    member, other = make()
    outsider, _ = make()
    own = project(owner)
    second = project(member)
    identifier = own['id']
    works = owner.get('/catalog/works').json()['works']
    planned = owner.put(f'/zones/{own["default_zone_id"]}/plan', json={'expected_revision': 0, 'entries': [{
        'catalog_work_id': works[0]['id'], 'start_at': '2020-01-01T00:00:00Z',
        'end_at': '2020-01-02T00:00:00Z', 'state': 'active', 'stage_key': 'excavation',
        'expected_equipment': [], 'allowed_equipment': [], 'excluded_equipment': []}]})
    assert planned.status_code == 200, planned.text
    signal = owner.get('/signals').json()['signals'][0]
    assert outsider.get('/signals').json()['summary']['open_count'] == 0
    assert {p['id'] for p in owner.get('/projects').json()['projects']} == {identifier}
    assert {p['id'] for p in member.get('/projects').json()['projects']} == {second['id']}
    assert outsider.get(f'/projects/{identifier}/zones').status_code == 404
    assert outsider.get(f'/projects/{identifier}/cover').status_code == 404
    assert outsider.get(f'/zones/{own["default_zone_id"]}/plan').status_code == 404
    assert outsider.get(f'/signals?project_id={identifier}').status_code == 404
    invitation = owner.post(f'/projects/{identifier}/invitations', json={'email': other['email'], 'role': 'viewer'}).json()
    assert outsider.post('/invitations/accept', json={'token': invitation['token']}).status_code == 404
    notifications = member.get('/notifications').json()['notifications']
    assert len(notifications) == 1 and notifications[0]['actionable']
    assert outsider.get('/notifications').json()['notifications'] == []
    accepted = member.post('/invitations/accept', json={'invitation_id': invitation['id']})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['role'] == 'viewer'
    assert member.get(f'/projects/{identifier}/zones').status_code == 200
    assert member.patch(f'/signals/{signal["id"]}', json={'state': 'resolved'}).status_code == 403
    assert member.post(f'/projects/{identifier}/zones', json={'name': 'No'}).status_code == 403
    assert member.put(f'/zones/{own["default_zone_id"]}/plan', json={}).status_code == 403
    assert member.post(f'/projects/{identifier}/invitations', json={'role': 'editor'}).status_code == 403
    general = owner.post(f'/projects/{identifier}/invitations', json={'role': 'editor'}).json()
    assert member.post('/invitations/accept', json={'token': general['token']}).json()['role'] == 'viewer'
    assert owner.post('/invitations/accept', json={'token': general['token']}).json()['role'] == 'owner'
    owner.delete(f'/projects/{identifier}/invitations/{general["id"]}')
    assert outsider.post('/invitations/accept', json={'token': general['token']}).status_code == 404
    owner.delete(f'/projects/{identifier}/members/{other["id"]}')
    assert member.get(f'/projects/{identifier}/zones').status_code == 404
    with store.engine.begin() as conn:
        conn.execute(text("UPDATE project_invitations SET expires_at=clock_timestamp()-interval '1 second' WHERE id=:id"), {'id': invitation['id']})
    assert member.post('/invitations/accept', json={'token': invitation['token']}).status_code == 404
    key = str(uuid4())
    payload = {'name': 'Replay', 'timezone': 'UTC'}
    assert owner.post('/projects', json=payload, headers={'Idempotency-Key': key}).status_code == 201
    assert member.post('/projects', json=payload, headers={'Idempotency-Key': key}).status_code == 409


def test_sessions_profile_csrf_and_secrets(accounts):
    make, store = accounts
    client, user = make()
    assert 'password' not in str(client.get('/account/session').json())
    assert client.patch('/account/profile', json={'name': 'Stolen'}, headers={'Origin': 'http://evil.test'}).status_code == 403
    assert client.patch('/account/profile', json={'theme': 'light'}).json()['user']['theme'] == 'light'
    assert client.patch('/account/profile', json={'password': 'another password'}).status_code == 403
    assert client.patch('/account/profile', json={'email': 'new@example.test', 'current_password': 'bad'}).status_code == 403
    second = TestClient(client.app, headers={'Origin': 'http://testserver'})
    assert second.post('/account/login', json={'email': user['email'], 'password': 'safe password 123'}).status_code == 200
    assert client.patch('/account/profile', json={'password': 'another password', 'current_password': 'safe password 123'}).status_code == 200
    assert second.get('/account/session').json()['user'] is None
    assert client.get('/account/session').json()['user']['id'] == user['id']
    assert 'httponly' in second.post('/account/login', json={'email': user['email'], 'password': 'another password'}).headers['set-cookie'].lower()
    assert second.post('/account/logout').status_code == 200
    assert second.get('/account/session').json()['user'] is None
    second.close()
    with store.engine.connect() as conn:
        assert conn.execute(text('SELECT password_hash FROM account_users WHERE id=:u'), {'u': user['id']}).scalar_one().startswith('scrypt$')


def test_run_artifact_and_annotation_access(accounts):
    make, _ = accounts
    owner, _ = make()
    outsider, _ = make()
    own = project(owner)
    unknown = uuid4()
    for path in (f'/runs/{unknown}/frames/{uuid4()}/annotations', f'/runs/{unknown}/artifacts/{uuid4()}/thumbnail'):
        assert outsider.get(path).status_code == 404
    assert outsider.post('/runs/single-image', json={'project_id': own['id']}).status_code == 404
    assert outsider.post('/runs/series', json={}).status_code == 400
    anonymous = TestClient(owner.app, headers={'Origin': 'http://testserver'})
    assert anonymous.get('/projects').status_code == 401
    assert anonymous.get('/signals').status_code == 401
    assert anonymous.get('/account/session').json() == {'user': None}
    anonymous.close()


def test_recovery_and_verification_are_not_available(accounts):
    make, _ = accounts
    client, _ = make()
    for path in ('/account/recover', '/account/reset', '/account/verify'):
        assert client.post(path, json={}).status_code == 404


def test_origin_with_api_root_path(accounts, monkeypatch):
    monkeypatch.setenv('PUBLIC_APP_URL', '')
    make, _ = accounts
    client, _ = make()
    client.app.root_path = '/api'
    assert client.patch('/api/account/profile', json={'theme': 'system'}).status_code == 200
    assert client.patch('/api/account/profile', json={'theme': 'light'}, headers={'Origin': 'http://foreign.test'}).status_code == 403


def test_actual_run_lists_and_files_are_member_scoped(accounts):
    import json
    make, store = accounts
    owner, _ = make()
    other, _ = make()
    own, foreign = project(owner), project(other)
    owned_run, foreign_run, orphan_run = uuid4(), uuid4(), uuid4()
    with store.engine.begin() as conn:
        for run, context in ((owned_run, {'project_id': own['id']}), (foreign_run, {'project_id': foreign['id']}), (orphan_run, {})):
            conn.execute(text("""INSERT INTO analysis_runs(id,state,purpose,analysis_intent,request_context)
                VALUES (:id,'queued','ordinary','observation_only',CAST(:context AS jsonb))"""), {'id': run, 'context': json.dumps(context)})
    listed = owner.get('/runs')
    assert listed.status_code == 200, listed.text
    assert listed.json()['total'] == 1
    assert [run['id'] for run in listed.json()['runs']] == [str(owned_run)]
    assert owner.get('/runs?unassigned=true').json()['total'] == 0
    assert owner.get(f'/runs?project_id={foreign["id"]}').status_code == 404
    assert owner.get(f'/runs/{owned_run}').status_code == 200
    for run in (foreign_run, orphan_run):
        assert owner.get(f'/runs/{run}').status_code == 404
        assert owner.get(f'/runs/{run}/artifacts/{uuid4()}').status_code == 404
        assert owner.get(f'/runs/{run}/artifacts/{uuid4()}/thumbnail').status_code == 404
        assert owner.get(f'/runs/{run}/frames/{uuid4()}/annotations').status_code == 404
        assert owner.post(f'/runs/{run}/frames/{uuid4()}/annotations', json={}).status_code == 404
        assert owner.post(f'/runs/{run}/retry', json={}).status_code == 404


def test_target_invitation_remains_bound_to_account_after_email_changes(accounts):
    make, store = accounts
    owner, _ = make()
    recipient, user = make()
    outsider, _ = make()
    own = project(owner)
    invitation = owner.post(f'/projects/{own["id"]}/invitations', json={'email': user['email'], 'role': 'editor'}).json()
    new_email = f'{uuid4()}@example.test'
    assert recipient.patch('/account/profile', json={'email': new_email, 'current_password': 'safe password 123'}).status_code == 200
    assert outsider.patch('/account/profile', json={'email': user['email'], 'current_password': 'safe password 123'}).status_code == 200
    assert outsider.post('/invitations/accept', json={'token': invitation['token']}).status_code == 404
    assert recipient.post('/invitations/accept', json={'token': invitation['token']}).status_code == 200
    with store.engine.begin() as conn:
        conn.execute(text("UPDATE account_sessions SET expires_at=clock_timestamp()-interval '1 second' WHERE user_id=:u"), {'u': user['id']})
    assert recipient.get('/account/session').json()['user'] is None


def test_throttle_registration_and_login(accounts):
    make, store = accounts
    client, user = make()
    with store.engine.begin() as conn:
        conn.execute(text('UPDATE account_throttles SET attempts=15 WHERE key=:key'),
                     {'key': __import__('hashlib').sha256(f'login:testclient:{user["email"]}'.encode()).hexdigest()})
    assert client.post('/account/login', json={'email': user['email'], 'password': 'safe password 123'}).status_code == 429


def test_campaign_reads_require_only_existing_admin_session(accounts):
    import secrets
    from app.application.accounts import digest
    make, store = accounts
    owner, _ = make()
    outsider, _ = make()
    own = project(owner)
    campaign, ordinary, orphan = uuid4(), uuid4(), uuid4()
    token = secrets.token_urlsafe(32)
    with store.engine.begin() as conn:
        conn.execute(text("""INSERT INTO analysis_runs(id,state,purpose,analysis_intent,request_context,binding_kind)
            VALUES (:campaign,'queued','comparison_campaign','observation_only','{}','comparison_cell'),
                   (:ordinary,'queued','ordinary','observation_only',jsonb_build_object('project_id',CAST(:project AS text)),NULL),
                   (:orphan,'queued','ordinary','observation_only','{}',NULL)"""),
            {'campaign': campaign, 'ordinary': ordinary, 'orphan': orphan, 'project': own['id']})
        conn.execute(text("INSERT INTO admin_sessions(token_hash,csrf,expires_at) VALUES (:token,'test',clock_timestamp()+interval '1 hour')"),
                     {'token': digest(token)})
    admin = TestClient(owner.app, base_url='https://testserver')
    admin.cookies.set('owner_session', token)
    assert admin.get('/account/session').json()['user'] is None
    assert admin.get(f'/runs/{campaign}').status_code == 200
    # A missing artifact reaches normal resolution, rather than failing account authentication.
    artifact = uuid4()
    reached = []
    original = store.resolve_run_artifact
    store.resolve_run_artifact = lambda run, identifier: reached.append((run, identifier)) or None
    try:
        assert admin.get(f'/runs/{campaign}/artifacts/{artifact}').status_code == 404
        assert reached == [(campaign, artifact)]
    finally:
        store.resolve_run_artifact = original
    assert outsider.get(f'https://testserver/runs/{campaign}').status_code == 401
    assert outsider.get(f'https://testserver/runs/{campaign}/artifacts/{artifact}').status_code == 401
    assert outsider.get(f'/runs/{ordinary}').status_code == 404
    assert admin.get(f'/runs/{ordinary}').status_code == 401
    assert admin.get(f'/runs/{orphan}').status_code == 404
    admin.close()


def test_demo_password_boundary():
    from fastapi import HTTPException
    from app.application.accounts import password
    from app.application.admin_password import verify_password
    with pytest.raises(HTTPException) as error:
        password('12345678')
    assert error.value.status_code == 400
    assert verify_password('demo-pass', password('demo-pass'))
