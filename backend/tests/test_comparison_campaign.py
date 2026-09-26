import copy
import json
import math
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.adapters.postgres import AdmissionStoreError, PostgresStore
from app.domain.comparison_campaign import CampaignGateError, build_manifest
from app.domain.evaluation_set import canonical_hash
from app.domain.evaluation_report import POLICY_REVISION, build_report
from app.domain.provider_comparison import project_comparison
from test_startup import database, integration
from test_admission import isolated_admission_database


ROOT = Path(__file__).resolve().parents[2]
EVALUATION = json.loads((ROOT / "evaluation/held-out-v1.json").read_text())


@pytest.fixture
def isolated_campaign_database(isolated_admission_database):
    from app.adapters.postgres import PostgresStore

    store = PostgresStore(isolated_admission_database)
    try:
        yield store
    finally:
        store.close()


def profiles(manifest=EVALUATION):
    hashes = [frame["image"]["sha256"] for frame in manifest["frames"]]
    local = {"kind": "local_process", "adapter": {"code": "grounding_dino"},
        "requested_model_identity": {"id": "IDEA-Research/grounding-dino-tiny", "revision": "e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e"},
        "runtime": {"os": "Darwin", "architecture": "arm64", "device": "cpu", "cpu_cores": 12,
                    "memory_bytes": 36 * 1024**3, "driver": "PyTorch CPU", "concurrency": 1,
                    "sdk_retries": 0, "per_image_timeout_seconds": 60, "batch_timeout_seconds": 600}}
    cloud = {"kind": "cloud_api", "adapter": {"code": "yandex_ai_studio"},
        "folder_id": "test-folder", "requested_model_identity": {"id": "gpt://test-folder/qwen3.6-35b-a3b"},
        "runtime": {"concurrency": 1, "sdk_retries": 0,
                    "per_image_timeout_seconds": 60, "batch_timeout_seconds": 600},
        "allowed_input_sha256": sorted(set(hashes)), "audit_run_ids": []}
    return local, cloud


def report_snapshot():
    manifest = build_manifest(EVALUATION, *profiles())
    manifest["evaluation_manifest_hash"] = canonical_hash(EVALUATION)
    cells = []
    for repeat in range(3):
        for fixture in manifest["fixtures"]:
            for candidate in manifest["candidates"]:
                run_id = str(uuid.uuid4())
                inputs, observations, invocations = [], [], []
                for frame in fixture["frames"]:
                    input_id = str(uuid.uuid4())
                    artifact_id = str(uuid.uuid4())
                    invocation_id = str(uuid.uuid4())
                    inputs.append({"input_id": input_id, "ordinal": frame["ordinal"],
                                   "artifact_id": artifact_id, "sha256": frame["image"]["sha256"]})
                    invocations.append({"id": invocation_id, "input_id": input_id,
                                        "state": "completed", "native_artifact_id": str(uuid.uuid4())})
                    for class_name, label in EVALUATION["frames"][frame["ordinal"]]["manual_labels"].items():
                        state = ("insufficient_data" if fixture["expected_outcome"] == "insufficient_data"
                                 else "not_analyzed" if fixture["expected_outcome"] == "not_analyzed"
                                 else "detected" if label == "yes" else "not_detected_in_frame")
                        observations.append({"input_id": input_id, "class_name": class_name,
                                             "state": state, "invocation_id": invocation_id,
                                             "source_artifact_id": artifact_id})
                cells.append({"repeat_ordinal": repeat, "fixture_ordinal": fixture["ordinal"],
                              "candidate_ordinal": candidate["ordinal"], "run_id": run_id,
                              "state": "succeeded", "error_code": None,
                              "latency_ms": 100, "outcome": fixture["expected_outcome"],
                              "projection": {"outcome": fixture["expected_outcome"]},
                              "inputs": inputs, "observations": observations,
                              "invocations": invocations, "artifact_ids": []})
    return {"id": str(uuid.uuid4()), "manifest_hash": canonical_hash(manifest),
            "evaluation_revision_id": str(uuid.uuid4()), "manifest": manifest, "cells": cells,
            "evaluation_frames": [{"id": frame["id"], "ordinal": frame["ordinal"],
                                   "manual_labels": copy.deepcopy(frame["manual_labels"])}
                                  for frame in EVALUATION["frames"]]}


def test_provider_projection_is_safe_and_accounts_for_each_planned_cell():
    snapshot = report_snapshot()
    snapshot["revision_number"] = 3
    for candidate in snapshot["manifest"]["candidates"]:
        candidate["profile_hash"] = "profile-revision-" + str(candidate["ordinal"])
    snapshot["manifest"]["candidates"][0]["snapshot"].update(
        returned_model_identity="checkpoint-sha256:model-only", audit_hash="private-audit")
    snapshot["manifest"]["candidates"][1]["snapshot"].update(
        returned_model_identity="gpt://private-folder/qwen3.6/latest",
        owner_evidence={"service_account_id": "private-service", "allowed_image_sha256": ["private-hash"],
                        "authorization_revision": "owner-v1", "checked_at": "2026-09-25T10:00:00Z",
                        "paid_account": True}, rights={"cloud_upload_authorization": "owner-v1"})
    snapshot["cells"][0].update(state="failed", error_code="observer_timeout")
    snapshot["cells"][1].update(state="failed", error_code="observer_error")
    snapshot["cells"].pop(2)
    result = project_comparison(snapshot, {0: {"status": "admitted", "authorization_state": "enabled", "revision": 1}, 1: None})
    assert result["complete"] is False
    assert len(result["cells"]) == 36
    assert result["cells"][2]["state"] == "missing" and result["cells"][2]["run_id"] is None
    assert result["cells"][0]["error_code"] == "observer_timeout"
    assert result["cells"][1]["error_code"] == "campaign_failure"
    assert result["fixtures"][0]["expected_outcome"] == "observations_only"
    assert result["fixtures"][0]["frames"][0]["manual_labels"] == {"excavator": "yes", "dump_truck": "yes"}
    assert result["cells"][0]["observed_outcome"] == "observations_only"
    assert result["cells"][0]["observations"] == [
        {"frame_ordinal": 0, "class_name": "dump_truck", "state": "detected"},
        {"frame_ordinal": 0, "class_name": "excavator", "state": "detected"}]
    assert result["cells"][2]["observed_outcome"] is None and result["cells"][2]["observations"] == []
    assert result["candidates"][0]["accounting"] == {"planned": 18, "terminal": 17, "succeeded": 16,
        "failed": 0, "timed_out": 1, "pending": 0, "missing": 1}
    assert result["candidates"][1]["accounting"]["failed"] == 1
    assert result["candidates"][1]["admission"]["status"] == "missing"
    assert result["candidates"][1]["admission"]["cloud_data_gate"] == "recorded"
    assert result["candidates"][1]["admission"]["commercial_gate"] == "paid_recorded"
    assert result["candidates"][0]["admission"]["evidence"] == "present"
    assert result["candidates"][1]["returned_identity"] == "qwen3.6/latest"
    assert result["candidates"][0]["profile_revision"] == snapshot["manifest"]["candidates"][0]["profile_hash"]
    encoded = json.dumps(result)
    for secret in ("private-folder", "private-service", "private-hash", "private-audit", '"audit_hash"', '"owner_evidence"',
                   '"profile_id"', '"profile_hash"', '"allowed_input_sha256"', '"winner"', '"score"'):
        assert secret not in encoded

    complete = report_snapshot()
    complete["revision_number"] = 4
    complete["cells"][12]["state"] = "failed"
    complete["cells"][12]["error_code"] = "observer_error"
    result = project_comparison(complete, {})
    assert result["complete"] is True
    assert result["candidates"][0]["repeat_disagreement"]["numerator"] == 1
    assert result["candidates"][0]["repeat_disagreement"]["denominator"] == 6
    assert result["candidates"][0]["latency_ms"]["succeeded_count"] == 17
    assert result["candidates"][0]["latency_ms"]["failed_count"] == 1
    assert "values" not in result["candidates"][0]["latency_ms"]
    assert result["candidates"][0]["cost"]["availability"] == "unavailable"


