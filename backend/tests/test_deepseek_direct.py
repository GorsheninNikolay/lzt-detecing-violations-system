import base64
import asyncio
import copy
import hashlib
import json
import uuid

import pytest

from app.application.submission import SubmissionError, submit, submit_series, validate_request
from app.config import Config
from app.profiles import deepseek, hybrid
from app.shared.cloud import canonical_bytes, digest, strict_json
from test_deepseek import annotation, body, photo, response
from test_admission import isolated_admission_database
from test_startup import database, integration


def direct_response():
    raw = response(annotation())
    raw['model'] = 'deepseek-flash'
    return raw


def test_legacy_snapshot_shape_unchanged():
    assert deepseek.snapshot('mock-folder') == {
        'kind': 'deepseek', 'adapter': {'code': 'yandex_deepseek', 'version': deepseek.REVISION},
        'folder_id': 'mock-folder',
        'requested_model_identity': {'id': 'gpt://mock-folder/' + deepseek.MODEL},
        'observation_contract': 'free-equipment-v1', 'instruction_version': deepseek.REVISION,
        'schema_version': deepseek.REVISION,
        'schema_sha256': digest(canonical_bytes([deepseek.SCHEMA, deepseek.ASSESSMENT_SCHEMA])),
        'instruction_sha256': digest((deepseek.PROMPT + deepseek.ANALYSIS_PROMPT).encode()),
        'reasoning_effort': 'none', 'temperature': 0, 'max_output_tokens': 8192,
        'store': False, 'data_logging_enabled': False,
        'runtime': {'per_image_timeout_seconds': 120, 'batch_timeout_seconds': 1200, 'sdk_retries': 0},
    }


@pytest.mark.parametrize('module', [deepseek, hybrid])
def test_direct_snapshot_and_constructor_do_not_call_provider(module, monkeypatch):
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: pytest.fail('constructor made a paid call'))
    profile = module.snapshot(provider='deepseek')
    frozen = copy.deepcopy(profile)
    assert profile['adapter']['code'] == 'deepseek_direct'
    assert profile['requested_model_identity']['id'] == 'deepseek-flash'
    assert not profile.get('folder_id')
    deepseek.DeepSeek(profile, 'direct-test-key')
    assert profile == frozen
    assert digest(canonical_bytes(profile)) != digest(canonical_bytes(module.snapshot('mock-folder')))


def test_saved_profile_selects_credentials(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://test:test@localhost/test')
    for key in ('S3_ENDPOINT', 'S3_BUCKET', 'S3_ACCESS_KEY', 'S3_SECRET_KEY'):
        monkeypatch.setenv(key, 'test')
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY', 'yandex-test-key')
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'direct-test-key')
    monkeypatch.setenv('CLOUD_PROVIDER', 'deepseek')
    config = Config.from_env()
    assert config.cloud_api_key == 'yandex-test-key'
    assert config.deepseek_api_key == 'direct-test-key'
    assert config.api_key_for(deepseek.snapshot('mock-folder')) == 'yandex-test-key'
    assert config.api_key_for(deepseek.snapshot(provider='deepseek')) == 'direct-test-key'


@pytest.mark.parametrize('provider', ['deepseek', 'yandex_ai_studio'])
def test_request_endpoint_and_headers_are_provider_specific(provider, monkeypatch):
    monkeypatch.delenv('HYBRID_BUDGET_LEDGER', raising=False)
    profile = deepseek.snapshot(provider=provider) if provider == 'deepseek' else deepseek.snapshot('mock-folder')
    calls = []

    def read(http_request, timeout):
        calls.append(http_request)
        request_body = strict_json(http_request.data)
        assert request_body['model'] == profile['requested_model_identity']['id']
        assert request_body['reasoning'] == {'effort': 'none'}
        assert request_body['temperature'] == 0
        assert request_body['max_output_tokens'] == 8192
        assert request_body['store'] is False
        assert request_body['text']['format']['schema'] == deepseek.compact_output_schema(deepseek.SCHEMA)
        raw = direct_response() if provider == 'deepseek' else response(annotation())
        return raw

    monkeypatch.setattr(deepseek, '_read_json', read)
    result = deepseek.DeepSeek(profile, 'test-key').call('frame', {})
    assert result['valid'], result['rejection']
    assert result['usage'] == {'input_tokens': 20, 'output_tokens': 10, 'total_tokens': 30}
    assert len(calls) == 1
    headers = {key.lower(): value for key, value in calls[0].header_items()}
    if provider == 'deepseek':
        assert calls[0].full_url == 'https://api.deepseek.com/responses'
        assert headers['authorization'] == 'Bearer test-key'
        assert 'openai-project' not in headers
        assert 'x-data-logging-enabled' not in headers
    else:
        assert calls[0].full_url == deepseek.ENDPOINT
        assert headers['authorization'] == 'Api-Key test-key'
        assert headers['openai-project'] == 'mock-folder'
        assert headers['x-data-logging-enabled'] == 'false'


