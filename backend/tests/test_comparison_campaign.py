import copy
import json
import math
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from app.adapters.postgres import AdmissionStoreError
from app.domain.comparison_campaign import CampaignGateError, build_manifest
from app.domain.evaluation_set import canonical_hash
from app.profiles import cloud_api, grounding_dino
from test_startup import database


ROOT = Path(__file__).resolve().parents[2]
EVALUATION = json.loads((ROOT / "evaluation/held-out-v1.json").read_text())


def profiles(manifest=EVALUATION):
    hashes = [frame["image"]["sha256"] for frame in manifest["frames"]]
    local = {"kind": "local_process", "adapter": {"code": "grounding_dino"},
        "requested_model_identity": {"id": grounding_dino.MODEL_ID, "revision": grounding_dino.MODEL_REVISION},
        "runtime": {"os": "Darwin", "architecture": "arm64", "device": "cpu", "cpu_cores": 12,
                    "memory_bytes": 36 * 1024**3, "driver": "PyTorch CPU", "concurrency": 1,
                    "sdk_retries": 0, "per_image_timeout_seconds": 60, "batch_timeout_seconds": 600}}
    cloud = {"kind": "cloud_api", "adapter": {"code": "yandex_ai_studio"},
        "folder_id": "test-folder", "requested_model_identity": {"id": f"gpt://test-folder/{cloud_api.MODEL}"},
        "runtime": {"concurrency": 1, "sdk_retries": 0,
                    "per_image_timeout_seconds": 60, "batch_timeout_seconds": 600},
        "allowed_input_sha256": sorted(set(hashes)), "audit_run_ids": []}
    return local, cloud


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


def patch_admission(monkeypatch, database, local_id, cloud_id, local, cloud):
    def authorized(_, profile_id, expected_revision=None):
        return ({local_id: local, cloud_id: cloud}[profile_id], 1)
    monkeypatch.setattr(database, "_require_authorized", authorized)