@pytest.mark.parametrize("corruption", ("outcome", "observation_class", "observation_state", "manual_label"))
def test_provider_projection_rejects_corrupt_evidence(corruption):
    snapshot = report_snapshot()
    snapshot["revision_number"] = 1
    cell = snapshot["cells"][0]
    if corruption == "outcome":
        cell["outcome"] = "private-outcome"
    elif corruption == "observation_class":
        cell["observations"][0]["class_name"] = "private-class"
    elif corruption == "observation_state":
        cell["observations"][0]["state"] = "private-state"
    else:
        snapshot["evaluation_frames"][0]["manual_labels"]["excavator"] = "private-label"
    with pytest.raises(CampaignGateError, match="comparison_(outcome|observation|labels)_invalid"):
        project_comparison(snapshot, {})


def test_latest_provider_comparison_rejects_manifest_hash_mismatch():
    class Connection:
        def execute(self, *_):
            return SimpleNamespace(scalar_one_or_none=lambda: uuid.uuid4())

    store = PostgresStore.__new__(PostgresStore)
    store.engine = SimpleNamespace(connect=lambda: nullcontext(Connection()))
    store.read_comparison_campaign = lambda _: {"manifest": {"changed": True}, "manifest_hash": "0" * 64}
    with pytest.raises(CampaignGateError, match="campaign_manifest_integrity_failed"):
        store.read_latest_provider_comparison()


def test_latest_provider_comparison_rejects_evaluation_manifest_hash_mismatch():
    class Connection:
        def execute(self, *_):
            return SimpleNamespace(scalar_one_or_none=lambda: uuid.uuid4())

    manifest = {"evaluation_manifest_hash": "a" * 64}
    store = PostgresStore.__new__(PostgresStore)
    store.engine = SimpleNamespace(connect=lambda: nullcontext(Connection()))
    store.read_comparison_campaign = lambda _: {"manifest": manifest,
        "manifest_hash": canonical_hash(manifest), "evaluation_manifest_hash": "b" * 64}
    with pytest.raises(CampaignGateError, match="campaign_manifest_integrity_failed"):
        store.read_latest_provider_comparison()


def test_criterion_report_matrix_and_literal_populations(monkeypatch):
    snapshot = report_snapshot()
    report = build_report(snapshot, POLICY_REVISION)
    assert report["status"] == "pass"
    assert len(report["criteria"]) == 4
    assert {row["key"] for row in report["criteria"]} == {
        "campaign_coverage", "mandatory_detections", "mandatory_outcomes", "zero_false_warnings"}
    assert all(row["status"] == "pass" for row in report["criteria"])
    assert report["measures"]["planned_cells"]["denominator"] == 36
    assert report["criteria"][1]["denominator"] == 72
    assert report["criteria"][2]["denominator"] == 36
    assert report["criteria"][3]["denominator"] == 30
    assert report["measures"]["false_detections"]["denominator"] == 24
    assert report["measures"]["latency_ms"]["measured_count"] == 36
    assert report["measures"]["cost"]["availability"] == "unavailable"
    assert report["measures"]["check_request_comprehension"]["availability"] == "unavailable"
    assert all(ref["run_id"] and ref["inputs"] and ref["invocations"] and ref["projection"]
               for ref in report["criteria"][0]["evidence"])

    pending = report_snapshot()
    pending["cells"][0].update(state="planned", outcome=None, projection=None,
                                inputs=[], observations=[], invocations=[])
    result = build_report(pending, POLICY_REVISION)
    assert result["status"] == "incomplete"
    assert result["criteria"][0]["status"] == "not_evaluated"
    assert result["criteria"][0]["denominator"] == 36
    assert result["measures"]["repeat_disagreement"]["denominator"] == 11

    absent = report_snapshot()
    absent["cells"].pop()
    result = build_report(absent, POLICY_REVISION)
    assert result["status"] == "incomplete"
    assert result["criteria"][0]["status"] == "fail"
    assert result["criteria"][0]["numerator"] == 1
    assert result["measures"]["planned_cells"]["numerator"] == 35
    assert any(ref["run_id"] is None for ref in result["criteria"][0]["evidence"])
    assert result["measures"]["repeat_disagreement"]["denominator"] == 11

    no_latency = report_snapshot()
    for cell in no_latency["cells"]:
        cell["latency_ms"] = None
    assert build_report(no_latency, POLICY_REVISION)["measures"]["latency_ms"] == {
        "availability": "unavailable", "measured_count": 0, "values": [], "denominator": 36}

    failed = report_snapshot()
    failed["cells"][0].update(state="failed", error_code="observer_timeout", outcome=None,
                               projection=None, observations=[])
    result = build_report(failed, POLICY_REVISION)
    assert result["status"] == "fail"
    assert result["criteria"][0]["status"] == "fail"
    assert result["measures"]["technical_errors"]["numerator"] == 1
    assert result["measures"]["detection_misses"]["numerator"] > 0

    non_applicable = report_snapshot()
    non_applicable["cells"][10].update(state="failed", error_code="observer_timeout",
                                        outcome=None, projection=None, observations=[])
    result = build_report(non_applicable, POLICY_REVISION)
    assert result["measures"]["detection_misses"]["numerator"] == 0
    assert result["measures"]["outcome_misses"]["numerator"] == 1

    false_detection = report_snapshot()
    false_cell = false_detection["cells"][2]
    negative = next(item for item in false_cell["observations"] if item["class_name"] == "dump_truck")
    negative["state"] = "detected"
    false_cell.update(state="failed", error_code="observer_timeout", outcome=None, projection=None)
    result = build_report(false_detection, POLICY_REVISION)
    evidence = result["measures"]["false_detections"]["evidence"]
    assert result["measures"]["false_detections"]["numerator"] == 1
    assert evidence[0]["run_id"] == false_cell["run_id"]
    assert evidence[0]["input_id"] == false_cell["inputs"][0]["input_id"]
    assert evidence[0]["observation"]["state"] == "detected"

    warning = report_snapshot()
    warning["cells"][4]["outcome"] = "check_requested"
    result = build_report(warning, POLICY_REVISION)
    assert result["status"] == "fail"
    assert result["criteria"][3]["status"] == "fail"
    assert result["measures"]["false_check_requests"]["numerator"] == 1

    for fixture_index in (8, 10):
        warning = report_snapshot()
        warning["cells"][fixture_index]["outcome"] = "check_requested"
        result = build_report(warning, POLICY_REVISION)
        assert result["criteria"][3]["status"] == "fail"
        assert result["criteria"][3]["numerator"] == 1
        assert result["criteria"][3]["denominator"] == 30
        assert result["criteria"][3]["misses"][0]["run_id"] == warning["cells"][fixture_index]["run_id"]

    disagree = report_snapshot()
    disagree["cells"][0]["observations"][0]["state"] = "not_detected_in_frame"
    result = build_report(disagree, POLICY_REVISION)
    assert result["measures"]["repeat_disagreement"]["numerator"] == 1
    assert result["measures"]["repeat_disagreement"]["denominator"] == 12

    from app.domain import evaluation_report
    monkeypatch.setattr(evaluation_report, "CRITERIA", ("campaign_coverage",))
    with pytest.raises(ValueError, match="readiness_criteria_invalid"):
        build_report(report_snapshot(), POLICY_REVISION)


