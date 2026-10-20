"""Durable one-shot cloud calls and immutable run projection."""
import asyncio
import json
import uuid
from datetime import datetime
from time import monotonic

from sqlalchemy import text
from app.config import Config
from app.domain.site_analysis import compare_equipment
from app.profiles.deepseek import DeepSeek, EQUIPMENT, REVISION, snapshot, oriented_image, validate_consent, provider_label
from app.shared.cloud import canonical_bytes, digest


def provision(store, folder_id=None, hybrid=False, provider="yandex_ai_studio"):
    from app.profiles.hybrid import snapshot as hybrid_snapshot
    profile = hybrid_snapshot(folder_id, provider) if hybrid else snapshot(folder_id, provider)
    identity = digest(canonical_bytes(profile))
    parent_id = uuid.uuid5(uuid.NAMESPACE_URL, 'deepseek-draft/' + identity)
    profile_id = uuid.uuid5(uuid.NAMESPACE_URL, 'deepseek/' + identity)
    audit = digest(canonical_bytes({'configuration': identity, 'verification': 'no_paid_probe'}))
    with store.engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
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
          AND r.current_attempt_id=:attempt AND r.purpose='ordinary' AND r.lease_expires_at>clock_timestamp() AND a.state='enabled'
          AND a.revision=r.authorization_revision FOR UPDATE OF r,a'''),
        {'id': work['id'], 'owner': work['owner'], 'attempt': work.get('current_attempt_id', work['id'])}).one_or_none()
    if not row:
        raise ValueError('ordinary_lease_rejected')
    if row.profile_snapshot.get('kind') != 'deepseek':
        raise ValueError('profile_retired')
    validate_consent(row.request_context, row.profile_snapshot)
    return row


def reserve(store, work, kind, context, frame=None, source_call_id=None):
    call_id = uuid.uuid4()
    with store.engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
        lease(db, work)
        db.execute(text('''INSERT INTO deepseek_calls(id,run_id,attempt_id,call_key,kind,input_id,context,source_call_id,validation_revision)
            VALUES (:id,:run,:attempt,:key,:kind,:input,CAST(:context AS jsonb),:source,:validation)'''),
            {'id': call_id, 'run': work['id'], 'attempt': work.get('current_attempt_id', work['id']),
             'source': source_call_id, 'validation': VALIDATION_REVISION if source_call_id else None, 'key': str(frame['input_id']) if frame else 'assessment',
             'kind': kind, 'input': frame['input_id'] if frame else None, 'context': json.dumps(context)})
        if kind == 'frame':
            db.execute(text("UPDATE analysis_stages SET state='succeeded' WHERE run_id=:run AND ordinal=1 AND state='running'"), {'run':work['id']})
            db.execute(text("UPDATE analysis_stages SET state='running' WHERE run_id=:run AND ordinal=2 AND state='pending'"), {'run':work['id']})
    return call_id


def save_result(store, work, call_id, result):
    with store.engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
        lease(db, work)
        saved = db.execute(text('''INSERT INTO deepseek_results(call_id,result)
            SELECT id,CAST(:result AS jsonb) FROM deepseek_calls
            WHERE id=:id AND run_id=:run AND attempt_id=:attempt'''),
            {'id':call_id,'run':work['id'],'attempt':work.get('current_attempt_id',work['id']),'result':json.dumps(result)})
        if saved.rowcount != 1:
            raise ValueError('ordinary_lease_rejected')
        if result.get('valid') is True:
            db.execute(text("""INSERT INTO attempt_call_refs(attempt_id,call_key,call_id)
                SELECT :attempt,call_key,id FROM deepseek_calls WHERE id=:id"""),
                {'attempt': work.get('current_attempt_id', work['id']), 'id': call_id})
        advance_frames(db, work)


def advance_frames(db, work):
    frames_complete = db.execute(text("""SELECT
        (SELECT count(*) FROM run_inputs WHERE run_id=:run) =
        (SELECT count(*) FROM attempt_call_refs f JOIN deepseek_calls c ON c.id=f.call_id
         WHERE f.attempt_id=:attempt AND c.kind='frame')"""),
        {'run': work['id'], 'attempt': work.get('current_attempt_id', work['id'])}).scalar_one()
    if frames_complete:
        db.execute(text("UPDATE analysis_stages SET state='succeeded',reason=NULL WHERE run_id=:run AND ordinal IN (1,2) AND state IN ('pending','running')"), {'run':work['id']})
        db.execute(text("UPDATE analysis_stages SET state='running' WHERE run_id=:run AND ordinal=3 AND state='pending'"), {'run':work['id']})


VALIDATION_REVISION = 'stage-recovery-validation-v1'


def effective_calls(store, work):
    with store.engine.connect() as db:
        return {r['call_key']: dict(r) for r in db.execute(text("""SELECT c.*,v.result
            FROM attempt_call_refs f JOIN deepseek_calls c ON c.id=f.call_id
            JOIN deepseek_results v ON v.call_id=c.id WHERE f.attempt_id=:attempt"""),
            {'attempt': work.get('current_attempt_id', work['id'])}).mappings()}


def prior_call(store, work, key):
    with store.engine.connect() as db:
        row = db.execute(text("""SELECT c.*,v.result FROM deepseek_calls c
            LEFT JOIN deepseek_results v ON v.call_id=c.id WHERE c.run_id=:run AND c.call_key=:key
            AND c.attempt_id<>:attempt ORDER BY c.created_at DESC,c.id DESC LIMIT 1"""),
            {'run': work['id'], 'key': key, 'attempt': work.get('current_attempt_id', work['id'])}).mappings().first()
        return dict(row) if row else None


def detector_output(store, work, frame, image):
    with store.engine.connect() as db:
        saved = db.execute(text('SELECT * FROM detector_stage_outputs WHERE run_id=:run AND input_id=:input'),
                           {'run':work['id'], 'input':frame['input_id']}).mappings().first()
    if saved:
        if saved['input_sha256'] != frame['sha256'] or saved['manifest'] != detector_manifest(work):
            raise ValueError('artifact_integrity_failed')
        return saved['output']
    old = prior_call(store, work, str(frame['input_id']))
    if old and old['context'].get('detectors'):
        output = old['context']['detectors']
    else:
        from app.profiles.yolo import detectors
        output = detectors().detect(image, str(frame['input_id']))
    with store.engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock_shared(804298270115)'))
        lease(db, work)
        db.execute(text("""INSERT INTO detector_stage_outputs(run_id,input_id,input_sha256,manifest,output)
            VALUES (:run,:input,:sha,CAST(:manifest AS jsonb),CAST(:output AS jsonb))"""),
            {'run':work['id'], 'input':frame['input_id'], 'sha':frame['sha256'],
             'manifest':json.dumps(detector_manifest(work)), 'output':json.dumps(output)})
    return output


def detector_manifest(work):
    return {'sha256': work['profile_snapshot'].get('detector_manifest_sha256')}


def revalidate(observer, old, context):
    if not old or not old['result'] or not old['result'].get('raw'):
        return None
    try:
        return observer.revalidate(old['kind'], context, old['result'])
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def class_state(value, name, detector_evidence=None):
    if name not in EQUIPMENT:
        return 'not_analyzed'
    objects = value.get('objects', value.get('observations', []))
    if any(o.get('catalog_class') == name and o.get('status') == 'identified' for o in objects):
        return 'detected'
    unresolved = {d['detection_id'] for d in value.get('detection_dispositions', []) if d['status'] == 'unresolved'}
    detectors = detector_evidence or value.get('detectors', {})
    unresolved_class = any(d['id'] in unresolved and d.get('catalog_class') in (None, name)
                           for model in detectors.get('models', []) for d in model['detections'])
    if (unresolved_class or not value.get('frame_usability', {'usable': True})['usable']
            or value.get('class_assessability', {}).get(name, 'assessable') != 'assessable'
            or any(o.get('status') == 'uncertain' and o.get('catalog_class') in (None, name) for o in objects)):
        return 'insufficient_data'
    return 'not_detected_in_frame'


def observation_context(frame, result):
    value = result['value']
    observations = [{**item, 'id': str(uuid.uuid5(uuid.NAMESPACE_URL, f"{frame['input_id']}/object/{i}")),
                     'visible': True, 'kind': 'equipment'} for i, item in enumerate(value['objects'])]
    observations += [{'id': f"{frame['input_id']}/scene/{name}", 'kind': 'scene', 'name': name,
                      'state': state, 'visible': state == 'present'} for name, state in value['scenes'].items()]
    return {'input_id': str(frame['input_id']), 'ordinal': frame['ordinal'],
            'sha256': frame['sha256'], 'source_artifact_id': str(frame['artifact_id']),
            'observations': observations, 'stage': value['stage'], 'stage_reason': value['stage_reason'],
            **{key: value[key] for key in ('frame_usability', 'class_assessability', 'detection_dispositions') if key in value},
            **({'detectors': result['detectors']} if 'detectors' in result else {})}


def freeze_context(store, work, frames):
    with store.engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
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
                JOIN attempt_call_refs af ON af.attempt_id=r.current_attempt_id AND af.call_key='assessment'
                JOIN deepseek_calls c ON c.id=af.call_id AND c.kind='assessment'
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
        rules = []
        if plan:
            entries = [{**e, 'starts_at': datetime.fromisoformat(e['starts_at']), 'ends_at': datetime.fromisoformat(e['ends_at'])} for e in plan['entries']]
            obs = []
            for frame in frames:
                for name in EQUIPMENT:
                    obs.append({'input_id': frame['input_id'], 'class_name': name, 'state': class_state(frame, name)})
            rules = compare_equipment(entries, [f['captured_at'] for f in frames], obs, [f['input_id'] for f in frames], set(EQUIPMENT), frames=frames)
        return {'frames': frames, 'rule_results': rules,
                'comparison_method': 'same_zone_independent_timed_frames' if reliable and len({f['sha256'] for f in frames}) > 1 else 'individual_frames_only', 'plan': plan, 'history': history, 'zone_id': context.get('zone_id'),
                'declared_context':dict(context), 'history_eligible':reliable,
                'instruction_version': row.profile_snapshot['instruction_version'], 'schema_version': row.profile_snapshot['schema_version']}


def mark_downstream(store, work, rule_complete=False, plan=None):
    with store.engine.begin() as db:
        db.execute(text('SELECT pg_advisory_xact_lock_shared(804298270115)'))
        lease(db, work)
        db.execute(text("UPDATE analysis_stages SET state='succeeded',reason=NULL WHERE run_id=:run AND ordinal=3 AND state IN ('running','pending')"), {'run':work['id']})
        if rule_complete:
            db.execute(text("UPDATE analysis_stages SET state=:state,reason=:reason WHERE run_id=:run AND ordinal=4 AND state IN ('running','pending')"),
                       {'run':work['id'],'state':'succeeded' if plan else 'skipped','reason':None if plan else 'not_applicable'})
            db.execute(text("UPDATE analysis_stages SET state='running',reason=NULL WHERE run_id=:run AND ordinal=5 AND state='pending'"), {'run':work['id']})
        else:
            db.execute(text("UPDATE analysis_stages SET state='running',reason=NULL WHERE run_id=:run AND ordinal=4 AND state='pending'"), {'run':work['id']})


def validate_downstream(work, frame_results, assessment, frozen):
    if work['profile_snapshot'].get('observation_contract') == 'hybrid-photo-signals-v1':
        from app.profiles.hybrid import validate_assessment, validate_frame
        validate_assessment(assessment['value'], frozen)
        for frame, _, result in frame_results:
            validate_frame(result['value'], {'detectors': result['detectors']})


def complete(store, work, frame_results, assessment, frozen):
    with store.engine.begin() as db:
        db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
        lease(db, work)
        effective = db.execute(text('SELECT call_key,call_id FROM attempt_call_refs WHERE attempt_id=:attempt'),
                               {'attempt':work.get('current_attempt_id', work['id'])}).all()
        expected_ids = {str(frame['input_id']): call_id for frame, call_id, _ in frame_results}
        if len(effective) != len(work['frames']) + 1 or any(
                key != 'assessment' and expected_ids.get(key) != call_id for key, call_id in effective):
            raise ValueError('observation_incomplete')
        observations = []
        hybrid = work['profile_snapshot'].get('observation_contract') == 'hybrid-photo-signals-v1'
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
            for name in work['requested_classes']:
                state = class_state(result['value'], name, result.get('detectors'))
                item = {'class_name': name, 'state': state, 'reason': 'unsupported_class' if name not in EQUIPMENT else 'uncertain_identification' if state=='insufficient_data' else None,
                        'input_id': str(frame['input_id']), 'ordinal': frame['ordinal'],
                        'source_artifact_id': str(frame['artifact_id']), 'invocation_id': str(call_id)}
                db.execute(text('''INSERT INTO observations
                    (run_id,input_id,class_name,state,reason,input_sha256,invocation_id,source_artifact_id)
                    VALUES (:run,:input_id,:class_name,:state,:reason,:sha,:invocation_id,:source_artifact_id)'''),
                    {'run': work['id'], 'sha': frame['sha256'], **item})
                observations.append(item)
        ids = [str(frame['input_id']) for frame in work['frames']]
        usable_ids = [frame['input_id'] for frame in frozen['frames'] if frame.get('frame_usability', {'usable': True})['usable']]
        projection = {'outcome': 'observations_only', 'frames': observations,
                      'ai_assessment': assessment['value'], 'series': {'usable_count': len(usable_ids), 'usable_input_ids': usable_ids,
                      'input_order': ids, 'excavator_supporting_input_ids': [o['input_id'] for o in observations if o['class_name'] == 'excavator' and o['state'] == 'detected'], 'dump_truck_persistence_input_ids': [], 'declared_observation_area': frozen.get('zone_id'), 'dump_truck_persistence_text': None},
                      'stage_hypotheses': [], 'source': provider_label(work['profile_snapshot']) + ' · Мультимодальная модель',
                      'limitations': ['Фотография не доказывает отсутствие техники; выводы требуют проверки человеком.']}
        projection['context'] = frozen['declared_context']
        projection['series']['declared_observation_area'] = frozen['declared_context'].get('observation_area')
        projection['hybrid_frames'] = frozen['frames'] if hybrid else []
        projection['stage_hypotheses'] = assessment['value'].get('stage_hypotheses', [])
        projection['created_signals'] = []
        projection['rule_results'] = frozen.get('rule_results', [])
        plan = frozen['plan']
        if plan:
            projection['plan_revision_id'] = plan['revision_id']
        candidates = list(frozen.get('rule_results', []))
        for risk in assessment['value']['risks'] if hybrid else []:
            matching = next((r for r in candidates if r['kind'] == risk['cause'] and r['entry_id'] == risk['work_entry_id']
                             and set(r.get('supporting_input_ids', [])) == set(risk['frame_ids'])), None)
            if matching is not None:
                matching['risk'] = risk
            else:
                candidates.append({'kind': risk['cause'], 'entry_id': risk['work_entry_id'],
                                   'supporting_input_ids': risk['frame_ids'], 'risk': risk})
        frame_by_id = {f['input_id']: f for f in frozen['frames']}
        for signal in candidates:
            if not frozen.get('zone_id'):
                continue
            supporting_ids = signal.get('supporting_input_ids', ids)
            supporting = [o for o in observations if o['input_id'] in supporting_ids and
                          (not signal.get('class_name') or o['class_name'] == signal['class_name'])]
            evidence_frames = [frame_by_id[key] for key in supporting_ids]
            basis = {'rule_revision': 'site-equipment-v2', 'supporting_input_ids': supporting_ids,
                     'observations': supporting, 'frames': evidence_frames, 'plan': plan, **signal}
            source = sorted({frame_by_id[key]['sha256'] for key in supporting_ids})
            cited = (set(signal.get('risk', {}).get('observation_ids', []))
                     if not signal.get('class_name') and signal['kind'] != 'stage_plan_mismatch' else set())
            evidence = sorted([{'sha256': f['sha256'], 'kind': o['kind'],
                                'class': o.get('catalog_class', o.get('name')),
                                'detections': sorted(ref.split('/', 1)[1] for ref in o.get('detection_ids', []))}
                               for f in evidence_frames for o in f['observations'] if o['id'] in cited],
                              key=lambda item: canonical_bytes(item))
            fingerprint = digest(canonical_bytes({'zone': frozen['zone_id'],
                'revision': plan['revision_id'] if plan else None, 'cause': signal['kind'],
                'work': signal['entry_id'], 'class': signal.get('class_name'), 'source': source, 'evidence': evidence}))
            db.execute(text('''INSERT INTO site_signals
                (id,fingerprint,run_id,zone_id,revision_id,work_entry_id,kind,basis)
                VALUES (:id,:fingerprint,:run,:zone,:revision,:entry,:kind,CAST(:basis AS jsonb))
                ON CONFLICT (fingerprint) DO NOTHING'''),
                {'id': uuid.uuid4(), 'fingerprint': fingerprint, 'run': work['id'], 'zone': frozen['zone_id'],
                 'revision': plan['revision_id'] if plan else None, 'entry': signal['entry_id'],
                 'kind': signal['kind'], 'basis': json.dumps(basis)})
            stored = db.execute(text('SELECT id,state FROM site_signals WHERE fingerprint=:fingerprint'),
                                {'fingerprint': fingerprint}).one()
            projection['created_signals'].append({'id': str(stored.id), 'state': stored.state, **signal})
        db.execute(text('''INSERT INTO result_projections(run_id,outcome,snapshot)
            VALUES (:run,'observations_only',CAST(:snapshot AS jsonb))'''),
            {'run': work['id'], 'snapshot': json.dumps(projection)})
        db.execute(text("UPDATE analysis_stages SET state='succeeded',reason=NULL WHERE run_id=:run"), {'run': work['id']})
        if not frozen['plan']:
            db.execute(text("UPDATE analysis_stages SET state='skipped',reason='not_applicable' WHERE run_id=:run AND ordinal=4"), {'run': work['id']})
        completed = db.execute(text('''UPDATE analysis_runs
            SET state='succeeded',lease_owner=NULL,lease_expires_at=NULL
            WHERE id=:run AND state='running' AND lease_owner=:owner
              AND lease_expires_at>clock_timestamp()'''),
            {'run': work['id'], 'owner': work['owner']})
        if completed.rowcount != 1:
            raise ValueError('ordinary_lease_rejected')


async def execute(runner, work, revision):
    renewal = asyncio.create_task(runner._renew(work['id'], work['owner'], revision))
    try:
        def check_renewal():
            if renewal.done():
                raise ValueError('ordinary_lease_rejected')
        def validate_work_lease():
            with runner.store.engine.begin() as db:
                db.execute(text("SELECT pg_advisory_xact_lock_shared(804298270115)"))
                lease(db, work)
        await asyncio.to_thread(validate_work_lease)
        observer = DeepSeek(work['profile_snapshot'], Config.from_env().api_key_for(work['profile_snapshot']))
        deadline = monotonic() + work['profile_snapshot']['runtime']['batch_timeout_seconds']
        results, frames, images = [], [], []
        hybrid = work['profile_snapshot'].get('observation_contract') == 'hybrid-photo-signals-v1'
        effective = await asyncio.to_thread(effective_calls, runner.store, work)
        prepared = []
        for frame in work['frames']:
            check_renewal()
            image = await asyncio.to_thread(runner.artifacts.read_verified, frame['key'], frame['sha256'], frame['size'])
            await asyncio.to_thread(oriented_image, image)
            key = str(frame['input_id'])
            context = {'input_id': key, 'sha256': frame['sha256'], 'ordinal': frame['ordinal'],
                       'instruction_version': work['profile_snapshot']['instruction_version'],
                       'schema_version': work['profile_snapshot']['schema_version']}
            if hybrid:
                context['detectors'] = await asyncio.to_thread(detector_output, runner.store, work, frame, image)
            prepared.append((frame, image, context))
        for frame, image, context in prepared:
            key = str(frame['input_id'])
            saved = effective.get(key)
            if saved:
                call_id, result = saved['id'], saved['result']
            else:
                old = await asyncio.to_thread(prior_call, runner.store, work, key)
                original_context = old['context'] if old else context
                result = await asyncio.to_thread(revalidate, observer, old, original_context)
                check_renewal()
                call_id = await asyncio.to_thread(reserve, runner.store, work, 'frame', original_context, frame,
                                                  old['id'] if result else None)
                if result is None:
                    timeout = min(120, deadline - monotonic())
                    if timeout <= 0:
                        raise ValueError('observer_timeout')
                    result = await asyncio.to_thread(observer.call, 'frame', original_context, image, timeout)
                if hybrid:
                    result['detectors'] = original_context['detectors']
                check_renewal()
                await asyncio.to_thread(save_result, runner.store, work, call_id, result)
                if result.get('valid') is not True:
                    raise ValueError('deepseek_response_invalid')
            results.append((frame, call_id, result))
            frames.append(observation_context(frame, result))
            images.append((key, image))
        def finish_frames():
            with runner.store.engine.begin() as db:
                db.execute(text('SELECT pg_advisory_xact_lock_shared(804298270115)'))
                lease(db, work)
                advance_frames(db, work)
        await asyncio.to_thread(finish_frames)
        old = await asyncio.to_thread(prior_call, runner.store, work, 'assessment')
        frozen = old['context'] if old else await asyncio.to_thread(freeze_context, runner.store, work, frames)
        saved = effective.get('assessment')
        if saved:
            assessment = saved['result']
        else:
            assessment = await asyncio.to_thread(revalidate, observer, old, frozen)
            check_renewal()
            call_id = await asyncio.to_thread(reserve, runner.store, work, 'assessment', frozen,
                                              source_call_id=old['id'] if assessment else None)
            if assessment is None:
                timeout = min(120, deadline - monotonic())
                if timeout <= 0:
                    raise ValueError('observer_timeout')
                assessment = await asyncio.to_thread(observer.call, 'assessment', frozen, None, timeout,
                                                    **({'images': images} if hybrid else {}))
            check_renewal()
            await asyncio.to_thread(save_result, runner.store, work, call_id, assessment)
            if assessment.get('valid') is not True:
                raise ValueError('deepseek_response_invalid')
        await asyncio.to_thread(mark_downstream, runner.store, work)
        await asyncio.to_thread(validate_downstream, work, results, assessment, frozen)
        await asyncio.to_thread(mark_downstream, runner.store, work, True, frozen['plan'])
        await asyncio.to_thread(complete, runner.store, work, results, assessment, frozen)
    except Exception as exc:
        code = str(exc)
        await asyncio.to_thread(runner.store.fail_ordinary, work['id'], work['owner'],
                                code if code in {'deepseek_response_invalid', 'observation_normalization_failed', 'observer_redirect_rejected', 'cloud_provider_mismatch', 'cloud_provider_unavailable', 'quality_budget_provider_mismatch', 'observer_balance_failed', 'ordinary_lease_rejected', 'profile_retired', 'cloud_consent_required', 'cloud_credential_missing', 'observer_timeout', 'observer_response_too_large', 'observer_quota_failed', 'observer_access_failed', 'observer_http_failed', 'observer_transport_failed', 'artifact_integrity_failed'} else 'deepseek_call_failed_or_uncertain')
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
        print(provision(store, os.getenv('YANDEX_CLOUD_FOLDER_ID'), hybrid=os.getenv('HYBRID_PHOTO_SIGNALS') == '1',
                        provider=os.getenv('CLOUD_PROVIDER', 'yandex_ai_studio')))
    finally:
        store.close()


if __name__ == '__main__':
    main()
