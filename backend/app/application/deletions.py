"""Explicit graph deletion and durable, reference-aware object cleanup."""
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.application.accounts import auth_required, current_user, locked_project_owner

router = APIRouter()
MANAGEMENT_LOCK = 804298270115


def lock_admission(connection):
    acquired = connection.execute(text('SELECT pg_try_advisory_xact_lock(:key)'), {'key': MANAGEMENT_LOCK}).scalar_one()
    if not acquired:
        raise HTTPException(409, 'deletion_active_work')


def lock_object(connection, key):
    connection.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,804298270116))'), {'key': key})


def operation_response(row):
    return {'deletion_id': str(row['id']), 'status': row['state']}


def requester(request):
    return current_user(request)['id'] if auth_required() else None


def authorize_operation(row, actor):
    if str(row['requester_id']) != str(actor):
        raise HTTPException(404, 'deletion_not_found')


def _video_result_keys(result):
    if not isinstance(result, dict):
        return
    for field in ('artifact_key', 'detections_artifact_key'):
        if isinstance(result.get(field), str) and result[field]:
            yield result[field]
    frames = result.get('selected_frames')
    if isinstance(frames, list):
        for frame in frames:
            if isinstance(frame, dict) and isinstance(frame.get('artifact_key'), str) and frame['artifact_key']:
                yield frame['artifact_key']


def _delete_rows(connection, operation, table, predicate, values):
    columns = connection.execute(text('''SELECT a.attname FROM pg_index i
        JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey)
        WHERE i.indrelid=to_regclass(:table) AND i.indisprimary ORDER BY a.attnum'''),
        {'table': table}).scalars().all()
    row_key = 'jsonb_build_object(' + ','.join(f"'{column}',t.{column}" for column in columns) + ')'
    connection.execute(text(f'''INSERT INTO deletion_row_authorizations(deletion_id,table_name,row_key)
        SELECT :operation,:table,{row_key} FROM {table} t WHERE {predicate}'''),
        {**values, 'operation': operation, 'table': table})
    connection.execute(text(f'DELETE FROM {table} t WHERE {predicate}'), values)


def _tombstone_keys(connection, kind, query, values):
    connection.execute(text(f'''INSERT INTO deleted_request_keys(kind,request_key,project_id)
        SELECT :kind,request_key,project_id FROM ({query}) keys ON CONFLICT DO NOTHING'''),
        {**values, 'kind': kind})


