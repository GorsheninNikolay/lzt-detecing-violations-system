"""Content binding and fail-closed qualification using local synthetic evidence."""
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image

from app.application.hybrid_readiness import content_hash, read_report
from app.profiles import hybrid, yolo
from app.profiles.deepseek import EQUIPMENT
from app.shared.cloud import digest



@pytest.fixture(autouse=True)
def preserve_pinned_source_hashes(monkeypatch):
    from app.application import hybrid_readiness
    monkeypatch.setattr(hybrid_readiness, 'SOURCE_MANIFEST_HASHES', dict(hybrid_readiness.SOURCE_MANIFEST_HASHES))


def save(root, name, value):
    path = root / name
    path.write_text(json.dumps(value))
    return {'path': name, 'sha256': digest(path.read_bytes())}


def qualified(root):
    profile = hybrid.snapshot('local-test')
    cases, annotations, runs = [], {}, []
    source = {'partition_hashes': {'bytes': {}, 'decoded_rgb': {}}, 'reserved_diagnostic_frames': []}
    evaluation = Path(__file__).resolve().parents[2] / 'evaluation/hybrid'
    from app.application import hybrid_readiness
    source['reserved_diagnostic_frames'] = json.loads(hybrid_readiness.DIAGNOSTIC_RESERVATIONS_PATH.read_text())['frames']
    source_root = root
    source['source_manifests'] = {}
    for model in ('apoce', 'kaggle'):
        path = source_root / (model + '.json')
        path.write_text(json.dumps({'pairs': [{'image': 'train.jpg', 'split': 'train',
            'image_sha256': 'train-' + model, 'pixel_sha256': 'train-rgb-' + model}]}))
        from app.application.hybrid_readiness import SOURCE_MANIFEST_HASHES
        SOURCE_MANIFEST_HASHES[model] = digest(path.read_bytes())
        source['source_manifests'][model] = {'path': str(path), 'sha256': digest(path.read_bytes())}
        for row in json.loads(path.read_text())['pairs']:
            member = {'id': model + '/' + row['image'], 'role': 'candidate_not_ground_truth' if row['split'] == 'test' else row['split']}
            source['partition_hashes']['bytes'].setdefault(row['image_sha256'], []).append(member)
            source['partition_hashes']['decoded_rgb'].setdefault(row['pixel_sha256'], []).append(member)
    for row in source['reserved_diagnostic_frames']:
        member = {'id': row['id'], 'role': 'diagnostic'}
        source['partition_hashes']['bytes'].setdefault(row['sha256'], []).append(member)
        source['partition_hashes']['decoded_rgb'].setdefault(row['rgb_sha256'], []).append(member)
    weights = {m['id']: m['sha256'] for m in yolo.manifest()['models']}
    i = 0
    for stage in ('excavation', 'concreting', 'roadwork'):
        for outcome in ('normal', 'grounded-risk', 'ambiguous', 'unusable'):
            key = str(i)
            image_path = root / (key + '.png')
            image = Image.new('RGB', (4, 4), (i, 20, 30)); image.save(image_path)
            sha = digest(image_path.read_bytes())
            rgb = digest(str(image.size).encode() + image.tobytes())
            label = root / (key + '.txt'); label.write_text('publisher original label')
            cases.append({'id': key, 'role': 'final_control', 'stage': stage, 'outcome': outcome,
                          'edge_cases': [], 'frames': [{'path': image_path.name, 'sha256': sha, 'rgb_sha256': rgb,
                                      'source_partition': 'new_control', 'source_group': None,
                                      'rights_reference': 'test-owned pixels', 'captured_at': None, 'timing_provenance': 'unknown',
                                      'original_label': {'path': label.name, 'sha256': digest(label.read_bytes())}}]})
            annotations[key] = {'label_review': 'approved', 'expectation_review': 'approved',
                                'rationale': 'Human reviewed original pixels and labels',
                                'expected': {'stage': stage, 'outcome': outcome, 'equipment': [EQUIPMENT[i % 8]],
                                             'warnings': ['visible-risk'] if outcome == 'grounded-risk' else []}}
            i += 1
    from test_hybrid_quality_components import synthetic_components, augment_edge_cases
    component_data = {}
    for case in cases:
        value, reference = synthetic_components(case, annotations[case['id']]['expected'], weights, profile, root)
        component_data[case['id']] = value
        annotations[case['id']]['component_reference'] = reference
    component_data.update(augment_edge_cases(cases, annotations, weights, profile, root))
    for case in cases:
        annotations[case['id']]['expected']['outcome'] = case['outcome']
        for n, frame in enumerate(case['frames']):
            if frame['captured_at'] is not None:
                frame['timing_provenance'] = 'verified_capture_record'
                name = case['id'] + '-time-' + str(n)
                original_record = save(root, name + '-original.json', {'captured_at': frame['captured_at'], 'unit_test_only': True})
                frame['capture_time_evidence'] = save(root, name + '.json', {'frame_sha256': frame['sha256'],
                    'captured_at': frame['captured_at'], 'provenance': 'independent_capture_record',
                    'decision': 'approved', 'reviewer': 'Synthetic test reviewer', 'simulated': False,
                    'original_record': original_record})
    inventory_ref = save(root, 'inventory.json', {'cases': cases, 'limitations': ['unknown_scene_groups']})
    annotations_ref = save(root, 'annotations.json', annotations)
    source_ref = save(root, 'source.json', source)
    review = {'detector_manifest_sha256': profile['detector_manifest_sha256'],
              'source_inventory_sha256': source_ref['sha256'],
              'mapping_decisions': {key: {'decision': 'approved', 'rationale': 'Human adjudicated mapping'} for key in weights},
              'actor_type': 'human', 'reviewer': 'Test reviewer', 'decision': 'approved',
              'reviewed_at': '2026-09-27T10:00:00Z', 'rationale': 'Final control and expectations reviewed.',
              'inventory_sha256': inventory_ref['sha256'], 'annotations_sha256': annotations_ref['sha256'],
              'case_ids': [case['id'] for case in cases]}
    budget = json.loads((evaluation / 'budget.json').read_text())
    for case in cases:
        for n in range(3):
            execution = case['id'] + '/' + str(n)
            result = {'execution_id': execution, 'case_id': case['id'], 'profile_sha256': content_hash(profile),
                      'model_sha256': weights, 'latency_ms': 123.4, 'observed': annotations[case['id']]['expected']}
            evidence = copy.deepcopy(component_data[case['id']])
            for call in [frame['deepseek'] for frame in evidence['frames']] + [evidence['assessment']]:
                call['raw']['id'] = execution + '/' + call['raw']['id']
                usage = call['raw']['usage']
                from decimal import Decimal
                cost = (Decimal(usage['input_tokens'])*Decimal('0.3') + Decimal(usage['output_tokens'])*Decimal('0.5')) / 1000
                budget['calls'].append({'id': call['raw']['id'] + '/reservation', 'response_id': call['raw']['id'],
                    'request_sha256': call['request_sha256'], 'upper_rub': '318.6688', 'usage': usage,
                    'actual_estimate_rub': str(cost), 'status': 'received_usage'})
            result['component_evidence'] = evidence
            runs.append({'execution_id': execution, 'case_id': case['id'], 'profile_sha256': content_hash(profile),
                         'model_sha256': weights, 'inventory_sha256': inventory_ref['sha256'],
                         'annotations_sha256': annotations_ref['sha256'],
                         'started_at': (datetime(2026, 9, 27, 12, tzinfo=timezone.utc) + timedelta(seconds=len(runs))).isoformat(),
                         'result': save(root, 'result-' + str(len(runs)) + '.json', result)})
    report = {'schema': 'hybrid-quality-v1', 'status': 'blocked', 'profile_sha256': content_hash(profile),
              'detector_manifest_sha256': profile['detector_manifest_sha256'], 'detector_manifest': yolo.manifest(),
              'inventory': inventory_ref, 'source_inventory': source_ref,
              'annotations': annotations_ref, 'budget_ledger': save(root, 'budget.json', budget), 'human_review': save(root, 'review.json', review), 'runs': runs}
    return profile, report


