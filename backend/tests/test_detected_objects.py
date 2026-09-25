from app.domain.observations import normalized_objects, stage_hypotheses
from app.profiles.grounding_dino_v2 import EQUIPMENT_PROMPTS, separate_overlapping_equipment
from app.profiles import grounding_dino
from pathlib import Path
import hashlib


def test_legacy_admitted_adapter_bytes_remain_bound():
    assert hashlib.sha256(Path(grounding_dino.__file__).read_bytes()).hexdigest() == (
        "9dae8b105388425cab01a701cdf5e3e8d16b683063e80816b69b2becbc29b431")


def test_normalized_boxes_preserve_multiple_instances_and_class_identity():
    native = {"image_size": [200, 100], "detections": [
        {"label": "a dump truck", "score": .8, "box": [10, 20, 60, 80]},
        {"label": "a dump truck", "score": .6, "box": [100, 10, 180, 90]},
        {"label": "a cargo truck", "score": .7, "box": [0, 0, 40, 50]},
    ]}
    result = normalized_objects(native, EQUIPMENT_PROMPTS)
    assert [item["class_name"] for item in result] == ["dump_truck", "dump_truck", "truck"]
    assert result[0]["box"] == [.05, .2, .3, .8]
    assert result[1]["box"] == [.5, .1, .9, .9]


def test_generic_truck_does_not_double_count_same_dump_truck():
    detections = [
        {"label": "a dump truck", "score": .8, "box": [0, 0, 100, 100]},
        {"label": "a cargo truck", "score": .78, "box": [1, 1, 99, 99]},
        {"label": "a cargo truck", "score": .7, "box": [150, 0, 250, 100]},
    ]
    assert [item["label"] for item in separate_overlapping_equipment(detections)] == [
        "a dump truck", "a cargo truck"]


def test_stage_hypothesis_needs_equipment_and_scene_in_same_frame():
    objects = [{"input_id": "first", "class_name": "excavator"}]
    features = [{"input_id": "second", "feature_name": "excavation_or_trench"}]
    assert stage_hypotheses(objects, features) == []
    features[0]["input_id"] = "first"
    assert stage_hypotheses(objects, features)[0]["stage"] == "excavation"


def test_legacy_box_rotates_with_exif_orientation():
    native = {"image_size": [200, 100], "detections": [
        {"label": "an excavator", "score": .9, "box": [0, 0, 100, 50]}]}
    [rotated] = normalized_objects(native, {"excavator": "an excavator"}, orientation=6)
    assert rotated["image_size"] == [100, 200]
    assert rotated["box"] == [.5, 0, 1, .5]
