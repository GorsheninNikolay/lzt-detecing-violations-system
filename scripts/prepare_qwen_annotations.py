"""Budgeted, resumable Qwen proposals; every proposal still requires human review."""

import argparse
import base64
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time
from urllib import request
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output/qwen-annotation-run'
LEDGER = OUTPUT / 'budget.sqlite'
MODEL = 'qwen3.6-35b-a3b'
ENDPOINT = 'https://ai.api.cloud.yandex.net/v1/responses'
MAX_INPUT = 262144
MAX_OUTPUT = 4096
TOTAL_MICRO = 1_000_000_000
RESERVE_MICRO = MAX_INPUT * 200 + MAX_OUTPUT * 300
EQUIPMENT = ('excavator', 'dump_truck', 'road_roller', 'truck_mounted_crane',
             'concrete_mixer_truck', 'bulldozer', 'truck', 'mobile_crane')
SCENES = ('excavation_or_trench', 'formwork', 'rebar', 'concrete_surface', 'road_base_or_surface')
STAGES = ('unknown', 'ambiguous', 'preparation', 'demolition', 'excavation', 'concreting',
          'installation', 'roadwork', 'utilities', 'landscaping')
STATES = ('present', 'absent', 'uncertain', 'unassessable')
PROMPT = '''Inspect only visible evidence in this construction-site photograph. Return the requested JSON.
For every equipment class and scene feature, report present, absent, uncertain (visible but ambiguous), or
unassessable (image conditions prevent judgment). Do not infer hidden equipment or work from expectations.
Draw one tight normalized [left, top, right, bottom] box per clearly identified machine, coordinates 0..1
relative to the whole original image. All present classes require boxes; no boxes for other states.
Do not label one physical machine as multiple truck classes. dump_truck has a tipping load bed;
concrete_mixer_truck has a mixing drum; truck is an ordinary cargo truck, excluding those specialized types.
truck_mounted_crane is a cargo truck with a loader/knuckle-boom crane and a usable cargo bed;
mobile_crane is a dedicated crane carrier with a large lifting boom. A tower crane is neither.
If these visual distinctions cannot be resolved, use uncertain. A bulldozer has a pushing blade;
a tracked excavator has a digging boom and bucket; tracks alone do not distinguish them.
Report only visible scene features. Stage is a hypothesis supported by actual activity and scene evidence;
equipment alone does not establish a stage. Use unknown if unsupported, ambiguous for multiple plausible
or simultaneous stages. Supply a short factual stage_reason. Never invent confidence, time, site or provenance.
'''


PROMPT_V2 = PROMPT + """
First inspect each individual visible vehicle's chassis, attachment and work tool.
An excavator's articulated digging arm can be raised high and may resemble a crane boom;
look for the digging bucket, crawler chassis, compact rotating cab and counterweight.
A crane lifts suspended loads using cable/hook; do not identify a crane solely from a long arm.
Do not use the construction site, building, sky, or whole photograph as an equipment box.
A box encloses one physical vehicle, including its visible attachment, not its surroundings.
Whole-image boxes are appropriate only when the vehicle actually fills the whole photograph.
Before answering, ensure every present class has at least one correctly localized object and
that every object belongs to a present class. If a vehicle cannot be identified or localized,
mark its plausible classes uncertain instead of fabricating an object. Write a short stage_reason in Russian.
"""
PROMPTS = {'v1': PROMPT, 'v2': PROMPT_V2}


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


SCHEMA = object_schema({
    'equipment': object_schema({name: {'type': 'string', 'enum': list(STATES)} for name in EQUIPMENT}),
    'objects': {'type': 'array', 'maxItems': 100, 'items': object_schema({
        'class_name': {'type': 'string', 'enum': list(EQUIPMENT)},
        'box': {'type': 'array', 'items': {'type': 'number', 'minimum': 0, 'maximum': 1},
                'minItems': 4, 'maxItems': 4}})},
    'scenes': object_schema({name: {'type': 'string', 'enum': list(STATES)} for name in SCENES}),
    'stage': {'type': 'string', 'enum': list(STAGES)},
    'stage_reason': {'type': 'string', 'minLength': 1, 'maxLength': 1000},
})


