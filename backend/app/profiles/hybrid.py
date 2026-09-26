"""Hybrid contract; legacy DeepSeek snapshots remain readable and executable."""
from copy import deepcopy
from datetime import datetime
import re

from app.profiles import deepseek as legacy
from app.shared.cloud import canonical_bytes, digest
from app.profiles.yolo import manifest

REVISION = 'hybrid-photo-signals-v1'
REFS = {'type': 'array', 'maxItems': 100, 'items': {'type': 'string', 'minLength': 1}}
NULL_TEXT = {'anyOf': [legacy.TEXT, {'type': 'null'}]}
ACTIONS = ('digging', 'loading', 'compacting', 'pouring', 'lifting', 'moving_material', 'no_visible_action', 'unknown')
FRAME_SCHEMA = deepcopy(legacy.SCHEMA)
FRAME_SCHEMA['properties']['objects']['items'] = legacy.object_schema({
    **FRAME_SCHEMA['properties']['objects']['items']['properties'],
    'detection_ids': REFS, 'disagreements': {'type': 'array', 'maxItems': 20, 'items': legacy.TEXT},
    'visual_action': {'type': 'string', 'enum': list(ACTIONS)}, 'action_evidence': legacy.TEXT,
    'idle_indicator': {'type': 'string', 'enum': ['stowed_work_attachment', 'parked_outside_work_area', 'none']},
})
FRAME_SCHEMA['properties'].update({
    'detection_dispositions': {'type': 'array', 'maxItems': 200, 'items': legacy.object_schema({
        'detection_id': {'type': 'string'}, 'status': {'type': 'string', 'enum': ['accepted', 'dismissed', 'unresolved']}, 'reason': legacy.TEXT})},
    'frame_usability': legacy.object_schema({'usable': {'type': 'boolean'}, 'reason': legacy.TEXT}),
    'class_assessability': legacy.object_schema({name: {'type': 'string', 'enum': ['assessable', 'unassessable', 'uncertain']}
                                                for name in legacy.EQUIPMENT}),
})
FRAME_SCHEMA['required'] = list(FRAME_SCHEMA['properties'])
COMPARISON_SCHEMA = legacy.object_schema({'same_view': {'type': 'boolean'}, 'view_reason': legacy.TEXT,
    'object_observation_ids': REFS, 'identity_reason': legacy.TEXT, 'non_work_evidence': legacy.TEXT})