def check(root, profile, report):
    path = root / 'report.json'; path.write_text(json.dumps(report))
    return read_report(profile, path)


def test_complete_report_is_calculated_even_when_status_is_blocked(tmp_path):
    profile, report = qualified(tmp_path)
    result = check(tmp_path, profile, report)
    assert result['status'] == 'pass', result
    assert result['measured']['execution_count'] == 3 * result['measured']['case_count']
    assert result['measured']['false_warnings'] == 0
    assert result['measured']['models']['hybrid']['per_class']['excavator']['precision'] == 1
    assert result['measured']['models']['kaggle']['mean_latency_ms'] > 0


@pytest.mark.parametrize('problem', ['source_tamper', 'result_tamper', 'review_tamper', 'unreviewed', 'machine_review',
    'false_warning', 'mismatch', 'two_runs', 'duplicate_run', 'same_execution_time', 'duplicate_case',
    'missing_class', 'missing_scenario', 'diagnostic', 'partition_overlap', 'nan_latency', 'wrong_weights', 'partial'])
def test_unqualified_evidence_remains_blocked(tmp_path, problem):
    profile, report = qualified(tmp_path)
    if problem in ('source_tamper', 'result_tamper', 'review_tamper'):
        name = {'source_tamper': '0.png', 'result_tamper': 'result-0.json', 'review_tamper': 'review.json'}[problem]
        (tmp_path / name).write_bytes(b'tampered')
    elif problem == 'partial':
        del report['annotations']
    elif problem == 'two_runs':
        report['runs'].pop(0)
    elif problem == 'duplicate_run':
        report['runs'].append(copy.deepcopy(report['runs'][0]))
    elif problem == 'same_execution_time':
        report['runs'][1]['started_at'] = report['runs'][0]['started_at']
    elif problem == 'wrong_weights':
        report['runs'][0]['model_sha256']['kaggle'] = 'wrong'
    else:
        field = 'human_review' if problem == 'machine_review' else 'source_inventory' if problem == 'partition_overlap' else 'annotations' if problem in ('unreviewed', 'missing_class') else 'inventory' if problem in ('duplicate_case', 'missing_scenario', 'diagnostic') else None
        ref = report[field] if field else report['runs'][0]['result']
        value = json.loads((tmp_path / ref['path']).read_text())
        if problem == 'machine_review': value['actor_type'] = 'machine'
        elif problem == 'unreviewed': value['0']['label_review'] = 'pending'
        elif problem == 'missing_class':
            for annotation in value.values(): annotation['expected']['equipment'] = ['excavator']
        elif problem == 'duplicate_case': value['cases'].append(copy.deepcopy(value['cases'][0]))
        elif problem == 'missing_scenario': value['cases'].pop()
        elif problem == 'diagnostic': value['cases'][0]['role'] = 'diagnostic'
        elif problem == 'partition_overlap':
            frame = json.loads((tmp_path / report['inventory']['path']).read_text())['cases'][0]['frames'][0]
            value['partition_hashes']['decoded_rgb'][frame['rgb_sha256']] = [{'role': 'train'}]
        elif problem == 'false_warning': value['observed']['warnings'].append('invented-warning')
        elif problem == 'mismatch': value['observed']['outcome'] = 'ambiguous'
        elif problem == 'nan_latency': value['latency_ms'] = float('nan')
        updated = save(tmp_path, ref['path'], value)
        if field: report[field] = updated
        else: report['runs'][0]['result'] = updated
        if field in ('inventory', 'annotations', 'source_inventory'):
            review = json.loads((tmp_path / 'review.json').read_text())
            review[field + '_sha256'] = updated['sha256']
            report['human_review'] = save(tmp_path, 'review.json', review)
    assert check(tmp_path, profile, report)['status'] == 'blocked'


