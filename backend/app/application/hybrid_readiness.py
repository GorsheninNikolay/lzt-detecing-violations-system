"""Qualify current-profile evidence without trusting self-reported pass flags."""
import json
import math
from datetime import datetime
from pathlib import Path

from decimal import Decimal

from app.profiles.deepseek import EQUIPMENT
from app.application.hybrid_quality_components import qualify_components
from app.shared.quality_budget import exposure, UPPER_RUB, verify_history
from app.shared.cloud import canonical_bytes, digest

REPORT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'hybrid-readiness.json'
DIAGNOSTIC_RESERVATIONS_PATH = Path(__file__).resolve().parents[3] / 'evaluation/hybrid/diagnostic-reservations.json'
STAGES = ('excavation', 'concreting', 'roadwork')
REQUIRED_EDGE_CASES = {'same_machine_multi_frame', 'similar_equipment', 'occlusion', 'repeated_image', 'interval_boundaries',
                       'concurrent_works', 'no_plan', 'unknown_time', 'visible_action', 'possible_idle'}
OUTCOMES = ('normal', 'grounded-risk', 'ambiguous', 'unusable')
SOURCE_MANIFEST_HASHES = {'kaggle': 'c53372324ceacdd600f35b6c0a5911912b540faa871283e717d27957adc057a6',
                              'apoce': '739eaca8d051d95a519c4aee344d18b883da21d8c3e0f9cf666d75d2bb6d801c'}


def content_hash(value):
    return digest(canonical_bytes(value))


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.utcoffset() is not None, 'execution_time_missing_timezone')
    return parsed


def artifact(ref, root, *, json_value=True):
    require(isinstance(ref, dict), 'artifact_reference_missing')
    path = (root / ref['path']).resolve()
    payload = path.read_bytes()
    require(digest(payload) == ref['sha256'], 'artifact_digest_mismatch')
    return json.loads(payload) if json_value else payload