ACTIVITY_SCHEMA = legacy.object_schema({
    'state': {'type': 'string', 'enum': ['working_signs', 'possible_idle', 'insufficient_data']},
    'reason': legacy.TEXT, 'uncertainty': legacy.TEXT,
    'comparison': {'anyOf': [COMPARISON_SCHEMA, {'type': 'null'}]},
    'frame_ids': REFS, 'observation_ids': REFS,
    'grounds': {'type': 'string', 'enum': ['visible_work_action', 'comparable_series_without_work_signs', 'insufficient_evidence']},
})
ASSESSMENT_SCHEMA = legacy.object_schema({
    **deepcopy(legacy.ASSESSMENT_SCHEMA['properties']),
    'activity': {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': ACTIVITY_SCHEMA},
    'stage_hypotheses': {'type': 'array', 'maxItems': 100, 'items': legacy.object_schema({
        'frame_ids': REFS, 'observation_ids': REFS,
        'stage': {'type': 'string', 'enum': list(legacy.STAGES)}, 'reason': legacy.TEXT,
        'work_entry_id': NULL_TEXT,
    })},
})
ASSESSMENT_SCHEMA['properties']['risks']['items'] = legacy.object_schema({
    **deepcopy(legacy.ASSESSMENT_SCHEMA['properties']['risks']['items']['properties']),
    'cause': {'type': 'string', 'enum': ['expected_equipment_missing', 'equipment_not_planned', 'possible_idle', 'visible_process_risk', 'visible_safety_risk', 'stage_plan_mismatch']},
    'work_entry_id': NULL_TEXT, 'impact': legacy.TEXT, 'recommended_check': legacy.TEXT,
    'limitations': {'type': 'array', 'minItems': 1, 'maxItems': 20, 'items': legacy.TEXT},
})
FRAME_PROMPT = legacy.PROMPT + '''
You also receive both YOLO detectors, their raw class names, scores and boxes. Treat these as fallible
proposals, never ground truth. Inspect the photograph yourself and reconcile each physical object once.
Reference all matching detection_ids; do not use a detection twice. Explain detector disagreements.
Return exactly one detection_dispositions entry for EVERY raw detection from BOTH models, even false
positives. Accepted must reference a reconciled object; dismissed/unresolved must explain visually why.
Accepted means the detection is associated with that physical object, even when its raw class is wrong.
Keep the corrected class and disagreement on the object. Dismissed means no object association: never
put a dismissed or unresolved detection_id in an object's detection_ids.
Unsupported classes retain their raw identity and null catalog_class. In particular APOCE lifting-equipment
is ambiguous and is NOT automatically mobile_crane. Set class_assessability independently for each catalog
class. Assessable means the visible region and image quality allow assessment of that class whether
present OR not detected. Do not label a clear visible region unassessable merely because a class is not
present. This never means site-wide absence. Poor visibility/occlusion/unusable photos cannot prove absence. Frame usability is explicit.
Describe visible action only (digging/loading/compacting/pouring/lifting/moving_material), or no_visible_action
or unknown. Equipment presence, raised boom, static pose or missing blur alone never prove work or idle.
Use idle_indicator only for visually explicit stowed work attachment or parking outside the work area,
otherwise none. Do not infer hidden engines, operators, work or inactivity.
A still photograph cannot prove rotation or lack of rotation, movement or lack of movement. Never say
'барабан не вращается', 'машина не движется' or equivalent from one photo. Say action is not assessable.
Stage/stage_reason are hypotheses about the scene, never assertions that work is occurring. If visual_action
is unknown, stage_reason must not assert ongoing compacting/pouring/digging. State scene compatibility.
'''
ASSESSMENT_PROMPT = legacy.ANALYSIS_PROMPT + '''
The current series photographs accompany the context. Reconcile observations with these photos.
Return per-evidence activity: working_signs requires a visible work action; possible_idle requires independent,
reliably timed comparable frames of the same zone and evidence beyond presence/static pose. Otherwise
insufficient_data. For possible_idle, comparison must bind the same physical object across each frame using
object_observation_ids, visible identity and comparable view reasons, and non-work evidence beyond a static
pose; each cited object must visibly have stowed work attachment or be parked outside the work area. This
is a possible condition requiring human checking, never a measured idle duration. For other activity states
comparison is null. Duplicate hashes are NOT independent observations. No duration or dynamics without
comparable independent frames. Stage hypotheses may be multiple, link frames and observations to applicable
work_entry_id or null. Use only the frozen plan revision, compare at each frame time with inclusive boundaries
and all concurrent operations. Rule results are conservative; do not invent missing/excluded-equipment risks
not supported by those rules. Every risk has a stable enumerated cause, applicable work (required for plan),
impact, recommended check and limitations. No process/safety signal without a zone. Reconcile duplicate
rule/model risks. No schedule delay assertion from equipment presence alone. Do not turn a hypothesis into fact.
An unusable frame cannot support a substantive stage hypothesis: use unknown/ambiguous with null
work_entry_id or omit that hypothesis. A planned stage is context, never evidence of a visible stage.
Emit a process/safety risk only for a specific visible abnormal condition. Multiple machines working normally,
ordinary soil piles or an indistinct shadow alone are not a risk. Do not invent underground utilities,
off-frame people or generic hazards. If no specific abnormal condition is visible, risks is empty.
'''


def snapshot(folder_id):
    profile = legacy.snapshot(folder_id)
    profile.update({'adapter': {'code': 'yandex_deepseek', 'version': REVISION},
                    'observation_contract': REVISION, 'instruction_version': REVISION, 'schema_version': REVISION,
                    'schema_sha256': digest(canonical_bytes([FRAME_SCHEMA, ASSESSMENT_SCHEMA])),
                    'instruction_sha256': digest((FRAME_PROMPT + ASSESSMENT_PROMPT).encode()),
                    'detector_manifest_sha256': digest(canonical_bytes(manifest()))})
    return profile


def validate_shape(value, schema):
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:
                validate_shape(value, option)
                return
            except ValueError:
                pass
        raise ValueError('hybrid_schema_invalid')
    kind = schema.get('type')
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'boolean': type(value) is bool,
             'number': type(value) in (int, float), 'null': value is None}
    if not any(valid.get(k, False) for k in (kind if isinstance(kind, list) else [kind])):
        raise ValueError('hybrid_schema_invalid')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError('hybrid_schema_invalid')
    if isinstance(value, dict):
        if set(value) != set(schema['properties']):
            raise ValueError('hybrid_schema_invalid')
        for key, item in value.items():
            validate_shape(item, schema['properties'][key])
    elif isinstance(value, list):
        if not schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 10000):
            raise ValueError('hybrid_schema_invalid')
        for item in value:
            validate_shape(item, schema['items'])
    elif isinstance(value, str) and not schema.get('minLength', 0) <= len(value.strip()) <= schema.get('maxLength', 10000):
        raise ValueError('hybrid_schema_invalid')
    elif type(value) in (int, float) and not schema.get('minimum', float('-inf')) <= value <= schema.get('maximum', float('inf')):
        raise ValueError('hybrid_schema_invalid')


