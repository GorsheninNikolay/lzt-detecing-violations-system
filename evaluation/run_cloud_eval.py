"""Run the four checked admission frames against a separately authorized cloud model."""

import argparse
import hashlib
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from cloud_api import CloudObserverError, observe


ADMISSION = Path(__file__).resolve().parents[1] / "backend" / "admission"


def main() -> None:
    raise SystemExit("profile_retired: historical Qwen evaluation is read-only")
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", required=True)
    parser.add_argument("--allow-cloud-upload", action="store_true")
    parser.add_argument("--confirmed-grant-rub", required=True)
    parser.add_argument("--reasoning-effort", choices=("none", "medium"), default="medium")
    args = parser.parse_args()
    try:
        balance = Decimal(args.confirmed_grant_rub)
    except InvalidOperation:
        parser.error("confirmed grant balance must be a number")
    if not args.allow_cloud_upload or not balance.is_finite() or balance <= 0:
        parser.error("cloud upload permission and positive verified grant balance are required")
    api_key = os.environ.get("YC_AI_API_KEY")
    if not api_key:
        parser.error("YC_AI_API_KEY is required")
    manifest = json.loads((ADMISSION / "manifest.json").read_text())
    if manifest["declared_license"] != "CC0" or len(manifest["fixtures"]) != 4:
        parser.error("unexpected fixture manifest")
    results = []
    for fixture in manifest["fixtures"]:
        entry = fixture["image"]
        path = ADMISSION / entry["path"]
        image = path.read_bytes()
        if len(image) != entry["size"] or hashlib.sha256(image).hexdigest() != entry["sha256"]:
            raise CloudObserverError("fixture_hash_mismatch")
        try:
            result = observe(image, args.folder_id, api_key, reasoning_effort=args.reasoning_effort)
            predicted = {name for name, state in result["states"].items() if state == "detected"}
            expected = set(fixture["expected_classes"])
            results.append({"fixture_id": fixture["id"], **result,
                            "misses": sorted(expected - predicted), "false_detections": sorted(predicted - expected)})
        except CloudObserverError as exc:
            results.append({"fixture_id": fixture["id"], "error": str(exc)})
    print(json.dumps({"schema_revision": "cloud-eval-v1", "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
