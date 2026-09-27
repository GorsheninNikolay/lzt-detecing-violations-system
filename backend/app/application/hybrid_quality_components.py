"""Measure original component outputs against reviewed visual references."""
from decimal import Decimal
from datetime import datetime
import base64
import math

from app.application.deepseek_runtime import observation_context
from app.profiles import deepseek, hybrid
from app.shared.cloud import canonical_bytes, digest


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def finite(value, *, positive=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0), 'component_measurement_invalid')
    return value


def box(value):
    require(isinstance(value, list) and len(value) == 4
            and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in value)
            and value[0] < value[2] and value[1] < value[3], 'component_box_invalid')
    return value


def iou(a, b):
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - overlap
    return overlap / union


def measure(predictions, references, threshold):
    for obj in predictions + references:
        require(obj['catalog_class'] is None or obj['catalog_class'] in deepseek.EQUIPMENT,
                'component_class_invalid')
        box(obj['box'])
    candidates = sorted(((iou(p['box'], r['box']), p_index, r_index)
                         for p_index, p in enumerate(predictions) for r_index, r in enumerate(references)
                         if p['catalog_class'] == r['catalog_class']), reverse=True)
    matched_p, matched_r, overlaps = set(), set(), []
    matches = []
    for overlap, p_index, r_index in candidates:
        if overlap >= threshold and p_index not in matched_p and r_index not in matched_r:
            matched_p.add(p_index); matched_r.add(r_index); overlaps.append(overlap)
            matches.append((p_index, r_index))
    tp, fp, fn = len(matches), len(predictions)-len(matches), len(references)-len(matches)
    per_class = {}
    for name in (*deepseek.EQUIPMENT, None):
        class_matches = [(p, r) for p, r in matches if references[r]['catalog_class'] == name]
        class_tp = len(class_matches)
        per_class[name or 'unsupported'] = {
            'tp': class_tp, 'fp': sum(p['catalog_class'] == name for p in predictions)-class_tp,
            'fn': sum(r['catalog_class'] == name for r in references)-class_tp,
            'matched_iou': [iou(predictions[p]['box'], references[r]['box']) for p, r in class_matches]}
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': tp/(tp+fp) if tp+fp else None,
            'recall': tp/(tp+fn) if tp+fn else None,
            'matched_iou': overlaps, 'matches': matches, 'per_class': per_class}


def add_measurement(total, measured, latency):
    for target, source in [(total, measured), *[(total['per_class'][name], values)
                                               for name, values in measured['per_class'].items()]]:
        for field in ('tp', 'fp', 'fn'): target[field] += source[field]
        target['matched_iou'].extend(source['matched_iou'])
    total['latency_ms'].append(finite(latency, positive=True))


def request_body(kind, context, profile, images):
    prompt = hybrid.FRAME_PROMPT if kind == 'frame' else hybrid.ASSESSMENT_PROMPT
    content = [{'type': 'input_text', 'text': prompt + canonical_bytes(context).decode()}]
    for key, raw in images:
        oriented, media, _ = deepseek.oriented_image(raw)
        if kind == 'assessment':
            content.append({'type': 'input_text', 'text': 'Current frame input_id: ' + key})
        content.append({'type': 'input_image', 'image_url': 'data:' + media + ';base64,'
                        + base64.b64encode(oriented).decode(), 'detail': 'auto'})
    return {'model': profile['requested_model_identity']['id'], 'store': False,
            'temperature': 0, 'max_output_tokens': deepseek.MAX_OUTPUT, 'reasoning': {'effort': 'none'},
            'text': {'format': {'type': 'json_schema', 'name': kind, 'strict': True,
                               'schema': hybrid.FRAME_SCHEMA if kind == 'frame' else hybrid.assessment_schema(context)}},
            'input': [{'role': 'user', 'content': content}]}


def response(call, profile, request):
    require(call['request'] == request and call['request_sha256'] == digest(canonical_bytes(request)),
            'component_request_binding_mismatch')
    value = deepseek.validate_response(call['raw'], profile['requested_model_identity']['id'], 'none')
    usage = deepseek.validate_usage(call['raw'])
    finite(call['latency_ms'], positive=True)
    cost = (Decimal(usage['input_tokens'])*Decimal('0.3') + Decimal(usage['output_tokens'])*Decimal('0.5')) / 1000
    return value, cost, {'response_id': call['raw']['id'], 'request_sha256': call['request_sha256'],
                         'usage': usage, 'cost_estimate_rub': str(cost)}


