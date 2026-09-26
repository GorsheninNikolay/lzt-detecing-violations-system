from datetime import datetime, timezone

from app.domain.site_analysis import compare_equipment
from app.application.submission import validate_images, SubmissionError
from PIL import Image
import io
import base64
import uuid
import pytest


def test_parallel_work_prevents_false_unplanned_signal_and_requires_explicit_exclusion():
    start, end = datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 3, tzinfo=timezone.utc)
    entries = [
        {"id": "a", "starts_at": start, "ends_at": end, "state": "active",
         "expected_equipment": ["excavator"], "allowed_equipment": [], "excluded_equipment": ["road_roller"]},
        {"id": "b", "starts_at": start, "ends_at": end, "state": "active",
         "expected_equipment": [], "allowed_equipment": ["road_roller"], "excluded_equipment": []},
    ]
    observations = [{"input_id": str(number), "class_name": "road_roller", "state": "detected"}
                    for number in range(3)]
    observations += [{"input_id": str(number), "class_name": "excavator", "state": "not_detected_in_frame"}
                     for number in range(3)]
    signals = compare_equipment(entries, ["2026-01-02T00:00:00+00:00"] * 3,
                                observations, ["0", "1", "2"], {"road_roller", "excavator"})
    assert {signal["kind"] for signal in signals} == {"expected_equipment_missing", "insufficient_observations"}
    assert signals[0]["kind"] == "expected_equipment_missing"
    assert signals[0]["entry_id"] == "a"
    assert signals[0]["supporting_input_ids"] == ["0", "1", "2"]


def test_plan_revision_and_capture_time_are_part_of_submission_identity():
    image = Image.new("RGB", (2, 2))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    body = {"intent": "observation_only", "scenario": "site", "observation_area": "north",
            "period": "2026-01-02T00:00:00+03:00",
            "image_base64": base64.b64encode(buffer.getvalue()).decode(),
            "project_id": str(uuid.uuid4()), "zone_id": str(uuid.uuid4()),
            "plan_revision_id": str(uuid.uuid4()), "capture_times": ["2026-01-02T00:00:00+03:00"]}
    _, _, _, original = validate_images(body, False)
    assert original != validate_images({**body, "plan_revision_id": str(uuid.uuid4())}, False)[3]
    assert original != validate_images({**body, "capture_times": ["2026-01-02T00:01:00+03:00"]}, False)[3]
    with pytest.raises(SubmissionError, match="invalid_plan_binding"):
        validate_images({**body, "capture_times": []}, False)


@pytest.mark.parametrize("stage,machine", [("concreting", "concrete_mixer_truck"),
                                             ("roadwork", "road_roller")])
def test_new_scenarios_require_matching_active_operation_and_assessable_series(stage, machine):
    entry = {"id": "work", "starts_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
             "ends_at": datetime(2026, 1, 3, tzinfo=timezone.utc), "state": "active",
             "stage_key": stage, "expected_equipment": [machine], "allowed_equipment": [],
             "excluded_equipment": []}
    times = ["2026-01-02T00:00:00+00:00"] * 3
    frames = ["0", "1", "2"]
    missing = [{"input_id": item, "class_name": machine, "state": "not_detected_in_frame"}
               for item in frames]
    assert compare_equipment([entry], times, missing, frames, {machine})[0]["kind"] == "expected_equipment_missing"
    assert compare_equipment([entry], times, missing, frames[:2], {machine})[0]["kind"] == "insufficient_observations"
    assert compare_equipment([entry], times, missing, frames, set())[0]["kind"] == "insufficient_observations"
    assert compare_equipment([{**entry, "stage_key": "excavation"}], times, missing, frames, {machine})[0]["kind"] == "expected_equipment_missing"
    detected = [{**missing[0], "state": "detected"}, *missing[1:]]
    assert compare_equipment([entry], times, detected, frames, {machine}) == []