def explanatory_text(value):
    fields = {'summary', 'reason', 'uncertainty', 'impact', 'action_evidence', 'evidence',
              'non_work_evidence', 'identity_reason', 'view_reason', 'stage_reason', 'text',
              'recommended_check', 'recommendations', 'limitations', 'disagreements', 'missing_localization_reason'}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in fields:
                if isinstance(item, str):
                    yield item
                elif isinstance(item, list):
                    yield from (text for text in item if isinstance(text, str))
            if isinstance(item, (dict, list)):
                yield from explanatory_text(item)
    elif isinstance(value, list):
        for item in value:
            yield from explanatory_text(item)


def asserts(text, pattern, *, recommendations_allowed=True):
    for clause in re.split(r'[.!?;\n]|\b(?:но|однако|but|however)\b', text, flags=re.I):
        if not re.search(pattern, clause, re.I):
            continue
        if re.search(r'невозможн|нельзя|недостаточно|нет данных|не подтвержд|не установл|не измер'
                     r'|не позволяет|не да[её]т|неизвестн|не доказыва|не доказан|не определ|не дела[ею]|не формиру|cannot|insufficient|unknown'
                     r'|not (?:verified|confirmed|established|measured)', clause, re.I):
            continue
        if recommendations_allowed and re.match(
                r'\s*(?:для оценки|чтобы оценить|проверить|уточнить|оценить|выполнить|необходимо|нужно|следует|'
                r'рекомендуется|требуется|check|assess|verify|to assess)\b', clause, re.I):
            continue
        return True
    return False


def validate_duration_claims(statements):
    duration = (r'(?:длительность|продолжительность|длится|продолжается|непрерывн\w*|простаива\w*)'
                r'.{0,80}\d+(?:[.,]\d+)?\s*(?:минут|час|дн|сут|секунд)'
                r'|(?:работа[ею]т|работал[аи]?|бездейств\w*|длился|длилась|длились|длятся)'
                r'.{0,40}\d+(?:[.,]\d+)?\s*(?:минут|час|дн|сут|секунд)'
                r'|(?:idle|work(?:ing)?|operation).{0,60}(?:for|duration|lasted).{0,20}'
                r'\d+\s*(?:minutes?|hours?|days?|seconds?)')
    if any(asserts(text, duration, recommendations_allowed=False) for text in statements):
        raise ValueError('hybrid_duration_unverified')


def distinct_instants(frames):
    try:
        times = [datetime.fromisoformat(f['captured_at']) for f in frames]
        return len(set(times)) if all(t.utcoffset() is not None for t in times) else 0
    except (KeyError, ValueError, TypeError):
        return 0


def assessment_schema(context):
    schema = deepcopy(ASSESSMENT_SCHEMA)
    frames = context['frames']
    if (context.get('comparison_method') != 'same_zone_independent_timed_frames'
            or len({f['sha256'] for f in frames}) < 2 or distinct_instants(frames) < 2):
        schema['properties']['activity']['items']['properties']['state']['enum'] = ['working_signs', 'insufficient_data']
        causes = schema['properties']['risks']['items']['properties']['cause']['enum']
        causes.remove('possible_idle')
    supported_rules = {rule['kind'] for rule in context.get('rule_results', [])}
    causes = schema['properties']['risks']['items']['properties']['cause']['enum']
    causes[:] = [cause for cause in causes if cause not in ('expected_equipment_missing', 'equipment_not_planned')
                 or cause in supported_rules]
    if not context.get('plan'):
        causes[:] = [cause for cause in causes if cause != 'stage_plan_mismatch']
    work_ids = [entry['id'] for entry in (context.get('plan') or {}).get('entries', [])]
    for key in ('risks', 'stage_hypotheses'):
        schema['properties'][key]['items']['properties']['work_entry_id'] = {
            'type': ['string', 'null'], 'enum': [*work_ids, None]}
    if not context.get('zone_id') or not any(f['frame_usability']['usable'] for f in frames):
        schema['properties']['risks']['maxItems'] = 0
    return schema


