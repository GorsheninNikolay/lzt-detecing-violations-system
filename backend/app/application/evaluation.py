"""Operator command to persist a reviewed held-out evaluation revision."""

import argparse
import json
from pathlib import Path

from app.adapters.postgres import PostgresStore
from app.config import Config


ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["freeze"])
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    store = PostgresStore(Config.database_url_from_env())
    try:
        decision, revision_id = store.freeze_evaluation_set(
            ROOT / "evaluation/held-out-v1.json", args.archive,
            sorted((ROOT / "backend/admission/exclusions").glob("*.json")),
            ROOT / "evaluation/contract-inventory.json",
            ROOT / "backend/admission/manifest.json",
            ROOT / "evaluation/historical-comparison-v1.json",
        )
        print(json.dumps({"status": decision["status"], "manifest_hash": decision["manifest_hash"],
                          "revision_id": str(revision_id) if revision_id else None, "errors": decision["errors"]}))
        if decision["status"] != "accepted":
            parser.exit(1)
    finally:
        store.close()


if __name__ == "__main__":
    main()
