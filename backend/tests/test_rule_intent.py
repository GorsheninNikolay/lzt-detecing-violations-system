import base64
import asyncio
import json
import hashlib
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.adapters.postgres import PostgresStore
from app.application import executor, submission
from app.application.submission import SubmissionError, validate_images
from app.domain.rule import RULE, RULE_POLICY, evaluate_rule, revisioned_snapshot
from app.main import create_app
from test_single_image import jpeg
from test_startup import database, integration


CONTEXT = {"scenario": "excavation", "observation_area": "north", "period": "2026-09-23T12:00:00+03:00"}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_CASES = json.loads((PROJECT_ROOT / "web/src/demoCases.json").read_text())["cases"]


def test_included_demo_assets_remain_excluded_from_held_out():
    from PIL import Image

    development = json.loads((PROJECT_ROOT / "backend/admission/exclusions/development_acceptance.json").read_text())
    held_out = json.loads((PROJECT_ROOT / "backend/admission/exclusions/held_out_evaluation.json").read_text())
    assert {case["sourceGroup"] for case in DEMO_CASES} == set(development["reserved_source_groups"])
    assert len(DEMO_CASES) == 2
    for case in DEMO_CASES:
        assert case["ruleRevision"] == RULE["revision"]
        assert case["sourceGroup"] not in held_out["reserved_source_groups"]
        assert len(case["frames"]) == 3
        for frame in case["frames"]:
            derived_path = PROJECT_ROOT / "web/public" / frame["path"].lstrip("/")
            derived = derived_path.read_bytes()
            assert hashlib.sha256(derived).hexdigest() == frame["sha256"]
            assert any(item["source_group"] == case["sourceGroup"] and
                       item["image"]["sha256"] == frame["originalSha256"] and
                       item["derived_image"]["sha256"] == frame["sha256"]
                       for item in development["fixtures"])
            assert all(item.get("image", {}).get("sha256") not in
                       (frame["originalSha256"], frame["sha256"]) for item in held_out["fixtures"])
            with Image.open(derived_path) as image:
                assert image.format == "JPEG" and image.width * image.height <= 40_000_000
            assert len(derived) <= 16_000_000


def test_included_demo_original_hashes_match_local_archive():
    archive_path = PROJECT_ROOT / "artifacts/dataset/Строительная_техника.zip"
    if not archive_path.exists():
        pytest.skip("Organizer archive is local and is not part of the repository")
    with zipfile.ZipFile(archive_path) as archive:
        for case in DEMO_CASES:
            assert case["sourceArchive"] == "artifacts/dataset/Строительная_техника.zip"
            for frame in case["frames"]:
                assert hashlib.sha256(archive.read(frame["sourceMember"])).hexdigest() == frame["originalSha256"]


def request(intent="rule_evaluation", stage="excavation"):
    return {"intent": intent, "stage": stage, **CONTEXT}