def validate_frame(value, context):
    validate_shape(value, FRAME_SCHEMA)
    validate_duration_claims(list(explanatory_text(value)))
    if not value['frame_usability']['usable'] and value['stage'] not in ('unknown', 'ambiguous'):
        raise ValueError('hybrid_unusable_stage')
    original = {k: value[k] for k in legacy.SCHEMA['properties']}
    original['objects'] = [{k: o[k] for k in legacy.SCHEMA['properties']['objects']['items']['properties']} for o in value['objects']]
    legacy.validate_annotation(original)
    detections = {d['id'] for model in context['detectors']['models'] for d in model['detections']}
    used = set()
    for obj in value['objects']:
        refs = obj['detection_ids']
        if len(refs) != len(set(refs)) or not set(refs) <= detections or used & set(refs):
            raise ValueError('hybrid_detection_reference_invalid')
        used.update(refs)
        if not value['frame_usability']['usable'] and obj['visual_action'] not in ('unknown', 'no_visible_action'):
            raise ValueError('hybrid_unusable_action')
    dispositions = value['detection_dispositions']
    if len(dispositions) != len(detections) or {d['detection_id'] for d in dispositions} != detections:
        raise ValueError('hybrid_detection_disposition_incomplete')
    if any((d['status'] == 'accepted') != (d['detection_id'] in used) for d in dispositions):
        raise ValueError('hybrid_detection_disposition_conflict')
    return value


def references(value, frames, require=True):
    ids, refs = value['frame_ids'], value['observation_ids']
    if not ids or (require and not refs) or len(ids) != len(set(ids)) or len(refs) != len(set(refs)):
        raise ValueError('hybrid_reference_invalid')
    if not set(ids) <= frames.keys():
        raise ValueError('hybrid_reference_invalid')
    observations = {o['id']: o for key in ids for o in frames[key]['observations']}
    if not set(refs) <= observations.keys() or (require and any(not set(refs) & {o['id'] for o in frames[key]['observations']} for key in ids)):
        raise ValueError('hybrid_reference_invalid')
    return [observations[key] for key in refs]


def applicable(entry, frame):
    try:
        time = datetime.fromisoformat(frame['captured_at'])
        return entry['state'] == 'active' and datetime.fromisoformat(entry['starts_at']) <= time <= datetime.fromisoformat(entry['ends_at'])
    except (ValueError, TypeError, KeyError):
        return False