class AnnotationError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AnnotationError('duplicate_json_key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(AnnotationError('nonfinite_json')))


def validate_annotation(value):
    if not isinstance(value, dict) or set(value) != set(SCHEMA['properties']):
        raise AnnotationError('annotation_fields_invalid')
    for field, names in (('equipment', EQUIPMENT), ('scenes', SCENES)):
        states = value[field]
        if (not isinstance(states, dict) or set(states) != set(names)
                or any(not isinstance(v, str) or v not in STATES for v in states.values())):
            raise AnnotationError('annotation_states_invalid')
    if (not isinstance(value['stage'], str) or value['stage'] not in STAGES
            or not isinstance(value['stage_reason'], str) or not value['stage_reason'].strip()
            or len(value['stage_reason']) > 1000):
        raise AnnotationError('annotation_stage_invalid')
    objects = value['objects']
    if not isinstance(objects, list) or len(objects) > 100:
        raise AnnotationError('annotation_objects_invalid')
    for item in objects:
        if (not isinstance(item, dict) or set(item) != {'class_name', 'box'}
                or not isinstance(item['class_name'], str) or item['class_name'] not in EQUIPMENT):
            raise AnnotationError('annotation_object_invalid')
        box = item['box']
        if (not isinstance(box, list) or len(box) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
                or box[0] >= box[2] or box[1] >= box[3]):
            raise AnnotationError('annotation_box_invalid')
    for name in EQUIPMENT:
        if (value['equipment'][name] == 'present') != any(o['class_name'] == name for o in objects):
            raise AnnotationError('annotation_presence_box_conflict')
    if len({json.dumps(o, sort_keys=True) for o in objects}) != len(objects):
        raise AnnotationError('annotation_duplicate_object')
    return value


def validate_response(response, model):
    if (not isinstance(response, dict) or response.get('model') not in (model.removesuffix('/latest'), model.removesuffix('/latest') + '/latest')
            or not isinstance(response.get('id'), str) or not response['id'].strip()
            or response.get('status') != 'completed' or response.get('error') is not None
            or response.get('incomplete_details') is not None):
        raise AnnotationError('response_identity_or_status_invalid')
    output = response.get('output')
    if not isinstance(output, list):
        raise AnnotationError('response_output_invalid')
    messages = [item for item in output if isinstance(item, dict) and item.get('type') == 'message']
    if len(messages) != 1 or messages[0].get('role') != 'assistant':
        raise AnnotationError('response_message_invalid')
    content = messages[0].get('content')
    if (not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict)
            or content[0].get('type') != 'output_text' or not isinstance(content[0].get('text'), str)):
        raise AnnotationError('response_text_invalid')
    return validate_annotation(strict_json(content[0]['text']))


class Budget:
    def __init__(self, path, prior_spend, binding, *, total_micro=TOTAL_MICRO,
                 max_input=MAX_INPUT, max_output=MAX_OUTPUT, input_rate=200, output_rate=300):
        self.total_micro = total_micro
        self.max_input, self.max_output = max_input, max_output
        self.input_rate, self.output_rate = input_rate, output_rate
        self.reserve_micro = max_input * input_rate + max_output * output_rate
        prior = Decimal(prior_spend) * 1_000_000
        if not prior.is_finite() or prior != prior.to_integral_value() or not 0 <= prior <= self.total_micro:
            raise AnnotationError('prior_spend_invalid')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('BEGIN EXCLUSIVE')
        try:
            self.db.execute('CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY CHECK(id=1), prior INTEGER, binding TEXT)')
            self.db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, state TEXT, amount INTEGER, input_tokens INTEGER, output_tokens INTEGER, response_id TEXT)')
            previous = self.db.execute('SELECT prior,binding FROM meta WHERE id=1').fetchone()
            if previous is None:
                self.db.execute('INSERT INTO meta VALUES (1,?,?)', (int(prior), binding))
            elif previous != (int(prior), binding):
                raise AnnotationError('budget_binding_or_prior_spend_changed')
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.db.close()
            raise

    def bind_experiment(self, name, config):
        self.db.execute('BEGIN EXCLUSIVE')
        try:
            self.db.execute('CREATE TABLE IF NOT EXISTS experiments (name TEXT PRIMARY KEY, config TEXT)')
            row = self.db.execute('SELECT config FROM experiments WHERE name=?', (name,)).fetchone()
            if row is None:
                self.db.execute('INSERT INTO experiments VALUES (?,?)', (name, config))
            elif row[0] != config:
                raise AnnotationError('experiment_configuration_changed')
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def reserve(self, image_id):
        self.db.execute('BEGIN EXCLUSIVE')
        try:
            if self.db.execute("SELECT 1 FROM calls WHERE state='usage_exceeds_bound'").fetchone():
                raise AnnotationError('budget_fenced_after_usage_bound_violation')
            if self.db.execute('SELECT 1 FROM calls WHERE id=?', (image_id,)).fetchone():
                self.db.commit()
                return False
            spent = self.db.execute('SELECT prior FROM meta').fetchone()[0]
            spent += self.db.execute('SELECT COALESCE(SUM(amount),0) FROM calls').fetchone()[0]
            if spent + self.reserve_micro > self.total_micro:
                raise AnnotationError('budget_exhausted')
            self.db.execute('INSERT INTO calls VALUES (?,\'reserved_unknown\',?,NULL,NULL,NULL)', (image_id, self.reserve_micro))
            self.db.commit()
            return True
        except BaseException:
            self.db.rollback()
            raise

    def settle(self, image_id, response):
        usage = response.get('usage') if isinstance(response, dict) else None
        if not isinstance(usage, dict):
            return False
        tokens = (usage.get('input_tokens'), usage.get('output_tokens'))
        if any(type(v) is not int or v < 0 for v in tokens):
            return False
        amount = tokens[0] * self.input_rate + tokens[1] * self.output_rate
        exceeds = tokens[0] > self.max_input or tokens[1] > self.max_output
        self.db.execute('BEGIN EXCLUSIVE')
        try:
            row = self.db.execute('SELECT state FROM calls WHERE id=?', (image_id,)).fetchone()
            if row is None:
                raise AnnotationError('response_without_budget_reservation')
            if row[0] == 'reserved_unknown':
                self.db.execute("UPDATE calls SET state=?,amount=?,input_tokens=?,output_tokens=?,response_id=? WHERE id=?",
                                ('usage_exceeds_bound' if exceeds else 'usage_recorded', amount, *tokens,
                                 response.get('id') if isinstance(response.get('id'), str) else None, image_id))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        if exceeds:
            raise AnnotationError('usage_exceeds_reserved_bound')
        return True

    def summary(self):
        return {'prior_spend_micro_rub': self.db.execute('SELECT prior FROM meta').fetchone()[0],
                'calls': [{'id': row[0], 'state': row[1], 'amount_micro_rub': row[2]}
                          for row in self.db.execute('SELECT id,state,amount FROM calls ORDER BY id')]}