def validate_edge_cases(tags, context, frames, assessment):
    entries = (context.get('plan') or {}).get('entries', [])
    comparable = [a for a in assessment['activity'] if a['comparison']
                  and len(a['comparison']['object_observation_ids']) >= 2]
    instants = [datetime.fromisoformat(f['captured_at'].replace('Z', '+00:00'))
                for f in context['frames'] if f['captured_at'] is not None]
    boundaries = [datetime.fromisoformat(e[name].replace('Z', '+00:00'))
                  for e in entries for name in ('starts_at', 'ends_at')]
    properties = {
        'no_plan': context.get('plan') is None,
        'unknown_time': any(f['captured_at'] is None for f in context['frames']),
        'repeated_image': len({f['sha256'] for f in context['frames']}) < len(context['frames']),
        'visible_action': any(a['state'] == 'working_signs' for a in assessment['activity']),
        'possible_idle': any(a['state'] == 'possible_idle' for a in assessment['activity']),
        'same_machine_multi_frame': bool(comparable),
        'interval_boundaries': bool(set(instants) & set(boundaries)),
        'concurrent_works': any(sum(hybrid.applicable(e, f) for e in entries) >= 2 for f in context['frames']),
        'occlusion': any(o['status'] == 'uncertain' or o['missing_localization_reason'] is not None
                         for frame in frames for o in frame['objects']),
        'similar_equipment': any(a['status'] == b['status'] == 'identified'
                                 and a['catalog_class'] is not None and a['catalog_class'] == b['catalog_class']
                                 and a['box'] is not None and b['box'] is not None and iou(a['box'], b['box']) == 0
                                 for frame in frames for index, a in enumerate(frame['objects'])
                                 for b in frame['objects'][index+1:]),
    }
    require(all(tag in properties and properties[tag] for tag in tags), 'component_edge_case_not_exercised')