@pytest.mark.parametrize('change', [
    lambda raw: raw.update(model='wrong'),
    lambda raw: raw.update(status='incomplete'),
    lambda raw: raw['usage'].update(input_tokens=True),
    lambda raw: raw['usage'].update(total_tokens=31),
    lambda raw: raw['output'][0]['content'][0].update(text='{"objects":'),
])
def test_direct_invalid_response_is_not_published(change, monkeypatch):
    monkeypatch.delenv('HYBRID_BUDGET_LEDGER', raising=False)
    raw = direct_response()
    change(raw)
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: raw)
    result = deepseek.DeepSeek(deepseek.snapshot(provider='deepseek'), 'test-key').call('frame', {})
    assert result['valid'] is False
    assert result['value'] is None
    assert result['usage'] is None
    assert result['rejection']


def test_direct_budget_ledger_rejected_before_http(monkeypatch, tmp_path):
    path = tmp_path / 'ledger.json'
    historical = b'{"preserved":"Yandex experiment"}'
    path.write_bytes(historical)
    monkeypatch.setenv('HYBRID_BUDGET_LEDGER', str(path))
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: pytest.fail('paid call before budget check'))
    with pytest.raises(ValueError, match='^quality_budget_provider_mismatch$'):
        deepseek.DeepSeek(deepseek.snapshot(provider='deepseek'), 'test-key').call('frame', {})
    assert path.read_bytes() == historical


class NoMutation:
    def read_submission(self, key, request_hash):
        return None

    def __getattr__(self, name):
        pytest.fail('provider mismatch accessed ' + name)


@pytest.mark.parametrize('series', [False, True])
@pytest.mark.parametrize('provider, consent_provider', [
    ('deepseek', None), ('deepseek', 'yandex_ai_studio'), ('yandex_ai_studio', 'deepseek'),
])
def test_provider_consent_checked_before_publication(series, provider, consent_provider):
    profile = deepseek.snapshot(provider='deepseek') if provider == 'deepseek' else deepseek.snapshot('mock-folder')
    request = body()
    if consent_provider is not None:
        request['cloud_provider'] = consent_provider
    if series:
        request['images_base64'] = [request.pop('image_base64'), base64.b64encode(photo('JPEG')).decode()]
    with pytest.raises(SubmissionError, match='^cloud_provider_mismatch$'):
        (submit_series if series else submit)(NoMutation(), NoMutation(), 'test-key', request,
                                              uuid.uuid4(), 1, profile)


@pytest.mark.parametrize('series', [False, True])
@pytest.mark.parametrize('provider, explicit', [('deepseek', True), ('yandex_ai_studio', True), ('yandex_ai_studio', False)])
def test_matching_provider_consent_reaches_admission(series, provider, explicit):
    profile = deepseek.snapshot(provider='deepseek') if provider == 'deepseek' else deepseek.snapshot('mock-folder')
    request = body()
    if explicit:
        request['cloud_provider'] = provider
    if series:
        request['images_base64'] = [request.pop('image_base64'), base64.b64encode(photo('JPEG')).decode()]
    run_id = uuid.uuid4()

    class Accepted:
        def begin_submission(self, *args):
            return 'accepted', run_id, None, None

    assert (submit_series if series else submit)(Accepted(), NoMutation(), 'test-key', request,
                                                 uuid.uuid4(), 1, profile) == ('queued', run_id)


