import logging
from types import SimpleNamespace
import uuid

import pytest

from app.application import submission


@pytest.mark.parametrize('series', [False, True])
@pytest.mark.parametrize('stage', ['validation', 'registration', 'publication'])
def test_private_admission_stage_preserves_error_contract_without_payload(monkeypatch, caplog, series, stage):
    secret = 'secret-request-data-must-not-be-logged'
    context = {}
    image = b'\xff\xd8\xff-test'

    def fail(*args, **kwargs):
        raise OSError(secret)

    monkeypatch.setattr(submission, 'validate_request', fail if stage == 'validation' else
                        lambda body: (image, context, [], 'hash'))
    monkeypatch.setattr(submission, 'validate_images', fail if stage == 'validation' else
                        lambda body, series: ([image, image], context, [], 'hash'))
    monkeypatch.setattr(submission, 'recover_provider_mismatch', lambda *args: None)
    failures = []
    store = SimpleNamespace(begin_submission=fail if stage == 'registration' else
                            lambda *args: ('created', None, uuid.uuid4(), None),
                            fail_submission=lambda key, code: failures.append(code))
    artifacts = SimpleNamespace(upload_temporary=fail)
    action = submission.submit_series if series else submission.submit
    with caplog.at_level(logging.ERROR, logger=submission.__name__):
        with pytest.raises(submission.SubmissionError if stage == 'publication' else OSError):
            action(store, artifacts, 'key', {'intent': 'observation_only'}, uuid.uuid4(), 1, {'kind': 'deepseek'})
    assert f'stage={stage}' in caplog.text
    assert f'media={"series" if series else "single"}' in caplog.text
    assert 'exception=OSError' in caplog.text
    assert secret not in caplog.text
    assert failures == (['submission_publication_failed'] if stage == 'publication' else [])


@pytest.mark.parametrize('series', [False, True])
@pytest.mark.parametrize('stage', ['authorization', 'submission', 'readback'])
def test_http_admission_error_is_safe_and_logs_actual_stage(monkeypatch, caplog, series, stage):
    import asyncio
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    monkeypatch.setenv('AUTH_REQUIRED', 'false')
    secret = 'private-inventory-error-detail'

    def fail(*args, **kwargs):
        raise PermissionError(secret)

    app = create_app()
    app.state.readiness.ready.set()
    app.state.claim_loop = SimpleNamespace(runtime_binding=(uuid.uuid4(), 1))
    app.state.store = SimpleNamespace(require_authorized=fail if stage == 'authorization' else
                                     lambda *args: ({'kind': 'deepseek'}, 1),
                                     read_ordinary=fail)
    app.state.artifacts = SimpleNamespace()
    if stage == 'submission':
        monkeypatch.setattr(submission, 'validate_images', fail)
        monkeypatch.setattr(submission, 'validate_request', fail)
    else:
        from app import main as main_module
        monkeypatch.setattr(main_module, 'submit_series' if series else 'submit',
                            lambda *args, **kwargs: ('queued', uuid.uuid4()))

    async def request():
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            return await client.post('/runs/series' if series else '/runs/single-image',
                                     json={'intent': 'observation_only'}, headers={'Idempotency-Key': 'key'})

    with caplog.at_level(logging.ERROR):
        response = asyncio.run(request())
    assert response.status_code == 503
    assert response.json() == {'code': 'submission_unavailable'}
    assert f'stage={stage}' in caplog.text
    assert secret not in response.text + caplog.text
