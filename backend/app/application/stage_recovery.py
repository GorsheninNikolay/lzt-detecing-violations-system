"""Explicit admission for one durable recovery of a failed attempt."""
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import text

from app.adapters.postgres import AdmissionStoreError
from app.profiles.deepseek import DeepSeek, validate_consent


def retry_stage(store, run_id, stage, key, artifacts, api_key, actor=None, *, ready=True, binding=None):
    with store.engine.connect() as db:
        source = db.execute(text("SELECT * FROM analysis_runs WHERE id=:id AND purpose='ordinary'"), {'id':run_id}).mappings().first()
        if not source:
            raise AdmissionStoreError('run_not_found')
        replay = db.execute(text('SELECT id,failed_stage,actor_id FROM run_attempts WHERE run_id=:run AND idempotency_key=:key'),
                            {'run':run_id,'key':key}).first()
        if replay:
            if replay.failed_stage != stage or str(replay.actor_id) != str(actor):
                raise AdmissionStoreError('idempotency_conflict')
            if actor:
                role = db.execute(text('SELECT role FROM project_members WHERE project_id=:p AND user_id=:u'),
                                  {'p':source['request_context'].get('project_id'),'u':actor}).scalar()
                if role not in ('owner','editor'):
                    raise HTTPException(403, 'insufficient_project_role')
            return replay.id
        if not ready:
            raise AdmissionStoreError('service_not_ready')
        if binding is not None and (source['profile_id'],source['authorization_revision']) != binding:
            raise AdmissionStoreError('profile_unauthorized')
        if not source['profile_snapshot'] or source['profile_snapshot'].get('kind') != 'deepseek':
            raise AdmissionStoreError('profile_retired')
        snapshot = source['profile_snapshot']
        store.require_authorized(source['profile_id'], source['authorization_revision'])
        if api_key is None:
            from app.config import Config
            api_key = Config.from_env().api_key_for(snapshot)
        DeepSeek(snapshot, api_key)
        validate_consent(source['request_context'], snapshot)
        inputs = db.execute(text('''SELECT i.*,a.key FROM run_inputs i JOIN artifact_metadata a ON a.id=i.artifact_id
            WHERE i.run_id=:id ORDER BY i.ordinal'''), {'id':run_id}).mappings().all()
    if not inputs:
        raise AdmissionStoreError('retry_source_unavailable')
    from app.adapters.artifacts import ArtifactGateError
    try:
        for frame in inputs:
            artifacts.read_verified(frame['key'], frame['sha256'], frame['size'])
    except ArtifactGateError:
        raise AdmissionStoreError('retry_source_unavailable') from None
    with store.engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock_shared(804298270115)'))
        project = source['request_context'].get('project_id')
        if project:
            if not db.execute(text('SELECT id FROM site_projects WHERE id=:id FOR UPDATE'), {'id':project}).first():
                raise AdmissionStoreError('run_not_found')
            if actor:
                role = db.execute(text('SELECT role FROM project_members WHERE project_id=:p AND user_id=:u'),
                                  {'p':project, 'u':actor}).scalar()
                if role not in ('owner','editor'):
                    raise HTTPException(403, 'insufficient_project_role')
        run = db.execute(text('SELECT * FROM analysis_runs WHERE id=:id FOR UPDATE'), {'id':run_id}).mappings().first()
        if not run:
            raise AdmissionStoreError('run_not_found')
        replay = db.execute(text('SELECT id,failed_stage,actor_id FROM run_attempts WHERE run_id=:run AND idempotency_key=:key'),
                            {'run':run_id,'key':key}).first()
        if replay:
            if replay.failed_stage != stage or str(replay.actor_id) != str(actor):
                raise AdmissionStoreError('idempotency_conflict')
            return replay.id
        auth = db.execute(text('SELECT state,revision FROM profile_authorizations WHERE profile_id=:id FOR SHARE'),
                          {'id':run['profile_id']}).first()
        if not auth or auth.state != 'enabled' or auth.revision != run['authorization_revision']:
            raise AdmissionStoreError('profile_unauthorized')
        stages = [dict(s) for s in db.execute(text('SELECT ordinal,name,state,reason FROM analysis_stages WHERE run_id=:run ORDER BY ordinal'),
                                             {'run':run_id}).mappings()]
        failed = next((s for s in stages if s['name'] == stage and s['state'] == 'failed'), None)
        parent = db.execute(text('SELECT status FROM run_attempts WHERE id=:id'), {'id':run['current_attempt_id']}).scalar()
        if run['state'] != 'failed' or parent != 'failed' or not failed:
            raise AdmissionStoreError('retry_ineligible')
        if db.execute(text('SELECT 1 FROM run_attempts WHERE parent_attempt_id=:id'), {'id':run['current_attempt_id']}).first():
            raise AdmissionStoreError('retry_ineligible')
        attempt = uuid.uuid4()
        db.execute(text('''INSERT INTO run_attempts(id,run_id,parent_attempt_id,failed_stage,actor_id,idempotency_key,status,before_stages)
            VALUES (:id,:run,:parent,:stage,:actor,:key,'queued',CAST(:before AS jsonb))'''),
            {'id':attempt,'run':run_id,'parent':run['current_attempt_id'],'stage':stage,'actor':actor,'key':key,'before':json.dumps(stages)})
        db.execute(text('''INSERT INTO attempt_call_refs(attempt_id,call_key,call_id)
            SELECT :attempt,call_key,call_id FROM attempt_call_refs WHERE attempt_id=:parent'''),
            {'attempt':attempt,'parent':run['current_attempt_id']})
        db.execute(text("UPDATE analysis_stages SET state='pending',reason=NULL WHERE run_id=:run AND ordinal>=:ordinal AND state IN ('failed','skipped','pending','running')"),
                   {'run':run_id,'ordinal':failed['ordinal']})
        db.execute(text("UPDATE analysis_runs SET current_attempt_id=:attempt,state='queued',error_code=NULL,lease_owner=NULL,lease_expires_at=NULL WHERE id=:run"),
                   {'run':run_id,'attempt':attempt})
        return attempt