def verified_sources(manifest_path, archive_path):
    manifest_bytes = manifest_path.read_bytes()
    manifest = strict_json(manifest_bytes)
    if manifest.get('schema_revision') != 'expansion-annotation-queue-v1' or len(manifest.get('images', [])) != 100:
        raise AnnotationError('expected_100_source_manifest')
    if digest(archive_path.read_bytes()) != manifest['archive_sha256']:
        raise AnnotationError('archive_hash_mismatch')
    images = {}
    with ZipFile(archive_path) as archive:
        for entry in manifest['images']:
            image_id = entry['id']
            if (not isinstance(image_id, str) or not image_id.isascii()
                    or not all(c.isalnum() or c == '-' for c in image_id) or not image_id or image_id in images):
                raise AnnotationError('image_id_invalid')
            payload = archive.read(entry['archive_member'])
            if (digest(payload) != entry['sha256'] or len(payload) != entry['bytes']
                    or not payload.startswith(b'\x89PNG\r\n\x1a\n')):
                raise AnnotationError('image_hash_or_format_mismatch')
            images[image_id] = payload
    return manifest, digest(manifest_bytes), images


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AnnotationError('cloud_redirect_rejected')


def cloud_request(model, image, key, *, prompt=PROMPT, reasoning='none'):
    body = {'model': model, 'store': False, 'reasoning': {'effort': reasoning},
            'max_output_tokens': MAX_OUTPUT, 'temperature': 0,
            'text': {'format': {'type': 'json_schema', 'name': 'equipment_annotations', 'strict': True, 'schema': SCHEMA}},
            'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt},
                      {'type': 'input_image', 'image_url': 'data:image/png;base64,' + base64.b64encode(image).decode()}]}]}
    req = request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={
        'Authorization': 'Api-Key ' + key, 'OpenAI-Project': model.split('/')[2], 'Content-Type': 'application/json', 'x-data-logging-enabled': 'false'})
    with request.build_opener(NoRedirect()).open(req, timeout=180) as result:
        data = result.read(1_048_577)
    if len(data) > 1_048_576:
        raise AnnotationError('cloud_response_too_large')
    return data


def write_once(path, data):
    with path.open('xb') as target:
        target.write(data)
        target.flush()
        os.fsync(target.fileno())