def admit_for_test(database, profile_id, snapshot, *, expired=False, uncovered=False):
    from app.profiles.grounding_dino import canonical_bytes, digest

    run_id, input_id = uuid.uuid4(), uuid.uuid4()
    canary_hash = "f" * 64
    cloud = snapshot["kind"] == "cloud_api"
    identity = snapshot["requested_model_identity"]["id"]
    module = cloud_api if cloud else grounding_dino
    snapshot["adapter"]["bundle_sha256"] = digest(Path(module.__file__).read_bytes())
    snapshot["runtime"]["uv_lock_sha256"] = digest((ROOT / "backend/uv.lock").read_bytes())
    snapshot["runtime"]["device"] = "remote_unreported" if cloud else "cpu"
    snapshot["audit_run_ids"] = [str(run_id)]
    snapshot["audit_report"] = {"run_ids": [str(run_id)]}
    snapshot["returned_model_identity"] = identity
    if cloud:
        allowed = sorted(set(snapshot["allowed_input_sha256"] + [canary_hash]))
        if uncovered:
            allowed.remove(snapshot["allowed_input_sha256"][0])
        snapshot["allowed_input_sha256"] = allowed
        snapshot["owner_evidence"] = {
            "account_id": "test-account", "cloud_id": "test-cloud", "folder_id": "test-folder",
            "service_account_id": "test-service", "api_key_id": "test-key",
            "checked_at": (datetime.now(timezone.utc) - timedelta(days=2 if expired else 0)).isoformat(),
            "paid_account": True, "folder_status": "ACTIVE", "service_account_status": "ACTIVE",
            "api_key_scope": "yc.ai.foundationModels.execute", "model_probe_response_id": "test-response",
            "model_probe_returned_uri": identity,
            "model_probe_states": {"excavator": "not_detected_in_frame",
                                   "dump_truck": "not_detected_in_frame"},
            "model_probe_request_data_controls": {"store": False, "x-data-logging-enabled": "false"},
            "authorization_revision": cloud_api.OWNER_DECISION_REVISION,
            "canary_image_sha256": [canary_hash], "allowed_image_sha256": allowed,
        }
    audit_hash = digest(canonical_bytes(snapshot["audit_report"]))
    with database.engine.begin() as connection:
        parent = connection.execute(text("SELECT parent_id FROM observer_profiles WHERE id = :id"),
                                    {"id": profile_id}).scalar_one()
        connection.execute(text("""UPDATE observer_profiles SET snapshot = CAST(:snapshot AS jsonb),
            profile_hash = :hash, audit_hash = :audit WHERE id = :id"""),
            {"id": profile_id, "snapshot": json.dumps(snapshot),
             "hash": digest(canonical_bytes(snapshot)), "audit": audit_hash})
        connection.execute(text("UPDATE profile_authorizations SET audit_hash = :audit WHERE profile_id = :id"),
                           {"id": profile_id, "audit": audit_hash})
        connection.execute(text("""INSERT INTO analysis_runs (id, state, purpose, profile_id)
            VALUES (:id, 'succeeded', 'profile_admission', :parent)"""),
            {"id": run_id, "parent": parent})
        connection.execute(text("""INSERT INTO run_inputs (run_id, ordinal, fixture_id, sha256, size, context, input_id)
            VALUES (:run, 0, 'canary', :hash, 1, '{}'::jsonb, :input)"""),
            {"run": run_id, "hash": canary_hash, "input": input_id})
        connection.execute(text("""INSERT INTO observer_invocations
            (id, run_id, fence, profile_id, stage_ordinal, input_sha256,
             intended_request_identity, returned_model_identity, actual_device, state, input_id)
            VALUES (:id, :run, 1, :parent, 2, :hash, 'requested', :identity,
                    :device, 'completed', :input)"""),
            {"id": uuid.uuid4(), "run": run_id, "parent": parent, "hash": canary_hash,
             "identity": identity, "device": "remote_unreported" if cloud else "cpu", "input": input_id})
        connection.execute(text("""INSERT INTO result_projections (run_id, outcome, snapshot)
            VALUES (:run, 'observations_only', '{}'::jsonb)"""), {"run": run_id})
    return snapshot


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
    patch_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
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
    patch_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    cells = database.read_comparison_campaign(database.freeze_comparison_campaign(revision, local_id, cloud_id))["cells"]
    assert cells[0]["run_id"] != cells[2]["run_id"]
    assert cells[0]["fixture_ordinal"] == 0 and cells[2]["fixture_ordinal"] == 1


def test_real_admission_gate_rejects_unauthorized_profile_without_cells(database):
    revision, local_id, cloud_id, _, _ = seed(database)
    with pytest.raises(AdmissionStoreError, match="profile_admission_evidence_missing"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM comparison_cells c JOIN comparison_campaigns p ON p.id = c.campaign_id WHERE p.evaluation_revision_id = :id"),
                                  {"id": revision}).scalar_one() == 0