def accept_deletion(request, target_kind, target_id):
    actor = requester(request)
    with request.app.state.store.engine.begin() as connection:
        lock_admission(connection)
        previous = connection.execute(text('SELECT * FROM deletion_operations WHERE target_kind=:kind AND target_id=:id'),
                                      {'kind': target_kind, 'id': target_id}).mappings().first()
        if previous:
            authorize_operation(previous, actor)
            return operation_response(previous)
        project_id = target_id if target_kind == 'project' else connection.execute(text('''
            SELECT (request_context->>'project_id')::uuid FROM analysis_runs WHERE id=:id AND purpose='ordinary'
            UNION ALL SELECT project_id FROM video_jobs WHERE id=:id'''), {'id': target_id}).scalar()
        if not project_id:
            raise HTTPException(404, 'run_not_found')
        if target_kind == 'project':
            locked_project_owner(connection, request, project_id)
        else:
            if not connection.execute(text('SELECT id FROM site_projects WHERE id=:id FOR UPDATE'), {'id': project_id}).first():
                raise HTTPException(404, 'project_not_found')
            if auth_required():
                role = connection.execute(text('SELECT role FROM project_members WHERE project_id=:p AND user_id=:u'),
                                          {'p': project_id, 'u': actor}).scalar()
                if not role:
                    raise HTTPException(404, 'run_not_found')
                if role not in ('owner', 'editor'):
                    raise HTTPException(403, 'insufficient_project_role')
        params = {'project': project_id, 'target': target_id, 'whole': target_kind == 'project'}
        runs = connection.execute(text('''SELECT id,state FROM analysis_runs
            WHERE purpose='ordinary' AND request_context->>'project_id'=CAST(:project AS text)
            AND (:whole OR id=:target) FOR UPDATE'''), params).all()
        videos = connection.execute(text('''SELECT id,state FROM video_jobs WHERE project_id=:project
            AND (:whole OR id=:target) FOR UPDATE'''), params).all()
        if target_kind == 'run' and not runs and not videos:
            raise HTTPException(404, 'run_not_found')
        if any(row.state in ('queued', 'running') for row in [*runs, *videos]):
            raise HTTPException(409, 'deletion_active_work')
        if target_kind == 'project' and connection.execute(text('''SELECT 1 FROM submission_requests
            WHERE state='publishing' AND (project_id=:project OR project_id IS NULL) LIMIT 1'''), params).first():
            raise HTTPException(409, 'deletion_publishing_submission')
        if target_kind == 'project' and connection.execute(text("SELECT 1 FROM video_admissions WHERE project_id=:project AND state='publishing' LIMIT 1"), params).first():
            raise HTTPException(409, 'deletion_publishing_submission')
        operation = uuid4()
        connection.execute(text('''INSERT INTO deletion_operations(id,target_kind,target_id,requester_id,state)
            VALUES (:id,:kind,:target,:actor,'cleaning')'''),
            {'id': operation, 'kind': target_kind, 'target': target_id, 'actor': actor})
        connection.execute(text("SELECT set_config('app.deletion_id',:id,true)"), {'id': str(operation)})
        connection.execute(text('SET CONSTRAINTS ALL DEFERRED'))
        values = {**params, 'runs': [row.id for row in runs], 'videos': [row.id for row in videos]}
        keys = set(connection.execute(text('SELECT key FROM artifact_metadata WHERE run_id=ANY(:runs)'), values).scalars())
        intents = connection.execute(text('''SELECT id,final_key FROM publication_intents WHERE run_id=ANY(:runs)
            OR submission_key IN (SELECT idempotency_key FROM submission_requests WHERE :whole AND project_id=:project)'''), values).all()
        values['intents'] = [row.id for row in intents]
        for row in intents:
            connection.execute(text('INSERT INTO deleted_receipt_ids(id) VALUES (:id) ON CONFLICT DO NOTHING'), {'id': row.id})
        for row in intents:
            keys.add(f'tmp/{row.id}')
            if row.final_key:
                keys.add(row.final_key)
        keys.update(connection.execute(text('SELECT object_key FROM video_artifacts WHERE job_id=ANY(:videos)'), values).scalars())
        for row in connection.execute(text('SELECT source_key,result FROM video_jobs WHERE id=ANY(:videos)'), values).mappings():
            keys.add(row['source_key'])
            keys.update(_video_result_keys(row['result']))
        if target_kind == 'project':
            keys.update(connection.execute(text('SELECT source_key FROM video_admissions WHERE project_id=:project'), values).scalars())
            cover = connection.execute(text('SELECT cover_sha256 FROM site_projects WHERE id=:project'), values).scalar()
            if cover:
                keys.add(f'project-covers/{project_id}/{cover}')
            keys.update(f'project-covers/{project_id}/{sha}' for sha in connection.execute(text('SELECT sha256 FROM project_cover_gc WHERE project_id=:project'), values).scalars())
        for key in keys:
            connection.execute(text('INSERT INTO deletion_objects(deletion_id,object_key) VALUES (:id,:key)'), {'id': operation, 'key': key})
        _tombstone_keys(connection, 'submission', '''SELECT idempotency_key AS request_key,project_id FROM submission_requests
            WHERE run_id=ANY(:runs) OR (:whole AND project_id=:project)''', values)
        _tombstone_keys(connection, 'video', '''SELECT project_id::text||':'||request_key AS request_key,project_id
            FROM video_jobs WHERE id=ANY(:videos)''', values)
        if target_kind == 'project':
            _tombstone_keys(connection, 'video', "SELECT project_id::text||':'||request_key AS request_key,project_id FROM video_admissions WHERE project_id=:project", values)
            _tombstone_keys(connection, 'project', '''SELECT request_key::text,CAST(:project AS uuid) AS project_id
                FROM project_requests WHERE response->>'id'=CAST(:project AS text)''', values)
            _tombstone_keys(connection, 'trial', '''SELECT user_id::text||':'||request_key::text AS request_key,project_id
                FROM trial_imports WHERE project_id=:project''', values)
        graph = [
            ('attempt_call_refs', 'attempt_id IN (SELECT id FROM run_attempts WHERE run_id=ANY(:runs))'),
            ('detector_stage_outputs', 'run_id=ANY(:runs)'),
            ('run_attempts', 'run_id=ANY(:runs)'),
            ('deepseek_results', 'call_id IN (SELECT id FROM deepseek_calls WHERE run_id=ANY(:runs))'),
            ('annotation_versions', 'proposal_id IN (SELECT id FROM annotation_proposals WHERE run_id=ANY(:runs))'),
            ('annotation_proposals', 'run_id=ANY(:runs)'),
            ('deepseek_calls', 'run_id=ANY(:runs)'),
            ('site_signals', 'run_id=ANY(:runs) OR (:whole AND zone_id IN (SELECT id FROM site_zones WHERE project_id=:project))'),
            *[(table, 'run_id=ANY(:runs)') for table in ('detected_objects','detected_scene_features','run_plan_bindings',
                'stage_confirmations','observations','observer_invocations','result_projections','analysis_stages','run_inputs','artifact_metadata')],
            ('submission_requests', 'run_id=ANY(:runs) OR (:whole AND project_id=:project)'),
            ('publication_intents', 'id=ANY(:intents)'),
            ('analysis_runs', 'id=ANY(:runs)'),
            ('video_calls', 'job_id=ANY(:videos)'),
            ('video_artifacts', 'job_id=ANY(:videos)'),
            ('video_jobs', 'id=ANY(:videos)'),
            ('activity_attribution', "kind='run' AND object_id=ANY(:runs)"),
        ]
        if target_kind == 'project':
            graph += [
                ('account_notifications', 'invitation_id IN (SELECT id FROM project_invitations WHERE project_id=:project)'),
                *[(table, 'project_id=:project') for table in ('project_invitations','project_members','project_membership_audit',
                    'project_cover_requests','project_cover_gc','assistant_messages','trial_photos','trial_imports','video_admissions')],
                ('zone_plan_entries', 'revision_id IN (SELECT id FROM zone_plan_revisions WHERE zone_id IN (SELECT id FROM site_zones WHERE project_id=:project))'),
                ('zone_plan_revisions', 'zone_id IN (SELECT id FROM site_zones WHERE project_id=:project)'),
                ('site_zones', 'project_id=:project'),
                ('project_requests', "response->>'id'=CAST(:project AS text)"),
                ('activity_attribution', "kind='project' AND object_id=:project"),
                ('site_projects', 'id=:project'),
            ]
        for table, predicate in graph:
            _delete_rows(connection, operation, table, predicate, values)
        connection.execute(text('DELETE FROM deletion_row_authorizations WHERE deletion_id=:id'), {'id': operation})
        if not keys:
            connection.execute(text("UPDATE deletion_operations SET state='completed' WHERE id=:id"), {'id': operation})
        state = 'cleaning' if keys else 'completed'
    return {'deletion_id': str(operation), 'status': state}