def test_policy_and_rule_revisions_identify_canonical_content():
    assert (revisioned_snapshot("test", {"z": {"b": 2, "a": 1}, "a": [1, 2]})["revision"] ==
            revisioned_snapshot("test", {"a": [1, 2], "z": {"a": 1, "b": 2}})["revision"])
    assert revisioned_snapshot("rule", RULE)["revision"] == RULE["revision"]
    assert revisioned_snapshot("policy", RULE_POLICY)["revision"] == RULE_POLICY["revision"]
    assert revisioned_snapshot("rule", {**RULE, "expectation": "changed"})["revision"] != RULE["revision"]
    assert revisioned_snapshot("policy", {**RULE_POLICY, "minimum_usable_same_area_frames": 4})["revision"] != RULE_POLICY["revision"]
    assert RULE["expectation"] == "Экскаватор работает постоянно, самосвалы появляются периодически."
    assert RULE["provenance"] == "demonstration rule"
    assert RULE_POLICY["minimum_usable_same_area_frames"] == 3
    assert RULE_POLICY["supported_media_types"] == ["image/jpeg"]
    assert RULE_POLICY["frame_order"] == "upload_order"
    assert RULE_POLICY["area_scope"] == "one_declared_observation_area"
    assert all(RULE_POLICY[name] is None for name in (
        "subjective_resolution_threshold", "visibility_threshold", "object_size_threshold",
        "image_quality_threshold", "cadence_threshold", "duration_threshold", "miss_rate_threshold",
        "false_detection_threshold", "stability_threshold"))


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
    ([('detected', 'not_detected_in_frame')] * 2, 2, 'insufficient_data'),
    ([('detected', 'not_detected_in_frame')] * 3, 3, 'check_requested'),
    ([('detected', 'not_detected_in_frame')] * 2 + [('detected', 'detected')], 3, 'no_check'),
    ([('not_detected_in_frame', 'detected')] * 3, 3, 'insufficient_data'),
    ([('not_detected_in_frame', 'not_detected_in_frame')] * 3, 3, 'insufficient_data'),
    ([('detected', 'not_analyzed')] * 3, 3, 'not_analyzed'),
    ([('detected', 'not_analyzed')] * 2, 2, 'not_analyzed'),
    ([('insufficient_data', 'not_analyzed')] * 3, 3, 'not_analyzed'),
    ([('detected', 'insufficient_data')] * 3, 3, 'insufficient_data'),
])
def test_rule_uses_normalized_frame_states(states, usable, outcome):
    frames = [{"input_id": str(index), "class_name": name, "state": state}
              for index, pair in enumerate(states) for name, state in zip(('excavator', 'dump_truck'), pair)]
    result = evaluate_rule(frames, [str(index) for index in range(usable)], RULE_POLICY, RULE, CONTEXT)
    assert result["outcome"] == outcome
    assert result["rule"]["revision"] == RULE["revision"]
    assert result["supporting_input_ids"] == (["0", "1", "2"] if outcome in ('check_requested', 'no_check') else [])
    if outcome == "insufficient_data" and any(state == "insufficient_data"
                                              for pair in states for state in pair):
        assert "Наблюдатель не смог оценить" in result["reason"]
        assert result["recommendation"] is None


def test_development_fixtures_cover_distinct_outcomes_without_held_out_sources():
    fixture_dir = Path(__file__).parent / "fixtures"
    manifest = json.loads((fixture_dir / "development_outcomes.json").read_text())
    held_out = json.loads((PROJECT_ROOT / "backend/admission/exclusions/held_out_evaluation.json").read_text())
    assert manifest["provenance"] == "synthetic normalized observations; no source image bytes"
    assert manifest["exclusion_tier"] == "development_acceptance" != held_out["tier"]
    groups = [case["source_group"] for case in manifest["cases"]]
    assert len(groups) == len(set(groups)) == 5
    assert not set(groups) & set(held_out["reserved_source_groups"])
    assert not set(groups) & {item["source_group"] for item in held_out["fixtures"]}
    assert {case["expected_outcome"] for case in manifest["cases"]} == {
        "observations_only", "no_check", "check_requested", "insufficient_data", "not_analyzed"}
    for case in manifest["cases"]:
        fixture = json.loads((fixture_dir / case["fixture"]).read_text()) if "fixture" in case else case
        assert case["source_group"] == fixture["source_group"]
        if case["intent"] == "observation_only":
            assert case["expected_outcome"] == "observations_only"
            assert any(item["state"] == "insufficient_data" for item in fixture["observations"])
            continue
        result = evaluate_rule(fixture["observations"], fixture["usable_input_ids"], RULE_POLICY, RULE, CONTEXT)
        assert result["outcome"] == case["expected_outcome"]
        assert bool(result["recommendation"]) == (case["expected_outcome"] == "check_requested")


def test_positive_development_fixture_is_separate_and_requests_no_check():
    fixture = json.loads((Path(__file__).parent / "fixtures/positive_no_check.json").read_text())
    held_out = json.loads((Path(__file__).parent.parent / "admission/exclusions/held_out_evaluation.json").read_text())
    assert fixture["source_group"] not in held_out["reserved_source_groups"]
    assert all(item.get("source_group") != fixture["source_group"] for item in held_out["fixtures"])
    result = evaluate_rule(fixture["observations"], fixture["usable_input_ids"], RULE_POLICY, RULE, fixture["context"])
    assert result["outcome"] == "no_check"
    assert result["supporting_input_ids"] == ["frame-0", "frame-2"]
    assert result["recommendation"] is None


