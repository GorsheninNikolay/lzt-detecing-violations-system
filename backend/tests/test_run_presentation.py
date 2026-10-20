import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.application.run_presentation import summary_snapshot
from app.main import create_app


def test_summary_retains_results_grounds_and_original_audit_without_repeating_images(monkeypatch):
    monkeypatch.setenv('AUTH_REQUIRED', 'false')
    identifier = str(uuid4())
    snapshot = {'run_id': identifier, 'purpose': 'ordinary', 'state': 'failed',
                'error_code': 'deepseek_response_invalid', 'retry_successor_id': None,
                'inputs': [{'input_id': 'frame', 'artifact_id': 'photo', 'sha256': 'source'}],
                'objects': [{'class_name': 'excavator'}], 'ai_assessment': None,
                'ai_evidence': [{'id': 'call', 'kind': 'assessment', 'input_id': None, 'state': 'invalid',
                                 'context': {'frames': [{'input_id': 'frame', 'observations': [{'id': 'object', 'evidence': 'Виден экскаватор'}]}]},
                                 'result': {'raw': {'output': 'immutable'}, 'request': {'image': 'x' * 3_000_000}}}]}
    original = deepcopy(snapshot)
    app = create_app()
    app.state.store = SimpleNamespace(read_ordinary=lambda _: deepcopy(snapshot))
    app.state.claim_loop = SimpleNamespace(runtime_binding=None)

    async def read():
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            full = await client.get('/runs/' + identifier)
            compact = await client.get('/runs/' + identifier, headers={'X-Response-Detail': 'summary'})
            return full, compact

    full, compact = asyncio.run(read())
    assert full.status_code == compact.status_code == 200
    assert full.json()['ai_evidence'][0]['result'] == original['ai_evidence'][0]['result']
    small = compact.json()
    assert small['ai_evidence'][0]['result'] is None
    assert small['ai_evidence'][0]['context'] == original['ai_evidence'][0]['context']
    for field in ('state', 'error_code', 'inputs', 'objects', 'ai_assessment'):
        assert small[field] == original[field]
    assert len(compact.content) < 2000
    assert len(full.content) > 3_000_000
    assert compact.headers['cache-control'] == 'no-store'
    assert compact.headers['vary'] == 'X-Response-Detail'
    assert snapshot == original


def test_summary_preserves_the_actual_conclusion_and_accepts_legacy_snapshots():
    assessment = {'summary': 'На площадке виден экскаватор.'}
    snapshot = {'state': 'succeeded', 'ai_assessment': assessment}
    assert summary_snapshot(snapshot)['ai_assessment'] == assessment
    assert 'ai_evidence' not in snapshot
