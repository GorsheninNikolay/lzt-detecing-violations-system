"""Durable one-shot cloud calls and immutable run projection."""
import asyncio
import json
import uuid
from datetime import datetime
from time import monotonic

from sqlalchemy import text
from app.config import Config
from app.domain.site_analysis import compare_equipment
from app.profiles.deepseek import DeepSeek, EQUIPMENT, REVISION, snapshot, oriented_image
from app.shared.cloud import canonical_bytes, digest


def provision(store, folder_id):
    profile = snapshot(folder_id)
    identity = digest(canonical_bytes(profile))
    parent_id = uuid.uuid5(uuid.NAMESPACE_URL, 'deepseek-draft/' + identity)
    profile_id = uuid.uuid5(uuid.NAMESPACE_URL, 'deepseek/' + identity)
    audit = digest(canonical_bytes({'configuration': identity, 'verification': 'no_paid_probe'}))
    with store.engine.begin() as db:
        db.execute(text('''INSERT INTO observer_profiles(id,status,profile_hash,snapshot)
            VALUES (:id,'draft',:hash,CAST(:snapshot AS jsonb)) ON CONFLICT DO NOTHING'''),
            {'id': parent_id, 'hash': digest(('draft/' + identity).encode()), 'snapshot': json.dumps(profile)})
        db.execute(text('''INSERT INTO observer_profiles(id,parent_id,status,profile_hash,snapshot,audit_hash)
            VALUES (:id,:parent,'admitted',:hash,CAST(:snapshot AS jsonb),:audit) ON CONFLICT DO NOTHING'''),
            {'id': profile_id, 'parent': parent_id, 'hash': identity, 'snapshot': json.dumps(profile), 'audit': audit})
        db.execute(text('''INSERT INTO profile_authorizations
            (profile_id,revision,state,reason,audit_hash,interactive_retry_allowed)
            VALUES (:id,1,'enabled','explicit_cloud_consent_per_run',:audit,false) ON CONFLICT DO NOTHING'''),
            {'id': profile_id, 'audit': audit})
    return profile_id


def lease(db, work):
    row = db.execute(text('''SELECT r.request_context,r.profile_snapshot,r.stage_key FROM analysis_runs r
        JOIN profile_authorizations a ON a.profile_id=r.profile_id
        WHERE r.id=:id AND r.state='running' AND r.lease_owner=:owner
          AND r.purpose='ordinary' AND r.lease_expires_at>clock_timestamp() AND a.state='enabled'
          AND a.revision=r.authorization_revision FOR UPDATE OF r,a'''),
        {'id': work['id'], 'owner': work['owner']}).one_or_none()
    if not row:
        raise ValueError('ordinary_lease_rejected')
    if row.profile_snapshot.get('kind') != 'deepseek':
        raise ValueError('profile_retired')
    if row.request_context.get('cloud_processing_consent') is not True:
        raise ValueError('cloud_consent_required')
    return row


def reserve(store, work, kind, context, frame=None):
    call_id = uuid.uuid4()
    with store.engine.begin() as db:
        lease(db, work)
        db.execute(text('''INSERT INTO deepseek_calls(id,run_id,call_key,kind,input_id,context)
            VALUES (:id,:run,:key,:kind,:input,CAST(:context AS jsonb))'''),
            {'id': call_id, 'run': work['id'], 'key': str(frame['input_id']) if frame else 'assessment',
             'kind': kind, 'input': frame['input_id'] if frame else None, 'context': json.dumps(context)})
        if kind == 'frame':
            db.execute(text("UPDATE analysis_stages SET state='succeeded' WHERE run_id=:run AND ordinal=1 AND state='running'"), {'run':work['id']})
            db.execute(text("UPDATE analysis_stages SET state='running' WHERE run_id=:run AND ordinal=2 AND state='pending'"), {'run':work['id']})
    return call_id


def save_result(store, work, call_id, result):
    with store.engine.begin() as db:
        lease(db, work)
        db.execute(text('INSERT INTO deepseek_results(call_id,result) VALUES (:id,CAST(:result AS jsonb))'),
                   {'id': call_id, 'result': json.dumps(result)})
        frames_complete = db.execute(text('''SELECT
            (SELECT count(*) FROM run_inputs WHERE run_id=:run) =
            (SELECT count(*) FROM deepseek_calls c JOIN deepseek_results r ON r.call_id=c.id
             WHERE c.run_id=:run AND c.kind='frame' AND COALESCE((r.result->>'valid')::boolean,true))'''),
            {'run':work['id']}).scalar_one()
        if frames_complete:
            db.execute(text("UPDATE analysis_stages SET state='succeeded' WHERE run_id=:run AND ordinal=2 AND state='running'"), {'run':work['id']})
            db.execute(text("UPDATE analysis_stages SET state='running' WHERE run_id=:run AND ordinal=3 AND state='pending'"), {'run':work['id']})