@pytest.mark.parametrize("stage", ["preparation", "demolition", "excavation", "concreting", "installation", "roadwork", "utilities", "landscaping"])
def test_each_stage_compares_only_its_relevant_frames(stage):
    times = [f"2026-01-0{day}T12:00:00+00:00" for day in [1, 1, 1, 2, 2, 2]]
    frames = [str(i) for i in range(6)]
    entry = {"id": "first", "starts_at": datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
             "ends_at": datetime.fromisoformat("2026-01-01T23:59:00+00:00"), "state": "active",
             "stage_key": stage, "expected_equipment": ["excavator"], "allowed_equipment": [], "excluded_equipment": []}
    observations = [{"input_id": key, "class_name": "excavator", "state": "not_detected_in_frame" if i < 3 else "detected"}
                    for i, key in enumerate(frames)]
    signals = compare_equipment([entry], times, observations, frames, {"excavator"}, frames)
    assert signals[0]["kind"] == "expected_equipment_missing"
    assert signals[0]["supporting_input_ids"] == frames[:3]
    assert compare_equipment([entry], times, observations[1:], frames, {"excavator"}, frames)[0]["kind"] == "insufficient_observations"
    assert compare_equipment([entry], times, observations, frames[1:], {"excavator"}, frames)[0]["kind"] == "insufficient_observations"


def test_time_specific_parallel_permission():
    start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    end = datetime.fromisoformat("2026-01-03T00:00:00+00:00")
    entries = [{"id": "a", "starts_at": start, "ends_at": end, "state": "active", "expected_equipment": [],
                "allowed_equipment": [], "excluded_equipment": ["road_roller"]},
               {"id": "b", "starts_at": start, "ends_at": datetime.fromisoformat("2026-01-02T00:00:00+00:00"),
                "state": "active", "expected_equipment": [], "allowed_equipment": ["road_roller"], "excluded_equipment": []}]
    observations = [{"input_id": key, "class_name": "road_roller", "state": "detected"} for key in ["a", "b"]]
    signals = compare_equipment(entries, ["2026-01-01T12:00:00+00:00", "2026-01-02T12:00:00+00:00"], observations,
                                ["a", "b"], {"road_roller"}, ["a", "b"])
    excluded = [signal for signal in signals if signal["kind"] == "equipment_not_planned"]
    assert len(excluded) == 1
    assert excluded[0]["supporting_input_ids"] == ["b"]


def test_three_assessable_frames_survive_fourth_unassessable():
    start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    entry = {"id": "work", "starts_at": start, "ends_at": start, "state": "active", "expected_equipment": ["excavator"],
             "allowed_equipment": [], "excluded_equipment": []}
    frames = ["0", "1", "2", "3"]
    observations = [{"input_id": key, "class_name": "excavator", "state": "not_detected_in_frame" if key != "3" else "insufficient_data"} for key in frames]
    signals = compare_equipment([entry], [start.isoformat()] * 4, observations, frames, {"excavator"}, frames)
    assert signals[0]["kind"] == "expected_equipment_missing"
    assert signals[0]["supporting_input_ids"] == frames[:3]


@pytest.mark.parametrize("stage", ["preparation", "demolition", "excavation", "concreting", "installation", "roadwork", "utilities", "landscaping"])
def test_quick_mode_confirmation_is_immutable_request_context(stage):
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2)).save(buffer, format="PNG")
    body = {"intent": "observation_only", "stage": stage, "stage_id": stage, "scenario": "site",
            "observation_area": "north", "period": "2026-01-02T00:00:00+03:00",
            "image_base64": base64.b64encode(buffer.getvalue()).decode(),
            "quick_expectations": ["excavator"], "expectations_confirmed": True}
    _, context, _, identity = validate_images(body, False)
    assert context["quick_expectations"] == ["excavator"]
    assert context["comparison_revision"] == "site-equipment-v2"
    assert validate_images({**body, "quick_expectations": ["dump_truck"]}, False)[3] != identity
    for changes in ({"expectations_confirmed": False}, {"quick_expectations": []}, {"project_id": str(uuid.uuid4())}):
        with pytest.raises(SubmissionError, match="invalid_quick_expectations"):
            validate_images({**body, **changes}, False)


