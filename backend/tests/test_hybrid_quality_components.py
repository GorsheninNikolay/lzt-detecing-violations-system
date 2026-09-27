"""Raw component qualification; fixtures are synthetic, never quality acceptance."""
import copy
import json
from pathlib import Path

import pytest

from app.application.hybrid_quality_components import qualify_components, measure, request_body
from app.application.deepseek_runtime import observation_context
from app.profiles import hybrid, deepseek, yolo
from app.shared.cloud import digest, canonical_bytes
from PIL import Image
from test_hybrid import frame_value, hybrid_assessment
from test_deepseek import response, photo


def synthetic_components(case, expected, weights, profile=None, root=None):
    profile = profile or hybrid.snapshot('local-test')
    reference = {'frames': {}, 'assessment': {}, 'context': {
        'zone_id': 'test-zone', 'plan': None, 'comparison_method': 'individual_frames_only', 'rule_results': []},
        'iou_match_threshold': 0.5}
    evidence = {'frames': []}
    contexts = []
    stage = 'unknown' if case['outcome'] in ('unusable', 'ambiguous') else case['stage']
    usable = case['outcome'] != 'unusable'
    expected['stage'] = stage
    expected['warnings'] = ['visible_process_risk'] if case['outcome'] == 'grounded-risk' else []
    for ordinal, source in enumerate(case['frames']):
        source.setdefault('input_id', case['id'] + '/frame/' + str(ordinal))
        key = source['input_id']
        models = []
        for definition in yolo.manifest()['models']:
            matches = [i for i, name in enumerate(definition['classes'])
                       if definition['mapping'][name] == expected['equipment'][0]]
            class_id = matches[0] if matches else 0
            raw_name = definition['classes'][class_id]
            models.append({'model_id': definition['id'], 'weights_sha256': weights[definition['id']],
                'image_size': [4, 4], 'latency_ms': 1.5, 'detections': [{
                    'id': key + '/' + definition['id'] + '/0', 'input_id': key,
                    'model_id': definition['id'], 'class_id': class_id, 'raw_class': raw_name,
                    'catalog_class': definition['mapping'][raw_name], 'score': 0.9, 'box': [.1, .2, .5, .8]}]})
        if root is not None:
            raw = (root / source['path']).read_bytes()
        else:
            raw = Path(source['path']).read_bytes()
        oriented, _, dimensions = deepseek.oriented_image(raw)
        for model in models: model['image_size'] = dimensions
        detectors = {'manifest': yolo.manifest(), 'oriented_sha256': digest(oriented), 'models': models}
        value = frame_value()
        value['stage'] = stage
        russian_names = ['экскаватор', 'самосвал', 'дорожный каток', 'кран-манипулятор',
                         'автобетоносмеситель', 'бульдозер', 'грузовик', 'автокран']
        value['objects'][0].update(catalog_class=expected['equipment'][0], type_en=expected['equipment'][0],
                                  type_ru=russian_names[deepseek.EQUIPMENT.index(expected['equipment'][0])],
                                  visual_action='digging' if usable else 'unknown',
                                  detection_ids=[m['detections'][0]['id'] for m in models])
        value['detection_dispositions'] = [{'detection_id': m['detections'][0]['id'],
                                          'status': 'accepted', 'reason': 'Synthetic association'} for m in models]
        value['frame_usability']['usable'] = usable
        raw_response = response(value)
        raw_response['model'] = profile['requested_model_identity']['id']
        raw_response['id'] = key + '/response'
        evidence['frames'].append({'input_id': key, 'sha256': source['sha256'], 'detectors': detectors,
                                   'deepseek': {'raw': raw_response, 'latency_ms': 5.5}})
        reference['frames'][key] = {'objects': [{k: value['objects'][0][k] for k in ('catalog_class', 'box', 'visual_action')}],
                                   'stage': stage, 'frame_usability': usable}
        context = observation_context({'input_id': key, 'ordinal': ordinal, 'sha256': source['sha256'], 'artifact_id': key},
                                      {'value': value, 'detectors': detectors})
        context['captured_at'] = source['captured_at']
        contexts.append(context)
    context = {**reference['context'], 'frames': contexts}
    assessment = hybrid_assessment(context)
    assessment['stage_hypothesis']['stage'] = stage
    if not usable:
        assessment['activity'][0].update(state='insufficient_data', grounds='insufficient_evidence')
    if case['outcome'] == 'grounded-risk':
        assessment['risks'] = [{'category': 'process', 'cause': 'visible_process_risk',
            'text': 'Проверить видимое препятствие', 'frame_ids': [contexts[0]['input_id']],
            'observation_ids': [contexts[0]['observations'][0]['id']], 'work_entry_id': None,
            'impact': 'Помеха проезду', 'recommended_check': 'Осмотреть участок', 'limitations': ['Только фото']}]
    reference['assessment'] = {'stage': stage, 'activity': sorted(a['state'] for a in assessment['activity']),
                               'signals': sorted(r['cause'] for r in assessment['risks'])}
    raw_response = response(assessment)
    raw_response.update(id=case['id'] + '/assessment', model=profile['requested_model_identity']['id'])
    evidence.update(assessment={'raw': raw_response, 'latency_ms': 6.5}, assessment_context=context)
    bind_requests(evidence, case, profile, root)
    return evidence, reference