@pytest.mark.parametrize('module', [deepseek, hybrid])
def test_unknown_provider_cannot_create_profile(module):
    with pytest.raises(ValueError):
        module.snapshot('mock-folder', provider='unknown')


def test_unknown_saved_adapter_cannot_call_provider(monkeypatch):
    profile = deepseek.snapshot(provider='deepseek')
    profile['adapter']['code'] = 'unknown'
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: pytest.fail('unknown provider made a call'))
    with pytest.raises(ValueError):
        deepseek.DeepSeek(profile, 'test-key')


@pytest.mark.parametrize('provider', [None, '', 'unknown', 42, [], {}])
@pytest.mark.parametrize('series', [False, True])
def test_malformed_explicit_provider_rejected_even_for_legacy(provider, series):
    request = body() | {'cloud_provider': provider}
    if series:
        request['images_base64'] = [request.pop('image_base64'), base64.b64encode(photo('JPEG')).decode()]
    with pytest.raises(SubmissionError):
        (submit_series if series else submit)(NoMutation(), NoMutation(), 'test-key', request,
                                              uuid.uuid4(), 1, deepseek.snapshot('mock-folder'))


def test_request_identity_preserves_legacy_hash_and_binds_explicit_recipient():
    request = body()
    image, context, requested, legacy_hash = validate_request(request)
    legacy_identity = {'context': context, 'requested_classes': sorted(requested),
                       'image_sha256': hashlib.sha256(image).hexdigest()}
    assert 'cloud_provider' not in context
    assert legacy_hash == hashlib.sha256(json.dumps(
        legacy_identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    hashes = []
    for provider in ('deepseek', 'yandex_ai_studio'):
        _, saved_context, _, request_hash = validate_request(request | {'cloud_provider': provider})
        assert saved_context['cloud_provider'] == provider
        hashes.append(request_hash)
    assert len({legacy_hash, *hashes}) == 3


@pytest.fixture
def direct_service(isolated_admission_database, monkeypatch):
    from app.adapters.artifacts import ArtifactStore
    from app.adapters.postgres import PostgresStore
    from app.application import deepseek_runtime
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'direct-test-key')
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY', 'yandex-test-key')
    monkeypatch.delenv('HYBRID_BUDGET_LEDGER', raising=False)
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(Config.from_env())
    profile_id = deepseek_runtime.provision(store, provider='deepseek')
    profile, revision = store.require_authorized(profile_id)
    try:
        yield store, artifacts, profile_id, profile, revision
    finally:
        store.close()


@pytest.mark.parametrize('series', [False, True])
def test_direct_durable_run_and_idempotent_recovery(direct_service, monkeypatch, series):
    from app.application.executor import ClaimLoop
    from test_deepseek import assessment
    store, artifacts, profile_id, profile, revision = direct_service
    request = body() | {'cloud_provider': 'deepseek'}
    if series:
        request['images_base64'] = [request.pop('image_base64'), base64.b64encode(photo('JPEG')).decode()]
    calls = []

    def provider(http_request, timeout):
        sent = strict_json(http_request.data)
        calls.append(sent)
        assert http_request.full_url == 'https://api.deepseek.com/responses'
        assert http_request.get_header('Authorization') == 'Bearer direct-test-key'
        raw = response(annotation() if sent['text']['format']['name'] == 'frame' else assessment())
        raw.update(model='deepseek-flash', id='direct-call-' + str(len(calls)))
        return raw

    monkeypatch.setattr(deepseek, '_read_json', provider)
    method = submit_series if series else submit
    key = str(uuid.uuid4())
    _, run_id = method(store, artifacts, key, request, profile_id, revision, profile)
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, artifacts
    work = store.claim_ordinary(profile_id, revision, 30)
    asyncio.run(runner._execute(work, revision))
    result = store.read_ordinary(run_id)
    assert result['state'] == 'succeeded', result['error_code']
    assert result['profile_snapshot'] == profile
    assert result['context']['cloud_provider'] == 'deepseek'
    assert result['result_projection']['source'] == 'DeepSeek · Мультимодальная модель'
    assert len(result['ai_evidence']) == len(calls) == (3 if series else 2)
    assert all(call['result']['model'] == 'deepseek-flash' for call in result['ai_evidence'])
    assert all(call['result']['usage']['total_tokens'] == 30 for call in result['ai_evidence'])
    assert 'direct-test-key' not in json.dumps(result)
    assert method(store, artifacts, key, request, profile_id, revision, profile) == ('queued', run_id)
    assert store.claim_ordinary(profile_id, revision, 30) is None
    assert len(calls) == (3 if series else 2)


@pytest.mark.parametrize('source_provider', ['deepseek', 'yandex_ai_studio'])
@pytest.mark.parametrize('repeat_processing', [False, True])
def test_provider_switch_blocks_retry_before_artifacts(direct_service, source_provider, repeat_processing):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from app.adapters.postgres import AdmissionStoreError
    from app.application import deepseek_runtime
    from app.main import create_app
    store, artifacts, direct_id, direct_profile, direct_revision = direct_service
    yandex_id = deepseek_runtime.provision(store, 'mock-folder')
    yandex_profile, yandex_revision = store.require_authorized(yandex_id)
    direct = (direct_id, direct_profile, direct_revision)
    yandex = (yandex_id, yandex_profile, yandex_revision)
    source, target = (direct, yandex) if source_provider == 'deepseek' else (yandex, direct)
    request = body() | {'cloud_provider': source_provider}
    _, run_id = submit(store, artifacts, str(uuid.uuid4()), request, source[0], source[2], source[1])
    work = store.claim_ordinary(source[0], source[2], 30)
    store.fail_ordinary(run_id, work['owner'], 'executor_interrupted')
    with pytest.raises(AdmissionStoreError, match='^cloud_provider_mismatch$'):
        store.retry_ordinary(run_id, target[0], target[2], target[1], NoMutation(), repeat_processing=repeat_processing)
    app = create_app()
    app.state.readiness.ready.set()
    app.state.store, app.state.artifacts = store, NoMutation()
    app.state.claim_loop = SimpleNamespace(runtime_binding=(target[0], target[2]))
    client = TestClient(app)
    assert client.get('/runs/' + str(run_id)).json()['retry_eligible'] is False
    rejected = client.post('/runs/' + str(run_id) + '/retry', json={'repeat_processing': repeat_processing})
    assert rejected.status_code == 409
    assert rejected.json() == {'code': 'cloud_provider_mismatch'}
    assert store.read_ordinary(run_id)['retry_successor_id'] is None


@pytest.mark.parametrize('failure', ['balance', 'timeout'])
def test_direct_failed_paid_call_is_durable_and_never_replayed(direct_service, monkeypatch, failure):
    from types import SimpleNamespace
    from urllib.error import HTTPError
    from app.adapters.postgres import AdmissionStoreError
    from app.application.executor import ClaimLoop
    from app.shared import cloud
    store, artifacts, profile_id, profile, revision = direct_service
    calls = []

    def open_request(http_request, **kwargs):
        calls.append(http_request)
        if failure == 'balance':
            raise HTTPError(http_request.full_url, 402, 'Insufficient Balance', {}, None)
        raise TimeoutError()

    monkeypatch.setattr(cloud.request, 'build_opener', lambda *args: SimpleNamespace(open=open_request))
    _, run_id = submit(store, artifacts, str(uuid.uuid4()), body() | {'cloud_provider': 'deepseek'},
                       profile_id, revision, profile)
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, artifacts
    work = store.claim_ordinary(profile_id, revision, 30)
    asyncio.run(runner._execute(work, revision))
    failed = store.read_ordinary(run_id)
    assert failed['state'] == 'failed'
    assert failed['error_code'] == ('observer_balance_failed' if failure == 'balance' else 'observer_timeout')
    assert failed['result_projection'] is None
    assert len(failed['ai_evidence']) == len(calls) == 1
    assert failed['ai_evidence'][0]['state'] == 'uncertain'
    with pytest.raises(AdmissionStoreError, match='^provider_call_not_replayable$'):
        store.retry_ordinary(run_id, profile_id, revision, profile, artifacts)
    assert store.claim_ordinary(profile_id, revision, 30) is None
    assert len(calls) == 1


@pytest.mark.parametrize('provider', ['deepseek', 'yandex_ai_studio', None])
def test_choices_disclose_saved_provider_without_secrets(provider):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    profile_id = uuid.uuid4()
    if provider:
        profile = deepseek.snapshot(provider='deepseek') if provider == 'deepseek' else deepseek.snapshot('mock-folder')
        app.state.claim_loop = SimpleNamespace(runtime_binding=(profile_id, 1))
        app.state.store = SimpleNamespace(require_authorized=lambda *args: (profile, 1))
    result = TestClient(app).get('/analysis-choices')
    assert result.status_code == 200
    assert result.headers['Cache-Control'] == 'no-store'
    assert result.json()['cloud_provider'] == provider
    assert result.json()['cloud_profile_id'] == (str(profile_id) if provider else None)
    assert 'stages' in result.json()
    assert 'api_key' not in result.text


def test_direct_response_without_reasoning_echo_preserves_raw(monkeypatch):
    monkeypatch.delenv('HYBRID_BUDGET_LEDGER', raising=False)
    raw = direct_response()
    del raw['reasoning']
    raw['usage']['output_tokens_details'] = {'reasoning_tokens': 0}
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: raw)
    result = deepseek.DeepSeek(deepseek.snapshot(provider='deepseek'), 'test-key').call('frame', {})
    assert result['valid'] is True
    assert 'reasoning' not in result['raw']
    raw['usage']['output_tokens_details']['reasoning_tokens'] = 1
    rejected = deepseek.DeepSeek(deepseek.snapshot(provider='deepseek'), 'test-key').call('frame', {})
    assert rejected['valid'] is False
    assert rejected['rejection'] == 'response_reasoning_unconfirmed'
    assert rejected['raw'] == raw