@pytest.mark.parametrize('payload', ['null', '[]', '{}', '{', 'true'])
def test_malformed_reports_never_raise(tmp_path, payload):
    path = tmp_path / 'report.json'; path.write_text(payload)
    assert read_report(hybrid.snapshot('test'), path)['status'] == 'blocked'


def test_stale_and_boolean_only_reports_are_blocked(tmp_path):
    profile, report = qualified(tmp_path)
    report['profile_sha256'] = 'old'
    assert check(tmp_path, profile, report)['code'] == 'current_report_stale'
    report = {'profile_sha256': content_hash(profile), 'detector_manifest_sha256': profile['detector_manifest_sha256'],
              'status': 'pass', 'criteria': {'approved': True}}
    assert check(tmp_path, profile, report)['code'] == 'reviewed_evidence_incomplete'


def rebind_inventory(root, report, value):
    report['inventory'] = save(root, 'inventory.json', value)
    review = json.loads((root / 'review.json').read_text())
    review['inventory_sha256'] = report['inventory']['sha256']
    report['human_review'] = save(root, 'review.json', review)
    for run in report['runs']:
        run['inventory_sha256'] = report['inventory']['sha256']


def test_reencoded_diagnostic_is_rejected_even_with_new_image_bytes(tmp_path):
    profile, report = qualified(tmp_path)
    original = tmp_path / 'diagnostic-original.png'
    with Image.open(original) as image:
        image = image.convert('RGB'); image.save(tmp_path / 'reencoded.png')
        pixels = digest(str(image.size).encode() + image.tobytes())
    inventory = json.loads((tmp_path / 'inventory.json').read_text())
    frame = inventory['cases'][0]['frames'][0]
    frame.update(path='reencoded.png', sha256=digest((tmp_path / 'reencoded.png').read_bytes()), rgb_sha256=pixels)
    rebind_inventory(tmp_path, report, inventory)
    result = check(tmp_path, profile, report)
    assert result['blocking_reasons'] == ['diagnostic_pixel_reuse']


