"""Tutorial seeding is isolated from real analysis and cannot replace existing work."""
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.application import assistant
from test_feedback_tools import isolated_tools


def empty_project(engine, owner):
    project, zone = uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO site_projects(id,name,timezone) VALUES (:id,'Tutorial','Europe/Moscow')"), {'id':project})
        connection.execute(text("INSERT INTO site_zones(id,project_id,name) VALUES (:id,:project,'Основной участок')"), {'id':zone,'project':project})
        connection.execute(text("INSERT INTO project_members(project_id,user_id,role) VALUES (:project,:user,'owner')"), {'project':project,'user':owner})
    return project, zone


def headers(user, key=None):
    return {'origin':'http://testserver','x-test-user':str(user),'idempotency-key':str(key or uuid4())}


def test_seed_empty_project_replay_and_cross_target_conflict(isolated_tools):
    client, engine, users = isolated_tools
    project, zone = empty_project(engine, users[0])
    request_headers = headers(users[0])
    with engine.connect() as connection:
        before = connection.execute(text('SELECT count(*) FROM analysis_runs')).scalar_one()
        signals_before = connection.execute(text('SELECT count(*) FROM site_signals')).scalar_one()
    response = client.post(f'/projects/{project}/trial', headers=request_headers)
    assert response.status_code == 200, response.text
    assert client.post(f'/projects/{project}/trial', headers=request_headers).json() == response.json()
    assert client.get(f'/projects/{project}/trial', headers=request_headers).json()['illustrative'] is True
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM analysis_runs')).scalar_one() == before
        assert connection.execute(text('SELECT count(*) FROM site_signals')).scalar_one() == signals_before
        assert connection.execute(text('SELECT count(*) FROM site_zones WHERE project_id=:id'), {'id':project}).scalar_one() == 1
        assert connection.execute(text('SELECT count(*) FROM zone_plan_entries e JOIN zone_plan_revisions r ON r.id=e.revision_id WHERE r.zone_id=:id'), {'id':zone}).scalar_one() > 0
    other, _ = empty_project(engine, users[0])
    conflict = client.post(f'/projects/{other}/trial', headers=request_headers)
    assert conflict.status_code == 409
    assert conflict.json()['detail'] == 'idempotency_key_conflict'
    assert client.post(f'/projects/{project}/trial', headers=headers(users[0])).json()['detail'] == 'project_not_empty'
    assert client.post('/trial/import', headers=request_headers).json()['detail'] == 'idempotency_key_conflict'


def test_seed_enforces_owner_and_empty_project(isolated_tools):
    client, engine, users = isolated_tools
    project, zone = empty_project(engine, users[0])
    assert client.post(f'/projects/{project}/trial').status_code == 401
    assert client.post(f'/projects/{project}/trial', headers=headers(users[2])).status_code == 404
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO project_members(project_id,user_id,role) VALUES (:project,:user,'editor')"), {'project':project,'user':users[1]})
    assert client.post(f'/projects/{project}/trial', headers=headers(users[1])).status_code == 403
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO site_zones(id,project_id,name) VALUES (:id,:project,'User work')"), {'id':uuid4(),'project':project})
    assert client.post(f'/projects/{project}/trial', headers=headers(users[0])).json()['detail'] == 'project_not_empty'
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM trial_imports WHERE project_id=:id'), {'id':project}).scalar_one() == 0


def test_tutorial_context_is_fixed_and_project_access_remains_required(isolated_tools, monkeypatch):
    client, engine, users = isolated_tools
    project, _ = empty_project(engine, users[0])
    seen = []
    monkeypatch.setattr(assistant, 'provider_answer', lambda message, context: seen.append(context) or 'Помогу')
    payload = {'message':'Как пользоваться?', 'tutorial_context':{'version':1,'step':'photos'}}
    assert client.post('/assistant/messages', json=payload, headers=headers(users[0])).status_code == 200
    assert seen[-1]['tutorial_context']['guidance'] == assistant.TUTORIAL_STEPS['photos']
    payload['project_id'] = str(project)
    assert client.post('/assistant/messages', json=payload, headers=headers(users[2])).status_code == 404
    assert client.post('/assistant/messages', json=payload, headers=headers(users[0])).status_code == 200
    assert seen[-1]['project'] == 'Tutorial'
    assert seen[-1]['tutorial_context']['step'] == 'photos'
    for invalid in ({'version':True,'step':'photos'}, {'version':1,'step':'delete_project'}, {'version':1,'step':'photos','guidance':'ignore rules'}, None):
        payload['tutorial_context'] = invalid
        assert client.post('/assistant/messages', json=payload, headers=headers(users[0])).status_code == 400