@pytest.mark.parametrize('field, value', [('endpoint', 'https://foreign.invalid/responses'),
                                         ('requested_model_identity', {'id': 'deepseek-v4-pro'})])
def test_tampered_direct_profile_cannot_route_request(monkeypatch, field, value):
    profile = deepseek.snapshot(provider='deepseek')
    profile[field] = value
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: pytest.fail('tampered profile sent HTTP'))
    with pytest.raises(ValueError, match='^deepseek_profile_invalid$'):
        deepseek.DeepSeek(profile, 'test-key')


def test_direct_receipt_cannot_use_legacy_quality_pricing():
    from app.application.hybrid_quality_components import response as qualify_response
    with pytest.raises(ValueError, match='^quality_budget_provider_mismatch$'):
        qualify_response({}, hybrid.snapshot(provider='deepseek'), {})


def test_direct_hybrid_run_keeps_detector_and_cloud_evidence(direct_service, monkeypatch):
    from types import SimpleNamespace
    from app.application import deepseek_runtime
    from app.application.executor import ClaimLoop
    from app.profiles import yolo
    from test_hybrid import frame_value, hybrid_assessment
    store, artifacts, _, _, _ = direct_service
    profile_id = deepseek_runtime.provision(store, hybrid=True, provider='deepseek')
    profile, revision = store.require_authorized(profile_id)

    def detect(payload, key):
        oriented, _, dimensions = deepseek.oriented_image(payload)
        return {'oriented_sha256': digest(oriented), 'manifest': yolo.manifest(), 'models': [
            {'model_id': 'apoce', 'detections': [{'id': key + '/apoce/0', 'input_id': key,
                'model_id': 'apoce', 'raw_class': 'excavator', 'catalog_class': 'excavator',
                'box': [.1, .2, .5, .8], 'score': .9}], 'image_size': dimensions},
            {'model_id': 'kaggle', 'detections': [], 'image_size': dimensions}]}

    calls = []

    def provider(http_request, timeout):
        sent = strict_json(http_request.data)
        kind = sent['text']['format']['name']
        prompt = hybrid.FRAME_PROMPT if kind == 'frame' else hybrid.ASSESSMENT_PROMPT
        ctx = strict_json(sent['input'][0]['content'][0]['text'].removeprefix(prompt))
        if kind == 'frame':
            value = frame_value()
            identity = ctx['detectors']['models'][0]['detections'][0]['id']
            value['objects'][0]['detection_ids'] = [identity]
            value['detection_dispositions'][0]['detection_id'] = identity
        else:
            value = hybrid_assessment(ctx)
            assert len([item for item in sent['input'][0]['content'] if item['type'] == 'input_image']) == 1
        calls.append(kind)
        raw = response(value)
        raw.update(model='deepseek-flash', id='hybrid-direct-' + kind)
        return raw

    monkeypatch.setattr(yolo, 'detectors', lambda: SimpleNamespace(detect=detect))
    monkeypatch.setattr(deepseek, '_read_json', provider)
    _, run_id = submit(store, artifacts, str(uuid.uuid4()), body() | {'cloud_provider': 'deepseek'},
                       profile_id, revision, profile)
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, artifacts
    asyncio.run(runner._execute(store.claim_ordinary(profile_id, revision, 30), revision))
    saved = store.read_ordinary(run_id)
    assert saved['state'] == 'succeeded', saved['error_code']
    assert calls == ['frame', 'assessment']
    assert saved['profile_snapshot'] == profile
    assert saved['result_projection']['source'] == 'DeepSeek · Мультимодальная модель'
    assert len(saved['result_projection']['hybrid_frames'][0]['detectors']['models']) == 2
    assert saved['ai_evidence'][0]['result']['detectors']['manifest'] == yolo.manifest()
    assert saved['ai_assessment']['activity'][0]['state'] == 'working_signs'