def qualify(report, profile, root):
    require(report.get('schema') == 'hybrid-quality-v1', 'report_contract_missing')
    manifest = report['detector_manifest']
    require(content_hash(manifest) == profile['detector_manifest_sha256'], 'manifest_content_mismatch')
    weights = {model['id']: model['sha256'] for model in manifest['models']}
    require(len(weights) == 2 and set(weights) == {'apoce', 'kaggle'}, 'models_incomplete')
    inventory = artifact(report['inventory'], root)
    source_inventory = artifact(report['source_inventory'], root)
    annotations = artifact(report['annotations'], root)
    review = artifact(report['human_review'], root)
    require(review['actor_type'] == 'human' and isinstance(review['reviewer'], str)
            and review['reviewer'].strip() and review['decision'] == 'approved'
            and isinstance(review['rationale'], str) and review['rationale'].strip(), 'human_adjudication_missing')
    instant(review['reviewed_at'])
    require(review['detector_manifest_sha256'] == profile['detector_manifest_sha256']
            and review['source_inventory_sha256'] == report['source_inventory']['sha256'], 'review_profile_binding_mismatch')
    require(set(review['mapping_decisions']) == set(weights) and all(
        decision['decision'] == 'approved' and isinstance(decision['rationale'], str) and decision['rationale'].strip()
        for decision in review['mapping_decisions'].values()), 'mapping_adjudication_missing')
    require(review['inventory_sha256'] == report['inventory']['sha256']
            and review['annotations_sha256'] == report['annotations']['sha256'], 'review_binding_mismatch')
    cases = inventory['cases']
    require(isinstance(cases, list) and cases, 'cases_missing')
    ids = [case['id'] for case in cases]
    require(all(isinstance(key, str) and key for key in ids) and len(set(ids)) == len(ids), 'duplicate_case_ids')
    require(set(review['case_ids']) == set(ids) and len(review['case_ids']) == len(ids), 'control_review_incomplete')
    require(set(annotations) == set(ids), 'annotations_incomplete')
    queue_path = Path(__file__).resolve().parents[3] / 'evaluation/hybrid/control-review-queue.json'
    reserved = json.loads(queue_path.read_text())['images']
    forbidden = {row['sha256'] for row in reserved}
    source_hashes, pixel_hashes = {}, {}
    partition_hashes = source_inventory['partition_hashes']
    authoritative_reservations = json.loads(DIAGNOSTIC_RESERVATIONS_PATH.read_text())['frames']
    reserved_pixels = {row['rgb_sha256'] for row in authoritative_reservations}
    require(source_inventory['reserved_diagnostic_frames'] == authoritative_reservations, 'diagnostic_pixels_not_bound')
    expected_source_hashes = SOURCE_MANIFEST_HASHES
    from collections import defaultdict
    recomputed = {'bytes': defaultdict(list), 'decoded_rgb': defaultdict(list)}
    for model_id, expected_hash in expected_source_hashes.items():
        ref = source_inventory['source_manifests'][model_id]
        require(ref['sha256'] == expected_hash, 'source_manifest_unrecognized')
        source_manifest = artifact(ref, root)
        for source in source_manifest['pairs']:
            role = 'candidate_not_ground_truth' if source['split'] == 'test' else source['split']
            member = {'id': model_id + '/' + source['image'], 'role': role}
            recomputed['bytes'][source['image_sha256']].append(member)
            recomputed['decoded_rgb'][source['pixel_sha256']].append(member)
    for source in authoritative_reservations:
        member = {'id': source['id'], 'role': 'diagnostic'}
        recomputed['bytes'][source['sha256']].append(member)
        recomputed['decoded_rgb'][source['rgb_sha256']].append(member)
    require(partition_hashes == recomputed, 'source_partition_map_tampered')
    require({row['sha256'] for row in source_inventory['reserved_diagnostic_frames']} == forbidden,
            'diagnostic_reservation_incomplete')
    coverage, classes, edge_cases = set(), set(), set()
    from PIL import Image, ImageOps
    import io
    for case in cases:
        require(case['role'] == 'final_control' and case['stage'] in STAGES and case['outcome'] in OUTCOMES,
                'case_role_or_scenario_invalid')
        coverage.add((case['stage'], case['outcome']))
        require(isinstance(case['edge_cases'], list) and set(case['edge_cases']) <= REQUIRED_EDGE_CASES, 'edge_case_tags_invalid')
        edge_cases.update(case['edge_cases'])
        annotation = annotations[case['id']]
        expected = annotation['expected']
        require(set(expected) == {'equipment', 'stage', 'outcome', 'warnings'}, 'expected_contract_invalid')
        require(expected['stage'] in (*STAGES, 'unknown', 'ambiguous') and expected['outcome'] == case['outcome']
                and (case['outcome'] in ('ambiguous', 'unusable') or expected['stage'] == case['stage']), 'expectation_conflict')
        require(isinstance(expected['equipment'], list) and set(expected['equipment']) <= set(EQUIPMENT)
                and len(set(expected['equipment'])) == len(expected['equipment']), 'equipment_invalid')
        require(isinstance(expected['warnings'], list) and all(isinstance(w, str) and w.strip() for w in expected['warnings'])
                and len(set(expected['warnings'])) == len(expected['warnings']), 'warnings_invalid')
        require(bool(expected['warnings']) == (case['outcome'] == 'grounded-risk'), 'warning_expectation_invalid')
        require(annotation['label_review'] == 'approved' and annotation['expectation_review'] == 'approved'
                and isinstance(annotation['rationale'], str) and annotation['rationale'].strip(), 'labels_unreviewed')
        classes.update(expected['equipment'])
        require(isinstance(case['frames'], list) and case['frames'], 'source_frames_missing')
        for frame in case['frames']:
            require(frame['source_partition'] in ('test', 'new_control') and 'source_group' in frame
                    and 'rights_reference' in frame and 'captured_at' in frame, 'source_provenance_missing')
            if frame['captured_at'] is None:
                require(frame['timing_provenance'] == 'unknown', 'unknown_time_provenance_invalid')
            else:
                instant(frame['captured_at'])
                require(frame['timing_provenance'] == 'verified_capture_record', 'capture_time_unverified')
                timing = artifact(frame['capture_time_evidence'], root)
                require(timing['frame_sha256'] == frame['sha256'] and timing['captured_at'] == frame['captured_at']
                        and timing['provenance'] in ('original_device_record', 'independent_capture_record')
                        and timing['decision'] == 'approved' and timing['simulated'] is False
                        and isinstance(timing['reviewer'], str) and timing['reviewer'].strip(), 'capture_time_unverified')
                artifact(timing['original_record'], root, json_value=False)
            require(frame['sha256'] not in forbidden, 'diagnostic_control_reuse')
            raw = artifact({'path': frame['path'], 'sha256': frame['sha256']}, root, json_value=False)
            with Image.open(io.BytesIO(raw)) as image:
                image = ImageOps.exif_transpose(image).convert('RGB')
                pixels = digest(str(image.size).encode() + image.tobytes())
            require(pixels == frame['rgb_sha256'], 'source_pixel_digest_mismatch')
            require(pixels not in reserved_pixels, 'diagnostic_pixel_reuse')
            for kind, value in (('bytes', frame['sha256']), ('decoded_rgb', pixels)):
                roles = partition_hashes[kind].get(value, [])
                require(not any(item['role'] in ('train', 'val', 'diagnostic') for item in roles),
                        'source_partition_overlap')
                require(frame['source_partition'] != 'test' or bool(roles), 'test_source_not_bound')
            require(source_hashes.get(frame['sha256'], case['id']) == case['id']
                    and pixel_hashes.get(pixels, case['id']) == case['id'], 'duplicate_control_frames')
            if frame['sha256'] in source_hashes or pixels in pixel_hashes:
                require('repeated_image' in case['edge_cases'], 'unreviewed_duplicate_input')
            source_hashes[frame['sha256']] = case['id']; pixel_hashes[pixels] = case['id']
            artifact(frame['original_label'], root, json_value=False)
            require(frame['source_group'] is not None or 'unknown_scene_groups' in inventory['limitations'],
                    'unknown_groups_not_disclosed')
    require(coverage == {(stage, outcome) for stage in STAGES for outcome in OUTCOMES}, 'scenario_coverage_incomplete')
    require(classes == set(EQUIPMENT), 'equipment_coverage_incomplete')
    require(edge_cases == REQUIRED_EDGE_CASES, 'edge_case_coverage_incomplete')
    runs = report['runs']
    require(isinstance(runs, list), 'runs_missing')
    execution_ids, execution_times, per_case = set(), set(), {key: 0 for key in ids}
    latency = []
    false_warnings = 0
    components, response_ids = [], set()
    cases_by_id = {case['id']: case for case in cases}
    for run in runs:
        require(run['case_id'] in per_case and isinstance(run['execution_id'], str) and run['execution_id']
                and run['execution_id'] not in execution_ids, 'duplicate_or_unknown_execution')
        started = instant(run['started_at'])
        require(started not in execution_times, 'executions_not_distinct')
        execution_ids.add(run['execution_id']); execution_times.add(started)
        require(run['profile_sha256'] == report['profile_sha256'] and run['model_sha256'] == weights
                and run['inventory_sha256'] == report['inventory']['sha256']
                and run['annotations_sha256'] == report['annotations']['sha256'], 'execution_binding_mismatch')
        result = artifact(run['result'], root)
        require(result['execution_id'] == run['execution_id'] and result['case_id'] == run['case_id']
                and result['profile_sha256'] == run['profile_sha256'] and result['model_sha256'] == weights,
                'result_binding_mismatch')
        elapsed = result['latency_ms']
        require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed > 0, 'measurement_invalid')
        latency.append(elapsed)
        expected = annotations[run['case_id']]['expected']
        component = qualify_components(result, annotations[run['case_id']], cases_by_id[run['case_id']], profile, weights, root)
        require(not response_ids.intersection(component['response_ids']), 'response_reused_across_executions')
        response_ids.update(component['response_ids'])
        components.append(component)
        reference_equipment = sorted({obj['catalog_class'] for frame in annotations[run['case_id']]['component_reference']['frames'].values()
                                      for obj in frame['objects'] if obj['catalog_class'] is not None})
        observed = {'equipment': reference_equipment, 'stage': component['semantic']['stage'],
                    'outcome': component['outcome'], 'warnings': component['semantic']['signals']}
        require(result['observed'] == observed, 'projected_component_mismatch')
        require(isinstance(observed, dict) and set(observed) == set(expected), 'observed_contract_invalid')
        require(isinstance(observed['warnings'], list) and all(isinstance(w, str) for w in observed['warnings']),
                'observed_warnings_invalid')
        false_warnings += len(set(observed['warnings']) - set(expected['warnings']))
        require(false_warnings == 0, 'false_warning')
        require(observed == expected, 'expected_observed_mismatch')
        per_case[run['case_id']] += 1
    require(all(count >= 3 for count in per_case.values()), 'three_executions_required')
    ledger = artifact(report['budget_ledger'], root)
    verify_history(ledger)
    historical = json.loads((queue_path.parent / 'budget.json').read_text())
    calls = {call['id']: call for call in ledger['calls']}
    require(len(calls) == len(ledger['calls']) and all(calls.get(call['id']) == call for call in historical['calls']),
            'historical_budget_exposure_missing')
    require(Decimal(str(ledger['limit_rub'])) == Decimal('1000') and exposure(ledger) <= Decimal('1000'), 'budget_exceeded')
    require(all(Decimal(str(call['upper_rub'])) == UPPER_RUB for call in ledger['calls']), 'budget_reservation_bound_invalid')
    response_calls = {}
    for call in ledger['calls']:
        if call.get('response_id'):
            require(call['response_id'] not in response_calls, 'budget_response_duplicate')
            response_calls[call['response_id']] = call
    for component in components:
        for paid in component['calls']:
            settled = response_calls.get(paid['response_id'])
            require(settled is not None and settled['request_sha256'] == paid['request_sha256']
                    and settled['usage'] == paid['usage']
                    and Decimal(str(settled['actual_estimate_rub'])) == Decimal(paid['cost_estimate_rub']),
                    'component_budget_binding_missing')
    component_cost = sum((Decimal(c['cost_estimate_rub']) for c in components), Decimal(0))
    aggregate_models = {}
    for model_id in (*weights, 'hybrid'):
        records = [component['models'][model_id] for component in components]
        aggregates = {}
        for catalog_class in (*EQUIPMENT, 'unsupported'):
            rows = [record['per_class'][catalog_class] for record in records]
            counts = {key: sum(row[key] for row in rows) for key in ('tp', 'fp', 'fn')}
            overlaps = [value for row in rows for value in row['matched_iou']]
            tp, fp, fn = counts['tp'], counts['fp'], counts['fn']
            aggregates[catalog_class] = {**counts, 'precision': tp/(tp+fp) if tp+fp else None,
                'recall': tp/(tp+fn) if tp+fn else None,
                'mean_matched_iou': sum(overlaps)/len(overlaps) if overlaps else None}
        timings = [value for record in records for value in record['latency_ms']]
        aggregate_models[model_id] = {'per_class': aggregates, 'mean_latency_ms': sum(timings)/len(timings)}
    return {'models': aggregate_models, 'component_measurements': components, 'component_cost_estimate_rub': str(component_cost),
            'budget_exposure_rub': str(exposure(ledger)), 'case_count': len(cases), 'execution_count': len(runs), 'false_warnings': false_warnings,
            'mean_latency_ms': sum(latency) / len(latency), 'per_case_executions': per_case,
            'limitations': inventory['limitations']}


def read_report(profile, path=None):
    if not isinstance(profile, dict) or profile.get('observation_contract') != 'hybrid-photo-signals-v1':
        return {'status': 'blocked', 'code': 'hybrid_profile_not_bound'}
    path = Path(path or REPORT_PATH)
    try:
        report = json.loads(path.read_text())
    except FileNotFoundError:
        return {'status': 'blocked', 'code': 'missing_current_report'}
    except (OSError, ValueError, RecursionError):
        return {'status': 'blocked', 'code': 'current_report_invalid'}
    if (not isinstance(report, dict) or report.get('profile_sha256') != content_hash(profile)
            or report.get('detector_manifest_sha256') != profile.get('detector_manifest_sha256')):
        return {'status': 'blocked', 'code': 'current_report_stale'}
    try:
        measurements = qualify(report, profile, path.parent)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ArithmeticError, RecursionError) as error:
        reason = str(error) if isinstance(error, ValueError) else 'evidence_missing_or_malformed'
        return {**report, 'status': 'blocked', 'code': 'reviewed_evidence_incomplete', 'blocking_reasons': [reason]}
    return {**report, 'status': 'pass', 'code': 'quality_evidence_qualified', 'measured': measurements,
            'blocking_reasons': []}