def test_missing_diagnostic_reservations_cannot_qualify(tmp_path, monkeypatch):
    from app.application import hybrid_readiness
    profile, report = qualified(tmp_path)
    monkeypatch.setattr(hybrid_readiness, 'DIAGNOSTIC_RESERVATIONS_PATH', tmp_path / 'missing-reservations.json')
    result = check(tmp_path, profile, report)
    assert result['status'] == 'blocked'
    assert result['blocking_reasons'] == ['evidence_missing_or_malformed']


@pytest.mark.parametrize('problem', ['fake_diagnostic_pixels', 'removed_train_role', 'missing_manifest', 'tampered_manifest'])
def test_original_provenance_cannot_be_replaced_by_rebound_inventory(tmp_path, problem):
    profile, report = qualified(tmp_path)
    source = json.loads((tmp_path / 'source.json').read_text())
    if problem == 'fake_diagnostic_pixels': source['reserved_diagnostic_frames'][0]['rgb_sha256'] = 'invented'
    elif problem == 'removed_train_role': source['partition_hashes']['bytes']['train-kaggle'] = []
    elif problem == 'missing_manifest': del source['source_manifests']['kaggle']
    elif problem == 'tampered_manifest':
        (tmp_path / 'kaggle.json').write_text('{}')
        source['source_manifests']['kaggle']['sha256'] = digest((tmp_path / 'kaggle.json').read_bytes())
    report['source_inventory'] = save(tmp_path, 'source.json', source)
    review = json.loads((tmp_path / 'review.json').read_text())
    review['source_inventory_sha256'] = report['source_inventory']['sha256']
    report['human_review'] = save(tmp_path, 'review.json', review)
    assert check(tmp_path, profile, report)['status'] == 'blocked'