@pytest.mark.parametrize('series', [False, True])
@pytest.mark.parametrize('source_provider', ['deepseek', 'yandex_ai_studio', None])
def test_accepted_submission_recovers_original_run_after_provider_switch(direct_service, series, source_provider):
    from sqlalchemy import text
    from app.application import deepseek_runtime
    store, artifacts, direct_id, direct_profile, direct_revision = direct_service
    yandex_id = deepseek_runtime.provision(store, 'mock-folder')
    yandex_profile, yandex_revision = store.require_authorized(yandex_id)
    direct = (direct_id, direct_revision, direct_profile)
    yandex = (yandex_id, yandex_revision, yandex_profile)
    source, target = (direct, yandex) if source_provider == 'deepseek' else (yandex, direct)
    request = body()
    if source_provider:
        request['cloud_provider'] = source_provider
    if series:
        request['images_base64'] = [request.pop('image_base64'), base64.b64encode(photo('JPEG')).decode()]
    method = submit_series if series else submit
    key = str(uuid.uuid4())
    _, original = method(store, artifacts, key, request, *source)
    assert method(store, NoMutation(), key, request, *target) == ('queued', original)
    assert store.read_ordinary(original)['profile_snapshot'] == source[2]
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM analysis_runs')).scalar_one() == 1
        assert db.execute(text('SELECT count(*) FROM deepseek_calls')).scalar_one() == 0