def qualify_components(result, annotation, case, profile, weights, root):
    evidence, reference = result['component_evidence'], annotation['component_reference']
    threshold = reference['iou_match_threshold']
    require(type(threshold) in (int, float) and math.isfinite(threshold) and 0 < threshold <= 1,
            'localization_protocol_missing')
    sources = {frame['input_id']: frame for frame in case['frames']}
    require(len(sources) == len(case['frames']) and set(reference['frames']) == set(sources),
            'component_sources_incomplete')
    frames = evidence['frames']
    require(isinstance(frames, list) and len(frames) == len(sources)
            and {f['input_id'] for f in frames} == set(sources), 'component_frames_incomplete')
    # Manifest identity is checked again on every raw detector result.
    totals = {name: {'tp': 0, 'fp': 0, 'fn': 0, 'matched_iou': [], 'latency_ms': []}
              for name in (*weights, 'hybrid')}
    for total in totals.values():
        total['per_class'] = {name: {'tp': 0, 'fp': 0, 'fn': 0, 'matched_iou': []}
                              for name in (*deepseek.EQUIPMENT, 'unsupported')}
    contexts, response_ids, cost, semantic_frames, calls, images = [], [], Decimal(0), [], [], []
    for ordinal, frame in enumerate(frames):
        key, source = frame['input_id'], sources[frame['input_id']]
        require(frame['sha256'] == source['sha256'], 'component_source_binding_mismatch')
        detectors = frame['detectors']
        raw = (root / source['path']).read_bytes()
        require(digest(raw) == source['sha256'], 'component_source_binding_mismatch')
        oriented, _, dimensions = deepseek.oriented_image(raw)
        images.append((key, raw))
        require(detectors['oriented_sha256'] == digest(oriented), 'component_detector_pixels_mismatch')
        require(digest(canonical_bytes(detectors['manifest'])) == profile['detector_manifest_sha256'],
                'component_manifest_mismatch')
        models = detectors['models']
        require(len(models) == len(weights) and {m['model_id'] for m in models} == set(weights),
                'component_models_incomplete')
        approved = reference['frames'][key]
        require(type(approved['frame_usability']) is bool and approved['stage'] in deepseek.STAGES,
                'component_reference_invalid')
        original = approved['objects']
        require(isinstance(original, list), 'component_reference_invalid')
        for obj in original:
            require(obj['visual_action'] in hybrid.ACTIONS, 'component_action_invalid')
        detection_ids = set()
        for model in models:
            name = model['model_id']
            require(model['weights_sha256'] == weights[name], 'component_weights_mismatch')
            require(model['image_size'] == dimensions, 'component_detector_dimensions_mismatch')
            for detection in model['detections']:
                require(detection['id'] not in detection_ids and detection['input_id'] == key
                        and detection['model_id'] == name, 'component_detection_binding_mismatch')
                detection_ids.add(detection['id'])
                finite(detection['score'])
                require(detection['score'] <= 1, 'component_detection_score_invalid')
                definition = next(m for m in detectors['manifest']['models'] if m['id'] == name)
                class_id = detection['class_id']
                require(type(class_id) is int and 0 <= class_id < len(definition['classes'])
                        and detection['raw_class'] == definition['classes'][class_id]
                        and detection['catalog_class'] == definition['mapping'][detection['raw_class']],
                        'component_class_binding_mismatch')
            measured = measure(model['detections'], original, threshold)
            add_measurement(totals[name], measured, model['latency_ms'])
        value, call_cost, receipt = response(frame['deepseek'], profile,
                                            request_body('frame', {'input_id': key, 'detectors': detectors},
                                                         profile, [(key, raw)]))
        calls.append(receipt)
        cost += call_cost; response_ids.append(frame['deepseek']['raw']['id'])
        hybrid.validate_frame(value, {'input_id': key, 'detectors': detectors})
        require(value['frame_usability']['usable'] == approved['frame_usability']
                and value['stage'] == approved['stage'], 'component_frame_semantics_mismatch')
        reconciled = [o for o in value['objects'] if o['status'] == 'identified' and o['catalog_class'] is not None]
        require(all(o['box'] is not None for o in reconciled), 'component_localization_missing')
        measured = measure(reconciled, original, threshold)
        for p_index, r_index in measured['matches']:
            require(reconciled[p_index]['visual_action'] == original[r_index]['visual_action'],
                    'component_action_mismatch')
        require(measured['fp'] == 0 and measured['fn'] == 0, 'component_reconciled_objects_mismatch')
        add_measurement(totals['hybrid'], measured, frame['deepseek']['latency_ms'])
        context = observation_context({'input_id': key, 'ordinal': ordinal, 'sha256': source['sha256'],
                                       'artifact_id': key}, {'value': value, 'detectors': detectors})
        context['captured_at'] = source['captured_at']
        contexts.append(context); semantic_frames.append(value)
    context = {**reference['context'], 'frames': contexts}
    require(evidence['assessment_context'] == context, 'component_context_mismatch')
    value, call_cost, receipt = response(evidence['assessment'], profile,
                                        request_body('assessment', context, profile, images))
    calls.append(receipt)
    cost += call_cost; response_ids.append(evidence['assessment']['raw']['id'])
    require(len(response_ids) == len(set(response_ids)), 'component_response_reused')
    hybrid.validate_shape(value, hybrid.assessment_schema(context))
    hybrid.validate_assessment(value, context)
    validate_edge_cases(case.get('edge_cases', []), context, semantic_frames, value)
    observed_assessment = {'stage': value['stage_hypothesis']['stage'],
                           'activity': sorted(a['state'] for a in value['activity']),
                           'signals': sorted(r['cause'] for r in value['risks'])}
    require(observed_assessment == reference['assessment'], 'component_assessment_mismatch')
    equipment = sorted({o['catalog_class'] for v in semantic_frames for o in v['objects']
                        if o['status'] == 'identified' and o['catalog_class'] is not None})
    expected = annotation['expected']
    require(equipment == sorted(expected['equipment']) and observed_assessment['stage'] == expected['stage']
            and sorted(set(observed_assessment['signals'])) == sorted(expected['warnings']),
            'component_expected_projection_mismatch')
    usable = any(v['frame_usability']['usable'] for v in semantic_frames)
    outcome = ('unusable' if not usable else 'grounded-risk' if value['risks'] else
               'ambiguous' if value['stage_hypothesis']['stage'] in ('unknown', 'ambiguous') else 'normal')
    require(outcome == case['outcome'], 'component_outcome_mismatch')
    for total in [*totals.values(), *(values for model in totals.values() for values in model['per_class'].values())]:
        tp, fp, fn = (total[field] for field in ('tp', 'fp', 'fn'))
        total.update(precision=tp/(tp+fp) if tp+fp else None, recall=tp/(tp+fn) if tp+fn else None,
                     mean_matched_iou=sum(total['matched_iou'])/len(total['matched_iou']) if total['matched_iou'] else None)
    return {'models': totals, 'semantic': observed_assessment, 'equipment': equipment, 'outcome': outcome,
            'cost_estimate_rub': str(cost), 'response_ids': response_ids,
            'calls': calls,
            'assessment_latency_ms': evidence['assessment']['latency_ms'],
            'iou_match_threshold': threshold}
