"""DeepSeek annotation proposals with a shared, fixed 400 RUB experiment ledger."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError

import prepare_qwen_annotations as shared

ROOT = shared.ROOT
OUTPUT = ROOT / 'output/deepseek-annotation-run'
LEDGER = OUTPUT / 'budget.sqlite'
MODEL = 'deepseek-v4.1-flash'
MAX_INPUT = 1_048_576
TOTAL_MICRO = 400_000_000
INPUT_RATE = 300
OUTPUT_RATE = 500
RESERVE_MICRO = MAX_INPUT * INPUT_RATE + shared.MAX_OUTPUT * OUTPUT_RATE


def error_summary(exc):
    body = exc.read(8192).decode('utf-8', errors='replace').lower()
    reasons = ('image_not_supported', 'subscription_required', 'permission_denied',
               'unsupported_parameter', 'invalid_request', 'model_not_found',
               'insufficient_quota', 'rate_limit_exceeded')
    reason = next((value for value in reasons if value in body), 'unclassified_provider_error')
    if reason == 'unclassified_provider_error':
        patterns = (
            ('subscription_required_or_restricted', r'\bsubscription\b|подписк'),
            ('image_input_unsupported', r'(image|vision|multimodal).*?(not support|unsupported|not available)'),
            ('reasoning_parameter_rejected', r'(reasoning|effort).*?(invalid|not support|unsupported|allowed)'),
            ('structured_output_rejected', r'(json_schema|response_format|structured).*?(invalid|not support|unsupported)'),
            ('model_access_restricted', r'(model).*?(not found|not available|access denied)'),
        )
        reason = next((label for label, pattern in patterns if re.search(pattern, body, re.S)), reason)
    return {'http_status': exc.code, 'reason': reason, 'retry': False,
            'reservation_retained': True}


def run(args):
    if not args.allow_cloud_upload:
        raise shared.AnnotationError('explicit_cloud_upload_authorization_required')
    key, folder = os.environ.get('YANDEX_API_KEY'), os.environ.get('YANDEX_FOLDER_ID')
    if not key or not folder or not all(c.isalnum() or c == '-' for c in folder):
        raise shared.AnnotationError('cloud_environment_missing_or_invalid')
    if not 1 <= args.limit <= 100:
        raise shared.AnnotationError('limit_invalid')
    manifest, source_hash, images = shared.verified_sources(args.manifest, args.archive)
    ids = args.ids or list(images)
    if len(set(ids)) != len(ids) or any(i not in images for i in ids):
        raise shared.AnnotationError('requested_ids_invalid')
    model = f'gpt://{folder}/{MODEL}/latest'
    config = {'source_manifest': source_hash, 'model': model, 'output': str(OUTPUT.resolve()),
              'prompt': shared.PROMPT_V2, 'schema': shared.SCHEMA, 'max_input': MAX_INPUT,
              'max_output': shared.MAX_OUTPUT, 'input_rate_micro': INPUT_RATE,
              'output_rate_micro': OUTPUT_RATE, 'budget_micro': TOTAL_MICRO}
    budget = shared.Budget(LEDGER, '0', shared.digest(json.dumps(config, sort_keys=True).encode()),
                           total_micro=TOTAL_MICRO, max_input=MAX_INPUT,
                           input_rate=INPUT_RATE, output_rate=OUTPUT_RATE)
    budget.bind_experiment(args.reasoning, json.dumps({'reasoning': args.reasoning, **config}, sort_keys=True))
    output = OUTPUT / args.reasoning
    for name in ('raw', 'annotations', 'errors', 'timing'):
        (output / name).mkdir(parents=True, exist_ok=True)
    count = 0
    try:
        for image_id in ids:
            call_id = args.reasoning + '/' + image_id
            raw_path = output / 'raw' / (image_id + '.json')
            annotation_path = output / 'annotations' / (image_id + '.json')
            if raw_path.exists():
                response = shared.strict_json(raw_path.read_bytes())
            else:
                if count >= args.limit:
                    break
                if not budget.reserve(call_id):
                    print(f'{image_id}: existing reservation; no retry', flush=True)
                    continue
                count += 1
                started = time.monotonic()
                try:
                    raw = shared.cloud_request(model, images[image_id], key,
                                               prompt=shared.PROMPT_V2, reasoning=args.reasoning)
                except HTTPError as exc:
                    try:
                        error = error_summary(exc)
                    finally:
                        exc.close()
                    shared.write_once(output / 'errors' / (image_id + '.json'), json.dumps(error).encode())
                    raise shared.AnnotationError('provider_http_error:' + json.dumps(error)) from None
                shared.write_once(raw_path, raw)
                shared.write_once(output / 'timing' / (image_id + '.json'),
                                  json.dumps({'elapsed_seconds': time.monotonic() - started,
                                              'requested_reasoning': args.reasoning}).encode())
                response = shared.strict_json(raw)
            if not budget.settle(call_id, response):
                raise shared.AnnotationError('response_usage_missing_reserve_retained')
            annotation = shared.validate_response(response, model)
            if not annotation_path.exists():
                shared.write_once(annotation_path, json.dumps(annotation, ensure_ascii=False).encode())
            print(f'{image_id}: proposal saved', flush=True)
    finally:
        try:
            shared.export_manifest(manifest, output, model, source_hash, prompt=shared.PROMPT_V2,
                                   experiment=args.reasoning, reasoning=args.reasoning, model_name=MODEL)
            print(json.dumps(budget.summary(), ensure_ascii=False), flush=True)
        finally:
            budget.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'evaluation/expansion/draft-annotations.json')
    parser.add_argument('--archive', type=Path, default=ROOT / 'artifacts/dataset/Строительная_техника.zip')
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--allow-cloud-upload', action='store_true')
    parser.add_argument('--reasoning', choices=('none', 'low'), default='none')
    run(parser.parse_args())


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc) if isinstance(exc, shared.AnnotationError)
              else 'annotation_run_failed_reservations_retained', file=sys.stderr)
        sys.exit(1)