def test_report_publication_cleans_temporary_object(monkeypatch):
    import hashlib

    from app.adapters.artifacts import ArtifactStore

    report_id = uuid.uuid4()
    payload = b'{"status":"incomplete"}'
    digest = hashlib.sha256(payload).hexdigest()
    store = ArtifactStore.__new__(ArtifactStore)
    calls = []
    monkeypatch.setattr(store, "upload_temporary", lambda *args: (f"tmp/{report_id}", digest, len(payload)))
    monkeypatch.setattr(store, "publish_final", lambda *args: f"sha256/{digest}")
    monkeypatch.setattr(store, "read_verified", lambda *args: payload)
    monkeypatch.setattr(store, "_delete_report_temporary", lambda *args: calls.append(args))
    assert store.publish_report(report_id, payload, digest) == f"sha256/{digest}"
    assert calls == [(f"tmp/{report_id}",)]

    class Missing(Exception):
        response = {"ResponseMetadata": {"HTTPStatusCode": 404}}

    class VersionedClient:
        versions = {"null", "old-version"}

        def delete_object(self, *, Bucket, Key, VersionId=None):
            if VersionId is None:
                self.versions.add("delete-marker")
            else:
                self.versions.remove(VersionId)

        def head_object(self, *, Bucket, Key):
            if self.versions:
                raise AssertionError("temporary versions remain")
            raise Missing()

    versioned = ArtifactStore.__new__(ArtifactStore)
    versioned.bucket = "test"
    versioned.client = VersionedClient()
    monkeypatch.setattr(versioned, "_health_versions", lambda key: [
        {"VersionId": value} for value in sorted(versioned.client.versions)])
    versioned._delete_report_temporary(f"tmp/{report_id}")
    assert not versioned.client.versions


def test_report_persistence_is_immutable_and_idempotent(isolated_campaign_database, monkeypatch):
    import hashlib

    database = isolated_campaign_database

    class MemoryArtifacts:
        objects = {}

        def publish_report(self, report_id, payload, digest):
            assert hashlib.sha256(payload).hexdigest() == digest
            key = f"sha256/{digest}"
            self.objects[key] = payload
            return key

        def read_verified(self, key, digest, size):
            payload = self.objects[key]
            assert len(payload) == size and hashlib.sha256(payload).hexdigest() == digest
            return payload

    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign_id = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    artifacts = MemoryArtifacts()
    assert database.read_latest_evaluation_report(artifacts) is None
    first = database.generate_evaluation_report(campaign_id, POLICY_REVISION, artifacts)
    assert first["status"] == "incomplete"
    latest = database.read_latest_evaluation_report(artifacts)
    assert latest["report"] == first
    assert latest["created_at"]
    assert latest["evaluation_set"]["id"] == str(revision)
    assert len(latest["evaluation_set"]["manifest_hash"]) == 64
    assert len(latest["evaluation_set"]["frames"]) == 11
    assert latest["evaluation_set"]["frames"] == [
        {"id": frame["id"], "ordinal": frame["ordinal"], "scenario": frame["scenario"],
         "image_sha256": frame["image"]["sha256"], "manual_labels": frame["manual_labels"],
         "sufficiency_notes": frame["sufficiency_notes"]}
        for frame in EVALUATION["frames"]]
    assert latest["fixtures"] == [
        {"ordinal": fixture["ordinal"], "scenario": fixture["scenario"],
         "expected_outcome": fixture["expected_outcome"]}
        for fixture in database.read_comparison_campaign(campaign_id)["manifest"]["fixtures"]]
    assert "archive_member" not in json.dumps(latest["evaluation_set"])
    assert "source_rights" not in json.dumps(latest["evaluation_set"])
    assert "snapshot" not in latest and "manifest" not in latest
    comparison_run = uuid.UUID(database.read_comparison_campaign(campaign_id)["cells"][0]["run_id"])
    assert database.read_ordinary(comparison_run) is None
    comparison_detail = database.read_run(comparison_run, "comparison_campaign")
    assert comparison_detail["purpose"] == "comparison_campaign"
    assert comparison_detail["profile_snapshot"] == {"adapter": {"code": "grounding_dino"}}
    cloud_run = uuid.UUID(database.read_comparison_campaign(campaign_id)["cells"][1]["run_id"])
    assert database.read_run(cloud_run, "comparison_campaign")["profile_snapshot"] == {
        "adapter": {"code": "yandex_ai_studio"}}
    assert all(item["run_id"] != str(comparison_run) for item in database.list_ordinary()["runs"])
    with monkeypatch.context() as patch:
        patch.setattr(database, "read_evaluation_report", lambda *_: {
            **first, "campaign_manifest_hash": "f" * 64})
        with pytest.raises(CampaignGateError, match="evaluation_report_integrity_failed"):
            database.read_latest_evaluation_report(artifacts)
    assert first == database.generate_evaluation_report(campaign_id, POLICY_REVISION, artifacts)
    assert len(first["criteria"]) == 4
    with database.engine.begin() as connection:
        assert connection.execute(text("""SELECT count(*) FROM evaluation_report_criteria
            WHERE report_id = :id"""), {"id": uuid.UUID(first["id"])}).scalar_one() == 4
        run_id = uuid.UUID(database.read_comparison_campaign(campaign_id)["cells"][0]["run_id"])
        connection.execute(text("""UPDATE analysis_runs SET state = 'failed',
            error_code = 'observer_timeout' WHERE id = :id"""), {"id": run_id})
    second = database.generate_evaluation_report(campaign_id, POLICY_REVISION, artifacts)
    assert second["id"] != first["id"]
    assert second["evidence_digest"] != first["evidence_digest"]
    assert database.read_latest_evaluation_report(artifacts)["report"] == second
    assert database.read_evaluation_report(uuid.UUID(first["id"]), artifacts) == first
    with pytest.raises(Exception, match="evaluation_reports_immutable"):
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE evaluation_reports SET policy_revision = 'other' WHERE id = :id"),
                               {"id": uuid.UUID(first["id"])})


def seed(database, manifest=EVALUATION, decision_hash=None):
    manifest = copy.deepcopy(manifest)
    manifest["campaign_test_nonce"] = str(uuid.uuid4())
    revision_id = uuid.uuid4()
    local_id, cloud_id = uuid.uuid4(), uuid.uuid4()
    local, cloud = profiles(manifest)
    local["test_nonce"] = str(uuid.uuid4())
    cloud["test_nonce"] = str(uuid.uuid4())
    source_hash = canonical_hash(manifest)
    with database.engine.begin() as connection:
        connection.execute(text("""INSERT INTO evaluation_set_revisions
            (id, revision_number, manifest_hash, manifest, inventory_evidence)
            VALUES (:id, (SELECT coalesce(max(revision_number), 0) + 1 FROM evaluation_set_revisions),
                    :hash, CAST(:manifest AS jsonb), '[]'::jsonb)"""),
            {"id": revision_id, "hash": source_hash, "manifest": json.dumps(manifest)})
        connection.execute(text("""INSERT INTO evaluation_freeze_decisions
            (id, revision_id, manifest_hash, status, inventory_evidence, errors)
            VALUES (:id, :revision, :hash, 'accepted', '[]'::jsonb, '[]'::jsonb)"""),
            {"id": uuid.uuid4(), "revision": revision_id, "hash": decision_hash or source_hash})
        for profile_id, snapshot in ((local_id, local), (cloud_id, cloud)):
            parent_id = uuid.uuid4()
            connection.execute(text("""INSERT INTO observer_profiles (id, status, profile_hash, snapshot)
                VALUES (:id, 'draft', :hash, '{}'::jsonb)"""), {"id": parent_id, "hash": str(parent_id)})
            connection.execute(text("""INSERT INTO observer_profiles
                (id, parent_id, status, profile_hash, snapshot, audit_hash)
                VALUES (:id, :parent, 'admitted', :hash, CAST(:snapshot AS jsonb), 'test-audit')"""),
                {"id": profile_id, "parent": parent_id, "hash": canonical_hash(snapshot),
                 "snapshot": json.dumps(snapshot)})
            connection.execute(text("""INSERT INTO profile_authorizations
                (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
                VALUES (:id, 1, 'enabled', 'test', 'test-audit', false)"""), {"id": profile_id})
    return revision_id, local_id, cloud_id, local, cloud


def patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud):
    """Materialize archived snapshots without admitting or calling retired providers."""
    def authorized(_, profile_id, expected_revision=None):
        return ({local_id: local, cloud_id: cloud}[profile_id], 1)
    monkeypatch.setattr(database, "_require_authorized", authorized)


def test_latest_provider_comparison_reads_frozen_cells_without_mutation(database, monkeypatch):
    for _ in range(2):
        revision, local_id, cloud_id, local, cloud = seed(database)
        patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
        campaign_id = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    before = database.read_comparison_campaign(campaign_id)
    comparison = database.read_latest_provider_comparison()
    assert comparison["campaign"]["id"] == str(campaign_id)
    assert comparison["campaign"]["revision_number"] == before["revision_number"]
    assert comparison["complete"] is False
    assert len(comparison["cells"]) == 36
    assert comparison["candidates"][0]["accounting"]["pending"] == 18
    assert comparison["candidates"][1]["admission"]["status"] == "admitted"
    assert comparison["candidates"][1]["admission"]["evidence"] == "missing"
    assert database.read_comparison_campaign(campaign_id) == before


def test_manifest_preserves_six_scenarios_eleven_frames_and_two_areas():
    local, cloud = profiles()
    plan = build_manifest(EVALUATION, local, cloud)
    assert [f["scenario"] for f in plan["fixtures"]] == list(dict.fromkeys(
        frame["scenario"] for frame in EVALUATION["frames"]))
    assert [frame["ordinal"] for fixture in plan["fixtures"] for frame in fixture["frames"]] == list(range(11))
    assert len({frame["context"]["observation_area"] for frame in plan["fixtures"][4]["frames"]}) == 2
    for invalid in (0, -1, math.inf, math.nan):
        changed = copy.deepcopy(local)
        changed["runtime"]["per_image_timeout_seconds"] = invalid
        with pytest.raises(CampaignGateError, match="candidate_runtime_invalid"):
            build_manifest(EVALUATION, changed, cloud)
    with pytest.raises(CampaignGateError, match="candidate_identity_invalid"):
        build_manifest(EVALUATION, cloud, local)