def bind_requests(evidence, case, profile, root):
    images = []
    for frame, source in zip(evidence['frames'], case['frames']):
        raw = ((root / source['path']) if root else Path(source['path'])).read_bytes()
        images.append((frame['input_id'], raw))
        body = request_body('frame', {'input_id': frame['input_id'], 'detectors': frame['detectors']}, profile,
                            [(frame['input_id'], raw)])
        frame['deepseek'].update(request=body, request_sha256=digest(canonical_bytes(body)))
    body = request_body('assessment', evidence['assessment_context'], profile, images)
    evidence['assessment'].update(request=body, request_sha256=digest(canonical_bytes(body)))


def augment_edge_cases(cases, annotations, weights, profile, root):
    def new_case(mode, count):
        case = copy.deepcopy(cases[0]); case.update(id='edge-' + mode, edge_cases=[], frames=[])
        annotation = copy.deepcopy(annotations[cases[0]['id']])
        annotation['expected'].update(equipment=['excavator'], warnings=[], outcome='normal')
        case['outcome'] = 'normal'
        for n in range(count):
            source = copy.deepcopy(cases[0]['frames'][0]); source.pop('input_id', None)
            path = root / ('edge-' + mode + '-' + str(n) + '.png')
            image = Image.new('RGB', (4, 4), (100 + len(cases), n + 50, 70)); image.save(path)
            source.update(path=path.name, sha256=digest(path.read_bytes()),
                          rgb_sha256=digest(str(image.size).encode() + image.tobytes()))
            case['frames'].append(source)
        cases.append(case); annotations[case['id']] = annotation
        return case, annotation

    for mode, count in (('repeated', 2), ('idle', 2), ('boundaries', 1), ('occlusion', 1), ('similar', 1)):
        case, annotation = new_case(mode, count)
        if mode == 'repeated':
            case['frames'][1] = copy.deepcopy(case['frames'][0])
            case['edge_cases'] = ['repeated_image', 'no_plan', 'unknown_time', 'visible_action']
        elif mode == 'idle':
            case.update(outcome='grounded-risk', edge_cases=['possible_idle', 'same_machine_multi_frame'])
            for n, source in enumerate(case['frames']): source['captured_at'] = f'2026-09-27T12:{n*10:02}:00Z'
        elif mode == 'boundaries':
            case['frames'][0]['captured_at'] = '2026-09-27T12:00:00Z'
            case['edge_cases'] = ['interval_boundaries', 'concurrent_works']
        elif mode == 'occlusion':
            case['edge_cases'] = ['occlusion']
        else:
            case['edge_cases'] = ['similar_equipment']
        evidence, reference = synthetic_components(case, annotation['expected'], weights, profile, root)
        if mode == 'idle':
            reference['context']['comparison_method'] = 'same_zone_independent_timed_frames'
            for frame in evidence['frames']:
                raw = frame['deepseek']['raw']; value = json.loads(raw['output'][0]['content'][0]['text'])
                value['objects'][0].update(visual_action='no_visible_action', idle_indicator='stowed_work_attachment',
                                          action_evidence='Рабочее оборудование сложено')
                raw['output'][0]['content'][0]['text'] = json.dumps(value)
                reference['frames'][frame['input_id']]['objects'][0]['visual_action'] = 'no_visible_action'
        elif mode == 'boundaries':
            reference['context']['plan'] = {'entries': [
                {'id': str(n), 'state': 'active', 'stage_key': case['stage'],
                 'starts_at': '2026-09-27T12:00:00Z', 'ends_at': '2026-09-27T13:00:00Z'} for n in range(2)]}
        elif mode == 'occlusion':
            raw = evidence['frames'][0]['deepseek']['raw']; value = json.loads(raw['output'][0]['content'][0]['text'])
            value['objects'].append({**copy.deepcopy(value['objects'][0]), 'catalog_class': None,
                'type_ru': deepseek.GENERIC, 'type_en': 'unidentified construction equipment',
                'status': 'uncertain', 'box': None, 'missing_localization_reason': 'Объект перекрыт',
                'detection_ids': [], 'visual_action': 'unknown'})
            raw['output'][0]['content'][0]['text'] = json.dumps(value)
        elif mode == 'similar':
            frame = evidence['frames'][0]; raw = frame['deepseek']['raw']
            value = json.loads(raw['output'][0]['content'][0]['text'])
            value['objects'].append({**copy.deepcopy(value['objects'][0]), 'box': [.6, .2, .9, .8], 'detection_ids': []})
            raw['output'][0]['content'][0]['text'] = json.dumps(value)
            reference['frames'][frame['input_id']]['objects'].append({
                k: value['objects'][1][k] for k in ('catalog_class', 'box', 'visual_action')})
        contexts = []
        for ordinal, (frame, source) in enumerate(zip(evidence['frames'], case['frames'])):
            value = json.loads(frame['deepseek']['raw']['output'][0]['content'][0]['text'])
            context = observation_context({'input_id': frame['input_id'], 'ordinal': ordinal,
                                          'sha256': source['sha256'], 'artifact_id': frame['input_id']},
                                         {'value': value, 'detectors': frame['detectors']})
            context['captured_at'] = source['captured_at']; contexts.append(context)
        context = {**reference['context'], 'frames': contexts}
        assessment = hybrid_assessment(context)
        assessment['stage_hypothesis']['stage'] = case['stage']
        if mode == 'idle':
            refs = [f['observations'][0]['id'] for f in contexts]
            assessment['activity'] = [{'state': 'possible_idle', 'reason': 'Возможный простой, нужна проверка',
                'uncertainty': 'Нельзя установить длительность', 'frame_ids': [f['input_id'] for f in contexts],
                'observation_ids': refs, 'grounds': 'comparable_series_without_work_signs',
                'comparison': {'same_view': True, 'view_reason': 'Совпадает фон', 'object_observation_ids': refs,
                               'identity_reason': 'Та же машина', 'non_work_evidence': 'Рабочее оборудование сложено'}}]
            assessment['risks'] = [{'category': 'process', 'cause': 'possible_idle', 'text': 'Возможный простой',
                'frame_ids': [f['input_id'] for f in contexts], 'observation_ids': refs, 'work_entry_id': None,
                'impact': 'Требуется проверка', 'recommended_check': 'Проверить на месте', 'limitations': ['По фото']}]
            annotation['expected']['warnings'] = ['possible_idle']
        reference['assessment'] = {'stage': case['stage'], 'activity': sorted(a['state'] for a in assessment['activity']),
                                   'signals': sorted(r['cause'] for r in assessment['risks'])}
        raw = evidence['assessment']['raw']; raw['output'][0]['content'][0]['text'] = json.dumps(assessment)
        evidence['assessment_context'] = context
        bind_requests(evidence, case, profile, root)
        annotation['component_reference'] = reference
        annotation['_synthetic_component_evidence'] = evidence
    return {case['id']: annotations[case['id']].pop('_synthetic_component_evidence') for case in cases
            if '_synthetic_component_evidence' in annotations[case['id']]}