def observation_context(frame, result):
    value = result['value']
    observations = [{**item, 'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f"{frame['input_id']}/object/{i}")),
                     'visible': True, 'kind': 'equipment'} for i, item in enumerate(value['objects'])]
    observations += [{'id': f"{frame['input_id']}/scene/{name}", 'kind': 'scene', 'name': name,
                      'state': state, 'visible': state == 'present'} for name, state in value['scenes'].items()]
    return {'input_id': str(frame['input_id']), 'ordinal': frame['ordinal'],
            'sha256': frame['sha256'], 'source_artifact_id': str(frame['artifact_id']),
            'observations': observations, 'stage': value['stage'], 'stage_reason': value['stage_reason']}


def freeze_context(store, work, frames):
    with store.engine.begin() as db:
        row = lease(db, work)
    with store.engine.connect() as db:
        context = dict(row.request_context)
        if row.stage_key is not None:
            context['stage'] = row.stage_key
        times = context.get('capture_times')
        supplied_times = isinstance(times, list) and len(times) == len(frames)
        reliable = bool(context.get('zone_id') and supplied_times)
        if reliable:
            try:
                parsed = [datetime.fromisoformat(t) for t in times]
                reliable = all(t.utcoffset() is not None for t in parsed) and parsed == sorted(parsed)
            except (ValueError, TypeError):
                reliable = False
        for index, frame in enumerate(frames):
            frame['captured_at'] = times[index] if supplied_times else None
        plan = None
        binding = db.execute(text('SELECT revision_id,zone_id FROM run_plan_bindings WHERE run_id=:id'),
                             {'id': work['id']}).one_or_none()
        if binding:
            entries = db.execute(text('''SELECT e.id,w.title,e.stage_key,e.starts_at,e.ends_at,e.state,
                e.expected_equipment,e.allowed_equipment,e.excluded_equipment
                FROM zone_plan_entries e JOIN catalog_works w ON w.id=e.catalog_work_id
                WHERE e.revision_id=:id ORDER BY e.starts_at,e.id'''), {'id': binding.revision_id}).mappings()
            plan = {'revision_id': str(binding.revision_id), 'zone_id': str(binding.zone_id),
                    'entries': [{**r, 'id':str(r['id']), 'starts_at': r['starts_at'].isoformat(), 'ends_at': r['ends_at'].isoformat()}
                                for r in entries]}
        history = []
        if reliable:
            candidates = db.execute(text('''SELECT r.id,v.result,t.last_capture FROM analysis_runs r
                JOIN deepseek_calls c ON c.run_id=r.id AND c.kind='assessment'
                JOIN deepseek_results v ON v.call_id=c.id
                CROSS JOIN LATERAL (
                    SELECT max((f->>'captured_at')::timestamptz) AS last_capture,
                           count(*) AS frame_count, bool_and(f->>'captured_at' IS NOT NULL) AS complete
                    FROM jsonb_array_elements(c.context->'frames') f
                ) t
                WHERE r.state='succeeded' AND r.id<>:id AND r.purpose='ordinary'
                AND r.request_context->>'zone_id'=:zone
                AND COALESCE((c.context->>'history_eligible')::boolean,true)
                AND t.frame_count>0 AND t.complete AND t.last_capture<:before
                ORDER BY t.last_capture DESC,r.id DESC LIMIT 3'''),
                {'id': work['id'], 'zone': context['zone_id'], 'before':min(parsed)}).mappings()
            for old in candidates:
                history.append({'run_id': str(old['id']), 'last_capture': old['last_capture'].isoformat(),
                                'assessment': old['result']['value']})
        return {'frames': frames, 'plan': plan, 'history': history, 'zone_id': context.get('zone_id'),
                'declared_context':dict(context), 'history_eligible':reliable,
                'instruction_version': REVISION, 'schema_version': REVISION}


