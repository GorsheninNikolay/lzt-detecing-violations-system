"""Operator commands for held-out revisions and byte-free comparison plans."""

import argparse
import json
import uuid
from pathlib import Path

from app.adapters.postgres import AdmissionStoreError, EvaluationStoreError, PostgresStore
from app.config import Config
from app.domain.comparison_campaign import CampaignGateError


ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    freeze = subcommands.add_parser("freeze")
    freeze.add_argument("--archive", type=Path, required=True)
    campaign = subcommands.add_parser("freeze-campaign")
    campaign.add_argument("--evaluation-revision", type=uuid.UUID, required=True)
    campaign.add_argument("--local-profile", type=uuid.UUID, required=True)
    campaign.add_argument("--cloud-profile", type=uuid.UUID, required=True)
    readback = subcommands.add_parser("read-campaign")
    readback.add_argument("--campaign", type=uuid.UUID, required=True)
    args = parser.parse_args()
    store = PostgresStore(Config.database_url_from_env())
    try:
        try:
            if args.command == "freeze":
                decision, revision_id = store.freeze_evaluation_set(
                    ROOT / "evaluation/held-out-v1.json", args.archive,
                    sorted((ROOT / "backend/admission/exclusions").glob("*.json")),
                    ROOT / "evaluation/contract-inventory.json",
                    ROOT / "backend/admission/manifest.json",
                    ROOT / "evaluation/historical-comparison-v1.json")
                result = {"status": decision["status"], "manifest_hash": decision["manifest_hash"],
                          "revision_id": str(revision_id) if revision_id else None, "errors": decision["errors"]}
                exit_code = 0 if decision["status"] == "accepted" else 1
            elif args.command == "freeze-campaign":
                campaign_id = store.freeze_comparison_campaign(args.evaluation_revision,
                    args.local_profile, args.cloud_profile)
                result = store.read_comparison_campaign(campaign_id)
                exit_code = 0
            else:
                result = store.read_comparison_campaign(args.campaign)
                exit_code = 0
        except (AdmissionStoreError, CampaignGateError, EvaluationStoreError) as exc:
            result, exit_code = {"status": "rejected", "error": str(exc)}, 1
        print(json.dumps(result))
        if exit_code:
            parser.exit(exit_code)
    finally:
        store.close()


if __name__ == "__main__":
    main()