def fixture(tmp_path, outcome='normal'):
    path = tmp_path / 'frame.png'; path.write_bytes(photo())
    profile = hybrid.snapshot('local-test')
    weights = {m['id']: m['sha256'] for m in yolo.manifest()['models']}
    case = {'id': 'case', 'stage': 'excavation', 'outcome': outcome,
            'frames': [{'path': path.name, 'sha256': digest(path.read_bytes()), 'captured_at': None}]}
    expected = {'equipment': ['excavator'], 'stage': 'excavation', 'warnings': []}
    evidence, reference = synthetic_components(case, expected, weights, profile, tmp_path)
    return {'component_evidence': evidence}, {'component_reference': reference, 'expected': expected}, case, profile, weights


@pytest.mark.parametrize('outcome', ['normal', 'grounded-risk', 'ambiguous', 'unusable'])
def test_original_components_are_validated_and_measured(tmp_path, outcome):
    result = qualify_components(*fixture(tmp_path, outcome), tmp_path)
    assert result['outcome'] == outcome
    assert result['models']['hybrid']['precision'] == 1
    assert result['models']['hybrid']['recall'] == 1
    assert result['models']['hybrid']['per_class']['excavator']['tp'] == 1
    assert result['models']['hybrid']['per_class']['excavator']['mean_matched_iou'] == 1
    assert result['cost_estimate_rub'] == '0.022'


