"""Run an already human-approved control three times, retaining every paid result."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from time import monotonic
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'output/hybrid-quality/yolo-config'))
from app.application.hybrid_readiness import artifact, content_hash, qualify, read_report
from app.application.deepseek_runtime import observation_context
from app.profiles.deepseek import DeepSeek
from app.profiles.yolo import Detectors
from app.application.hybrid_quality_components import box
from app.profiles import deepseek, hybrid
from app.shared.cloud import digest
from app.shared.quality_budget import status, verify_history


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def run(report_path, profile_path, ledger_path, resume=False):
    report_path = report_path.resolve()
    report_path.relative_to((ROOT / 'output').resolve())
    root = report_path.parent
    report = json.loads(report_path.read_text())
    profile = json.loads(profile_path.read_text())
    if report.get('profile_sha256') != content_hash(profile):
        raise ValueError('control_profile_mismatch')
    if report.get('runs') and not resume:
        raise ValueError('control_has_prior_runs_use_resume')
    report.setdefault('runs', [])
    ledger = json.loads(ledger_path.read_text())
    verify_history(ledger)
    report['budget_ledger'] = {'path': str(ledger_path.resolve()), 'sha256': digest(ledger_path.read_bytes())}
    try:
        qualify(report, profile, root)
    except ValueError as error:
        if str(error) != 'three_executions_required':
            raise
    else:
        print(json.dumps({'status': 'pass', 'report': str(report_path), 'code': 'already_complete_no_paid_calls'}))
        return 0
    if not status(ledger_path)['can_reserve']:
        raise ValueError('quality_budget_exhausted')
    os.environ['HYBRID_BUDGET_LEDGER'] = str(ledger_path.resolve())
    detectors = Detectors()
    if content_hash(detectors.manifest) != profile['detector_manifest_sha256']:
        raise ValueError('control_detector_manifest_mismatch')
    inventory = artifact(report['inventory'], root)
    annotations = artifact(report['annotations'], root)
    weights = {m['id']: m['sha256'] for m in report['detector_manifest']['models']}
    for case in inventory['cases']:
        reference = annotations[case['id']]['component_reference']
        if set(reference['frames']) != {frame['input_id'] for frame in case['frames']} or not isinstance(reference['context'], dict):
            raise ValueError('control_reference_incomplete')
        threshold = reference['iou_match_threshold']
        if type(threshold) not in (int, float) or not 0 < threshold <= 1:
            raise ValueError('control_reference_invalid')
        if set(reference['assessment']) != {'stage', 'activity', 'signals'}:
            raise ValueError('control_reference_invalid')
        for value in reference['frames'].values():
            if type(value['frame_usability']) is not bool or value['stage'] not in deepseek.STAGES:
                raise ValueError('control_reference_invalid')
            for obj in value['objects']:
                box(obj['box'])
                if obj['catalog_class'] not in deepseek.EQUIPMENT or obj['visual_action'] not in hybrid.ACTIONS:
                    raise ValueError('control_reference_invalid')
    observer = DeepSeek(profile, os.environ.get('YANDEX_AI_STUDIO_API_KEY'))
    name = 'control-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]
    directory = root / name
    directory.mkdir(exist_ok=False)
    failed = None
    for case in inventory['cases']:
        completed = sum(r['case_id'] == case['id'] for r in report['runs'])
        for repetition in range(completed, 3):
            identity = str(uuid.uuid4())
            started = monotonic()
            result = {'execution_id': identity, 'case_id': case['id'], 'profile_sha256': report['profile_sha256'],
                      'model_sha256': weights, 'started_at': datetime.now(timezone.utc).isoformat(),
                      'repetition': repetition + 1, 'component_evidence': {'frames': []}, 'status': 'running'}
            frames, images = [], []
            try:
                for ordinal, source in enumerate(case['frames']):
                    raw = artifact({'path': source['path'], 'sha256': source['sha256']}, root, json_value=False)
                    key = source['input_id']
                    detection = detectors.detect(raw, key)
                    context = {'input_id': key, 'detectors': detection}
                    call = observer.call('frame', context, raw)
                    frame = {'input_id': key, 'sha256': source['sha256'], 'detectors': detection,
                             'frame_context': context, 'deepseek': call}
                    result['component_evidence']['frames'].append(frame)
                    write(directory / f'{identity}-frame-{ordinal}.json', frame)
                    if not call['valid']:
                        raise ValueError('control_frame_rejected:' + str(call['rejection']))
                    frozen = observation_context({'input_id': key, 'ordinal': ordinal, 'sha256': source['sha256'],
                                                  'artifact_id': key}, {'value': call['value'], 'detectors': detection})
                    frozen['captured_at'] = source['captured_at']
                    frames.append(frozen); images.append((key, raw))
                context = {**annotations[case['id']]['component_reference']['context'], 'frames': frames}
                assessment = observer.call('assessment', context, images=images)
                result['component_evidence'].update(assessment_context=context, assessment=assessment)
                write(directory / f'{identity}-assessment.json', assessment)
                if not assessment['valid']:
                    raise ValueError('control_assessment_rejected:' + str(assessment['rejection']))
                values = [f['deepseek']['value'] for f in result['component_evidence']['frames']]
                value = assessment['value']
                usable = any(v['frame_usability']['usable'] for v in values)
                outcome = ('unusable' if not usable else 'grounded-risk' if value['risks'] else
                           'ambiguous' if value['stage_hypothesis']['stage'] in ('unknown', 'ambiguous') else 'normal')
                result['observed'] = {'equipment': sorted({o['catalog_class'] for v in values for o in v['objects']
                    if o['status'] == 'identified' and o['catalog_class'] is not None}),
                    'stage': value['stage_hypothesis']['stage'], 'outcome': outcome,
                    'warnings': sorted(r['cause'] for r in value['risks'])}
                result['status'] = 'completed'
            except Exception as error:
                failed = str(error)
                result.update(status='failed_or_uncertain', error=failed)
            result['latency_ms'] = (monotonic()-started)*1000
            path = directory / (identity + '.json')
            write(path, result)
            if failed:
                break
            report['runs'].append({'case_id': case['id'], 'execution_id': identity,
                'started_at': result['started_at'], 'profile_sha256': report['profile_sha256'], 'model_sha256': weights,
                'inventory_sha256': report['inventory']['sha256'], 'annotations_sha256': report['annotations']['sha256'],
                'result': {'path': str(path), 'sha256': digest(path.read_bytes())}})
        if failed:
            break
    report['budget_ledger'] = {'path': str(ledger_path.resolve()), 'sha256': digest(ledger_path.read_bytes())}
    path = root / (name + '-report.json')
    write(path, report)
    qualified = read_report(profile, path)
    write(directory / 'checkpoint.json', {'status': qualified['status'], 'code': qualified.get('code'),
          'failure': failed, 'report': str(path), 'runs': len(report['runs']), 'budget': status(ledger_path)})
    print(json.dumps({'status': qualified['status'], 'report': str(path), 'code': qualified.get('code')}))
    return 0 if qualified['status'] == 'pass' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--budget-ledger', type=Path, default=ROOT / 'evaluation/hybrid/budget.json')
    parser.add_argument('--resume', action='store_true', help='Reuse verified completed executions; retain uncertain paid exposure')
    args = parser.parse_args()
    raise SystemExit(run(args.report, args.profile, args.budget_ledger, args.resume))