def test_freeze_binds_all_cells_and_immutable_runs(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign_id = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    result = database.read_comparison_campaign(campaign_id)
    assert len(result["cells"]) == 36
    assert len({cell["run_id"] for cell in result["cells"]}) == 36
    assert all(cell["state"] == "planned" for cell in result["cells"])
    with database.engine.connect() as connection:
        for cell in result["cells"]:
            fixture = result["manifest"]["fixtures"][cell["fixture_ordinal"]]
            candidate = result["manifest"]["candidates"][cell["candidate_ordinal"]]
            run = connection.execute(text("SELECT * FROM analysis_runs WHERE id = :id"),
                                     {"id": uuid.UUID(cell["run_id"])}).one()
            assert run.profile_id == uuid.UUID(candidate["profile_id"])
            assert run.profile_snapshot == candidate["snapshot"]
            assert run.authorization_revision == 1 and run.binding_kind == "comparison_cell"
            assert run.purpose == "comparison_campaign" and run.rule_snapshot == result["manifest"]["rule"]
            assert run.taxonomy_snapshot == result["manifest"]["taxonomy"]
            assert run.requested_classes == fixture["requested_classes"]
            assert run.request_context["observation_areas"] == [
                frame["context"]["observation_area"] for frame in fixture["frames"]]
            if fixture["scenario"] == "insufficient_series":
                assert run.request_context["observation_area"] == "multiple_observation_areas"
                assert run.request_context["frame_contexts"] == [
                    frame["context"] for frame in fixture["frames"]]
            assert run.policy_snapshot == ({"intent": "rule_evaluation", **result["manifest"]["rule_policy"]}
                                          if fixture["scenario"].endswith("_series") else
                                          result["manifest"]["observation_policy"])
    with pytest.raises(CampaignGateError, match="campaign_already_frozen"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    for change in ("purpose = 'ordinary'", "state = 'queued'"):
        with pytest.raises(Exception, match="comparison_run_immutable"):
            with database.engine.begin() as connection:
                connection.execute(text(f"UPDATE analysis_runs SET {change} WHERE id = :id"),
                                   {"id": uuid.UUID(result["cells"][0]["run_id"])})


def test_duplicate_hashes_keep_distinct_fixture_cells(database, monkeypatch):
    manifest = copy.deepcopy(EVALUATION)
    manifest["frames"][1]["image"]["sha256"] = manifest["frames"][0]["image"]["sha256"]
    revision, local_id, cloud_id, local, cloud = seed(database, manifest)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    cells = database.read_comparison_campaign(database.freeze_comparison_campaign(revision, local_id, cloud_id))["cells"]
    assert cells[0]["run_id"] != cells[2]["run_id"]
    assert cells[0]["fixture_ordinal"] == 0 and cells[2]["fixture_ordinal"] == 1


def test_real_admission_gate_rejects_unauthorized_profile_without_cells(database):
    revision, local_id, cloud_id, _, _ = seed(database)
    with pytest.raises(AdmissionStoreError, match="profile_retired"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM comparison_cells c JOIN comparison_campaigns p ON p.id = c.campaign_id WHERE p.evaluation_revision_id = :id"),
                                  {"id": revision}).scalar_one() == 0


def test_decision_hash_mismatch_rolls_back(database, monkeypatch):
    manifest = copy.deepcopy(EVALUATION)
    manifest["frames"][0]["sufficiency_notes"] = str(uuid.uuid4())
    revision, local_id, cloud_id, local, cloud = seed(database, manifest, "wrong")
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    with pytest.raises(CampaignGateError, match="evaluation_decision_mismatch"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)


def test_revoked_and_uncovered_cloud_scope_leave_no_campaign(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    with database.engine.begin() as connection:
        connection.execute(text("UPDATE profile_authorizations SET state = 'revoked' WHERE profile_id = :id"),
                           {"id": cloud_id})
    original = database._require_authorized

    def local_only(connection, profile_id, expected_revision=None):
        if profile_id == local_id:
            return local, 1
        return original(connection, profile_id, expected_revision)

    monkeypatch.setattr(database, "_require_authorized", local_only)
    with pytest.raises(AdmissionStoreError, match="profile_retired"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    cloud["allowed_input_sha256"].pop()
    with pytest.raises(CampaignGateError, match="cloud_image_not_authorized"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM comparison_campaigns WHERE evaluation_revision_id = :id"),
                                  {"id": revision}).scalar_one() == 0


def test_concurrent_freeze_is_single_complete_revision(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)

    def freeze():
        try:
            return database.freeze_comparison_campaign(revision, local_id, cloud_id)
        except CampaignGateError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: freeze(), range(2)))
    assert sum(isinstance(item, uuid.UUID) for item in outcomes) == 1
    assert "campaign_already_frozen" in outcomes
    campaign_id = next(item for item in outcomes if isinstance(item, uuid.UUID))
    assert len(database.read_comparison_campaign(campaign_id)["cells"]) == 36


def test_changed_request_gets_distinct_revision_without_rewriting_prior(database, monkeypatch):
    from app.domain import comparison_campaign

    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    first = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    first_result = database.read_comparison_campaign(first)
    changed_policy = {**comparison_campaign.RULE_POLICY, "revision": "policy-successor-test"}
    monkeypatch.setattr(comparison_campaign, "RULE_POLICY", changed_policy)
    second = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    second_result = database.read_comparison_campaign(second)
    assert second != first
    assert database.read_comparison_campaign(first) == first_result
    assert second_result["revision_number"] > first_result["revision_number"]
    assert second_result["evaluation_revision_id"] == first_result["evaluation_revision_id"]
    assert [item["profile_id"] for item in second_result["manifest"]["candidates"]] == [
        item["profile_id"] for item in first_result["manifest"]["candidates"]]
    assert second_result["manifest"]["rule_policy"]["revision"] == "policy-successor-test"


def test_mid_transaction_failure_rolls_back_all_cells(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    original = database.engine
    from sqlalchemy import event

    def fail_cell(connection, cursor, statement, parameters, context, executemany):
        if "INSERT INTO comparison_cells" in statement and parameters["repeat"] == 1:
            raise RuntimeError("injected_cell_failure")

    event.listen(original, "before_cursor_execute", fail_cell)
    try:
        with pytest.raises(RuntimeError, match="injected_cell_failure"):
            database.freeze_comparison_campaign(revision, local_id, cloud_id)
    finally:
        event.remove(original, "before_cursor_execute", fail_cell)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM comparison_campaigns WHERE evaluation_revision_id = :id"),
                                  {"id": revision}).scalar_one() == 0


def test_cli_safe_rejection_and_missing_campaign(database, monkeypatch, capsys):
    import sys
    from app.application import evaluation

    monkeypatch.setattr(evaluation.Config, "database_url_from_env", lambda: database.engine.url.render_as_string(hide_password=False))
    monkeypatch.setattr(sys, "argv", ["evidence-evaluation", "read-campaign", "--campaign", str(uuid.uuid4())])
    with pytest.raises(SystemExit) as exit_code:
        evaluation.main()
    assert exit_code.value.code == 1
    assert json.loads(capsys.readouterr().out) == {"status": "rejected", "error": "campaign_missing"}
    monkeypatch.setattr(sys, "argv", ["evidence-evaluation", "freeze-campaign",
        "--evaluation-revision", str(uuid.uuid4()), "--local-profile", str(uuid.uuid4()),
        "--cloud-profile", str(uuid.uuid4())])
    with pytest.raises(SystemExit) as exit_code:
        evaluation.main()
    assert exit_code.value.code == 1
    assert json.loads(capsys.readouterr().out) == {"status": "rejected", "error": "evaluation_revision_missing"}


def test_downgrade_refuses_planned_campaign_and_keeps_evidence(database, monkeypatch):
    from alembic import command
    from alembic.config import Config as AlembicConfig

    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign_id = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    assert len(database.read_comparison_campaign(campaign_id)["cells"]) == 36
    monkeypatch.setenv("DATABASE_URL", database.engine.url.render_as_string(hide_password=False))
    with pytest.raises(RuntimeError, match="deepseek_evidence_preservation_requires_forward_migration"):
        command.downgrade(AlembicConfig(str(ROOT / "backend/alembic.ini")), "0009_evaluation_set")
    assert len(database.read_comparison_campaign(campaign_id)["cells"]) == 36


class MemoryArtifacts:
    def __init__(self):
        self.objects = {}
        self.uploads = []

    def upload_temporary(self, intent_id, payload, media_type):
        import hashlib
        digest = hashlib.sha256(payload).hexdigest()
        self.objects[f"tmp/{intent_id}"] = payload
        self.uploads.append(intent_id)
        return f"tmp/{intent_id}", digest, len(payload)

    def publish_final(self, intent_id, payload, media_type, digest, size):
        assert self.objects[f"tmp/{intent_id}"] == payload
        self.objects[f"sha256/{digest}"] = payload
        return f"sha256/{digest}"

    def read_verified(self, key, digest, size):
        import hashlib
        payload = self.objects[key]
        assert hashlib.sha256(payload).hexdigest() == digest and len(payload) == size
        return payload

    def publish_report(self, report_id, payload, digest):
        import hashlib
        assert hashlib.sha256(payload).hexdigest() == digest
        key = f"sha256/{digest}"
        self.objects[key] = payload
        return key

    def inspect_reconciliation(self, key, digest=None, size=None, creator=None):
        return "missing", None


def execution_manifest(tmp_path):
    import hashlib
    import io
    import zipfile
    from PIL import Image

    manifest = copy.deepcopy(EVALUATION)
    members = {}
    for frame in manifest["frames"]:
        ordinal = frame["ordinal"]
        image = io.BytesIO()
        Image.new("RGB", (2, 2), (ordinal * 17, 1, 2)).save(image, format="JPEG")
        for kind, payload in (("image", image.getvalue()), ("label", str(ordinal).encode())):
            item = frame[kind]
            item["sha256"] = hashlib.sha256(payload).hexdigest()
            item["size"] = len(payload)
            members[item["archive_member"]] = payload
    archive = tmp_path / "private.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name, payload in members.items():
            output.writestr(name, payload)
    manifest["source_archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    return manifest, archive


def test_historical_archive_rejects_late_member_mismatch(tmp_path):
    from app.application.executor import _verified_campaign_archive

    manifest, archive = execution_manifest(tmp_path)
    manifest["frames"][-1]["image"]["sha256"] = "f" * 64
    with archive.open("rb") as source:
        with pytest.raises(CampaignGateError, match="archive_content_mismatch"):
            _verified_campaign_archive(source, manifest)


def test_recovery_refuses_live_lease_even_without_provider(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    run_id = uuid.UUID(database.read_comparison_campaign(campaign)["cells"][0]["run_id"])
    with database.engine.begin() as connection:
        connection.execute(text("""UPDATE analysis_runs SET state = 'running',
            lease_owner = 'test-owner', lease_expires_at = clock_timestamp() + interval '1 hour'
            WHERE id = :run"""), {"run": run_id})
    with pytest.raises(CampaignGateError, match="campaign_ownership_uncertain"):
        database.recover_comparison_campaign(campaign)
    assert database.next_comparison_cell(campaign)["run_id"] == run_id
    database.fail_comparison_cell(run_id, "test_cleanup", "test-owner")


def test_terminal_campaign_outcome_and_evidence_cannot_change(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    run_id = uuid.UUID(database.read_comparison_campaign(campaign)["cells"][0]["run_id"])
    database.fail_comparison_cell(run_id, "test_failure")
    for statement in ("UPDATE analysis_runs SET error_code = 'other' WHERE id = :run",
                      "UPDATE analysis_runs SET retry_predecessor_id = gen_random_uuid() WHERE id = :run",
                      "INSERT INTO analysis_stages (run_id, ordinal, name, state) VALUES (:run, 0, 'input_registration', 'pending')",
                      "INSERT INTO result_projections (run_id, outcome, snapshot) VALUES (:run, 'observations_only', '{}'::jsonb)",
                      "INSERT INTO run_inputs (run_id, ordinal, sha256, size, context) VALUES (:run, 0, 'x', 1, '{}'::jsonb)",
                      "INSERT INTO publication_intents (id, run_id, idempotency_key, media_type, state) VALUES (gen_random_uuid(), :run, gen_random_uuid()::text, 'image/jpeg', 'pending_upload')"):
        with pytest.raises(Exception, match="comparison_(run|evidence|input)_immutable"):
            with database.engine.begin() as connection:
                connection.execute(text(statement), {"run": run_id})
    ordinary = uuid.uuid4()
    with database.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs (id, state, purpose) VALUES (:id, 'queued', 'ordinary')"),
                           {"id": ordinary})
    intent = database.create_publication_intent(ordinary, "image/jpeg", f"ordinary:{ordinary}")
    with pytest.raises(Exception, match="comparison_evidence_immutable"):
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE publication_intents SET run_id = :run WHERE id = :id"),
                               {"run": run_id, "id": intent})


def test_comparison_claim_and_success_require_complete_evidence(database, monkeypatch, tmp_path):
    from app.application.executor import _verified_campaign_archive

    campaign, archive, artifacts = historical_campaign_setup(database, monkeypatch, tmp_path)
    run_id = database.next_comparison_cell(campaign)["run_id"]
    with pytest.raises(CampaignGateError, match="campaign_inputs_incomplete"):
        database.claim_comparison_cell(run_id, 0)
    frame = database.read_comparison_campaign(campaign)["manifest"]["fixtures"][0]["frames"][0]
    with archive.open("rb") as source:
        image = _verified_campaign_archive(source, database.comparison_source(campaign))[frame["ordinal"]]
    database.publish_comparison_input(run_id, frame, image, artifacts)
    with pytest.raises(CampaignGateError, match="campaign_inputs_incomplete"):
        database.claim_comparison_cell(run_id, 0)
    work = database.claim_comparison_cell(run_id, 1)
    with pytest.raises(Exception, match="comparison_evidence_incomplete"):
        with database.engine.begin() as connection:
            connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL,
                lease_expires_at = NULL WHERE id = :run"""), {"run": run_id})
    classes = database.read_comparison_campaign(campaign)["manifest"]["fixtures"][0]["requested_classes"]
    frames = [{"input_id": str(work["frames"][0]["input_id"]), "class_name": class_name,
               "state": "not_detected_in_frame", "source_artifact_id": str(work["frames"][0]["artifact_id"]),
               "invocation_id": None} for class_name in classes]
    with database.engine.begin() as connection:
        connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run"),
                           {"run": run_id})
        for observation in frames:
            connection.execute(text("""INSERT INTO observations
                (run_id, input_id, class_name, state, input_sha256, source_artifact_id)
                VALUES (:run, :input, :class_name, :state, :hash, :artifact)"""),
                {"run": run_id, "input": work["frames"][0]["input_id"],
                 "class_name": observation["class_name"], "state": observation["state"],
                 "hash": frame["image"]["sha256"], "artifact": work["frames"][0]["artifact_id"]})
        connection.execute(text("""INSERT INTO result_projections (run_id, outcome, snapshot)
            VALUES (:run, 'observations_only', CAST(:snapshot AS jsonb))"""),
            {"run": run_id, "snapshot": json.dumps({"outcome": "observations_only", "frames": frames})})
    with pytest.raises(Exception, match="comparison_evidence_incomplete"):
        with database.engine.begin() as connection:
            connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL,
                lease_expires_at = NULL WHERE id = :run"""), {"run": run_id})
    assert database.read_comparison_campaign(campaign)["cells"][0]["state"] == "running"
    database.fail_comparison_cell(run_id, "test_cleanup", work["owner"])


def test_comparison_failure_method_rejects_ordinary_run(database):
    run_id = uuid.uuid4()
    with database.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs (id, state, purpose) VALUES (:id, 'queued', 'ordinary')"),
                           {"id": run_id})
    with pytest.raises(CampaignGateError, match="campaign_cell_missing"):
        database.fail_comparison_cell(run_id, "wrong_run")
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT state FROM analysis_runs WHERE id = :run"),
                                  {"run": run_id}).scalar_one() == "queued"