@pytest.mark.parametrize('problem', ['missing_model', 'weights', 'pixels', 'dimensions', 'provider_model',
    'provider_usage', 'response_reuse', 'request', 'request_digest', 'expected_equipment',
    'context', 'activity', 'action', 'localization', 'latency'])
def test_missing_or_conflicting_component_evidence_blocks(tmp_path, problem):
    args = fixture(tmp_path)
    evidence = args[0]['component_evidence']; frame = evidence['frames'][0]
    if problem == 'missing_model': frame['detectors']['models'].pop()
    elif problem == 'weights': frame['detectors']['models'][0]['weights_sha256'] = 'wrong'
    elif problem == 'pixels': frame['detectors']['oriented_sha256'] = 'wrong'
    elif problem == 'dimensions': frame['detectors']['models'][0]['image_size'] = [1, 1]
    elif problem == 'provider_model': frame['deepseek']['raw']['model'] = 'foreign'
    elif problem == 'provider_usage': frame['deepseek']['raw']['usage']['input_tokens'] = True
    elif problem == 'response_reuse': evidence['assessment']['raw']['id'] = frame['deepseek']['raw']['id']
    elif problem == 'request': frame['deepseek']['request']['model'] = 'foreign'
    elif problem == 'request_digest': frame['deepseek']['request_sha256'] = 'wrong'
    elif problem == 'expected_equipment': args[1]['expected']['equipment'] = ['bulldozer']
    elif problem == 'context': evidence['assessment_context'] = copy.deepcopy(evidence['assessment_context']); evidence['assessment_context']['zone_id'] = 'other'
    elif problem == 'activity': args[1]['component_reference']['assessment']['activity'] = ['insufficient_data']
    elif problem == 'latency': evidence['assessment']['latency_ms'] = float('nan')
    else:
        value = json.loads(frame['deepseek']['raw']['output'][0]['content'][0]['text'])
        if problem == 'action': value['objects'][0]['visual_action'] = 'pouring'
        else: value['objects'][0]['box'] = [.6, .2, .9, .8]
        frame['deepseek']['raw']['output'][0]['content'][0]['text'] = json.dumps(value)
    with pytest.raises(ValueError): qualify_components(*args, tmp_path)


def test_matching_does_not_count_duplicate_predictions_twice():
    obj = {'catalog_class': 'excavator', 'box': [.1, .2, .5, .8]}
    result = measure([obj, obj], [obj], 0.5)
    assert (result['tp'], result['fp'], result['fn']) == (1, 1, 0)


@pytest.mark.parametrize('tag', ['possible_idle', 'same_machine_multi_frame', 'occlusion',
                               'interval_boundaries', 'concurrent_works', 'repeated_image'])
def test_edge_labels_cannot_substitute_for_actual_exercised_conditions(tmp_path, tag):
    args = fixture(tmp_path)
    args[2]['edge_cases'] = [tag]
    with pytest.raises(ValueError, match='edge_case_not_exercised'):
        qualify_components(*args, tmp_path)


def test_edge_conditions_are_derived_from_raw_context(tmp_path):
    args = fixture(tmp_path)
    args[2]['edge_cases'] = ['no_plan', 'unknown_time', 'visible_action']
    assert qualify_components(*args, tmp_path)['outcome'] == 'normal'


def test_edge_fixture_exercises_timed_idle_duplicates_and_plan_boundaries(tmp_path):
    result, annotation, case, profile, weights = fixture(tmp_path)
    cases, annotations = [case], {case['id']: annotation}
    evidence = augment_edge_cases(cases, annotations, weights, profile, tmp_path)
    for extra in cases[1:]:
        measured = qualify_components({'component_evidence': evidence[extra['id']]}, annotations[extra['id']],
                                      extra, profile, weights, tmp_path)
        assert measured['outcome'] == extra['outcome']