def retry_hints(store, run):
    eligible = False
    observer = None
    try:
        from app.config import Config
        profile, _ = store.require_authorized(uuid.UUID(run['profile_id']), run['authorization_revision'])
        observer = DeepSeek(profile, Config.from_env().api_key_for(profile))
        validate_consent(run.get('context', {}), profile)
        eligible = run['state'] == 'failed' and profile == run.get('profile_snapshot')
    except (ValueError, AdmissionStoreError, TypeError, KeyError):
        pass
    with store.engine.connect() as db:
        attempt = db.execute(text('SELECT current_attempt_id FROM analysis_runs WHERE id=:run'), {'run':run['run_id']}).scalar()
        rows = db.execute(text('SELECT id,parent_attempt_id,failed_stage,status,created_at FROM run_attempts WHERE run_id=:run ORDER BY created_at,id'),
                          {'run':run['run_id']}).mappings().all()
    run['current_attempt_id'] = str(attempt)
    run['attempts'] = [{**r,'id':str(r['id']),'parent_attempt_id':str(r['parent_attempt_id']) if r['parent_attempt_id'] else None,
                        'created_at':r['created_at'].isoformat()} for r in rows]
    for stage in run['stages']:
        stage['retryable'] = eligible and stage['state'] == 'failed'
        stage['retry_cost'] = stage['retryable']
        if stage['retryable'] and observer:
            calls = run.get('ai_evidence', [])
            effective = {c.get('input_id') for c in calls if c.get('kind') == 'frame' and c.get('effective')}
            originals = [c for c in calls if c.get('kind') == 'assessment']
            if len(effective) == len(run.get('inputs', [])) and originals:
                original = originals[-1]
                try:
                    observer.revalidate('assessment', original['context'], original['result'])
                    stage['retry_cost'] = False
                except (ValueError, TypeError, KeyError, AttributeError):
                    pass
    return run
