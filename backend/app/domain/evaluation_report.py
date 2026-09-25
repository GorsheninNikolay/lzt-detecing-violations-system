"""Literal readiness accounting for a frozen comparison campaign."""

import hashlib
import json


POLICY_REVISION = "criterion-readiness-v1"
CRITERIA = ("campaign_coverage", "mandatory_detections", "mandatory_outcomes", "zero_false_warnings")
TERMINAL = {"succeeded", "failed"}


def repeat_disagreement(groups: dict, repeats: int) -> tuple[list[dict], int]:
    disagreement = []
    complete_groups = 0
    for group, group_cells in sorted(groups.items()):
        if len(group_cells) != repeats or any(cell["state"] not in TERMINAL for cell in group_cells):
            continue
        complete_groups += 1
        signatures = {json.dumps([cell["state"], cell.get("error_code"), cell.get("outcome"),
            sorted((item["class_name"], item["state"],
                    next((source["ordinal"] for source in cell["inputs"]
                          if source["input_id"] == item["input_id"]), None))
                   for item in cell["observations"])], sort_keys=True) for cell in group_cells}
        if len(signatures) > 1:
            disagreement.append({"fixture_ordinal": group[0], "candidate_ordinal": group[1],
                                 "run_ids": [cell["run_id"] for cell in group_cells]})
    return disagreement, complete_groups


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str,
                                     allow_nan=False).encode()).hexdigest()


def _reference(cell: dict) -> dict:
    return {key: cell[key] for key in ("run_id", "repeat_ordinal", "fixture_ordinal",
                                       "candidate_ordinal", "state", "error_code", "outcome", "projection",
                                       "inputs", "observations", "invocations", "artifact_ids")}