def test_comparison_claim_rejects_partial_multiframe_fixture(database, monkeypatch, tmp_path):
    from app.application.executor import _verified_campaign_archive

    campaign, archive, artifacts = historical_campaign_setup(database, monkeypatch, tmp_path)
    readback = database.read_comparison_campaign(campaign)
    fixture = next(f for f in readback["manifest"]["fixtures"] if len(f["frames"]) > 1)
    target = next(cell for cell in readback["cells"] if cell["fixture_ordinal"] == fixture["ordinal"])
    for cell in readback["cells"][:readback["cells"].index(target)]:
        database.fail_comparison_cell(uuid.UUID(cell["run_id"]), "test_preceding_cell_failed")
    with archive.open("rb") as source:
        images = _verified_campaign_archive(source, database.comparison_source(campaign))
    frame = fixture["frames"][0]
    database.publish_comparison_input(uuid.UUID(target["run_id"]), frame, images[frame["ordinal"]], artifacts)
    with pytest.raises(CampaignGateError, match="campaign_inputs_incomplete"):
        database.claim_comparison_cell(uuid.UUID(target["run_id"]), 1)
    database.fail_comparison_cell(uuid.UUID(target["run_id"]), "test_cleanup")


def test_completed_invocation_is_immutable_while_campaign_still_running(database, monkeypatch, tmp_path):
    from app.application.executor import _verified_campaign_archive

    campaign, archive, artifacts = historical_campaign_setup(database, monkeypatch, tmp_path)
    cell = database.next_comparison_cell(campaign)
    frame = database.read_comparison_campaign(campaign)["manifest"]["fixtures"][0]["frames"][0]
    with archive.open("rb") as source:
        image = _verified_campaign_archive(source, database.comparison_source(campaign))[frame["ordinal"]]
    database.publish_comparison_input(cell["run_id"], frame, image, artifacts)
    work = database.claim_comparison_cell(cell["run_id"], 1)
    invocation = uuid.uuid4()
    with database.engine.begin() as connection:
        connection.execute(text("""UPDATE analysis_runs SET provider_safe_after = clock_timestamp() + interval '1 minute'
            WHERE id = :run"""), {"run": work["id"]})
        connection.execute(text("""INSERT INTO observer_invocations
            (id, run_id, input_id, fence, profile_id, authorization_revision, stage_ordinal,
             input_sha256, intended_request_identity, state, provider_settled_at)
            SELECT :id, id, :input, 1, profile_id, authorization_revision, 2,
                   :hash, 'historical-request', 'completed', clock_timestamp()
            FROM analysis_runs WHERE id = :run"""),
            {"id": invocation, "run": work["id"], "input": work["frames"][0]["input_id"],
             "hash": frame["image"]["sha256"]})
        connection.execute(text("UPDATE analysis_runs SET provider_safe_after = clock_timestamp() WHERE id = :run"),
                           {"run": work["id"]})
    for statement in ("UPDATE observer_invocations SET returned_model_identity = 'changed' WHERE id = :id",
                      "DELETE FROM observer_invocations WHERE id = :id"):
        with pytest.raises(Exception, match="comparison_invocation_immutable"):
            with database.engine.begin() as connection:
                connection.execute(text(statement), {"id": invocation})
    with database.engine.begin() as connection:
        connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run"),
                           {"run": work["id"]})
        for class_name in ("excavator", "crane"):
            connection.execute(text("""INSERT INTO observations
                (run_id, input_id, class_name, state, input_sha256, invocation_id, source_artifact_id)
                VALUES (:run, :input, :class_name, 'not_detected_in_frame', :hash, :invocation, :artifact)"""),
                {"run": work["id"], "input": work["frames"][0]["input_id"],
                 "class_name": class_name, "hash": frame["image"]["sha256"],
                 "invocation": invocation, "artifact": work["frames"][0]["artifact_id"]})
        connection.execute(text("""INSERT INTO result_projections (run_id, outcome, snapshot)
            VALUES (:run, 'observations_only', '{}'::jsonb)"""), {"run": work["id"]})
    with pytest.raises(Exception, match="comparison_evidence_incomplete"):
        with database.engine.begin() as connection:
            connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL,
                lease_expires_at = NULL WHERE id = :run"""), {"run": work["id"]})
    with database.engine.begin() as connection:
        connection.execute(text("""UPDATE observations SET class_name = 'dump_truck'
            WHERE run_id = :run AND class_name = 'crane'"""), {"run": work["id"]})
        frames = [{"input_id": str(work["frames"][0]["input_id"]), "class_name": class_name,
                   "state": "not_detected_in_frame", "source_artifact_id": str(work["frames"][0]["artifact_id"]),
                   "invocation_id": str(invocation)} for class_name in ("excavator", "dump_truck")]
        connection.execute(text("""UPDATE result_projections SET snapshot = CAST(:snapshot AS jsonb)
            WHERE run_id = :run"""),
            {"run": work["id"], "snapshot": json.dumps({"outcome": "observations_only", "frames": frames})})
    with pytest.raises(Exception, match="comparison_evidence_incomplete"):
        with database.engine.begin() as connection:
            connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL,
                lease_expires_at = NULL WHERE id = :run"""), {"run": work["id"]})
    database.fail_comparison_cell(work["id"], "test_cleanup", work["owner"])