def export_manifest(manifest, output, model, source_hash, *, prompt=PROMPT, experiment='v1', reasoning='none', model_name=MODEL):
    result = deepcopy(manifest)
    result.update(model=model_name, model_uri=model, model_file_sha256=None, adapter_bundle_sha256=None,
                  source_manifest_sha256=source_hash, prompt_sha256=digest(prompt.encode()),
                  experiment=experiment, reasoning_effort=reasoning,
                  compatible_review_manifest_sha256=[source_hash])
    for entry in result['images']:
        entry.update(review_state='unreviewed', equipment_candidates=[], scene_candidates=[], stage_candidates=[])
        annotation_path = output / 'annotations' / (entry['id'] + '.json')
        if annotation_path.exists():
            value = validate_annotation(strict_json(annotation_path.read_bytes()))
            response = strict_json((output / 'raw' / (entry['id'] + '.json')).read_bytes())
            validate_response(response, model)
            entry.update(provider_response_id=response['id'], equipment_candidates=value['objects'], equipment_states=value['equipment'],
                         scene_states=value['scenes'], stage_proposal=value['stage'], stage_reason=value['stage_reason'],
                         annotation_proposal={k: value[k] for k in ('equipment', 'scenes', 'stage')})
    target = output / 'draft-annotations.json'
    temporary = output / ('manifest-' + str(os.getpid()) + '.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'evaluation/expansion/draft-annotations.json')
    parser.add_argument('--archive', type=Path, default=ROOT / 'artifacts/dataset/Строительная_техника.zip')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--prior-spend-rub', required=True, help='Confirmed prior spend within the shared 1000 RUB budget; immutable after initialization')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--allow-cloud-upload', action='store_true')
    parser.add_argument('--experiment', choices=('v1', 'v2'), default='v1')
    parser.add_argument('--prompt-version', choices=('v1', 'v2'), default='v1')
    parser.add_argument('--reasoning', choices=('none', 'medium'), default='none')
    args = parser.parse_args()
    if not args.allow_cloud_upload:
        raise AnnotationError('explicit_cloud_upload_authorization_required')
    key, folder = os.environ.get('YANDEX_API_KEY'), os.environ.get('YANDEX_FOLDER_ID')
    if not key or not folder or not all(c.isalnum() or c == '-' for c in folder):
        raise AnnotationError('cloud_environment_missing_or_invalid')
    if args.limit < 1 or args.limit > 100:
        raise AnnotationError('limit_invalid')
    manifest, source_hash, images = verified_sources(args.manifest, args.archive)
    ids = args.ids or list(images)
    if len(set(ids)) != len(ids) or any(i not in images for i in ids):
        raise AnnotationError('requested_ids_invalid')
    model = f'gpt://{folder}/{MODEL}/latest'
    binding = json.dumps({'manifest': source_hash, 'model': model, 'output': str(args.output.resolve()),
                          'prompt': PROMPT, 'schema': SCHEMA, 'max_output': MAX_OUTPUT}, sort_keys=True)
    if args.experiment == 'v1' and (args.prompt_version != 'v1' or args.reasoning != 'none'):
        raise AnnotationError('v1_configuration_is_immutable')
    budget = Budget(LEDGER, args.prior_spend_rub, digest(binding.encode()))
    prompt = PROMPTS[args.prompt_version]
    budget.bind_experiment(args.experiment, json.dumps({'prompt': prompt, 'reasoning': args.reasoning,
                                                       'schema': SCHEMA, 'max_output': MAX_OUTPUT}, sort_keys=True))
    output = args.output if args.experiment == 'v1' else args.output / args.experiment
    for name in ('raw', 'annotations'):
        (output / name).mkdir(parents=True, exist_ok=True)
    count = 0
    try:
        for image_id in ids:
            call_id = image_id if args.experiment == 'v1' else args.experiment + '/' + image_id
            raw_path = output / 'raw' / (image_id + '.json')
            annotation_path = output / 'annotations' / (image_id + '.json')
            if raw_path.exists():
                response = strict_json(raw_path.read_bytes())
                if not budget.settle(call_id, response):
                    raise AnnotationError('response_usage_missing_reserve_retained')
                try:
                    annotation = validate_response(response, model)
                except (ValueError, TypeError):
                    print(f'{image_id}: validation_error; no retry', flush=True)
                    continue
                if not annotation_path.exists():
                    write_once(annotation_path, json.dumps(annotation, ensure_ascii=False).encode())
                continue
            if count >= args.limit:
                break
            if not budget.reserve(call_id):
                print(f'{image_id}: existing reservation; no retry', flush=True)
                continue
            count += 1
            started = time.monotonic()
            raw = cloud_request(model, images[image_id], key, prompt=prompt, reasoning=args.reasoning)
            write_once(raw_path, raw)
            response = strict_json(raw)
            if not budget.settle(call_id, response):
                raise AnnotationError('response_usage_missing_reserve_retained')
            annotation = validate_response(response, model)
            write_once(annotation_path, json.dumps(annotation, ensure_ascii=False).encode())
            print(f'{image_id}: proposal saved ({time.monotonic() - started:.1f}s)', flush=True)
    finally:
        export_manifest(manifest, output, model, source_hash, prompt=prompt,
                        experiment=args.experiment, reasoning=args.reasoning)
        print(json.dumps(budget.summary(), ensure_ascii=False))
        budget.db.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc) if isinstance(exc, AnnotationError) else 'annotation_run_failed_reservations_retained', file=sys.stderr)
        sys.exit(1)