@pytest.mark.parametrize('series', [False, True])
def test_mismatched_provider_recovery_is_read_only_and_hash_bound(direct_service, series):
    from sqlalchemy import text
    from app.application.submission import validate_images
    store, _, profile_id, profile, revision = direct_service
    request = body() | {'cloud_provider': 'yandex_ai_studio'}
    if series:
        request['images_base64'] = [request.pop('image_base64'), base64.b64encode(photo('JPEG')).decode()]
    method = submit_series if series else submit
    key = str(uuid.uuid4())
    with pytest.raises(SubmissionError, match='^cloud_provider_mismatch$'):
        method(store, NoMutation(), key, request, profile_id, revision, profile)
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM submission_requests')).scalar_one() == 0
    request_hash = validate_images(request, series)[3]
    store.begin_submission(key, request_hash, 'image/png')
    original = store.read_submission(key, request_hash)
    with pytest.raises(SubmissionError, match='^submission_in_progress$'):
        method(store, NoMutation(), key, request, profile_id, revision, profile)
    assert store.read_submission(key, request_hash) == original
    with pytest.raises(SubmissionError, match='^idempotency_key_conflict$'):
        method(store, NoMutation(), key, request | {'scenario': 'changed'}, profile_id, revision, profile)
    store.fail_submission(key, 'submission_interrupted')
    with pytest.raises(SubmissionError, match='^submission_interrupted$'):
        method(store, NoMutation(), key, request, profile_id, revision, profile)


