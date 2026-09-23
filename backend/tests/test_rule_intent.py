import base64
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.adapters.postgres import PostgresStore
from app.application import executor, submission
from app.application.submission import SubmissionError, validate_images
from app.domain.rule import RULE, RULE_POLICY, evaluate_rule
from app.main import create_app
from test_single_image import jpeg
from test_startup import database, integration


CONTEXT = {"scenario": "excavation", "observation_area": "north", "period": "2026-09-23T12:00:00+03:00"}


def request(intent="rule_evaluation", stage="excavation"):
    return {"intent": intent, "stage": stage, **CONTEXT}


def test_intent_is_part_of_request_identity_and_rule_scope():
    from io import BytesIO
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (2, 2)).save(output, "JPEG")
    image = base64.b64encode(output.getvalue()).decode()
    rule = {**request(), "image_base64": image}
    observation = {**rule, "intent": "observation_only"}
    assert validate_images(rule, False)[3] != validate_images(observation, False)[3]
    with pytest.raises(SubmissionError, match="rule_not_applicable"):
        validate_images({**rule, "stage": "other"}, False)
    assert validate_images({**observation, "stage": "other"}, False)


@pytest.mark.parametrize("requested", [["excavator"], ["dump_truck"], ["crane", "excavator"]])
def test_rule_requires_both_informative_classes(requested):
    with pytest.raises(SubmissionError, match="invalid_requested_classes"):
        validate_images({**request(), "requested_classes": requested}, False)


@pytest.mark.parametrize("states,usable,outcome", [
    ([('detected', 'not_detected_in_frame')], 1, 'insufficient_data'),
    ([('detected', 'not_detected_in_frame')] * 3, 3, 'check_requested'),
    ([('detected', 'not_detected_in_frame')] * 2 + [('detected', 'detected')], 3, 'no_check'),
    ([('not_detected_in_frame', 'detected')] * 3, 3, 'insufficient_data'),
    ([('not_detected_in_frame', 'not_detected_in_frame')] * 3, 3, 'insufficient_data'),
    ([('detected', 'not_analyzed')] * 3, 3, 'not_analyzed'),
    ([('detected', 'insufficient_data')] * 3, 3, 'insufficient_data'),
])
def test_rule_uses_normalized_frame_states(states, usable, outcome):
    frames = [{"input_id": str(index), "class_name": name, "state": state}
              for index, pair in enumerate(states) for name, state in zip(('excavator', 'dump_truck'), pair)]
    result = evaluate_rule(frames, [str(index) for index in range(usable)], RULE_POLICY, RULE, CONTEXT)
    assert result["outcome"] == outcome
    assert result["rule"]["revision"] == RULE["revision"]
    assert result["supporting_input_ids"] == (["0", "1", "2"] if outcome == 'check_requested' else [])


def test_choices_are_served_as_authoritative_api_contract():
    async def check():
        async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as client:
            response = await client.get("/analysis-choices")
        assert response.status_code == 200
        stages = response.json()["stages"]
        assert stages[0]["id"] == "excavation" and stages[0]["rule"]["provenance"] == "demonstration rule"
        assert stages[1]["rule"] is None
    import asyncio
    asyncio.run(check())


def test_direct_rule_request_for_other_stage_is_rejected_by_api():
    from io import BytesIO
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (2, 2)).save(output, "JPEG")
    app = create_app()
    app.state.readiness.ready.set()
    app.state.claim_loop = SimpleNamespace(runtime_binding=(uuid.uuid4(), 1))
    app.state.store = SimpleNamespace(require_authorized=lambda *_: ({}, 1))
    app.state.artifacts = None

    async def check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/runs/single-image", headers={"Idempotency-Key": "rule-other"},
                json={**request(stage="other"), "image_base64": base64.b64encode(output.getvalue()).decode()})
        assert response.status_code == 400 and response.json() == {"code": "rule_not_applicable"}

    import asyncio
    asyncio.run(check())


def test_rule_intent_survives_publication_execution_and_readback(integration, monkeypatch):
    _, store, artifacts = integration
    parent, profile = uuid.uuid4(), uuid.uuid4()
    snapshot = {"model_files": {"model.safetensors": "a" * 64},
                "runtime": {"per_image_timeout_seconds": 2, "batch_timeout_seconds": 600}}
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO observer_profiles (id, status, profile_hash, snapshot) VALUES (:id, 'draft', :hash, '{}'::jsonb)"),
                           {"id": parent, "hash": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
            VALUES (:id, :parent, 'admitted', :hash, '{}'::jsonb, :audit)"""),
            {"id": profile, "parent": parent, "hash": uuid.uuid4().hex, "audit": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO profile_authorizations
            (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
            SELECT :id, 1, 'enabled', 'test', audit_hash, false FROM observer_profiles WHERE id = :id"""), {"id": profile})

    detected_dump = False

    def observed(*_):
        detections = [{"label": "an excavator", "score": 0.8, "box": [1, 2, 3, 4]}]
        if detected_dump:
            detections.append({"label": "a dump truck", "score": 0.8, "box": [1, 2, 3, 4]})
        return {"states": {"excavator": "detected", "dump_truck": "detected" if detected_dump else "not_detected_in_frame"},
                "returned_model_identity": f"checkpoint-sha256:{'a' * 64}", "actual_device": "cpu",
                "latency_ms": 1.0, "peak_memory_bytes": 1024,
                "native": {"detections": detections,
                           "image_size": [96, 96]}}

    monkeypatch.setattr(executor, "_observe_bounded", observed)
    loop = executor.ClaimLoop()
    loop.store, loop.artifacts, loop.snapshot_dir = store, artifacts, "unused"

    async def run_case(count, expected, dump=False):
        nonlocal detected_dump
        detected_dump = dump
        images = [jpeg((10 + index, 20, 30)) for index in range(count)]
        body = {**request(), **({"image_base64": base64.b64encode(images[0]).decode()} if count == 1
                               else {"images_base64": [base64.b64encode(image).decode() for image in images]})}
        submit = submission.submit if count == 1 else submission.submit_series
        _, run_id = submit(store, artifacts, uuid.uuid4().hex, body, profile, 1, snapshot)
        queued = store.read_ordinary(run_id)
        assert queued["intent"] == "rule_evaluation"
        assert queued["rule_snapshot"]["revision"] == RULE["revision"]
        await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
        done = store.read_ordinary(run_id)
        assert done["state"] == "succeeded" and done["outcome"] == expected, done["error_code"]
        assert done["stages"][4]["state"] == "succeeded"
        assert bool(done["result_projection"]["recommendation"]) == (expected == "check_requested")
        if expected == "no_check":
            assert done["result_projection"]["outcome"] == "no_check"
            assert done["result_projection"]["recommendation"] is None

    asyncio.run(run_case(1, "insufficient_data"))
    asyncio.run(run_case(2, "insufficient_data"))
    asyncio.run(run_case(3, "check_requested"))
    asyncio.run(run_case(3, "no_check", dump=True))
