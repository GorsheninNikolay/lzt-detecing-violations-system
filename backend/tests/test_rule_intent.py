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
from PIL import Image

from app.application.submission import SubmissionError, validate_images
from app.domain.rule import RULE, RULE_POLICY, evaluate_rule, revisioned_snapshot
from app.main import create_app


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
    return {"cloud_processing_consent": True, "intent": intent, "stage": stage, **CONTEXT}


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
    bound_by_stage_id = {key: value for key, value in rule.items() if key != "stage"}
    bound_by_stage_id["stage_id"] = "excavation"
    assert validate_images(bound_by_stage_id, False)[1]["stage_id"] == "excavation"
    assert validate_images({**rule, "stage_id": "excavation"}, False)
    with pytest.raises(SubmissionError, match="invalid_stage_id"):
        validate_images({**rule, "stage": "other", "stage_id": "excavation"}, False)
    with pytest.raises(SubmissionError, match="rule_not_applicable"):
        validate_images({key: value for key, value in rule.items() if key != "stage"}, False)
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
        assert stages[0]["id"] == "excavation" and stages[0]["rule"] is None
        assert stages[1]["rule"] is None
    import asyncio
    asyncio.run(check())


def test_direct_rule_request_for_other_stage_is_rejected_by_api():
    from io import BytesIO
    from PIL import Image
    from app.profiles.deepseek import snapshot as deepseek_snapshot

    output = BytesIO()
    Image.new("RGB", (2, 2)).save(output, "JPEG")
    app = create_app()
    app.state.readiness.ready.set()
    app.state.claim_loop = SimpleNamespace(runtime_binding=(uuid.uuid4(), 1))
    app.state.store = SimpleNamespace(require_authorized=lambda *_: (deepseek_snapshot('test-folder'), 1))
    app.state.artifacts = None

    async def check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/runs/single-image", headers={"Idempotency-Key": "rule-other"},
                json={**request(stage="other"), "image_base64": base64.b64encode(output.getvalue()).decode()})
        assert response.status_code == 400 and response.json() == {"code": "rule_not_applicable"}

    import asyncio
    asyncio.run(check())