@router.delete('/projects/{identifier}')
def delete_project(identifier: UUID, request: Request):
    return JSONResponse(accept_deletion(request, 'project', identifier), status_code=202)


@router.delete('/runs/{identifier}')
def delete_run(identifier: UUID, request: Request):
    return JSONResponse(accept_deletion(request, 'run', identifier), status_code=202)


@router.get('/deletions/{identifier}')
def read_deletion(identifier: UUID, request: Request):
    with request.app.state.store.engine.connect() as connection:
        row = connection.execute(text('SELECT * FROM deletion_operations WHERE id=:id'), {'id': identifier}).mappings().first()
    if not row:
        raise HTTPException(404, 'deletion_not_found')
    authorize_operation(row, requester(request))
    return operation_response(row)


def cleanup_deletions(engine, artifacts, batch_size=20):
    for _ in range(batch_size):
        with engine.begin() as connection:
            operation = connection.execute(text('''SELECT id FROM deletion_operations d
                WHERE state='cleaning' AND (NOT EXISTS (SELECT 1 FROM deletion_objects o WHERE o.deletion_id=d.id)
                    OR EXISTS (SELECT 1 FROM deletion_objects o
                        WHERE o.deletion_id=d.id AND o.retry_after<=clock_timestamp()))
                ORDER BY id LIMIT 1 FOR UPDATE OF d SKIP LOCKED''')).scalar()
            if operation is None:
                return
            row = connection.execute(text('''SELECT deletion_id,object_key FROM deletion_objects
                WHERE deletion_id=:id AND retry_after<=clock_timestamp()
                ORDER BY retry_after,object_key LIMIT 1 FOR UPDATE'''), {'id': operation}).first()
            if row is None:
                connection.execute(text("UPDATE deletion_operations SET state='completed' WHERE id=:id"), {'id': operation})
                continue
            lock_object(connection, row.object_key)
            reference = connection.execute(text('''SELECT 1 FROM artifact_metadata WHERE key=:key
                UNION ALL SELECT 1 FROM publication_intents WHERE final_key=:key
                UNION ALL SELECT 1 FROM video_admissions WHERE source_key=:key
                UNION ALL SELECT 1 FROM video_artifacts WHERE object_key=:key
                UNION ALL SELECT 1 FROM video_jobs WHERE source_key=:key
                    OR result->>'artifact_key'=:key OR result->>'detections_artifact_key'=:key
                    OR EXISTS (SELECT 1 FROM jsonb_array_elements(CASE
                        WHEN jsonb_typeof(result->'selected_frames')='array' THEN result->'selected_frames'
                        ELSE '[]'::jsonb END) frame WHERE frame->>'artifact_key'=:key)
                UNION ALL SELECT 1 FROM evaluation_reports WHERE artifact_key=:key
                UNION ALL SELECT 1 FROM site_projects WHERE 'project-covers/'||id::text||'/'||cover_sha256=:key
                LIMIT 1'''), {'key': row.object_key}).first()
            if not reference:
                try:
                    artifacts._delete_report_temporary(row.object_key)
                except Exception:
                    connection.execute(text('''UPDATE deletion_objects
                        SET retry_after=clock_timestamp()+interval '30 seconds'
                        WHERE deletion_id=:id AND object_key=:key'''), {'id': row.deletion_id, 'key': row.object_key})
                    logging.getLogger(__name__).warning('Deletion object cleanup will retry', exc_info=True)
                    continue
            connection.execute(text('DELETE FROM deletion_objects WHERE deletion_id=:id AND object_key=:key'),
                               {'id': row.deletion_id, 'key': row.object_key})
            connection.execute(text('''UPDATE deletion_operations SET state='completed' WHERE id=:id
                AND NOT EXISTS (SELECT 1 FROM deletion_objects WHERE deletion_id=:id)'''), {'id': row.deletion_id})