def test_decision_hash_mismatch_rolls_back(database, monkeypatch):
    manifest = copy.deepcopy(EVALUATION)
    manifest["frames"][0]["sufficiency_notes"] = str(uuid.uuid4())
    revision, local_id, cloud_id, local, cloud = seed(database, manifest, "wrong")
    patch_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
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
    with pytest.raises(AdmissionStoreError, match="profile_unauthorized"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    patch_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
    cloud["allowed_input_sha256"].pop()
    with pytest.raises(CampaignGateError, match="cloud_image_not_authorized"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM comparison_campaigns WHERE evaluation_revision_id = :id"),
                                  {"id": revision}).scalar_one() == 0


def test_concurrent_freeze_is_single_complete_revision(database, monkeypatch):
    revision, local_id, cloud_id, local, cloud = seed(database)
    patch_admission(monkeypatch, database, local_id, cloud_id, local, cloud)

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
    admit_for_test(database, local_id, local)
    admit_for_test(database, cloud_id, cloud)
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
    patch_admission(monkeypatch, database, local_id, cloud_id, local, cloud)
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

    monkeypatch.setattr(evaluation.Config, "database_url_from_env", lambda: str(database.engine.url))
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


def test_expired_cloud_evidence_is_rejected_by_real_gate(database):
    revision, local_id, cloud_id, local, cloud = seed(database)
    admit_for_test(database, local_id, local)
    admit_for_test(database, cloud_id, cloud, expired=True)
    with pytest.raises(AdmissionStoreError, match="profile_owner_evidence_expired"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    evidence = cloud["owner_evidence"]
    current = {**evidence, "checked_at": datetime.now(timezone.utc).isoformat()}
    cloud_api.validate_owner_evidence(current, ["f" * 64], cloud["allowed_input_sha256"])
    with pytest.raises(cloud_api.CloudObserverError, match="cloud_account_evidence_stale"):
        cloud_api.validate_owner_evidence(evidence, ["f" * 64], cloud["allowed_input_sha256"])
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM comparison_campaigns WHERE evaluation_revision_id = :id"),
                                  {"id": revision}).scalar_one() == 0


def test_downgrade_refuses_planned_campaign_and_keeps_evidence(database, monkeypatch):
    from alembic import command
    from alembic.config import Config as AlembicConfig

    revision, local_id, cloud_id, local, cloud = seed(database)
    admit_for_test(database, local_id, local)
    admit_for_test(database, cloud_id, cloud)
    campaign_id = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    assert len(database.read_comparison_campaign(campaign_id)["cells"]) == 36
    monkeypatch.setenv("DATABASE_URL", str(database.engine.url))
    with pytest.raises(RuntimeError, match="comparison_campaign_evidence_exists"):
        command.downgrade(AlembicConfig(str(ROOT / "backend/alembic.ini")), "0009_evaluation_set")
    assert len(database.read_comparison_campaign(campaign_id)["cells"]) == 36


def test_real_admitted_pair_freezes_complete_campaign(database):
    revision, local_id, cloud_id, local, cloud = seed(database)
    admit_for_test(database, local_id, local)
    admit_for_test(database, cloud_id, cloud)
    campaign_id = database.freeze_comparison_campaign(revision, local_id, cloud_id)
    result = database.read_comparison_campaign(campaign_id)
    assert len(result["cells"]) == 36
    assert all(cell["state"] == "planned" for cell in result["cells"])
    assert result["manifest"]["candidates"][0]["profile_id"] == str(local_id)
    assert result["manifest"]["candidates"][1]["profile_id"] == str(cloud_id)


def test_real_cloud_scope_missing_frame_rejected(database):
    revision, local_id, cloud_id, local, cloud = seed(database)
    admit_for_test(database, local_id, local)
    admit_for_test(database, cloud_id, cloud, uncovered=True)
    with pytest.raises(CampaignGateError, match="cloud_image_not_authorized"):
        database.freeze_comparison_campaign(revision, local_id, cloud_id)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM comparison_campaigns WHERE evaluation_revision_id = :id"),
                                  {"id": revision}).scalar_one() == 0


def test_successful_freeze_campaign_cli_uses_real_admission(database, monkeypatch, capsys):
    import sys
    from app.application import evaluation

    revision, local_id, cloud_id, local, cloud = seed(database)
    admit_for_test(database, local_id, local)
    admit_for_test(database, cloud_id, cloud)
    monkeypatch.setattr(evaluation.Config, "database_url_from_env", lambda: str(database.engine.url))
    monkeypatch.setattr(sys, "argv", ["evidence-evaluation", "freeze-campaign",
        "--evaluation-revision", str(revision), "--local-profile", str(local_id),
        "--cloud-profile", str(cloud_id)])
    evaluation.main()
    result = json.loads(capsys.readouterr().out)
    assert uuid.UUID(result["id"])
    assert len(result["cells"]) == 36
    assert result["evaluation_revision_id"] == str(revision)