@pytest.mark.parametrize('supplied', [None, 'yandex_ai_studio'])
def test_worker_rejects_persisted_recipient_before_artifacts_and_reservation(direct_service, monkeypatch, supplied):
    from types import SimpleNamespace
    from sqlalchemy import text
    from app.application import deepseek_runtime
    from app.application.executor import ClaimLoop
    from app.profiles import yolo
    store, artifacts, profile_id, profile, revision = direct_service
    _, run_id = submit(store, artifacts, str(uuid.uuid4()), body() | {'cloud_provider': 'deepseek'},
                       profile_id, revision, profile)
    work = store.claim_ordinary(profile_id, revision, 30)
    context = {'cloud_processing_consent': True}
    if supplied:
        context['cloud_provider'] = supplied
    row = SimpleNamespace(profile_snapshot=profile, request_context=context, stage_key=None)
    persisted_db = SimpleNamespace(execute=lambda *args: SimpleNamespace(one_or_none=lambda: row))
    actual_lease = deepseek_runtime.lease
    monkeypatch.setattr(deepseek_runtime, 'lease', lambda db, current: actual_lease(persisted_db, current))
    monkeypatch.setattr(yolo, 'detectors', lambda: pytest.fail('recipient rejection reached detectors'))
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: pytest.fail('recipient rejection sent HTTP'))
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, NoMutation()
    asyncio.run(runner._execute(work, revision))
    assert store.read_ordinary(run_id)['error_code'] == 'cloud_provider_mismatch'
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM deepseek_calls')).scalar_one() == 0


def test_budget_configuration_fails_before_reservation_and_can_be_retried(direct_service, monkeypatch, tmp_path):
    from sqlalchemy import text
    from app.application.executor import ClaimLoop
    store, artifacts, profile_id, profile, revision = direct_service
    _, run_id = submit(store, artifacts, str(uuid.uuid4()), body() | {'cloud_provider': 'deepseek'},
                       profile_id, revision, profile)
    work = store.claim_ordinary(profile_id, revision, 30)
    ledger = tmp_path / 'legacy-ledger.json'
    ledger.write_bytes(b'preserve historical ledger')
    monkeypatch.setenv('HYBRID_BUDGET_LEDGER', str(ledger))
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: pytest.fail('budget configuration sent HTTP'))
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, NoMutation()
    asyncio.run(runner._execute(work, revision))
    assert store.read_ordinary(run_id)['error_code'] == 'quality_budget_provider_mismatch'
    with store.engine.connect() as db:
        assert db.execute(text('SELECT count(*) FROM deepseek_calls')).scalar_one() == 0
    assert ledger.read_bytes() == b'preserve historical ledger'
    monkeypatch.delenv('HYBRID_BUDGET_LEDGER')
    successor = store.retry_ordinary(run_id, profile_id, revision, profile, artifacts)
    assert store.read_ordinary(successor)['state'] == 'queued'


@pytest.mark.parametrize('context', [{'cloud_processing_consent': True, 'cloud_provider': None},
                                  {'cloud_processing_consent': True, 'cloud_provider': ''}])
def test_durable_legacy_consent_distinguishes_omission_from_invalid_value(context):
    with pytest.raises(ValueError, match='^cloud_provider_unavailable$'):
        deepseek.validate_consent(context, deepseek.snapshot('mock-folder'))
    deepseek.validate_consent({'cloud_processing_consent': True}, deepseek.snapshot('mock-folder'))


def test_startup_rejects_incompatible_ledger_without_paid_probe(direct_service, monkeypatch, tmp_path):
    from app.main import create_app, lifespan
    _, _, profile_id, _, _ = direct_service
    monkeypatch.setenv('OBSERVER_PROFILE_ID', str(profile_id))
    monkeypatch.setenv('HYBRID_BUDGET_LEDGER', str(tmp_path / 'legacy-ledger.json'))
    monkeypatch.setattr(deepseek, '_read_json', lambda *args: pytest.fail('startup made paid probe'))

    async def check():
        app = create_app()
        async with lifespan(app):
            await app.state.startup_task
            assert app.state.readiness.ready.is_set() is False
            assert app.state.readiness.code == 'observer_snapshot_invalid'

    asyncio.run(check())