def test_timeout_accounting_keeps_manifest_denominator(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    cells = database.read_comparison_campaign(campaign)["cells"]
    database.fail_comparison_cell(uuid.UUID(cells[0]["run_id"]), "observer_timeout")
    database.fail_comparison_cell(uuid.UUID(cells[1]["run_id"]), "artifact_publication_failed")
    assert database.read_comparison_campaign(campaign)["accounting"] == {
        "planned": 36, "succeeded": 0, "failed": 1, "timed_out": 1, "missing": 34}


def test_ordinary_maintenance_ignores_running_campaign_and_pending_input(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    run_id = uuid.UUID(database.read_comparison_campaign(campaign)["cells"][0]["run_id"])
    intent = database.create_publication_intent(run_id, "image/jpeg", f"comparison:{run_id}:input:0")
    with database.engine.begin() as connection:
        connection.execute(text("""UPDATE analysis_runs SET state = 'running', lease_owner = 'expired-owner',
            lease_expires_at = clock_timestamp() - interval '1 second' WHERE id = :run"""),
            {"run": run_id})
    assert database.recover() == 0
    database.reconcile(MemoryArtifacts(), runtime=True)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT state FROM analysis_runs WHERE id = :run"),
                                  {"run": run_id}).scalar_one() == "running"
        assert connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"),
                                  {"id": intent}).scalar_one() == "pending_upload"
    assert database.recover_comparison_campaign(campaign) == 1


def test_input_publication_adopts_stable_intent_after_restart(database, monkeypatch, tmp_path):
    from app.application.executor import _verified_campaign_archive

    manifest, archive = execution_manifest(tmp_path)
    revision, local_id, cloud_id, local, cloud = seed(database, manifest)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    run_id = uuid.UUID(database.read_comparison_campaign(campaign)["cells"][0]["run_id"])
    frame = database.read_comparison_campaign(campaign)["manifest"]["fixtures"][0]["frames"][0]
    with archive.open("rb") as source:
        image = _verified_campaign_archive(source, database.comparison_source(campaign))[frame["ordinal"]]
    artifacts = MemoryArtifacts()
    key = f"comparison:{run_id}:input:{frame['ordinal']}"
    intent = database.create_publication_intent(run_id, "image/jpeg", key)
    _, digest, size = artifacts.upload_temporary(intent, image, "image/jpeg")
    database.publication_content_verified(intent, digest, size, f"sha256/{digest}")
    database.publish_comparison_input(run_id, frame, image, artifacts)
    database.publish_comparison_input(run_id, frame, image, artifacts)
    assert artifacts.uploads == [intent]
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM run_inputs WHERE run_id = :run"),
                                  {"run": run_id}).scalar_one() == 1
        assert connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"),
                                  {"id": intent}).scalar_one() == "referenced"


def test_campaign_cli_startup_and_accounting_errors_are_json(database, monkeypatch, capsys):
    import sys
    from app.application import evaluation

    monkeypatch.setenv("DATABASE_URL", "invalid")
    monkeypatch.setattr(sys, "argv", ["evidence-evaluation", "campaign-accounting",
                                      "--campaign", str(uuid.uuid4())])
    with pytest.raises(SystemExit) as exit_info:
        evaluation.main()
    assert exit_info.value.code == 1
    assert json.loads(capsys.readouterr().out) == {"status": "rejected",
                                                   "error": "invalid_database_dialect"}
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    monkeypatch.setenv("DATABASE_URL", database.engine.url.render_as_string(hide_password=False))
    monkeypatch.setattr(sys, "argv", ["evidence-evaluation", "campaign-accounting",
                                      "--campaign", str(campaign)])
    evaluation.main()
    assert json.loads(capsys.readouterr().out) == {"planned": 36, "succeeded": 0,
                                                   "failed": 0, "timed_out": 0, "missing": 36}
    monkeypatch.setattr(sys, "argv", ["evidence-evaluation", "read-campaign",
                                      "--campaign", str(campaign)])
    evaluation.main()
    readback = json.loads(capsys.readouterr().out)
    assert len(readback["cells"]) == 36
    assert readback["accounting"]["planned"] == 36


def test_revocation_winning_row_lock_prevents_byte_publication(database, monkeypatch, tmp_path):
    import threading
    import time
    from app.application.executor import _verified_campaign_archive

    manifest, archive = execution_manifest(tmp_path)
    revision, local_id, cloud_id, local, cloud = seed(database, manifest)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    run_id = uuid.UUID(database.read_comparison_campaign(campaign)["cells"][0]["run_id"])
    frame = database.read_comparison_campaign(campaign)["manifest"]["fixtures"][0]["frames"][0]
    with archive.open("rb") as source:
        image = _verified_campaign_archive(source, database.comparison_source(campaign))[frame["ordinal"]]
    artifacts = MemoryArtifacts()
    attempted = threading.Event()

    def publish():
        attempted.set()
        database.publish_comparison_input(run_id, frame, image, artifacts)

    with ThreadPoolExecutor(max_workers=1) as pool:
        connection = database.engine.connect()
        transaction = connection.begin()
        try:
            connection.execute(text("UPDATE profile_authorizations SET state = 'revoked' WHERE profile_id = :id"),
                               {"id": local_id})
            future = pool.submit(publish)
            assert attempted.wait(2)
            time.sleep(0.1)
            assert not future.done()
            assert artifacts.uploads == []
            transaction.commit()
            with pytest.raises(CampaignGateError, match="profile_unauthorized"):
                future.result(timeout=5)
            assert artifacts.uploads == []
        finally:
            if transaction.is_active:
                transaction.rollback()
            connection.close()


