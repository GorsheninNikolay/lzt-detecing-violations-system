"""Safe public projection of a frozen provider comparison."""

from app.domain.evaluation_report import TERMINAL, repeat_disagreement
from app.domain.observations import CLASSES
from app.domain.comparison_campaign import CampaignGateError


TIMEOUT_ERRORS = {"observer_timeout", "campaign_timeout"}
OUTCOMES = {"observations_only", "no_check", "check_requested", "insufficient_data", "not_analyzed"}
OBSERVATION_STATES = {"detected", "not_detected_in_frame", "insufficient_data", "not_analyzed"}


def _identity(value):
    if not isinstance(value, str):
        return None
    if value.startswith("gpt://"):
        return value.split("/", 3)[-1] if value.count("/") >= 3 else None
    return value


def project_comparison(snapshot: dict, admissions: dict[int, dict | None]) -> dict:
    manifest = snapshot["manifest"]
    evaluation_frames = {frame["ordinal"]: frame for frame in snapshot["evaluation_frames"]}
    fixtures = []
    for fixture in manifest["fixtures"]:
        frames = []
        for frame in fixture["frames"]:
            evidence = evaluation_frames.get(frame["ordinal"])
            labels = evidence.get("manual_labels") if evidence and evidence.get("id") == frame["id"] else None
            if not isinstance(labels, dict) or set(labels) != set(CLASSES) or any(
                    label not in {"yes", "no", "unknown"} for label in labels.values()):
                raise CampaignGateError("comparison_labels_invalid")
            frames.append({"ordinal": frame["ordinal"],
                           "manual_labels": {name: labels[name] for name in CLASSES}})
        fixtures.append({"ordinal": fixture["ordinal"], "scenario": fixture["scenario"],
                         "expected_outcome": fixture["expected_outcome"], "frames": frames})
    by_key = {(cell["repeat_ordinal"], cell["fixture_ordinal"], cell["candidate_ordinal"]): cell
              for cell in snapshot["cells"]}
    groups = {}
    cells = []
    candidates = []
    for candidate in manifest["candidates"]:
        ordinal = candidate["ordinal"]
        profile = candidate["snapshot"]
        admission = admissions.get(ordinal)
        requested = profile.get("requested_model_identity", {})
        owner = profile.get("owner_evidence") if profile.get("kind") == "cloud_api" else None
        owner = owner if isinstance(owner, dict) else {}
        data_revision = owner.get("authorization_revision")
        data_recorded = bool(data_revision and data_revision == profile.get("rights", {}).get("cloud_upload_authorization"))
        candidates.append({
            "ordinal": ordinal, "kind": candidate["kind"],
            "profile_revision": candidate.get("profile_hash"),
            "model_revision": requested.get("revision"),
            "requested_identity": _identity(requested.get("id")),
            "returned_identity": _identity(profile.get("returned_model_identity")),
            "authorization_revision": candidate.get("authorization_revision"),
            "admission": {"status": admission["status"] if admission else "missing",
                          "authorization_state": admission["authorization_state"] if admission else None,
                          "current_revision": admission["revision"] if admission else None,
                          "evidence": "present" if profile.get("audit_hash") else "missing",
                          "cloud_data_gate": "recorded" if data_recorded else
                                             "missing" if profile.get("kind") == "cloud_api" else "not_applicable",
                          "data_decision_revision": data_revision if data_recorded else None,
                          "data_checked_at": owner.get("checked_at") if data_recorded else None,
                          "commercial_gate": "paid_recorded" if owner.get("paid_account") is True else
                                             "unresolved" if profile.get("kind") == "cloud_api" else "not_applicable"},
            "identity_gap": profile.get("identity_gap") if profile.get("identity_gap") in {
                "hosted_model_revision_unpinnable", "awaiting_offline_load",
                "local checkpoint digest identifies loaded bytes; no remote model identity was returned"} else None,
        })
    for repeat in range(manifest["repeats"]):
        for fixture in manifest["fixtures"]:
            for candidate in manifest["candidates"]:
                key = (repeat, fixture["ordinal"], candidate["ordinal"])
                cell = by_key.get(key)
                state = cell["state"] if cell else "missing"
                if cell and (cell["outcome"] not in OUTCOMES and cell["outcome"] is not None
                             or state == "succeeded" and cell["outcome"] is None):
                    raise CampaignGateError("comparison_outcome_invalid")
                input_ordinals = {item["input_id"]: item["ordinal"] for item in cell["inputs"]} if cell else {}
                if cell and any(item["input_id"] not in input_ordinals or item["class_name"] not in CLASSES
                                or item["state"] not in OBSERVATION_STATES
                                for item in cell["observations"]):
                    raise CampaignGateError("comparison_observation_invalid")
                observations = sorted(({"frame_ordinal": input_ordinals[item["input_id"]],
                                        "class_name": item["class_name"], "state": item["state"]}
                                       for item in cell["observations"]),
                                      key=lambda item: (item["frame_ordinal"], item["class_name"])) if cell else []
                cells.append({"repeat_ordinal": repeat, "fixture_ordinal": fixture["ordinal"],
                              "candidate_ordinal": candidate["ordinal"],
                              "run_id": cell["run_id"] if cell else None, "state": state,
                              "error_code": (cell["error_code"] if cell["error_code"] in TIMEOUT_ERRORS else
                                             "campaign_failure" if state == "failed" else None) if cell else None,
                              "latency_ms": cell["latency_ms"] if cell else None,
                              "observed_outcome": cell["outcome"] if cell else None,
                              "observations": observations})
                if cell:
                    groups.setdefault((fixture["ordinal"], candidate["ordinal"]), []).append(cell)
    disagreements, _ = repeat_disagreement(groups, manifest["repeats"])
    for candidate in candidates:
        ordinal = candidate["ordinal"]
        own = [cell for cell in cells if cell["candidate_ordinal"] == ordinal]
        terminal = sum(cell["state"] in TERMINAL for cell in own)
        timed_out = sum(cell["state"] == "failed" and cell["error_code"] in TIMEOUT_ERRORS for cell in own)
        failed = sum(cell["state"] == "failed" for cell in own) - timed_out
        succeeded_latency = [cell["latency_ms"] for cell in own
                             if cell["state"] == "succeeded" and cell["latency_ms"] is not None]
        failed_latency = [cell["latency_ms"] for cell in own
                          if cell["state"] == "failed" and cell["latency_ms"] is not None]
        complete_groups = sum(len(group) == manifest["repeats"] and all(cell["state"] in TERMINAL for cell in group)
                              for (fixture, member), group in groups.items() if member == ordinal)
        candidate["accounting"] = {"planned": len(own), "terminal": terminal,
                                   "succeeded": sum(cell["state"] == "succeeded" for cell in own),
                                   "failed": failed, "timed_out": timed_out,
                                   "pending": sum(cell["state"] not in TERMINAL and cell["state"] != "missing" for cell in own),
                                   "missing": sum(cell["state"] == "missing" for cell in own)}
        candidate["repeat_disagreement"] = {"numerator": sum(item["candidate_ordinal"] == ordinal for item in disagreements),
                                             "denominator": complete_groups,
                                             "evidence": [item for item in disagreements if item["candidate_ordinal"] == ordinal]}
        candidate["latency_ms"] = {"availability": "observed" if succeeded_latency or failed_latency else "unavailable",
                                   "succeeded_count": len(succeeded_latency), "failed_count": len(failed_latency)}
        candidate["cost"] = {"availability": "unavailable", "reason": "cost_not_recorded"}
    return {"campaign": {"id": snapshot["id"], "revision_number": snapshot["revision_number"],
                          "evaluation_revision_id": snapshot["evaluation_revision_id"]},
            "repeats": manifest["repeats"],
            "fixtures": fixtures,
            "candidates": candidates, "cells": cells,
            "complete": all(cell["state"] in TERMINAL for cell in cells)}