@pytest.mark.parametrize('provider', ['deepseek', 'yandex_ai_studio'])
def test_explicit_reanalysis_succeeds_with_fresh_receipts_and_audit(direct_service, monkeypatch, provider):
    from sqlalchemy import text
    from app.application.executor import ClaimLoop
    from app.application import deepseek_runtime
    from test_deepseek import assessment
    store, artifacts, profile_id, profile, revision = direct_service
    if provider == 'yandex_ai_studio':
        profile_id = deepseek_runtime.provision(store, 'mock-folder')
        profile, revision = store.require_authorized(profile_id)
    from fastapi.testclient import TestClient
    from app.main import create_app
    monkeypatch.setenv('AUTH_REQUIRED', 'true')
    app = create_app()
    app.state.store, app.state.artifacts = store, artifacts
    runner = ClaimLoop()
    runner.store, runner.artifacts = store, artifacts
    runner.runtime_binding = profile_id, revision
    app.state.claim_loop = runner
    app.state.readiness.ready.set()
    client = TestClient(app, headers={'Origin': 'http://testserver'})
    credentials = {'email': f'{uuid.uuid4()}@example.test', 'password': 'safe password 123'}
    assert client.post('/account/register', json={**credentials, 'name': 'Editor'}).status_code == 200
    requester = client.post('/account/login', json=credentials).json()['user']['id']
    project = client.post('/projects', json={'name': 'Reanalysis', 'timezone': 'UTC'}).json()
    request = body() | {'cloud_provider': provider, 'project_id': project['id'],
        'zone_id': project['default_zone_id'], 'capture_times': ['2026-09-26T12:00:00Z']}
    _, source = submit(store, artifacts, str(uuid.uuid4()), request, profile_id, revision, profile)
    monkeypatch.setattr(deepseek, '_read_json', lambda *_: (_ for _ in ()).throw(TimeoutError()))
    asyncio.run(runner._execute(store.claim_ordinary(profile_id, revision, 30), revision))
    original = store.read_ordinary(source)
    assert original['state'] == 'failed' and original['ai_evidence'][0]['state'] == 'uncertain'
    with store.engine.connect() as db:
        original_policy = db.execute(text('SELECT policy_snapshot FROM analysis_runs WHERE id=:id'), {'id': source}).scalar_one()
    acceptance = client.post(f'/runs/{source}/retry', json={'repeat_processing': True})
    assert acceptance.status_code == 202, acceptance.text
    successor = uuid.UUID(acceptance.json()['run_id'])
    with store.engine.connect() as db:
        policy = db.execute(text('SELECT policy_snapshot FROM analysis_runs WHERE id=:id'), {'id': successor}).scalar_one()
    assert policy == {**original_policy, 'manual_reanalysis': {
        'repeat_processing': True, 'requester_id': requester, 'predecessor_id': str(source)}}
    calls = []
    def successful(request, _):
        kind = strict_json(request.data)['text']['format']['name']
        calls.append(kind)
        raw = response(annotation() if kind == 'frame' else assessment())
        if provider == 'deepseek':
            raw['model'] = 'deepseek-flash'
        return raw
    monkeypatch.setattr(deepseek, '_read_json', successful)
    work = store.claim_ordinary(profile_id, revision, 30)
    assert work['id'] == successor
    asyncio.run(runner._execute(work, revision))
    result = store.read_ordinary(successor)
    assert result['state'] == 'succeeded', result['error_code']
    assert result['ai_assessment'] and result['result_projection']
    assert len(calls) == len(result['ai_evidence']) == 2
    assert all(item['state'] == 'completed' and item['result'] for item in result['ai_evidence'])
    assert not ({item['id'] for item in original['ai_evidence']} & {item['id'] for item in result['ai_evidence']})
    after = store.read_ordinary(source)
    for key in original.keys() - {'retry_successor_id', 'successor_run_id'}:
        assert after[key] == original[key]
    with store.engine.connect() as db:
        assert db.execute(text('SELECT policy_snapshot FROM analysis_runs WHERE id=:id'), {'id': source}).scalar_one() == original_policy