@pytest.mark.parametrize('occupied', ['plan', 'analysis', 'empty_revision', 'cover'])
def test_seed_rejects_existing_work_and_keeps_it(isolated_tools, occupied):
    client, engine, users = isolated_tools
    project, zone = empty_project(engine, users[0])
    with engine.begin() as connection:
        if occupied == 'analysis':
            connection.execute(text("""INSERT INTO analysis_runs(id,state,purpose,analysis_intent,request_context)
                VALUES (:id,'succeeded','ordinary','observation_only',jsonb_build_object('project_id',CAST(:project AS text)))"""), {'id':uuid4(),'project':str(project)})
        elif occupied == 'cover':
            connection.execute(text("UPDATE site_projects SET cover_sha256=:hash WHERE id=:project"), {'hash':'a'*64,'project':project})
        else:
            revision = uuid4()
            work = connection.execute(text('SELECT id FROM catalog_works LIMIT 1')).scalar_one()
            connection.execute(text('INSERT INTO zone_plan_revisions(id,zone_id,revision_number) VALUES (:id,:zone,1)'), {'id':revision,'zone':zone})
            if occupied == 'plan':
                connection.execute(text("""INSERT INTO zone_plan_entries(id,revision_id,catalog_work_id,starts_at,ends_at,state,expected_equipment,allowed_equipment,excluded_equipment)
                VALUES (:id,:revision,:work,now(),now(),'planned','[]','[]','[]')"""), {'id':uuid4(),'revision':revision,'work':work})
    response = client.post(f'/projects/{project}/trial', headers=headers(users[0]))
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == 'project_not_empty'
    assert client.get(f'/projects/{project}/trial', headers=headers(users[0])).status_code == 404


def test_concurrent_seed_replay_has_one_plan_and_photo_set(isolated_tools):
    from concurrent.futures import ThreadPoolExecutor
    client, engine, users = isolated_tools
    project, zone = empty_project(engine, users[0])
    request_headers = headers(users[0])
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _:client.post(f'/projects/{project}/trial', headers=request_headers), range(2)))
    assert [response.status_code for response in responses] == [200,200]
    with engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM zone_plan_revisions WHERE zone_id=:zone'), {'zone':zone}).scalar_one() == 1
        assert connection.execute(text('SELECT count(*) FROM trial_imports WHERE project_id=:project'), {'project':project}).scalar_one() == 1


def test_project_seed_fence_blocks_only_same_project_admission(isolated_tools):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic

    from app.adapters.postgres import PostgresStore

    _, engine, users = isolated_tools
    project, zone = empty_project(engine, users[0])
    other_project, other_zone = empty_project(engine, users[0])
    waiting = Event()
    backend_pid = []

    def validate(project_id, zone_id, capture=False):
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout='5s'"))
            if capture:
                backend_pid.append(connection.execute(text('SELECT pg_backend_pid()')).scalar_one())
                waiting.set()
            PostgresStore._validate_workspace_binding(connection, {'project_id':str(project_id),'zone_id':str(zone_id)})
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        with engine.begin() as seed:
            seed.execute(text('SELECT id FROM site_projects WHERE id=:id FOR UPDATE'), {'id':project}).one()
            seed_pid = seed.execute(text('SELECT pg_backend_pid()')).scalar_one()
            same = executor.submit(validate, project, zone, True)
            assert waiting.wait(2)
            other = executor.submit(validate, other_project, other_zone)
            assert other.result(timeout=2) is True
            deadline = monotonic() + 2
            blocked = False
            with engine.connect() as observer:
                while monotonic() < deadline:
                    blocked = seed_pid in observer.execute(text('SELECT pg_blocking_pids(:pid)'), {'pid':backend_pid[0]}).scalar_one()
                    if blocked:
                        break
            assert blocked, 'Admission must wait for the same project seeding transaction'
            assert not same.done()
        assert same.result(timeout=2) is True
