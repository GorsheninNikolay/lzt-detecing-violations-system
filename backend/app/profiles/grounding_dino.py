"""Pinned, offline Grounding DINO Tiny CPU observer."""

import hashlib
import io
import json
import platform
import resource
import subprocess
import time
from importlib.metadata import version
from pathlib import Path


MODEL_ID = "IDEA-Research/grounding-dino-tiny"
MODEL_REVISION = "e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e"
PROMPTS = ("an excavator", "a dump truck")
BOX_THRESHOLD = 0.35
TEXT_THRESHOLD = 0.25
PREPROCESSING_REVISION = "grounding-dino-processor-v1"
ADAPTER_VERSION = "grounding-dino-cpu-v1"


class ObserverError(RuntimeError):
    pass


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def prepare_snapshot(snapshot_dir: Path) -> dict[str, str]:
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=MODEL_ID, revision=MODEL_REVISION, local_dir=str(snapshot_dir))
    return model_hashes(snapshot_dir)


def model_hashes(snapshot_dir: Path) -> dict[str, str]:
    files = {}
    for path in sorted(snapshot_dir.rglob("*")):
        if path.is_file() and ".cache" not in path.relative_to(snapshot_dir).parts:
            files[path.relative_to(snapshot_dir).as_posix()] = digest(path.read_bytes())
    if not files or not any(name.endswith(".safetensors") for name in files):
        raise ObserverError("model_snapshot_incomplete")
    return files


def verify_snapshot(snapshot_dir: Path, expected: dict[str, str]) -> None:
    if model_hashes(snapshot_dir) != expected:
        raise ObserverError("model_snapshot_hash_mismatch")


def draft_snapshot(lock_file: Path, fixture_manifest: dict, expected_files: dict[str, str]) -> dict:
    if not expected_files or "model.safetensors" not in expected_files:
        raise ObserverError("model_snapshot_incomplete")
    adapter_hash = digest(Path(__file__).read_bytes())
    return {
        "kind": "local_process", "adapter": {"code": "grounding_dino", "version": ADAPTER_VERSION,
            "entrypoint": "app.profiles.grounding_dino.GroundingDinoCpu", "bundle_sha256": adapter_hash},
        "requested_model_identity": {"id": MODEL_ID, "revision": MODEL_REVISION},
        "returned_model_identity": None,
        "identity_gap": "awaiting_offline_load",
        "model_files": expected_files,
        "preprocessing": PREPROCESSING_REVISION,
        "prompt": list(PROMPTS), "box_threshold": BOX_THRESHOLD, "text_threshold": TEXT_THRESHOLD,
        "taxonomy": {"an excavator": "excavator", "a dump truck": "dump_truck"},
        "observation_contract": "presence-only-v1", "outcome_contract": "observations-only-v1",
        "rights": {"model": "Apache-2.0", "fixtures": fixture_manifest["declared_license"],
            "manifest_sha256": digest(canonical_bytes(fixture_manifest))},
        "runtime": {"python": platform.python_version(), "os": platform.system(), "architecture": platform.machine(),
            "device": "cpu", "cpu_cores": 12, "memory_bytes": 36 * 1024**3, "concurrency": 1,
            "driver": "PyTorch CPU", "torch": version("torch"), "transformers": version("transformers"),
            "uv": subprocess.check_output(["uv", "--version"], text=True).strip(),
            "sdk_retries": 0, "uv_lock_sha256": digest(lock_file.read_bytes())},
    }


class GroundingDinoCpu:
    def __init__(self, snapshot_dir: Path, expected_hashes: dict[str, str]):
        import torch
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoProcessor, GroundingDinoForObjectDetection

        verify_snapshot(snapshot_dir, expected_hashes)
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise ObserverError("cpu_baseline_platform_mismatch")
        self.processor = AutoProcessor.from_pretrained(str(snapshot_dir), local_files_only=True)
        weights = load_file(str(snapshot_dir / "model.safetensors"), device="cpu")
        for key in tuple(weights):
            if key.endswith(("in_proj_weight", "in_proj_bias")):
                source = weights.pop(key)
                prefix, suffix = key.rsplit("in_proj_", 1)
                for name, value in zip(("query", "key", "value"), source.chunk(3, dim=0)):
                    weights[f"{prefix}{name}.{suffix}"] = value
        self.model = GroundingDinoForObjectDetection(AutoConfig.from_pretrained(str(snapshot_dir), local_files_only=True))
        missing, unexpected = self.model.load_state_dict(weights, strict=False)
        if unexpected and any(not key.startswith("model.text_backbone.pooler.") for key in unexpected):
            raise ObserverError("model_weight_mapping_failed")
        if any(not key.startswith(("bbox_embed.", "model.decoder.bbox_embed.")) for key in missing):
            raise ObserverError("model_weight_mapping_failed")
        self.model.to("cpu").eval()
        self.torch = torch
        self.returned_identity = f"checkpoint-sha256:{expected_hashes['model.safetensors']}"
        if str(next(self.model.parameters()).device) != "cpu":
            raise ObserverError("actual_device_mismatch")

    def observe(self, image_bytes: bytes) -> dict:
        from PIL import Image

        start = time.perf_counter()
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
        inputs = self.processor(images=image, text=[list(PROMPTS)], return_tensors="pt")
        if any(str(value.device) != "cpu" for value in inputs.values() if hasattr(value, "device")):
            raise ObserverError("actual_device_mismatch")
        with self.torch.no_grad():
            output = self.model(**inputs)
        result = self.processor.post_process_grounded_object_detection(
            output, inputs.input_ids, threshold=BOX_THRESHOLD, text_threshold=TEXT_THRESHOLD,
            target_sizes=[image.size[::-1]], text_labels=[list(PROMPTS)],
        )[0]
        labels, scores, boxes = result["text_labels"], result["scores"], result["boxes"]
        if len(labels) != len(scores) or len(labels) != len(boxes):
            raise ObserverError("observation_normalization_failed")
        detections = [
            {"label": str(label), "score": float(score), "box": [float(x) for x in box]}
            for label, score, box in zip(labels, scores, boxes)
        ]
        return {"returned_model_identity": self.returned_identity,
            "actual_device": str(next(self.model.parameters()).device),
            "latency_ms": (time.perf_counter() - start) * 1000,
            "peak_memory_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "native": {"detections": detections, "image_size": list(image.size)},
            "states": {name: "detected" if any(d["label"] == prompt for d in detections)
                else "not_detected_in_frame" for prompt, name in
                (("an excavator", "excavator"), ("a dump truck", "dump_truck"))}}
