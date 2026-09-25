"""Experimental eight-class observer; requires a separate admission corpus."""

import io
import hashlib
import resource
import time
from pathlib import Path

from PIL import Image, ImageOps

from app.profiles.grounding_dino import (
    BOX_THRESHOLD, TEXT_THRESHOLD, GroundingDinoCpu, ObserverError,
)
from app.profiles import grounding_dino


EQUIPMENT_PROMPTS = {
    "excavator": "an excavator",
    "dump_truck": "a dump truck",
    "road_roller": "a road roller",
    "truck_mounted_crane": "a truck mounted crane",
    "concrete_mixer_truck": "a concrete mixer truck",
    "bulldozer": "a bulldozer",
    "truck": "a cargo truck",
    "mobile_crane": "a mobile crane",
}
SCENE_PROMPTS = {
    "excavation_or_trench": "an excavation trench",
    "formwork": "concrete formwork",
    "rebar": "reinforcement bars",
    "concrete_surface": "a concrete structure",
    "road_base_or_surface": "a road surface under construction",
}


def bundle_hash() -> str:
    return hashlib.sha256(Path(grounding_dino.__file__).read_bytes() + Path(__file__).read_bytes()).hexdigest()


def separate_overlapping_equipment(detections: list[dict]) -> list[dict]:
    conflicting = (("a dump truck", "a cargo truck"),
                   ("a truck mounted crane", "a mobile crane"))

    def overlap(first: list[float], second: list[float]) -> float:
        left, top = max(first[0], second[0]), max(first[1], second[1])
        right, bottom = min(first[2], second[2]), min(first[3], second[3])
        intersection = max(0, right - left) * max(0, bottom - top)
        a = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
        b = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
        return intersection / (a + b - intersection) if a + b > intersection else 0

    suppressed = set()
    for specific, other in conflicting:
        for i, first in enumerate(detections):
            if first["label"] != specific or i in suppressed:
                continue
            for j, second in enumerate(detections):
                if second["label"] != other or j in suppressed or overlap(first["box"], second["box"]) < .75:
                    continue
                suppressed.add(i if second["score"] > first["score"] + .1 else j)
    return [item for index, item in enumerate(detections) if index not in suppressed]


class GroundingDinoCpuV2(GroundingDinoCpu):
    def observe(self, image_bytes: bytes) -> dict:
        start = time.perf_counter()
        all_prompts = list(EQUIPMENT_PROMPTS.values()) + list(SCENE_PROMPTS.values())
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        inputs = self.processor(images=image, text=[all_prompts], return_tensors="pt")
        if any(str(value.device) != "cpu" for value in inputs.values() if hasattr(value, "device")):
            raise ObserverError("actual_device_mismatch")
        with self.torch.no_grad():
            output = self.model(**inputs)
        result = self.processor.post_process_grounded_object_detection(
            output, inputs.input_ids, threshold=BOX_THRESHOLD, text_threshold=TEXT_THRESHOLD,
            target_sizes=[image.size[::-1]], text_labels=[all_prompts],
        )[0]
        labels, scores, boxes = result["text_labels"], result["scores"], result["boxes"]
        if len(labels) != len(scores) or len(labels) != len(boxes):
            raise ObserverError("observation_normalization_failed")
        detections = separate_overlapping_equipment([
            {"label": str(label), "score": float(score), "box": [float(x) for x in box]}
            for label, score, box in zip(labels, scores, boxes)
        ])
        return {"returned_model_identity": self.returned_identity,
            "actual_device": str(next(self.model.parameters()).device),
            "latency_ms": (time.perf_counter() - start) * 1000,
            "peak_memory_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "native": {"detections": detections, "image_size": list(image.size)},
            "states": {name: "detected" if any(d["label"] == prompt for d in detections)
                else "not_detected_in_frame" for name, prompt in EQUIPMENT_PROMPTS.items()}}
