"""Local, append-only checkpoint and source-bound quality preparation; never calls an API."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'output/hybrid-quality/yolo-config'))
from app.shared.cloud import canonical_bytes, digest
from app.profiles import hybrid, yolo

SOURCE = Path('/private/tmp/lzt-yolo-training-extracted/lzt-yolo-training-kit')
OUTPUT = ROOT / 'output/hybrid-quality'
HISTORY = ROOT / 'evaluation/hybrid/history'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def new_directory(profile_hash, command):
    path = OUTPUT / profile_hash / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + command + '-' + uuid.uuid4().hex[:8])
    path.mkdir(parents=True, exist_ok=False)
    return path


def identity():
    profile = hybrid.snapshot('local-quality-no-cloud-credentials')
    return profile, digest(canonical_bytes(profile))


def snapshot(expected_kaggle_sha='215ee62fbe670d846affc120e9a626d24dd1fadf7723578123845aab8babca31'):
    import torch
    from ultralytics import YOLO
    old = yolo.manifest()
    updated = deepcopy(old)
    receipts = []
    for model in updated['models']:
        source = ROOT / 'artifacts/Models' / model['filename']
        payload = source.read_bytes()
        sha = digest(payload)
        target = OUTPUT / 'checkpoints' / sha / model['filename']
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if digest(target.read_bytes()) != sha:
                raise ValueError('immutable_checkpoint_corrupted')
        else:
            with target.open('xb') as stream:
                stream.write(payload)
        detector = YOLO(str(target), task='detect')
        names = [detector.names[i] for i in range(len(detector.names))]
        if names != model['classes']:
            raise ValueError('checkpoint_classes_mismatch')
        if model['id'] == 'apoce' and sha != model['sha256']:
            raise ValueError('apoce_changed')
        checkpoint = torch.load(target, map_location='cpu', weights_only=False)
        epoch = checkpoint.get('epoch')
        if model['id'] == 'kaggle' and sha != expected_kaggle_sha:
            raise ValueError('unexpected_kaggle_checkpoint')
        model['sha256'] = sha
        receipts.append({'model_id': model['id'], 'sha256': sha, 'classes': names,
                         'stored_epoch': epoch, 'epoch_numbering': 'zero-based; -1 indicates stripped checkpoint',
                         'completed_epoch_number': epoch + 1 if type(epoch) is int and epoch >= 0 else None,
                         'mapping_review': 'pending_human_adjudication', 'checkpoint_path': str(target.relative_to(ROOT))})
    old_sha = digest(canonical_bytes(old))
    if old != updated:
        archive = HISTORY / old_sha
        archive.mkdir(parents=True, exist_ok=True)
        archived_sources = [(yolo.MANIFEST_PATH, archive / 'yolo-manifest.json'),
            (ROOT / 'backend/app/data/hybrid-readiness.json', archive / 'hybrid-readiness.json')]
        for name in ('weights-provenance.json', 'yolo-smoke-summary.json', 'control-review-queue.json',
                     'independent-visual-review.json', 'budget.json'):
            archived_sources.append((ROOT / 'evaluation/hybrid' / name, archive / name))
        for source in sorted((ROOT / 'evaluation/hybrid/results').rglob('*')):
            if source.is_file():
                archived_sources.append((source, archive / 'results' / source.relative_to(ROOT / 'evaluation/hybrid/results')))
        for source, target in archived_sources:
            payload = source.read_bytes()
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if target.read_bytes() != payload:
                    raise ValueError('historical_archive_conflict')
            else:
                with target.open('xb') as stream:
                    stream.write(payload)
            if digest(target.read_bytes()) != digest(payload):
                raise ValueError('historical_archive_incomplete')
        yolo.MANIFEST_PATH.write_text(json.dumps(updated, indent=2) + '\n')
    profile, sha = identity()
    directory = new_directory(sha, 'snapshot')
    receipt = {'profile': profile, 'profile_sha256': sha,
         'manifest': updated, 'manifest_sha256': digest(canonical_bytes(updated)), 'checkpoints': receipts,
         'historical_manifest_sha256': old_sha, 'quality_acceptance': 'blocked_pending_human_review'}
    write(directory / 'snapshot.json', receipt)
    write(HISTORY / sha / (directory.name + '.json'), receipt)
    return directory


def integrity(source):
    spec = importlib.util.spec_from_file_location('quality_source_integrity', source / 'integrity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(source):
    check = integrity(source)
    profile, sha = identity()
    directory = new_directory(sha, 'inventory')
    manifest = yolo.manifest()
    organizer = json.loads((ROOT / 'evaluation/hybrid/control-review-queue.json').read_text())
    rows, test_counts, partitions = [], {}, {}
    byte_groups, pixel_groups = defaultdict(list), defaultdict(list)
    for model in manifest['models']:
        source_manifest = check.load_manifest(source, model['id'])
        if source_manifest['names'] != model['classes']:
            raise ValueError('source_checkpoint_classes_mismatch')
        partitions[model['id']] = dict(Counter(row['split'] for row in source_manifest['pairs']))
        test_counts[model['id']] = partitions[model['id']].get('test', 0)
        for row in source_manifest['pairs']:
            key = model['id'] + '/' + row['image']
            role = 'candidate_not_ground_truth' if row['split'] == 'test' else row['split']
            byte_groups[row['image_sha256']].append({'id': key, 'role': role})
            pixel_groups[row['pixel_sha256']].append({'id': key, 'role': role})
            if row['split'] != 'test':
                continue
            for field in ('image', 'label'):
                if check.file_sha(source / row[field]) != row[field + '_sha256']:
                    raise ValueError('source_pair_tampered:' + row[field])
            raw = (source / row['image']).read_bytes()
            size, pixels = check.image_info(raw, row['dimensions'])
            if pixels != row['pixel_sha256']:
                raise ValueError('source_pixel_hash_mismatch')
            labels = check.labels((source / row['label']).read_bytes(), len(source_manifest['names']))
            if len(labels) != row['box_count'] or dict(Counter(str(box[0]) for box in labels)) != row['class_boxes']:
                raise ValueError('source_label_metadata_mismatch')
            rights = {'reference': 'metadata/kaggle.json', 'publisher_license_claim': 'CC0: Public Domain'} if model['id'] == 'kaggle' else {
                'reference': 'metadata/apoce/README.roboflow.txt', 'publisher_license_claim': None}
            rows.append({'id': key, 'role': role, 'model_id': model['id'], 'source_partition': row['split'],
                'source_path': row['source_path'], 'path': str(source / row['image']),
                'label_path': str(source / row['label']), 'image_sha256': row['image_sha256'],
                'label_sha256': row['label_sha256'], 'rgb_sha256': pixels, 'dimensions': list(size),
                'source_group': None, 'source_group_provenance': 'unknown; file names do not establish independence',
                'rights_reference': rights, 'captured_at': None, 'timing_provenance': 'unknown',
                'original_labels': [{'class_id': box[0], 'raw_class': model['classes'][box[0]],
                                     'xywh': list(box[1:])} for box in labels],
                'review_status': 'pending_human_adjudication'})
    if test_counts != {'kaggle': 1309, 'apoce': 94}:
        raise ValueError('unexpected_test_inventory_counts')
    for row in organizer['images']:
        image_path = ROOT / 'output/hybrid-review/images' / Path(row['archive_member']).name
        raw = image_path.read_bytes()
        if digest(raw) != row['sha256']:
            raise ValueError('diagnostic_source_hash_mismatch')
        _, row['rgb_sha256'] = check.image_info(raw)
        pixel_groups[row['rgb_sha256']].append({'id': row['id'], 'role': 'diagnostic'})
        byte_groups[row['sha256']].append({'id': row['id'], 'role': 'diagnostic'})
    clusters = []
    for kind, groups in (('bytes', byte_groups), ('decoded_rgb', pixel_groups)):
        for value, members in groups.items():
            if len(members) > 1:
                clusters.append({'kind': kind, 'sha256': value, 'members': members,
                                 'cross_role': len({m['role'] for m in members}) > 1})
    result = {'schema': 'hybrid-test-inventory-v1', 'profile_sha256': sha,
         'source_manifest_index_sha256': check.file_sha(source / 'manifest-index.json'),
         'source_manifest_sha256': {m['id']: check.file_sha(source / 'manifests' / (m['id'] + '.json')) for m in manifest['models']},
         'test_counts': test_counts, 'partitions': partitions, 'frames': rows, 'duplicate_clusters': clusters,
         'partition_hashes': {'bytes': dict(byte_groups), 'decoded_rgb': dict(pixel_groups)},
         'reserved_diagnostic_frames': json.loads((ROOT / 'evaluation/hybrid/diagnostic-reservations.json').read_text())['frames'],
         'source_manifests': {m['id']: {'path': str(source / 'manifests' / (m['id'] + '.json')),
              'sha256': check.file_sha(source / 'manifests' / (m['id'] + '.json'))} for m in manifest['models']},
         'limitations': ['unknown_scene_groups', 'unknown_capture_times', 'publisher_labels_not_human_reference',
                         'train_val_pixels_from_integrity_bound_source_manifests; test_pixels_verified']}
    write(directory / 'inventory.json', result)
    write(directory / 'review-packet.json', {'schema': 'hybrid-human-review-packet-v1',
        'status': 'candidates_not_ground_truth', 'inventory_sha256': digest((directory / 'inventory.json').read_bytes()),
        'required_equipment': list(hybrid.legacy.EQUIPMENT),
        'required_edge_cases': ['same_machine_multi_frame', 'similar_equipment', 'occlusion', 'repeated_image', 'interval_boundaries',
             'concurrent_works', 'no_plan', 'unknown_time', 'visible_action', 'possible_idle'],
        'required_scenarios': [{'stage': s, 'outcome': o} for s in ('excavation', 'concreting', 'roadwork')
                                for o in ('normal', 'grounded-risk', 'ambiguous', 'unusable')],
        'frames': rows, 'mapping_review': {m['id']: {'status': 'pending_human_adjudication', 'mapping': m['mapping']} for m in manifest['models']},
        'blocking_reasons': ['Approve original labels and expectations; adjudicate ambiguous classes.',
            'Select independent final controls; all 15 organizer frames remain diagnostic.',
            'Resolve cross-role byte/pixel duplicates; unknown groups prevent claiming source independence.',
            'Collect three fresh independent hybrid executions per approved case; zero false warnings required.']})
    write(HISTORY / sha / (directory.name + '.json'), {'kind': 'inventory_receipt',
        'profile_sha256': sha, 'inventory_path': str((directory / 'inventory.json').relative_to(ROOT)),
        'inventory_sha256': digest((directory / 'inventory.json').read_bytes()), 'test_counts': test_counts,
        'status': 'candidates_not_ground_truth'})
    return directory


def baseline(inventory_path, limit):
    data = json.loads(inventory_path.read_text())
    profile, sha = identity()
    if data['profile_sha256'] != sha:
        raise ValueError('inventory_profile_stale')
    directory = new_directory(sha, 'baseline')
    detector = yolo.Detectors()
    count = 0
    for row in data['frames'][:limit] if limit else data['frames']:
        raw = Path(row['path']).read_bytes()
        if digest(raw) != row['image_sha256']:
            raise ValueError('source_image_changed')
        result = detector.detect(raw, row['id'])
        write(directory / (str(count).zfill(5) + '.json'), {'execution_id': uuid.uuid4().hex,
             'case_id': row['id'], 'profile_sha256': sha, 'source_image_sha256': row['image_sha256'],
             'original_label_sha256': row['label_sha256'], 'detector_result': result,
             'reference_status': 'publisher_labels_not_human_reference'})
        count += 1
    write(directory / 'summary.json', {'status': 'diagnostic_only', 'frames': count,
         'profile_sha256': sha, 'inventory_sha256': digest(inventory_path.read_bytes()),
         'paid_api_calls': 0, 'human_approved_reference_count': 0})
    write(HISTORY / sha / (directory.name + '.json'), {'kind': 'baseline_receipt',
        'profile_sha256': sha, 'summary_path': str((directory / 'summary.json').relative_to(ROOT)),
        'summary_sha256': digest((directory / 'summary.json').read_bytes()), 'frames': count, 'status': 'diagnostic_only'})
    return directory


def overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union else 0


def measure(inventory_path, baseline_path):
    inventory_data = json.loads(inventory_path.read_text())
    profile, sha = identity()
    summary = json.loads((baseline_path / 'summary.json').read_text())
    if summary['profile_sha256'] != sha or summary['inventory_sha256'] != digest(inventory_path.read_bytes()):
        raise ValueError('baseline_inventory_or_profile_stale')
    directory = new_directory(sha, 'measure')
    sources = {row['id']: row for row in inventory_data['frames']}
    totals = defaultdict(lambda: {'tp': 0, 'fp': 0, 'fn': 0, 'matched_ious': []})
    latencies = defaultdict(list)
    files = sorted(baseline_path.glob('[0-9]*.json'))
    if len(files) != summary['frames']:
        raise ValueError('baseline_count_mismatch')
    evidence = []
    for path in files:
        result = json.loads(path.read_text()); row = sources[result['case_id']]
        if result['profile_sha256'] != sha or result['source_image_sha256'] != row['image_sha256'] or result['original_label_sha256'] != row['label_sha256']:
            raise ValueError('baseline_source_binding_mismatch')
        raw_detector = result['detector_result']
        if digest(canonical_bytes(raw_detector['manifest'])) != profile['detector_manifest_sha256']:
            raise ValueError('baseline_manifest_stale')
        expected_models = {m['id']: m['sha256'] for m in raw_detector['manifest']['models']}
        if len(raw_detector['models']) != 2 or {m['model_id']: m['weights_sha256'] for m in raw_detector['models']} != expected_models:
            raise ValueError('baseline_model_binding_mismatch')
        model = next(m for m in raw_detector['models'] if m['model_id'] == row['model_id'])
        for other in result['detector_result']['models']:
            latencies[other['model_id']].append(other['latency_ms'])
        truth = []
        for label in row['original_labels']:
            x, y, w, h = label['xywh']
            truth.append({'raw_class': label['raw_class'], 'box': [x-w/2, y-h/2, x+w/2, y+h/2]})
        matched = set()
        for detection in sorted(model['detections'], key=lambda d: -d['score']):
            candidates = [(overlap(detection['box'], label['box']), i) for i, label in enumerate(truth)
                          if i not in matched and label['raw_class'] == detection['raw_class']]
            score, index = max(candidates, default=(0, -1))
            key = row['model_id'] + '/' + detection['raw_class']
            if score >= .5:
                matched.add(index); totals[key]['tp'] += 1; totals[key]['matched_ious'].append(score)
            else:
                totals[key]['fp'] += 1
        for i, label in enumerate(truth):
            if i not in matched: totals[row['model_id'] + '/' + label['raw_class']]['fn'] += 1
        evidence.append({'path': str(path), 'sha256': digest(path.read_bytes())})
    measured = {}
    for key, counts in totals.items():
        tp, fp, fn = counts['tp'], counts['fp'], counts['fn']
        measured[key] = {'tp': tp, 'fp': fp, 'fn': fn,
                        'precision': tp / (tp + fp) if tp + fp else None,
                        'recall': tp / (tp + fn) if tp + fn else None,
                        'mean_matched_iou': sum(counts['matched_ious']) / tp if tp else None}
    write(directory / 'measurements.json', {'status': 'diagnostic_only_publisher_reference',
        'profile_sha256': sha, 'inventory_sha256': digest(inventory_path.read_bytes()),
        'frames': len(files), 'matching_rule': 'same original class, greedy descending confidence, IoU >= 0.5; no quality acceptance threshold',
        'source_reference': 'unapproved_original_publisher_labels; each model measured on own source test partition',
        'per_original_class': measured, 'mean_latency_ms': {key: sum(values)/len(values) for key, values in latencies.items()},
        'baseline_artifacts': evidence})
    write(HISTORY / sha / (directory.name + '.json'), {'kind': 'measurement_receipt',
        'profile_sha256': sha, 'measurements_path': str((directory / 'measurements.json').relative_to(ROOT)),
        'measurements_sha256': digest((directory / 'measurements.json').read_bytes()), 'frames': len(files),
        'status': 'diagnostic_only_publisher_reference'})
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    snap = sub.add_parser('snapshot')
    snap.add_argument('--expected-kaggle-sha', default='215ee62fbe670d846affc120e9a626d24dd1fadf7723578123845aab8babca31')
    inv = sub.add_parser('inventory'); inv.add_argument('--source', type=Path, default=SOURCE)
    base = sub.add_parser('baseline'); base.add_argument('--inventory', type=Path, required=True)
    base.add_argument('--limit', type=int, default=0)
    measured = sub.add_parser('measure'); measured.add_argument('--inventory', type=Path, required=True)
    measured.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'baseline' and args.limit < 0:
        parser.error('--limit must be nonnegative')
    if args.command == 'measure':
        directory = measure(args.inventory, args.baseline)
        print(json.dumps({'status': 'diagnostic_measurements_only', 'output': str(directory)}))
        return
    directory = snapshot(args.expected_kaggle_sha) if args.command == 'snapshot' else inventory(args.source) if args.command == 'inventory' else baseline(args.inventory, args.limit)
    print(json.dumps({'status': 'local_preparation_complete_quality_blocked', 'output': str(directory)}))


if __name__ == '__main__':
    main()