def test_persistent_non_detection_fixture_is_separate_and_requests_a_check():
    fixture = json.loads((Path(__file__).parent / "fixtures/persistent_non_detection.json").read_text())
    held_out = json.loads((Path(__file__).parent.parent / "admission/exclusions/held_out_evaluation.json").read_text())
    assert fixture["source_group"].startswith("synthetic-development-")
    assert fixture["source_group"] not in held_out["reserved_source_groups"]
    assert all(item.get("source_group") != fixture["source_group"] for item in held_out["fixtures"])
    assert fixture["context"] == CONTEXT
    result = evaluate_rule(fixture["observations"], fixture["usable_input_ids"], RULE_POLICY, RULE, fixture["context"])
    assert result == {
        "outcome": "check_requested",
        "reason": ("Есть повод проверить возможную задержку вывоза грунта: "
                   "экскаватор обнаружен хотя бы в одном пригодном кадре, самосвал не обнаружен ни в одном пригодном кадре."),
        "rule": RULE, "policy": RULE_POLICY, "context": CONTEXT,
        "supporting_input_ids": fixture["usable_input_ids"],
        "uncertainty": "Необнаружение в кадре не доказывает отсутствие техники на всей площадке.",
        "recommendation": RULE["recommendation"],
    }


def test_stricter_policy_revision_uses_its_bound_minimum_in_the_reason():
    policy = revisioned_snapshot("policy", {**RULE_POLICY, "minimum_usable_same_area_frames": 4})
    frames = [{"input_id": str(index), "class_name": name, "state": state}
              for index in range(3)
              for name, state in zip(("excavator", "dump_truck"), ("detected", "not_detected_in_frame"))]
    result = evaluate_rule(frames, ["0", "1", "2"], policy, RULE, CONTEXT)
    assert policy["revision"] != RULE_POLICY["revision"]
    assert result["policy"]["revision"] == policy["revision"]
    assert result["outcome"] == "insufficient_data"
    assert "минимум 4 пригодных кадров" in result["reason"]
    assert result["recommendation"] is None


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
            VALUES (:id, :parent, 'admitted', :hash, CAST(:snapshot AS jsonb), :audit)"""),
            {"id": profile, "parent": parent, "hash": uuid.uuid4().hex,
             "snapshot": json.dumps(snapshot), "audit": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO profile_authorizations
            (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
            SELECT :id, 1, 'enabled', 'test', audit_hash, false FROM observer_profiles WHERE id = :id"""), {"id": profile})

    with pytest.raises(DBAPIError, match="analysis_run_rule_binding_incomplete"):
        with store.engine.begin() as connection:
            connection.execute(text("""INSERT INTO analysis_runs (id, state, purpose, analysis_intent, stage_key)
                VALUES (:id, 'queued', 'ordinary', 'rule_evaluation', 'excavation')"""), {"id": uuid.uuid4()})

    def insert_binding(policy, bound_snapshot=snapshot):
        run_id = uuid.uuid4()
        with store.engine.begin() as connection:
            connection.execute(text("""INSERT INTO analysis_runs
                (id, state, purpose, profile_id, authorization_revision, binding_kind, profile_snapshot,
                 request_context, policy_snapshot, rule_snapshot, analysis_intent, stage_key,
                 taxonomy_snapshot, requested_classes)
                VALUES (:id, 'queued', 'ordinary', :profile, 1, 'admitted_profile',
                    CAST(:profile_snapshot AS jsonb), CAST(:context AS jsonb), CAST(:policy AS jsonb),
                    CAST(:rule AS jsonb), 'rule_evaluation', 'excavation',
                    CAST(:taxonomy AS jsonb), CAST(:classes AS jsonb))"""), {
                        "id": run_id, "profile": profile,
                        "profile_snapshot": json.dumps(bound_snapshot),
                        "context": json.dumps(CONTEXT),
                        "policy": json.dumps({"intent": "rule_evaluation", **policy}),
                        "rule": json.dumps(RULE),
                        "taxonomy": json.dumps({"portable_classes": ["excavator", "dump_truck"],
                                               "revision": "presence-only-v1"}),
                        "classes": json.dumps(["excavator", "dump_truck"]),
                    })
        return run_id

    stricter_policy = revisioned_snapshot("policy", {**RULE_POLICY, "minimum_usable_same_area_frames": 4})
    stricter_run = insert_binding(stricter_policy)
    with store.engine.begin() as connection:
        connection.execute(text("DELETE FROM analysis_runs WHERE id = :run"), {"run": stricter_run})
    with pytest.raises(DBAPIError, match="analysis_run_rule_binding_incomplete"):
        insert_binding(revisioned_snapshot("policy", {**RULE_POLICY, "minimum_usable_same_area_frames": 2}))
    with pytest.raises(DBAPIError, match="analysis_run_rule_binding_incomplete"):
        insert_binding(revisioned_snapshot("policy", {**RULE_POLICY, "admission": "all_images"}))
    with pytest.raises(DBAPIError, match="analysis_run_rule_binding_incomplete"):
        insert_binding(RULE_POLICY, {**snapshot, "runtime": {"batch_timeout_seconds": 1}})

    detected_dump = False
    active_demo = None
    observed_index = 0

    def observed(*_):
        nonlocal observed_index
        index = observed_index
        observed_index += 1
        excavator_seen = index == 0 or bool(active_demo)
        dump_seen = index in (0, 1) if active_demo and active_demo["id"] == "truck" else detected_dump and index == 2
        detections = []
        if excavator_seen:
            detections.append({"label": "an excavator", "score": 0.8, "box": [1, 2, 3, 4]})
        if dump_seen:
            detections.append({"label": "a dump truck", "score": 0.8, "box": [1, 2, 3, 4]})
        return {"states": {"excavator": "detected" if excavator_seen else "not_detected_in_frame",
                           "dump_truck": "detected" if dump_seen else "not_detected_in_frame"},
                "returned_model_identity": f"checkpoint-sha256:{'a' * 64}", "actual_device": "cpu",
                "latency_ms": 1.0, "peak_memory_bytes": 1024,
                "native": {"detections": detections,
                           "image_size": [96, 96]}}

    monkeypatch.setattr(executor, "_observe_bounded", observed)
    loop = executor.ClaimLoop()
    loop.store, loop.artifacts, loop.snapshot_dir = store, artifacts, "unused"

    async def run_case(count, expected, dump=False, demo=None, requested=None, unassessable=False,
                       intent="rule_evaluation"):
        nonlocal detected_dump, observed_index, active_demo
        detected_dump = dump
        active_demo = demo
        observed_index = 0
        images = ([(PROJECT_ROOT / "web/public" / frame["path"].lstrip("/")).read_bytes()
                   for frame in demo["frames"]] if demo else
                  [jpeg((10 + index, 20, 30)) for index in range(count)])
        monkeypatch.setattr(executor, "_unassessable", lambda image: unassessable and image == images[0])
        context = ({"scenario": demo["scenario"], "observation_area": demo["observationArea"],
                    "period": demo["period"] + ":00+03:00"} if demo else CONTEXT)
        body = {**request(intent=intent), **context,
                **({"requested_classes": requested} if requested else {}),
                **({"image_base64": base64.b64encode(images[0]).decode()} if count == 1
                               else {"images_base64": [base64.b64encode(image).decode() for image in images]})}
        submit = submission.submit if count == 1 else submission.submit_series
        _, run_id = submit(store, artifacts, uuid.uuid4().hex, body, profile, 1, snapshot)
        queued = store.read_ordinary(run_id)
        assert queued["intent"] == intent
        if intent == "rule_evaluation":
            assert queued["rule_snapshot"]["revision"] == RULE["revision"]
            assert queued["policy_snapshot"] == {"intent": "rule_evaluation", **RULE_POLICY}
            assert queued["rule_snapshot"] == RULE
        assert queued["taxonomy_snapshot"] == {"portable_classes": ["excavator", "dump_truck"], "revision": "presence-only-v1"}
        assert queued["profile_id"] == str(profile)
        assert queued["authorization_revision"] == 1
        assert queued["binding_kind"] == "admitted_profile"
        assert queued["profile_snapshot"] == snapshot
        assert queued["context"] == context
        assert queued["requested_classes"] == (requested or ["excavator", "dump_truck"])
        assert [item["ordinal"] for item in queued["inputs"]] == list(range(count))
        if demo:
            assert [item["sha256"] for item in queued["inputs"]] == [frame["sha256"] for frame in demo["frames"]]
        with store.engine.connect() as connection:
            assert connection.execute(text("SELECT context FROM run_inputs WHERE run_id = :run ORDER BY ordinal"),
                                      {"run": run_id}).scalars().all() == [context] * count
        await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
        done = store.read_ordinary(run_id)
        assert done["state"] == "succeeded" and done["outcome"] == expected, done["error_code"]
        assert done["stages"][4]["state"] == ("succeeded" if intent == "rule_evaluation" else "skipped")
        assert bool(done["result_projection"].get("recommendation")) == (expected == "check_requested")
        assert done["result_projection"]["series"]["input_order"] == [item["input_id"] for item in done["inputs"]]
        if expected in ("insufficient_data", "not_analyzed", "observations_only"):
            if intent == "rule_evaluation":
                assert done["result_projection"]["supporting_input_ids"] == []
            assert done["result_projection"]["frames"] == [
                {key: item[key] for key in ("input_id", "ordinal", "class_name", "state", "reason", "source_artifact_id", "invocation_id")}
                for item in done["observations"]]
            if unassessable:
                affected = [item for item in done["result_projection"]["frames"] if item["input_id"] == done["inputs"][0]["input_id"]]
                assert all(item["state"] == "insufficient_data" and item["reason"] == "frame_unassessable" for item in affected)
                if intent == "rule_evaluation":
                    assert done["inputs"][0]["input_id"] in done["result_projection"]["reason"]
            if requested:
                unsupported = [item for item in done["result_projection"]["frames"] if item["class_name"] == "crane"]
                assert len(unsupported) == count
                assert all(item["state"] == "not_analyzed" and item["reason"] == "unsupported_class" and
                           item["source_artifact_id"] == done["inputs"][item["ordinal"]]["artifact_id"] for item in unsupported)
                if intent == "rule_evaluation":
                    assert all(item["input_id"] in done["result_projection"]["reason"] for item in unsupported)
        if expected == "check_requested":
            projection = done["result_projection"]
            input_ids = [item["input_id"] for item in done["inputs"]]
            assert projection["outcome"] == "check_requested"
            assert projection["supporting_input_ids"] == input_ids
            assert projection["series"]["usable_input_ids"] == input_ids
            assert projection["series"]["input_order"] == input_ids
            assert projection["series"]["declared_observation_area"] == context["observation_area"]
            assert projection["series"]["excavator_supporting_input_ids"] == (input_ids if demo else input_ids[:1])
            assert projection["series"]["dump_truck_persistence_input_ids"] == input_ids
            assert projection["context"] == context
            assert projection["rule"] == queued["rule_snapshot"] == RULE
            assert projection["rule"]["expectation"] == RULE["expectation"]
            assert projection["rule"]["provenance"] == "demonstration rule"
            assert projection["policy"] == queued["policy_snapshot"]
            assert projection["reason"] == ("Есть повод проверить возможную задержку вывоза грунта: "
                                            "экскаватор обнаружен хотя бы в одном пригодном кадре, самосвал не обнаружен ни в одном пригодном кадре.")
            assert projection["uncertainty"] == "Необнаружение в кадре не доказывает отсутствие техники на всей площадке."
            assert projection["recommendation"] == RULE["recommendation"]
            assert projection["frames"] == [{key: item[key] for key in ("input_id", "ordinal", "class_name", "state", "reason", "source_artifact_id", "invocation_id")}
                                            for item in done["observations"]]
            assert [(item["input_id"], item["class_name"], item["state"]) for item in projection["frames"]] == [
                (input_id, class_name, state) for input_id in input_ids for class_name, state in
                (("dump_truck", "not_detected_in_frame"),
                 ("excavator", "detected" if demo or input_id == input_ids[0] else "not_detected_in_frame"))
            ]
            assert all(frame["source_artifact_id"] == next(item["artifact_id"] for item in done["inputs"]
                                                            if item["input_id"] == frame["input_id"])
                       for frame in projection["frames"])
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": run_id}).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run AND outcome = 'check_requested'"),
                                          {"run": run_id}).scalar_one() == 1
        if expected == "no_check":
            projection = done["result_projection"]
            assert projection["outcome"] == "no_check"
            assert projection["recommendation"] is None
            assert projection["rule"]["revision"] == queued["rule_snapshot"]["revision"]
            assert projection["policy"]["revision"] == queued["policy_snapshot"]["revision"]
            assert projection["context"] == context
            assert projection["series"]["usable_input_ids"] == [item["input_id"] for item in done["inputs"]]
            assert projection["supporting_input_ids"] == ([item["input_id"] for item in done["inputs"]] if demo else
                                                        [done["inputs"][0]["input_id"], done["inputs"][2]["input_id"]])
            assert projection["frames"] == [{key: item[key] for key in ("input_id", "ordinal", "class_name", "state", "reason", "source_artifact_id", "invocation_id")}
                                            for item in done["observations"]]
            assert all(frame["source_artifact_id"] == next(item["artifact_id"] for item in done["inputs"]
                                                            if item["input_id"] == frame["input_id"])
                       for frame in projection["frames"])
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": run_id}).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run AND outcome = 'check_requested'"),
                                          {"run": run_id}).scalar_one() == 0
        return run_id

    asyncio.run(run_case(1, "insufficient_data"))
    asyncio.run(run_case(2, "insufficient_data"))
    asyncio.run(run_case(3, "insufficient_data", unassessable=True))
    asyncio.run(run_case(1, "observations_only", unassessable=True, intent="observation_only"))
    asyncio.run(run_case(2, "not_analyzed", requested=["excavator", "dump_truck", "crane"]))
    asyncio.run(run_case(3, "not_analyzed", requested=["excavator", "dump_truck", "crane"]))
    asyncio.run(run_case(3, "observations_only", requested=["excavator", "dump_truck", "crane"], intent="observation_only"))
    run_id = asyncio.run(run_case(3, "check_requested"))
    asyncio.run(run_case(3, "no_check", dump=True))
    for demo in DEMO_CASES:
        asyncio.run(run_case(3, demo["expectedOutcome"], demo=demo))

    updates = [
        ("request_context", json.dumps({**CONTEXT, "scenario": "changed"}), "jsonb"),
        ("profile_id", str(uuid.uuid4()), "uuid"),
        ("authorization_revision", 2, None),
        ("binding_kind", "changed", None),
        ("profile_snapshot", json.dumps({**snapshot, "changed": True}), "jsonb"),
        ("policy_snapshot", json.dumps({**RULE_POLICY, "minimum_usable_same_area_frames": 4}), "jsonb"),
        ("rule_snapshot", json.dumps({**RULE, "expectation": "changed"}), "jsonb"),
        ("analysis_intent", "observation_only", None),
        ("stage_key", "other", None),
        ("taxonomy_snapshot", json.dumps({"portable_classes": ["excavator"], "revision": "changed"}), "jsonb"),
        ("requested_classes", json.dumps(["excavator"]), "jsonb"),
    ]
    for column, value, type_ in updates:
        cast = f"CAST(:value AS {type_})" if type_ else ":value"
        with pytest.raises(DBAPIError, match="analysis_run_binding_immutable"):
            with store.engine.begin() as connection:
                connection.execute(text(f"UPDATE analysis_runs SET {column} = {cast} WHERE id = :run"),
                                   {"value": value, "run": run_id})
    manifest_before = store.read_ordinary(run_id)["inputs"]
    manifest_mutations = [
        "UPDATE run_inputs SET ordinal = ordinal + 10 WHERE run_id = :run AND ordinal = 0",
        "DELETE FROM run_inputs WHERE run_id = :run AND ordinal = 0",
        """INSERT INTO run_inputs (run_id, ordinal, sha256, size, context, artifact_id)
            VALUES (:run, 99, :hash, 1, CAST(:context AS jsonb), :artifact)""",
    ]
    for mutation in manifest_mutations:
        with pytest.raises(DBAPIError, match="accepted_run_manifest_immutable"):
            with store.engine.begin() as connection:
                connection.execute(text(mutation), {
                    "run": run_id, "hash": "b" * 64,
                    "context": json.dumps(CONTEXT), "artifact": uuid.uuid4(),
                })
    retained = store.read_ordinary(run_id)
    assert retained["inputs"] == manifest_before
    assert retained["context"] == CONTEXT
    assert retained["policy_snapshot"] == {"intent": "rule_evaluation", **RULE_POLICY}
    assert retained["rule_snapshot"] == RULE