def complete(store, work, frame_results, assessment, frozen):
    with store.engine.begin() as db:
        lease(db, work)
        expected = db.execute(text('SELECT count(*) FROM deepseek_calls WHERE run_id=:run'), {'run': work['id']}).scalar_one()
        completed = db.execute(text('''SELECT count(*) FROM deepseek_calls c JOIN deepseek_results r ON r.call_id=c.id
            WHERE c.run_id=:run'''), {'run': work['id']}).scalar_one()
        if expected != len(work['frames']) + 1 or expected != completed:
            raise ValueError('observation_incomplete')
        observations = []
        for frame, call_id, result in frame_results:
            db.execute(text('''INSERT INTO observer_invocations
                (id,run_id,input_id,fence,profile_id,authorization_revision,stage_ordinal,input_sha256,
                 intended_request_identity,returned_model_identity,returned_request_identity,actual_device,
                 preprocessing_revision,state)
                SELECT :id,id,:input,1,profile_id,authorization_revision,2,:sha,:model,:model,:response,
                    'remote_unreported','exif-oriented-v1','completed' FROM analysis_runs WHERE id=:run'''),
                {'id': call_id, 'input': frame['input_id'], 'sha': frame['sha256'], 'model': result['model'],
                 'response': result['raw']['id'], 'run': work['id']})
            for ordinal, obj in enumerate(result['value']['objects']):
                identity = uuid.uuid5(uuid.NAMESPACE_URL, f"{frame['input_id']}/object/{ordinal}")
                db.execute(text('''INSERT INTO detected_objects
                    (id,run_id,input_id,invocation_id,ordinal,class_name,score,box,image_size,details)
                    VALUES (:id,:run,:input,:call,:ordinal,:class,NULL,CAST(:box AS jsonb),CAST(:size AS jsonb),CAST(:details AS jsonb))'''),
                    {'id': identity, 'run': work['id'], 'input': frame['input_id'], 'call': call_id, 'ordinal': ordinal,
                     'class': obj['catalog_class'] or 'unknown', 'box': json.dumps(obj['box']),
                     'size': json.dumps(result['image_size']), 'details': json.dumps(obj)})
            detected = {obj['catalog_class'] for obj in result['value']['objects'] if obj['status']=='identified'}
            uncertain = {obj['catalog_class'] for obj in result['value']['objects'] if obj['status']=='uncertain'}
            for name in work['requested_classes']:
                state = 'detected' if name in detected else 'insufficient_data' if name in uncertain else 'not_detected_in_frame' if name in EQUIPMENT else 'not_analyzed'
                item = {'class_name': name, 'state': state, 'reason': 'unsupported_class' if name not in EQUIPMENT else 'uncertain_identification' if state=='insufficient_data' else None,
                        'input_id': str(frame['input_id']), 'ordinal': frame['ordinal'],
                        'source_artifact_id': str(frame['artifact_id']), 'invocation_id': str(call_id)}
                db.execute(text('''INSERT INTO observations
                    (run_id,input_id,class_name,state,reason,input_sha256,invocation_id,source_artifact_id)
                    VALUES (:run,:input_id,:class_name,:state,:reason,:sha,:invocation_id,:source_artifact_id)'''),
                    {'run': work['id'], 'sha': frame['sha256'], **item})
                observations.append(item)
        ids = [str(frame['input_id']) for frame in work['frames']]
        projection = {'outcome': 'observations_only', 'frames': observations,
                      'ai_assessment': assessment['value'], 'series': {'usable_count': len(ids), 'usable_input_ids': ids,
                      'input_order': ids, 'excavator_supporting_input_ids': [o['input_id'] for o in observations if o['class_name'] == 'excavator' and o['state'] == 'detected'], 'dump_truck_persistence_input_ids': [], 'declared_observation_area': frozen.get('zone_id'), 'dump_truck_persistence_text': None},
                      'stage_hypotheses': [], 'source': 'Yandex AI Studio DeepSeek',
                      'limitations': ['Фотография не доказывает отсутствие техники; выводы требуют проверки человеком.']}
        projection['context'] = frozen['declared_context']
        projection['series']['declared_observation_area'] = frozen['declared_context'].get('observation_area')
        if frozen['plan']:
            plan = frozen['plan']
            entries = [{**entry,'starts_at':datetime.fromisoformat(entry['starts_at']),
                        'ends_at':datetime.fromisoformat(entry['ends_at'])} for entry in plan['entries']]
            signals = compare_equipment(entries, [frame['captured_at'] for frame in frozen['frames']],
                                        observations, ids, set(EQUIPMENT))
            projection['plan_revision_id'] = plan['revision_id']
            projection['rule_results'] = signals
            for signal in signals:
                supporting = [item for item in observations if not signal.get('class_name')
                              or item['class_name']==signal['class_name']]
                basis = {'rule_revision':'site-equipment-v1','supporting_input_ids':ids,
                         'observations':supporting,**signal}
                fingerprint = digest(canonical_bytes({'run':str(work['id']),**signal}))
                db.execute(text('''INSERT INTO site_signals
                    (id,fingerprint,run_id,zone_id,revision_id,work_entry_id,kind,basis)
                    VALUES (:id,:fingerprint,:run,:zone,:revision,:entry,:kind,CAST(:basis AS jsonb))
                    ON CONFLICT (fingerprint) DO NOTHING'''),
                    {'id':uuid.uuid4(),'fingerprint':fingerprint,'run':work['id'],'zone':plan['zone_id'],
                     'revision':plan['revision_id'],'entry':signal['entry_id'],'kind':signal['kind'],
                     'basis':json.dumps(basis)})
        db.execute(text('''INSERT INTO result_projections(run_id,outcome,snapshot)
            VALUES (:run,'observations_only',CAST(:snapshot AS jsonb))'''),
            {'run': work['id'], 'snapshot': json.dumps(projection)})
        db.execute(text("UPDATE analysis_stages SET state='succeeded',reason=NULL WHERE run_id=:run"), {'run': work['id']})
        if not frozen['plan']:
            db.execute(text("UPDATE analysis_stages SET state='skipped',reason='not_applicable' WHERE run_id=:run AND ordinal=4"), {'run': work['id']})
        db.execute(text("UPDATE analysis_runs SET state='succeeded',lease_owner=NULL,lease_expires_at=NULL WHERE id=:run"), {'run': work['id']})


