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
    assert signals == [{"kind": "expected_equipment_missing", "entry_id": "a",
                        "class_name": "excavator",
                        "reason": "Expected equipment was not detected in the assessable series."}]


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
    assert compare_equipment([entry], times, missing, frames, set()) == []
    assert compare_equipment([{**entry, "stage_key": "excavation"}], times, missing, frames, {machine}) == []
    detected = [{**missing[0], "state": "detected"}, *missing[1:]]
    assert compare_equipment([entry], times, detected, frames, {machine}) == []


def test_workspace_trio_is_independent_of_optional_plan_and_hash_bound():
    buffer = io.BytesIO()
    Image.new('RGB', (2, 2)).save(buffer, format='PNG')
    body = {'intent': 'observation_only', 'scenario': 'site', 'observation_area': 'main',
            'period': '2026-09-26T12:00:00+03:00', 'image_base64': base64.b64encode(buffer.getvalue()).decode(),
            'project_id': str(uuid.uuid4()), 'zone_id': str(uuid.uuid4()),
            'capture_times': ['2026-09-26T12:00:00+03:00']}
    _, context, _, identity = validate_images(body, False)
    assert context['project_id'] == body['project_id'] and 'plan_revision_id' not in context
    assert validate_images({**body, 'project_id': str(uuid.uuid4())}, False)[3] != identity
    assert validate_images({**body, 'plan_revision_id': str(uuid.uuid4())}, False)[3] != identity
    for missing in ('project_id', 'zone_id', 'capture_times'):
        with pytest.raises(SubmissionError, match='invalid_plan_binding'):
            validate_images({key: value for key, value in body.items() if key != missing}, False)
    with pytest.raises(SubmissionError, match='invalid_plan_binding'):
        validate_images({**body, 'capture_times': ['2026-09-26T12:00:00']}, False)


def test_foreign_workspace_is_rejected_before_publication():
    from app.application.submission import submit
    from app.adapters.postgres import AdmissionStoreError
    from unittest.mock import Mock
    buffer = io.BytesIO()
    Image.new('RGB', (2, 2)).save(buffer, format='PNG')
    body = {'intent': 'observation_only', 'scenario': 'site', 'observation_area': 'main',
            'period': '2026-09-26T12:00:00+03:00', 'image_base64': base64.b64encode(buffer.getvalue()).decode(),
            'project_id': str(uuid.uuid4()), 'zone_id': str(uuid.uuid4()),
            'capture_times': ['2026-09-26T12:00:00+03:00']}
    store, artifacts = Mock(), Mock()
    store.validate_plan_binding.side_effect = AdmissionStoreError('invalid_plan_binding')
    with pytest.raises(SubmissionError, match='invalid_plan_binding'):
        submit(store, artifacts, 'workspace-invalid', body, uuid.uuid4(), 1, {})
    store.begin_submission.assert_not_called()
    assert artifacts.mock_calls == []