def test_claim_requires_first_unfinished_tuple(database, monkeypatch, tmp_path):
    from app.application.executor import _verified_campaign_archive

    manifest, archive = execution_manifest(tmp_path)
    revision, local_id, cloud_id, local, cloud = seed(database, manifest)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    readback = database.read_comparison_campaign(campaign)
    first, later = (uuid.UUID(c["run_id"]) for c in readback["cells"][:2])
    frame = readback["manifest"]["fixtures"][0]["frames"][0]
    with archive.open("rb") as source:
        image = _verified_campaign_archive(source, database.comparison_source(campaign))[frame["ordinal"]]
    database.publish_comparison_input(later, frame, image, MemoryArtifacts())
    with pytest.raises(CampaignGateError, match="campaign_cell_out_of_order"):
        database.claim_comparison_cell(later, 1)
    assert database.next_comparison_cell(campaign)["run_id"] == first
    database.fail_comparison_cell(first, "test_failure")
    work = database.claim_comparison_cell(later, 1)
    assert work["id"] == later
    database.fail_comparison_cell(later, "test_cleanup", work["owner"])


def test_attached_campaign_publication_is_immutable(database, monkeypatch, tmp_path):
    from app.application.executor import _verified_campaign_archive

    manifest, archive = execution_manifest(tmp_path)
    revision, local_id, cloud_id, local, cloud = seed(database, manifest)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    readback = database.read_comparison_campaign(campaign)
    run_id = uuid.UUID(readback["cells"][0]["run_id"])
    frame = readback["manifest"]["fixtures"][0]["frames"][0]
    with archive.open("rb") as source:
        image = _verified_campaign_archive(source, database.comparison_source(campaign))[frame["ordinal"]]
    database.publish_comparison_input(run_id, frame, image, MemoryArtifacts())
    with database.engine.connect() as connection:
        artifact, intent = connection.execute(text("SELECT id, intent_id FROM artifact_metadata WHERE run_id = :run"),
                                              {"run": run_id}).one()
    ordinary = uuid.uuid4()
    with database.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs (id, state, purpose) VALUES (:run, 'queued', 'ordinary')"),
                           {"run": ordinary})
    for statement in (
        "UPDATE publication_intents SET state = 'quarantined' WHERE id = :intent",
        "UPDATE publication_intents SET sha256 = 'changed' WHERE id = :intent",
        "UPDATE publication_intents SET run_id = :ordinary WHERE id = :intent",
        "DELETE FROM publication_intents WHERE id = :intent",
        "UPDATE artifact_metadata SET size = size + 1 WHERE id = :artifact",
        "DELETE FROM artifact_metadata WHERE id = :artifact",
    ):
        with pytest.raises(Exception, match="comparison_evidence_immutable"):
            with database.engine.begin() as connection:
                connection.execute(text(statement), {"intent": intent, "artifact": artifact, "ordinary": ordinary})
    work = database.claim_comparison_cell(run_id, 1)
    with pytest.raises(Exception, match="comparison_evidence_immutable"):
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE publication_intents SET state = 'pending_upload' WHERE id = :intent"),
                               {"intent": intent})
    database.fail_comparison_cell(run_id, "test_cleanup", work["owner"])


@pytest.mark.parametrize("wrong_owner", [False, True])
def test_campaign_input_requires_matching_published_intent(database, monkeypatch, wrong_owner):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    readback = database.read_comparison_campaign(campaign)
    run_id = uuid.UUID(readback["cells"][0]["run_id"])
    other_run = uuid.UUID(readback["cells"][1]["run_id"])
    frame = readback["manifest"]["fixtures"][0]["frames"][0]
    intent, artifact = uuid.uuid4(), uuid.uuid4()
    with database.engine.begin() as connection:
        connection.execute(text("""INSERT INTO publication_intents
            (id, run_id, idempotency_key, media_type, state, sha256, size, final_key)
            VALUES (:id, :run, :key, 'image/jpeg', :state, :hash, :size, :final)"""),
            {"id": intent, "run": other_run if wrong_owner else run_id, "key": str(intent),
             "state": "object_published" if wrong_owner else "pending_upload",
             "hash": frame["image"]["sha256"], "size": frame["image"]["size"],
             "final": f"sha256/{frame['image']['sha256']}"})
        connection.execute(text("""INSERT INTO artifact_metadata
            (id, run_id, intent_id, key, sha256, size, media_type)
            VALUES (:id, :run, :intent, :key, :hash, :size, 'image/jpeg')"""),
            {"id": artifact, "run": run_id, "intent": intent, "key": f"sha256/{frame['image']['sha256']}",
             "hash": frame["image"]["sha256"], "size": frame["image"]["size"]})
    with pytest.raises(Exception, match="comparison_input_mismatch"):
        with database.engine.begin() as connection:
            connection.execute(text("""INSERT INTO run_inputs (run_id, ordinal, sha256, size, context, artifact_id)
                VALUES (:run, :ordinal, :hash, :size, CAST(:context AS jsonb), :artifact)"""),
                {"run": run_id, "ordinal": frame["ordinal"], "hash": frame["image"]["sha256"],
                 "size": frame["image"]["size"], "context": json.dumps(frame["context"]), "artifact": artifact})


def test_execute_cli_rejects_retired_campaign_before_reading_archive(database, monkeypatch, tmp_path, capsys):
    import sys
    from app.application import evaluation

    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    artifacts = MemoryArtifacts()
    monkeypatch.setattr(evaluation, "PostgresStore", lambda url: database)
    monkeypatch.setattr(evaluation, "ArtifactStore", lambda config: artifacts)
    monkeypatch.setattr(evaluation.Config, "database_url_from_env", lambda: database.engine.url.render_as_string(hide_password=False))
    monkeypatch.setattr(evaluation.Config, "from_env", classmethod(lambda cls: type("ConfigStub", (), {
        "observer_snapshot_dir": None})()))
    monkeypatch.setattr(sys, "argv", ["evidence-evaluation", "execute-campaign", "--campaign", str(campaign),
                                      "--archive", str(tmp_path / "absent.zip")])
    with pytest.raises(SystemExit) as error:
        evaluation.main()
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out) == {"status": "rejected", "error": "profile_retired"}
    assert artifacts.uploads == []
    assert database.read_comparison_campaign(campaign)["accounting"]["missing"] == 36


def historical_campaign_setup(database, monkeypatch, tmp_path):
    manifest, archive = execution_manifest(tmp_path)
    revision, local_id, cloud_id, local, cloud = seed(database, manifest)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    return campaign, archive, MemoryArtifacts()


def test_empty_database_downgrade_requires_forward_migration(isolated_campaign_database):
    from alembic import command
    from alembic.config import Config as AlembicConfig

    database = isolated_campaign_database
    migrations = AlembicConfig(str(ROOT / "backend/alembic.ini"))
    with pytest.raises(RuntimeError, match="deepseek_evidence_preservation_requires_forward_migration"):
        command.downgrade(migrations, "0010_comparison_campaign")
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0022_deepseek"


@pytest.mark.parametrize("recover", [False, True])
def test_incomplete_native_intent_is_quarantined_on_cell_failure(database, monkeypatch, recover):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_historical_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    campaign = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    run_id = database.next_comparison_cell(campaign)["run_id"]
    intent = database.create_publication_intent(run_id, "application/json", f"{run_id}:native")
    with database.engine.begin() as connection:
        connection.execute(text("""UPDATE analysis_runs SET state = 'running', lease_owner = 'test-owner',
            lease_expires_at = clock_timestamp() + (:seconds * interval '1 second') WHERE id = :run"""),
            {"run": run_id, "seconds": -1 if recover else 60})
    if recover:
        assert database.recover_comparison_campaign(campaign) == 1
    else:
        database.fail_comparison_cell(run_id, "native_publication_failed", "test-owner")
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"),
                                  {"id": intent}).scalar_one() == "quarantined"
    assert database.read_comparison_campaign(campaign)["cells"][0]["state"] == "failed"