async def execute(runner, work, revision):
    renewal = asyncio.create_task(runner._renew(work['id'], work['owner'], revision))
    try:
        def check_renewal():
            if renewal.done():
                raise ValueError('ordinary_lease_rejected')
        observer = DeepSeek(work['profile_snapshot'], Config.from_env().cloud_api_key)
        deadline = monotonic() + work['profile_snapshot']['runtime']['batch_timeout_seconds']
        results, frames = [], []
        for frame in work['frames']:
            image = await asyncio.to_thread(runner.artifacts.read_verified, frame['key'], frame['sha256'], frame['size'])
            await asyncio.to_thread(oriented_image, image)
            context = {'input_id': str(frame['input_id']), 'sha256': frame['sha256'], 'ordinal': frame['ordinal'],
                       'instruction_version': REVISION, 'schema_version': REVISION}
            timeout = min(120, deadline - monotonic())
            if timeout <= 0:
                raise ValueError('observer_timeout')
            check_renewal()
            call_id = await asyncio.to_thread(reserve, runner.store, work, 'frame', context, frame)
            result = await asyncio.to_thread(observer.call, 'frame', context, image, timeout)
            check_renewal()
            await asyncio.to_thread(save_result, runner.store, work, call_id, result)
            if result.get('valid') is not True:
                raise ValueError('deepseek_response_invalid')
            results.append((frame, call_id, result))
            frames.append(observation_context(frame, result))
        frozen = await asyncio.to_thread(freeze_context, runner.store, work, frames)
        timeout = min(120, deadline - monotonic())
        if timeout <= 0:
            raise ValueError('observer_timeout')
        check_renewal()
        call_id = await asyncio.to_thread(reserve, runner.store, work, 'assessment', frozen)
        assessment = await asyncio.to_thread(observer.call, 'assessment', frozen, None, timeout)
        check_renewal()
        await asyncio.to_thread(save_result, runner.store, work, call_id, assessment)
        if assessment.get('valid') is not True:
            raise ValueError('deepseek_response_invalid')
        await asyncio.to_thread(complete, runner.store, work, results, assessment, frozen)
    except Exception as exc:
        code = str(exc)
        await asyncio.to_thread(runner.store.fail_ordinary, work['id'], work['owner'],
                                code if code in {'ordinary_lease_rejected', 'profile_retired', 'cloud_consent_required', 'cloud_credential_missing', 'observer_timeout', 'observer_response_too_large', 'observer_quota_failed', 'observer_access_failed', 'observer_http_failed', 'observer_transport_failed', 'artifact_integrity_failed'} else 'deepseek_call_failed_or_uncertain')
    finally:
        renewal.cancel()
        try:
            await renewal
        except (asyncio.CancelledError, Exception):
            pass


def main():
    import os
    from app.adapters.postgres import PostgresStore
    store = PostgresStore(Config.database_url_from_env())
    try:
        print(provision(store, os.environ['YANDEX_CLOUD_FOLDER_ID']))
    finally:
        store.close()


if __name__ == '__main__':
    main()