def test_missing_required_edge_coverage_stays_blocked(tmp_path):
    profile, report = qualified(tmp_path)
    inventory = json.loads((tmp_path / 'inventory.json').read_text())
    for case in inventory['cases']:
        case['edge_cases'] = [tag for tag in case['edge_cases'] if tag != 'similar_equipment']
    rebind_inventory(tmp_path, report, inventory)
    assert check(tmp_path, profile, report)['blocking_reasons'] == ['edge_case_coverage_incomplete']


@pytest.mark.parametrize('problem', ['unknown_provenance', 'missing_record', 'simulated', 'unapproved'])
def test_invented_capture_time_never_qualifies(tmp_path, problem):
    profile, report = qualified(tmp_path)
    inventory = json.loads((tmp_path / 'inventory.json').read_text())
    frame = next(case for case in inventory['cases'] if case['id'] == 'edge-idle')['frames'][0]
    if problem == 'unknown_provenance': frame['timing_provenance'] = 'file_name_inference'
    elif problem == 'missing_record': del frame['capture_time_evidence']
    else:
        ref = frame['capture_time_evidence']; timing = json.loads((tmp_path / ref['path']).read_text())
        if problem == 'simulated': timing['simulated'] = True
        else: timing['decision'] = 'pending'
        frame['capture_time_evidence'] = save(tmp_path, ref['path'], timing)
    rebind_inventory(tmp_path, report, inventory)
    assert check(tmp_path, profile, report)['status'] == 'blocked'


@pytest.mark.parametrize('problem', ['missing_history', 'missing_response', 'usage_mismatch', 'request_mismatch',
                                     'unresolved_over_cap', 'malformed_money', 'false_reservation_bound'])
def test_budget_exposure_and_each_paid_response_are_bound(tmp_path, problem):
    profile, report = qualified(tmp_path)
    ledger = json.loads((tmp_path / 'budget.json').read_text())
    if problem == 'missing_history': ledger['calls'].pop(0)
    elif problem == 'missing_response': del ledger['calls'][-1]['response_id']
    elif problem == 'usage_mismatch': ledger['calls'][-1]['usage']['input_tokens'] += 1
    elif problem == 'request_mismatch': ledger['calls'][-1]['request_sha256'] = 'wrong'
    elif problem == 'malformed_money': ledger['calls'][-1]['actual_estimate_rub'] = 'not money'
    elif problem == 'false_reservation_bound': ledger['calls'].append({'id': 'fake', 'upper_rub': '0', 'actual_estimate_rub': None})
    else:
        ledger['calls'].extend({'id': str(i), 'upper_rub': '318.6688', 'actual_estimate_rub': None} for i in range(3))
    report['budget_ledger'] = save(tmp_path, 'budget.json', ledger)
    assert check(tmp_path, profile, report)['status'] == 'blocked'


def test_projected_only_result_cannot_qualify_without_original_components(tmp_path):
    profile, report = qualified(tmp_path)
    ref = report['runs'][0]['result']; result = json.loads((tmp_path / ref['path']).read_text())
    del result['component_evidence']
    report['runs'][0]['result'] = save(tmp_path, ref['path'], result)
    assert check(tmp_path, profile, report)['status'] == 'blocked'


def test_known_observed_stage_cannot_cover_a_different_scenario(tmp_path):
    profile, report = qualified(tmp_path)
    inventory = json.loads((tmp_path / 'inventory.json').read_text())
    inventory['cases'][0]['stage'] = 'concreting'
    rebind_inventory(tmp_path, report, inventory)
    result = check(tmp_path, profile, report)
    assert result['status'] == 'blocked'
    assert result['blocking_reasons'] == ['expectation_conflict']