def validate_assessment(value, context):
    validate_shape(value, ASSESSMENT_SCHEMA)
    base = {k: deepcopy(value[k]) for k in legacy.ASSESSMENT_SCHEMA['properties']}
    base['risks'] = [{k: r[k] for k in legacy.ASSESSMENT_SCHEMA['properties']['risks']['items']['properties']} for r in value['risks']]
    legacy.validate_assessment(base, context)
    frames = {f['input_id']: f for f in context['frames']}
    entries = {e['id']: e for e in (context.get('plan') or {}).get('entries', [])}
    for activity in value['activity']:
        observations = references(activity, frames, require=activity['state'] != 'insufficient_data')
        if activity['state'] == 'insufficient_data':
            if activity['grounds'] != 'insufficient_evidence':
                raise ValueError('hybrid_activity_ground_invalid')
            continue
        if any(not frames[key]['frame_usability']['usable'] for key in activity['frame_ids']):
            raise ValueError('hybrid_usable_evidence_required')
        if activity['state'] == 'working_signs':
            if activity['grounds'] != 'visible_work_action' or any(not any(
                    o['id'] in activity['observation_ids'] and o.get('visual_action') in ACTIONS[:6]
                    for o in frames[key]['observations']) for key in activity['frame_ids']):
                raise ValueError('hybrid_work_action_required')
        else:
            comparison = activity['comparison']
            if (activity['grounds'] != 'comparable_series_without_work_signs'
                    or context.get('comparison_method') != 'same_zone_independent_timed_frames'
                    or len({frames[key]['sha256'] for key in activity['frame_ids']}) < 2
                    or distinct_instants([frames[key] for key in activity['frame_ids']]) < 2
                    or not comparison or not comparison['same_view']):
                raise ValueError('hybrid_independent_frames_required')
            matched = references({'frame_ids': activity['frame_ids'], 'observation_ids': comparison['object_observation_ids']}, frames)
            if (not set(comparison['object_observation_ids']) <= set(activity['observation_ids'])
                    or len(matched) != len(activity['frame_ids'])
                    or len({o.get('catalog_class') for o in matched}) != 1
                    or any(o.get('catalog_class') is None or o.get('status') != 'identified'
                           or o.get('visual_action') != 'no_visible_action'
                           or o.get('idle_indicator') not in ('stowed_work_attachment', 'parked_outside_work_area') for o in matched)):
                raise ValueError('hybrid_idle_correspondence_unverified')
    if (value['stage_hypothesis']['stage'] not in ('unknown', 'ambiguous')
            and not any(f['frame_usability']['usable'] for f in frames.values())):
        raise ValueError('hybrid_unusable_stage')
    for hypothesis in value['stage_hypotheses']:
        if hypothesis['stage'] not in ('unknown', 'ambiguous') and any(not frames.get(key, {}).get('frame_usability', {}).get('usable') for key in hypothesis['frame_ids']):
            raise ValueError('hybrid_unusable_stage')
        references(hypothesis, frames)
        work = hypothesis['work_entry_id']
        if work is not None and (work not in entries or any(not applicable(entries[work], frames[key]) for key in hypothesis['frame_ids'])
                                 or hypothesis['stage'] not in ('unknown', 'ambiguous')
                                 and entries[work].get('stage_key') != hypothesis['stage']):
            raise ValueError('hybrid_work_reference_invalid')
    for risk in value['risks']:
        observations = references(risk, frames)
        if not context.get('zone_id') or any(not frames[key]['frame_usability']['usable'] for key in risk['frame_ids']):
            raise ValueError('hybrid_usable_zone_required')
        categories = {'expected_equipment_missing': 'plan', 'equipment_not_planned': 'plan',
                      'stage_plan_mismatch': 'plan', 'visible_process_risk': 'process', 'visible_safety_risk': 'safety'}
        if risk['cause'] in categories and risk['category'] != categories[risk['cause']]:
            raise ValueError('hybrid_risk_category_conflict')
        work = risk['work_entry_id']
        if work is not None and (work not in entries or any(not applicable(entries[work], frames[key]) for key in risk['frame_ids'])):
            raise ValueError('hybrid_work_reference_invalid')
        if risk['category'] == 'plan' and work is None:
            raise ValueError('hybrid_plan_work_required')
        if risk['cause'] in ('expected_equipment_missing', 'equipment_not_planned'):
            if not any(r['kind'] == risk['cause'] and r['entry_id'] == work and set(r['supporting_input_ids']) == set(risk['frame_ids'])
                       for r in context.get('rule_results', [])):
                raise ValueError('hybrid_rule_support_required')
        if risk['cause'] == 'stage_plan_mismatch':
            for key in risk['frame_ids']:
                planned = {e.get('stage_key') for e in entries.values() if applicable(e, frames[key])}
                if not any(key in h['frame_ids'] and h['stage'] not in (*planned, 'unknown', 'ambiguous') for h in value['stage_hypotheses']):
                    raise ValueError('hybrid_stage_mismatch_unverified')
        if risk['cause'] == 'possible_idle' and not any(a['state'] == 'possible_idle'
                and set(a['frame_ids']) == set(risk['frame_ids']) and set(risk['observation_ids']) <= set(a['observation_ids'])
                for a in value['activity']):
            raise ValueError('hybrid_idle_correspondence_unverified')
        if risk['cause'] in ('visible_process_risk', 'visible_safety_risk') and not all(o.get('visible') is True for o in observations):
            raise ValueError('hybrid_visible_evidence_required')
    statements = list(explanatory_text(value))
    validate_duration_claims(statements)
    temporal = any(a['state'] == 'possible_idle' and a['comparison'] and a['comparison']['same_view']
                   for a in value['activity'])
    if not temporal and any(asserts(t, r'динамика.{0,50}(?:показывает|подтверждает)|(?:темп|производительность).{0,30}(?:вырос|снизил|увеличил)|(?:increased|decreased) productivity') for t in statements):
        raise ValueError('hybrid_dynamics_unverified')
    if not any(a['state'] == 'possible_idle' for a in value['activity']) and any(asserts(t, r'простаива|простой|\bidle\b') for t in statements):
        raise ValueError('hybrid_idle_correspondence_unverified')
    if any(asserts(t, r'отстав|отста[ёе]|задерж|delay|behind\s+schedule') for t in statements) and not any(r['category'] == 'plan' and r['work_entry_id'] for r in value['risks']):
        raise ValueError('hybrid_delay_work_required')
    return value
