"""Make an unreviewed annotation queue from the organizer PNG archive."""

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageOps

from app.domain.observations import normalized_objects, scene_features, stage_hypotheses
from app.profiles.grounding_dino_v2 import (
    EQUIPMENT_PROMPTS, SCENE_PROMPTS, GroundingDinoCpuV2, bundle_hash,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "artifacts/dataset/Строительная_техника.zip"
OUTPUT = ROOT / "evaluation/expansion/draft-annotations.json"


def build(snapshot_dir: Path | None) -> dict:
    if snapshot_dir is not None:
        raise ValueError("profile_retired")
    archive_hash = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    hashes = json.loads((ROOT / "backend/admission/model-files.json").read_text())
    observer = None
    images = []
    with ZipFile(ARCHIVE) as archive:
        names = sorted((name for name in archive.namelist() if re.search(r"Screenshot_\d+\.png$", name)),
                       key=lambda name: int(re.search(r"Screenshot_(\d+)\.png$", name).group(1)))
        if len(names) != 100:
            raise ValueError("expected_100_png_sources")
        for index, name in enumerate(names, 1):
            payload = archive.read(name)
            with Image.open(io.BytesIO(payload)) as source:
                if source.format != "PNG":
                    raise ValueError("non_png_source")
                image_size = list(ImageOps.exif_transpose(source).size)
            entry = {"id": f"organizer-png-{index:03d}", "archive_member": name,
                     "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
                     "oriented_image_size": image_size, "source_site_camera_sequence_group": None,
                     "capture_at": None, "review_state": "unreviewed",
                     "equipment_candidates": [], "scene_candidates": [], "stage_candidates": []}
            if observer:
                result = observer.observe(payload)
                entry["equipment_candidates"] = normalized_objects(result["native"], EQUIPMENT_PROMPTS)
                entry["scene_candidates"] = scene_features(result["native"], SCENE_PROMPTS)
                entry["stage_candidates"] = stage_hypotheses(
                    [{**item, "input_id": entry["id"]} for item in entry["equipment_candidates"]],
                    [{**item, "input_id": entry["id"]} for item in entry["scene_candidates"]])
            images.append(entry)
            if index % 10 == 0:
                print(f"processed {index}/100", flush=True)
    return {"schema_revision": "expansion-annotation-queue-v1", "status": "machine_candidates_not_ground_truth",
            "archive_sha256": archive_hash, "model_file_sha256": hashes["model.safetensors"] if observer else None,
            "adapter_bundle_sha256": bundle_hash() if observer else None,
            "equipment_classes": list(EQUIPMENT_PROMPTS), "scene_features": list(SCENE_PROMPTS),
            "split": None, "split_reason": "Site/camera/series provenance is unknown; no independent evaluation split is justified.",
            "images": images}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-dir", type=Path, help="Verified offline model directory; omit for metadata only")
    args = parser.parse_args()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = build(args.snapshot_dir)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