@pytest.mark.parametrize("stage", [[], {}, 1, None])
def test_malformed_stage_returns_submission_error(stage):
    with pytest.raises(SubmissionError, match="invalid_stage_id"):
        validate_images({"intent": "observation_only", "stage_id": stage}, False)


@pytest.mark.parametrize("supported,state,usable", [(set(), "not_analyzed", True), ({"excavator"}, "insufficient_data", True), ({"excavator"}, None, True), ({"excavator"}, "not_detected_in_frame", False)])
def test_exclusion_only_reports_unevaluable_frame_ids(supported, state, usable):
    start = datetime.fromisoformat("2026-01-01T00:00:00Z")
    entry = {"id": "work", "starts_at": start, "ends_at": start, "state": "active",
             "expected_equipment": [], "allowed_equipment": [], "excluded_equipment": ["excavator"]}
    frames = ["a", "b", "c"]
    observations = [{"input_id": key, "class_name": "excavator", "state": state} for key in frames] if state else []
    results = compare_equipment([entry], [start.isoformat()] * 3, observations, frames if usable else [], supported, frames)
    result = next(item for item in results if item.get("class_name") == "excavator")
    assert result["kind"] == "insufficient_observations"
    assert result["supporting_input_ids"] == frames


def test_partly_uncovered_series_explicitly_reports_outside_frames():
    start = datetime.fromisoformat("2026-01-01T00:00:00Z")
    entry = {"id": "work", "starts_at": start, "ends_at": start, "state": "active",
             "expected_equipment": ["excavator"], "allowed_equipment": [], "excluded_equipment": []}
    frames = ["a", "b", "c", "outside"]
    observations = [{"input_id": key, "class_name": "excavator", "state": "detected"} for key in frames]
    results = compare_equipment([entry], [start.isoformat()] * 3 + ["2026-01-02T00:00:00Z"], observations, frames, {"excavator"}, frames)
    assert len(results) == 1
    assert results[0]["kind"] == "insufficient_observations"
    assert results[0]["supporting_input_ids"] == ["outside"]


@pytest.mark.parametrize("hashes,expected", [(["same"] * 3, "insufficient_observations"), (["a", "b", "c"], "expected_equipment_missing")])
def test_minimum_frames_counts_distinct_evidence(hashes, expected):
    start = datetime.fromisoformat("2026-01-01T00:00:00Z")
    entry = {"id": "work", "starts_at": start, "ends_at": start, "state": "active",
             "expected_equipment": ["excavator"], "allowed_equipment": [], "excluded_equipment": []}
    frames = ["a", "b", "c"]
    observations = [{"input_id": key, "class_name": "excavator", "state": "not_detected_in_frame"} for key in frames]
    result = compare_equipment([entry], [start.isoformat()] * 3, observations, frames, {"excavator"}, frames, dict(zip(frames, hashes)))
    assert result[0]["kind"] == expected
    assert result[0]["supporting_input_ids"] == frames



def test_active_work_without_confirmed_association_is_not_success():
    start = datetime.fromisoformat("2026-01-01T00:00:00Z")
    entry = {"id": "work", "starts_at": start, "ends_at": start, "state": "active",
             "expected_equipment": [], "allowed_equipment": ["excavator"], "excluded_equipment": []}
    frames = ["a", "b", "c"]
    result = compare_equipment([entry], [start.isoformat()] * 3, [], frames, {"excavator"}, frames)
    assert len(result) == 1
    assert result[0]["kind"] == "insufficient_observations"
    assert result[0]["supporting_input_ids"] == frames