def build_report(snapshot: dict, policy_revision: str) -> dict:
    if policy_revision != POLICY_REVISION:
        raise ValueError("readiness_policy_revision_unknown")
    manifest = snapshot["manifest"]
    fixtures = manifest["fixtures"]
    labels_by_ordinal = {frame["ordinal"]: frame for frame in snapshot["evaluation_frames"]}
    repeats, candidates = manifest["repeats"], len(manifest["candidates"])
    cells = snapshot["cells"]
    expected_keys = {(repeat, fixture["ordinal"], candidate["ordinal"])
                     for repeat in range(repeats) for fixture in fixtures
                     for candidate in manifest["candidates"]}
    if len(expected_keys) != 36 or len(labels_by_ordinal) != 11:
        raise ValueError("campaign_manifest_invalid")
    by_key = {(cell["repeat_ordinal"], cell["fixture_ordinal"], cell["candidate_ordinal"]): cell
              for cell in cells}
    if len(by_key) != len(cells) or set(by_key) - expected_keys:
        raise ValueError("campaign_cells_invalid")

    coverage_misses = []
    absent = []
    detection_misses = []
    false_detections = []
    outcome_misses = []
    false_warnings = []
    pending = []
    detection_pending = []
    warning_pending = []
    technical_errors = []
    detection_population = []
    negative_population = []
    outcome_population = []
    warning_population = []
    latency = []
    all_refs = []
    by_repeat_group = {}
    for key in sorted(expected_keys):
        repeat, fixture_ordinal, candidate = key
        fixture = fixtures[fixture_ordinal]
        cell = by_key.get(key)
        if cell is None:
            cell = {"run_id": None, "repeat_ordinal": repeat, "fixture_ordinal": fixture_ordinal,
                    "candidate_ordinal": candidate, "state": "missing", "error_code": None,
                    "outcome": None, "projection": None, "inputs": [], "observations": [],
                    "invocations": [], "artifact_ids": []}
            absent.append(_reference(cell))
        ref = _reference(cell)
        all_refs.append(ref)
        by_repeat_group.setdefault((fixture_ordinal, candidate), []).append(cell)
        if cell["state"] not in TERMINAL:
            pending.append(ref)
        elif cell["state"] == "failed":
            technical_errors.append(ref)
        if cell.get("latency_ms") is not None:
            latency.append({"run_id": cell["run_id"], "milliseconds": cell["latency_ms"]})
        if cell["state"] != "succeeded":
            coverage_misses.append(ref)
        outcome_population.append(ref)
        if cell["state"] in TERMINAL and (cell["state"] != "succeeded" or
                                           cell.get("outcome") != fixture["expected_outcome"]):
            outcome_misses.append(ref)
        if fixture["expected_outcome"] != "check_requested":
            warning_population.append(ref)
            if cell["state"] not in TERMINAL:
                warning_pending.append(ref)
            if cell.get("outcome") == "check_requested":
                false_warnings.append(ref)
        if fixture["expected_outcome"] in {"insufficient_data", "not_analyzed"}:
            continue
        inputs = {item["ordinal"]: item for item in cell["inputs"]}
        observed = {(item["input_id"], item["class_name"]): item for item in cell["observations"]}
        for frame in fixture["frames"]:
            labels = labels_by_ordinal[frame["ordinal"]]
            if labels["id"] != frame["id"]:
                raise ValueError("evaluation_frame_mismatch")
            for class_name, label in labels["manual_labels"].items():
                if label not in {"yes", "no"}:
                    continue
                item = inputs.get(frame["ordinal"])
                observation = observed.get((item["input_id"], class_name)) if item else None
                detail = {"run_id": cell["run_id"], "fixture_ordinal": fixture_ordinal,
                          "frame_ordinal": frame["ordinal"], "candidate_ordinal": candidate,
                          "repeat_ordinal": repeat, "class_name": class_name,
                          "input_id": item["input_id"] if item else None,
                          "input_artifact_id": item["artifact_id"] if item else None,
                          "observation": observation,
                          "state": cell["state"], "error_code": cell["error_code"]}
                if label == "yes":
                    detection_population.append(detail)
                    if cell["state"] not in TERMINAL:
                        detection_pending.append(detail)
                    if cell["state"] in TERMINAL and (cell["state"] != "succeeded" or not observation
                            or observation["state"] != "detected"):
                        detection_misses.append(detail)
                else:
                    negative_population.append(detail)
                    if observation and observation["state"] == "detected":
                        false_detections.append(detail)

    disagreement, complete_groups = repeat_disagreement(by_repeat_group, repeats)

    def criterion(key: str, misses: list, population: list, pending_population: list) -> dict:
        status = "fail" if misses else "not_evaluated" if pending_population else "pass"
        return {"key": key, "status": status,
                "reason": "observed_failure" if misses else "pending_evidence" if status == "not_evaluated" else "all_applicable_passed",
                "numerator": len(misses), "denominator": len(population),
                "evidence": population, "misses": misses}

    criteria = [
        criterion("campaign_coverage", [ref for ref in coverage_misses if ref["state"] in TERMINAL] + absent,
                  all_refs, pending),
        criterion("mandatory_detections", detection_misses, detection_population, detection_pending),
        criterion("mandatory_outcomes", outcome_misses, outcome_population, pending),
        criterion("zero_false_warnings", false_warnings, warning_population, warning_pending),
    ]
    if tuple(row["key"] for row in criteria) != CRITERIA:
        raise ValueError("readiness_criteria_invalid")
    if any(row["status"] == "not_evaluated" for row in criteria):
        overall = "incomplete"
    elif any(row["status"] == "fail" for row in criteria):
        overall = "fail"
    else:
        overall = "pass"
    return {"schema_revision": "evaluation-report-v1", "campaign_id": snapshot["id"],
            "campaign_manifest_hash": snapshot["manifest_hash"],
            "evaluation_revision_id": snapshot["evaluation_revision_id"],
            "evaluation_manifest_hash": manifest["evaluation_manifest_hash"],
            "policy_revision": policy_revision, "evidence_digest": _digest(snapshot),
            "status": overall, "criteria": criteria,
            "measures": {
                "planned_cells": {"numerator": len(cells), "denominator": len(expected_keys), "evidence": all_refs},
                "technical_errors": {"numerator": len(technical_errors), "denominator": len(expected_keys), "evidence": technical_errors},
                "detection_misses": {"numerator": len(detection_misses), "denominator": len(detection_population), "evidence": detection_misses},
                "false_detections": {"numerator": len(false_detections), "denominator": len(negative_population), "evidence": false_detections},
                "outcome_misses": {"numerator": len(outcome_misses), "denominator": len(outcome_population), "evidence": outcome_misses},
                "false_check_requests": {"numerator": len(false_warnings), "denominator": len(warning_population), "evidence": false_warnings},
                "repeat_disagreement": {"numerator": len(disagreement), "denominator": complete_groups,
                                        "evaluated_groups": complete_groups, "evidence": disagreement},
                "latency_ms": {"availability": "observed" if latency else "unavailable",
                               "measured_count": len(latency), "values": latency,
                               "denominator": len(expected_keys)},
                "cost": {"availability": "unavailable", "reason": "cost_not_recorded"},
                "check_request_comprehension": {"availability": "unavailable",
                                                "reason": "comprehension_not_recorded"},
            }}
