from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import fcntl
import hashlib
import json
import math
import tempfile
import uuid
from pathlib import Path
from time import monotonic

from app.domain.observations import CLASSES, STAGES, normalized_states
from app.domain.evaluation_set import inspect_evaluation_set, reserve_held_out_inventory, canonical_hash
from app.domain.comparison_campaign import CampaignGateError, build_manifest
from app.profiles import cloud_api, grounding_dino
from app.profiles.grounding_dino import canonical_bytes, digest
from app.adapters.artifacts import ArtifactGateError, ArtifactStore
from app.domain.rule import RULE, RULE_POLICY, evaluate_rule


class DatabaseGateError(RuntimeError):
    pass


class ReconciliationGateError(RuntimeError):
    pass


class RecoveryGateError(RuntimeError):
    pass


class AdmissionStoreError(RuntimeError):
    pass


class EvaluationStoreError(RuntimeError):
    pass


LOCK_ID = 804298270113


class PostgresStore:
    def __init__(self, url: str):
        self.engine: Engine = create_engine(url, pool_pre_ping=True,
            connect_args={"connect_timeout": 5, "options": "-c statement_timeout=30000 -c lock_timeout=5000"})

    def close(self) -> None:
        self.engine.dispose()

    def freeze_evaluation_set(self, manifest_path: Path, archive_path: Path, inventory_paths: list[Path],
                              contract_path: Path, admission_path: Path, historical_path: Path) -> tuple[dict, uuid.UUID | None]:
        held_out = next((path for path in inventory_paths if path.stem == "held_out_evaluation"), None)
        lock_target = held_out or manifest_path
        lock_name = hashlib.sha256(str(lock_target.resolve()).encode()).hexdigest()[:24]
        lock_path = Path(tempfile.gettempdir()) / f"evaluation-inventory-{lock_name}.lock"
        with lock_path.open("a+b") as file_lock:
            fcntl.flock(file_lock, fcntl.LOCK_EX)
            with self.engine.begin() as connection:
                connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": LOCK_ID + 1})
                decision = inspect_evaluation_set(manifest_path, archive_path, inventory_paths,
                                                  contract_path, admission_path, historical_path)
                if decision["status"] == "accepted":
                    # Reserve before commit: a failed insert leaves a conservative exclusion, never an exposed fixture.
                    reserve_held_out_inventory(held_out, decision["manifest"], decision["manifest_hash"])
                revision_id = self._record_evaluation_decision(connection, decision)
        return decision, revision_id

    def _record_evaluation_decision(self, connection, decision: dict) -> uuid.UUID | None:
        """Persist a byte-free rejection or atomically append a frozen revision."""
        revision_id = None
        if decision["status"] == "accepted":
            if decision.get("errors") or not decision.get("manifest"):
                raise EvaluationStoreError("evaluation_decision_invalid")
            if connection.execute(text("SELECT 1 FROM evaluation_set_revisions WHERE manifest_hash = :hash"),
                                  {"hash": decision["manifest_hash"]}).first():
                raise EvaluationStoreError("evaluation_revision_already_frozen")
            revision_id = uuid.uuid4()
            connection.execute(text("""INSERT INTO evaluation_set_revisions
                (id, revision_number, manifest_hash, manifest, inventory_evidence)
                VALUES (:id, (SELECT coalesce(max(revision_number), 0) + 1 FROM evaluation_set_revisions),
                        :hash, CAST(:manifest AS jsonb), CAST(:evidence AS jsonb))"""),
                {"id": revision_id, "hash": decision["manifest_hash"],
                 "manifest": json.dumps(decision["manifest"]),
                 "evidence": json.dumps(decision["inventory_evidence"])})
        connection.execute(text("""INSERT INTO evaluation_freeze_decisions
            (id, revision_id, manifest_hash, status, inventory_evidence, errors)
            VALUES (:id, :revision, :hash, :status, CAST(:evidence AS jsonb), CAST(:errors AS jsonb))"""),
            {"id": uuid.uuid4(), "revision": revision_id, "hash": decision["manifest_hash"],
             "status": decision["status"], "evidence": json.dumps(decision["inventory_evidence"]),
             "errors": json.dumps(decision["errors"])})
        return revision_id

    def freeze_comparison_campaign(self, evaluation_revision_id: uuid.UUID,
                                   local_profile_id: uuid.UUID, cloud_profile_id: uuid.UUID) -> uuid.UUID:
        with self.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": LOCK_ID + 2})
            evaluation = connection.execute(text("""SELECT manifest, manifest_hash FROM evaluation_set_revisions
                WHERE id = :id FOR SHARE"""), {"id": evaluation_revision_id}).one_or_none()
            if not evaluation:
                raise CampaignGateError("evaluation_revision_missing")
            if not connection.execute(text("""SELECT 1 FROM evaluation_freeze_decisions
                WHERE revision_id = :id AND status = 'accepted' AND manifest_hash = :hash"""),
                {"id": evaluation_revision_id, "hash": evaluation.manifest_hash}).first():
                raise CampaignGateError("evaluation_decision_mismatch")
            local, local_revision = self._require_authorized(connection, local_profile_id)
            cloud, cloud_revision = self._require_authorized(connection, cloud_profile_id)
            manifest = build_manifest(evaluation.manifest, local, cloud)
            hashes = [frame["image"]["sha256"] for fixture in manifest["fixtures"] for frame in fixture["frames"]]
            canary_hashes = [item.sha256 for item in connection.execute(text(
                "SELECT sha256 FROM run_inputs WHERE run_id = ANY(:ids)"),
                {"ids": [uuid.UUID(value) for value in cloud["audit_run_ids"]]}).all()]
            if sorted(cloud.get("allowed_input_sha256", [])) != sorted(set(canary_hashes + hashes)):
                raise CampaignGateError("cloud_image_not_authorized")
            for candidate, profile_id, revision in zip(manifest["candidates"],
                    (local_profile_id, cloud_profile_id), (local_revision, cloud_revision)):
                candidate["profile_id"] = str(profile_id)
                candidate["authorization_revision"] = revision
                candidate["profile_hash"] = digest(canonical_bytes(candidate["snapshot"]))
            manifest["evaluation_revision_id"] = str(evaluation_revision_id)
            manifest["evaluation_manifest_hash"] = evaluation.manifest_hash
            manifest_hash = canonical_hash(manifest)
            if connection.execute(text("SELECT 1 FROM comparison_campaigns WHERE manifest_hash = :hash"),
                                  {"hash": manifest_hash}).first():
                raise CampaignGateError("campaign_already_frozen")
            campaign_id = uuid.uuid4()
            connection.execute(text("""INSERT INTO comparison_campaigns
                (id, revision_number, evaluation_revision_id, manifest_hash, manifest)
                VALUES (:id, (SELECT coalesce(max(revision_number), 0) + 1 FROM comparison_campaigns),
                        :evaluation, :hash, CAST(:manifest AS jsonb))"""),
                {"id": campaign_id, "evaluation": evaluation_revision_id,
                 "hash": manifest_hash, "manifest": json.dumps(manifest)})
            for repeat in range(3):
                for fixture in manifest["fixtures"]:
                    areas = [frame["context"]["observation_area"] for frame in fixture["frames"]]
                    context = {"scenario": fixture["scenario"], "observation_area": areas[0] if len(set(areas)) == 1 else "multiple_observation_areas",
                               "observation_areas": areas, "period": "held_out_comparison",
                               "frame_contexts": [frame["context"] for frame in fixture["frames"]],
                               "expected_outcome": fixture["expected_outcome"]}
                    rule_run = fixture["scenario"].endswith("_series")
                    for candidate in manifest["candidates"]:
                        run_id = uuid.uuid4()
                        connection.execute(text("""INSERT INTO analysis_runs
                            (id, state, purpose, profile_id, authorization_revision, binding_kind,
                             profile_snapshot, request_context, policy_snapshot, rule_snapshot,
                             analysis_intent, stage_key, taxonomy_snapshot, requested_classes)
                            VALUES (:id, 'planned', 'comparison_campaign', :profile, :revision,
                                'comparison_cell', CAST(:snapshot AS jsonb), CAST(:context AS jsonb),
                                CAST(:policy AS jsonb), CAST(:rule AS jsonb), :intent, :stage,
                                CAST(:taxonomy AS jsonb), CAST(:classes AS jsonb))"""),
                            {"id": run_id, "profile": uuid.UUID(candidate["profile_id"]),
                             "revision": candidate["authorization_revision"],
                             "snapshot": json.dumps(candidate["snapshot"]), "context": json.dumps(context),
                             "policy": json.dumps({"intent": "rule_evaluation", **manifest["rule_policy"]}
                                                  if rule_run else manifest["observation_policy"]),
                             "rule": json.dumps(manifest["rule"]),
                             "intent": "rule_evaluation" if rule_run else "observation_only",
                             "stage": "excavation" if rule_run else None,
                             "taxonomy": json.dumps(manifest["taxonomy"]),
                             "classes": json.dumps(fixture["requested_classes"])})
                        connection.execute(text("""INSERT INTO comparison_cells
                            (campaign_id, repeat_ordinal, fixture_ordinal, candidate_ordinal, run_id)
                            VALUES (:campaign, :repeat, :fixture, :candidate, :run)"""),
                            {"campaign": campaign_id, "repeat": repeat,
                             "fixture": fixture["ordinal"], "candidate": candidate["ordinal"], "run": run_id})
            return campaign_id

    def read_comparison_campaign(self, campaign_id: uuid.UUID) -> dict:
        with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            row = connection.execute(text("""SELECT revision_number, evaluation_revision_id, manifest_hash, manifest
                FROM comparison_campaigns WHERE id = :id"""), {"id": campaign_id}).one_or_none()
            if not row:
                raise CampaignGateError("campaign_missing")
            cells = connection.execute(text("""SELECT c.repeat_ordinal, c.fixture_ordinal, c.candidate_ordinal,
                c.run_id, r.state, r.error_code,
                (SELECT count(*) FROM run_inputs i WHERE i.run_id = r.id) AS input_count,
                (SELECT count(*) FROM observer_invocations v WHERE v.run_id = r.id) AS invocation_count,
                (SELECT count(*) FROM observations o WHERE o.run_id = r.id) AS observation_count,
                (SELECT count(*) FROM result_projections p WHERE p.run_id = r.id) AS projection_count,
                (SELECT coalesce(jsonb_agg(i.input_id ORDER BY i.ordinal), '[]'::jsonb)
                    FROM run_inputs i WHERE i.run_id = r.id) AS input_ids,
                (SELECT coalesce(jsonb_agg(v.id ORDER BY i.ordinal), '[]'::jsonb)
                    FROM observer_invocations v JOIN run_inputs i ON i.input_id = v.input_id
                    WHERE v.run_id = r.id) AS invocation_ids,
                (SELECT coalesce(jsonb_agg(jsonb_build_object('run_id', o.run_id,
                    'input_id', o.input_id, 'class_name', o.class_name)
                    ORDER BY i.ordinal, o.class_name), '[]'::jsonb)
                    FROM observations o JOIN run_inputs i ON i.input_id = o.input_id
                    WHERE o.run_id = r.id) AS observation_ids,
                (SELECT coalesce(jsonb_agg(a.id ORDER BY a.id), '[]'::jsonb)
                    FROM artifact_metadata a WHERE a.run_id = r.id) AS artifact_ids
                FROM comparison_cells c JOIN analysis_runs r ON r.id = c.run_id
                WHERE c.campaign_id = :id ORDER BY c.repeat_ordinal, c.fixture_ordinal, c.candidate_ordinal"""),
                {"id": campaign_id}).all()
            planned = row.manifest["repeats"] * len(row.manifest["fixtures"]) * len(row.manifest["candidates"])
            succeeded = sum(item.state == "succeeded" for item in cells)
            timed_out = sum(item.state == "failed" and item.error_code in
                            ("observer_timeout", "campaign_timeout") for item in cells)
            failed = sum(item.state == "failed" for item in cells) - timed_out
            return {"id": str(campaign_id), "revision_number": row.revision_number,
                    "evaluation_revision_id": str(row.evaluation_revision_id),
                    "manifest_hash": row.manifest_hash, "manifest": row.manifest,
                    "accounting": {"planned": planned, "succeeded": succeeded, "failed": failed,
                                   "timed_out": timed_out, "missing": planned - succeeded - failed - timed_out},
                    "cells": [{"repeat_ordinal": item.repeat_ordinal, "fixture_ordinal": item.fixture_ordinal,
                               "candidate_ordinal": item.candidate_ordinal, "run_id": str(item.run_id),
                               "state": item.state, "error_code": item.error_code,
                               "input_count": item.input_count, "invocation_count": item.invocation_count,
                               "observation_count": item.observation_count,
                               "projection_count": item.projection_count,
                               "input_ids": item.input_ids, "invocation_ids": item.invocation_ids,
                               "observation_ids": item.observation_ids,
                               "artifact_ids": item.artifact_ids} for item in cells]}

    def comparison_execution_lock(self):
        connection = self.engine.connect()
        if not connection.execute(text("SELECT pg_try_advisory_lock(:key)"),
                                  {"key": LOCK_ID + 3}).scalar_one():
            connection.close()
            raise CampaignGateError("campaign_executor_busy")
        connection.commit()
        return connection

    def comparison_source(self, campaign_id: uuid.UUID) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(text("""SELECT e.manifest FROM comparison_campaigns c
                JOIN evaluation_set_revisions e ON e.id = c.evaluation_revision_id
                WHERE c.id = :id"""), {"id": campaign_id}).one_or_none()
            if not row:
                raise CampaignGateError("campaign_missing")
            return row.manifest

    def next_comparison_cell(self, campaign_id: uuid.UUID) -> dict | None:
        with self.engine.begin() as connection:
            connection.execute(text("SELECT 1 FROM comparison_campaigns WHERE id = :id FOR UPDATE"),
                               {"id": campaign_id})
            row = connection.execute(text("""SELECT c.repeat_ordinal, c.fixture_ordinal,
                c.candidate_ordinal, c.run_id, r.state, r.profile_snapshot,
                r.authorization_revision, r.requested_classes
                FROM comparison_cells c JOIN analysis_runs r ON r.id = c.run_id
                WHERE c.campaign_id = :id AND r.state NOT IN ('succeeded', 'failed')
                ORDER BY c.repeat_ordinal, c.fixture_ordinal, c.candidate_ordinal LIMIT 1"""),
                {"id": campaign_id}).mappings().one_or_none()
            return dict(row) if row else None

    def require_comparison_authorized(self, run_id: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.profile_id, r.profile_snapshot, r.authorization_revision, a.revision,
                a.state FROM analysis_runs r JOIN profile_authorizations a
                ON a.profile_id = r.profile_id WHERE r.id = :id"""),
                {"id": run_id}).one_or_none()
            if not row or row.state != 'enabled':
                raise CampaignGateError("profile_unauthorized")
            if row.revision != row.authorization_revision:
                raise CampaignGateError("authorization_revision_changed")
            snapshot, _ = self._require_authorized(connection, row.profile_id, row.authorization_revision)
            if snapshot != row.profile_snapshot:
                raise CampaignGateError("profile_runtime_mismatch")

    def publish_comparison_input(self, run_id: uuid.UUID, frame: dict,
                                 payload: bytes, artifacts: ArtifactStore) -> None:
        with self.engine.begin() as gate:
            row = gate.execute(text("""SELECT r.profile_id, r.profile_snapshot, r.authorization_revision, a.revision, a.state
                FROM analysis_runs r JOIN profile_authorizations a ON a.profile_id = r.profile_id
                WHERE r.id = :run AND r.purpose = 'comparison_campaign'
                FOR SHARE OF a"""), {"run": run_id}).one_or_none()
            if not row or row.state != 'enabled':
                raise CampaignGateError("profile_unauthorized")
            if row.revision != row.authorization_revision:
                raise CampaignGateError("authorization_revision_changed")
            snapshot, _ = self._require_authorized(gate, row.profile_id, row.authorization_revision)
            if snapshot != row.profile_snapshot:
                raise CampaignGateError("profile_runtime_mismatch")
            self._publish_comparison_input(run_id, frame, payload, artifacts)

    def _publish_comparison_input(self, run_id: uuid.UUID, frame: dict,
                                  payload: bytes, artifacts: ArtifactStore) -> None:
        image = frame['image']
        key = f"comparison:{run_id}:input:{frame['ordinal']}"
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO publication_intents
                (id, run_id, idempotency_key, media_type, state)
                VALUES (:id, :run, :key, 'image/jpeg', 'pending_upload')
                ON CONFLICT (idempotency_key) DO NOTHING"""),
                {"id": uuid.uuid4(), "run": run_id, "key": key})
            intent = connection.execute(text("""SELECT id, state, sha256, size FROM publication_intents
                WHERE idempotency_key = :key AND run_id = :run FOR UPDATE"""),
                {"key": key, "run": run_id}).one()
            if intent.state != 'pending_upload' and (intent.sha256 != image['sha256'] or
                                                       intent.size != image['size']):
                raise CampaignGateError("campaign_input_mismatch")
        if intent.state == 'pending_upload':
            _, digest, size = artifacts.upload_temporary(intent.id, payload, 'image/jpeg')
            self.publication_content_verified(intent.id, digest, size, f'sha256/{digest}')
            intent_state = 'content_verified'
        else:
            intent_state = intent.state
        if intent_state == 'content_verified':
            artifacts.publish_final(intent.id, payload, 'image/jpeg', image['sha256'], image['size'])
            self.publication_object_published(intent.id)
        artifacts.read_verified(f"sha256/{image['sha256']}", image['sha256'], image['size'])
        with self.engine.begin() as connection:
            run = connection.execute(text("SELECT state FROM analysis_runs WHERE id = :run FOR UPDATE"),
                                     {"run": run_id}).scalar_one()
            if run != 'planned':
                raise CampaignGateError("campaign_input_attachment_rejected")
            existing = connection.execute(text("SELECT sha256, size FROM run_inputs WHERE run_id = :run AND ordinal = :ordinal"),
                                          {"run": run_id, "ordinal": frame['ordinal']}).one_or_none()
            if existing:
                if existing.sha256 != image['sha256'] or existing.size != image['size']:
                    raise CampaignGateError("campaign_input_mismatch")
                return
            artifact_id = uuid.uuid4()
            connection.execute(text("""INSERT INTO artifact_metadata
                (id, run_id, intent_id, key, sha256, size, media_type)
                VALUES (:id, :run, :intent, :key, :hash, :size, 'image/jpeg')"""),
                {"id": artifact_id, "run": run_id, "intent": intent.id,
                 "key": f"sha256/{image['sha256']}", "hash": image['sha256'], "size": image['size']})
            connection.execute(text("UPDATE publication_intents SET state = 'referenced' WHERE id = :id"),
                               {"id": intent.id})
            connection.execute(text("""INSERT INTO run_inputs
                (run_id, ordinal, sha256, size, context, artifact_id)
                VALUES (:run, :ordinal, :hash, :size, CAST(:context AS jsonb), :artifact)"""),
                {"run": run_id, "ordinal": frame['ordinal'], "hash": image['sha256'],
                 "size": image['size'], "context": json.dumps(frame['context']), "artifact": artifact_id})

    def claim_comparison_cell(self, run_id: uuid.UUID, frame_count: int,
                              lease_seconds: int = 30) -> dict:
        self.require_comparison_authorized(run_id)
        owner = str(uuid.uuid4())
        with self.engine.begin() as connection:
            campaign = connection.execute(text("""SELECT p.id FROM comparison_campaigns p
                JOIN comparison_cells c ON c.campaign_id = p.id WHERE c.run_id = :run
                FOR UPDATE OF p"""), {"run": run_id}).scalar_one_or_none()
            first = connection.execute(text("""SELECT c.run_id FROM comparison_cells c
                JOIN analysis_runs r ON r.id = c.run_id
                WHERE c.campaign_id = :campaign AND r.state NOT IN ('succeeded', 'failed')
                ORDER BY c.repeat_ordinal, c.fixture_ordinal, c.candidate_ordinal LIMIT 1"""),
                {"campaign": campaign}).scalar_one_or_none()
            if first != run_id:
                raise CampaignGateError("campaign_cell_out_of_order")
            row = connection.execute(text("""SELECT state, profile_snapshot, requested_classes,
                authorization_revision FROM analysis_runs WHERE id = :run FOR UPDATE"""),
                {"run": run_id}).one()
            count = connection.execute(text("SELECT count(*) FROM run_inputs WHERE run_id = :run"),
                                       {"run": run_id}).scalar_one()
            expected_count = connection.execute(text("""SELECT jsonb_array_length(fixture.value->'frames')
                FROM comparison_cells c JOIN comparison_campaigns p ON p.id = c.campaign_id,
                LATERAL jsonb_array_elements(p.manifest->'fixtures') fixture
                WHERE c.run_id = :run AND (fixture.value->>'ordinal')::int = c.fixture_ordinal"""),
                {"run": run_id}).scalar_one()
            if row.state != 'planned' or count != expected_count or frame_count != expected_count:
                raise CampaignGateError("campaign_inputs_incomplete")
            connection.execute(text("""UPDATE analysis_runs SET state = 'running', lease_owner = :owner,
                lease_expires_at = clock_timestamp() + (:seconds * interval '1 second') WHERE id = :run"""),
                {"run": run_id, "owner": owner, "seconds": lease_seconds})
            for ordinal, name in enumerate(STAGES):
                connection.execute(text("""INSERT INTO analysis_stages (run_id, ordinal, name, state)
                    VALUES (:run, :ordinal, :name, :state)"""),
                    {"run": run_id, "ordinal": ordinal, "name": name,
                     "state": 'succeeded' if ordinal == 0 else 'running' if ordinal == 1 else 'pending'})
            frames = connection.execute(text("""SELECT i.input_id, i.ordinal, i.sha256, i.size,
                a.key, a.id AS artifact_id FROM run_inputs i JOIN artifact_metadata a ON a.id = i.artifact_id
                WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": run_id}).mappings().all()
            return {"id": run_id, "owner": owner, "profile_snapshot": row.profile_snapshot,
                    "requested_classes": row.requested_classes,
                    "authorization_revision": row.authorization_revision,
                    "frames": [dict(frame) for frame in frames], "campaign": True}

    def renew_comparison(self, run_id: uuid.UUID, owner: str, revision: int,
                         lease_seconds: int = 30) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE analysis_runs SET
                lease_expires_at = clock_timestamp() + (:seconds * interval '1 second')
                WHERE id = :run AND purpose = 'comparison_campaign' AND state = 'running'
                  AND lease_owner = :owner AND lease_expires_at > clock_timestamp()
                  AND lease_expires_at < clock_timestamp() + (:seconds * interval '1 second')"""),
                {"run": run_id, "owner": owner, "seconds": lease_seconds})
            if changed.rowcount != 1:
                raise CampaignGateError("campaign_lease_rejected")

    def settle_comparison_invocation(self, run_id: uuid.UUID, owner: str,
                                     invocation_id: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            run = connection.execute(text("""SELECT state, lease_owner,
                lease_expires_at > clock_timestamp() AS live FROM analysis_runs
                WHERE id = :run FOR UPDATE"""), {"run": run_id}).one_or_none()
            if not run or run.state != 'running' or run.lease_owner != owner or not run.live:
                raise CampaignGateError("campaign_ownership_uncertain")
            changed = connection.execute(text("""UPDATE observer_invocations
                SET provider_settled_at = clock_timestamp() WHERE id = :id AND run_id = :run
                AND state = 'reserved' AND provider_settled_at IS NULL"""),
                {"id": invocation_id, "run": run_id})
            if changed.rowcount != 1:
                raise CampaignGateError("campaign_invocation_settlement_rejected")
            connection.execute(text("""UPDATE analysis_runs SET provider_safe_after = clock_timestamp()
                WHERE id = :run AND state = 'running' AND lease_owner = :owner"""),
                {"run": run_id, "owner": owner})

    def fail_comparison_cell(self, run_id: uuid.UUID, code: str,
                             owner: str | None = None) -> None:
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.state, r.lease_owner,
                lease_expires_at > clock_timestamp() AS live,
                provider_safe_after > clock_timestamp() AS provider_active
                FROM analysis_runs r JOIN comparison_cells c ON c.run_id = r.id
                WHERE r.id = :run AND r.purpose = 'comparison_campaign' FOR UPDATE OF r"""),
                {"run": run_id}).one_or_none()
            if row is None:
                raise CampaignGateError("campaign_cell_missing")
            if row.state not in ('planned', 'running'):
                return
            if row.state == 'running' and (row.lease_owner != owner or not row.live):
                raise CampaignGateError("campaign_ownership_uncertain")
            if row.provider_active:
                raise CampaignGateError("campaign_provider_may_be_active")
            connection.execute(text("UPDATE observer_invocations SET state = 'failed' WHERE run_id = :run AND state = 'reserved'"),
                               {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = :code WHERE run_id = :run AND state = 'running'"),
                               {"run": run_id, "code": code})
            connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND state = 'pending'"),
                               {"run": run_id})
            connection.execute(text("""UPDATE publication_intents SET state = 'quarantined'
                WHERE run_id = :run AND state NOT IN ('referenced', 'failed_integrity', 'quarantined')"""),
                {"run": run_id})
            connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = :code,
                lease_owner = NULL, lease_expires_at = NULL WHERE id = :run"""),
                {"run": run_id, "code": code})

    def require_comparison_execution_exclusive(self, campaign_id: uuid.UUID) -> None:
        with self.engine.connect() as connection:
            if connection.execute(text("""SELECT 1 FROM comparison_cells c
                JOIN analysis_runs r ON r.id = c.run_id
                WHERE c.campaign_id != :campaign AND r.state = 'running' LIMIT 1"""),
                {"campaign": campaign_id}).first():
                raise CampaignGateError("campaign_ownership_uncertain")

    def recover_comparison_campaign(self, campaign_id: uuid.UUID) -> int:
        with self.engine.begin() as connection:
            connection.execute(text("SELECT 1 FROM comparison_campaigns WHERE id = :id FOR UPDATE"),
                               {"id": campaign_id})
            rows = connection.execute(text("""SELECT r.id, r.lease_owner, r.lease_expires_at,
                r.provider_safe_after, clock_timestamp() AS now FROM comparison_cells c
                JOIN analysis_runs r ON r.id = c.run_id WHERE c.campaign_id = :campaign
                AND r.state = 'running' FOR UPDATE OF r"""), {"campaign": campaign_id}).all()
            for row in rows:
                if (row.lease_owner is None or row.lease_expires_at is None or
                    row.lease_expires_at > row.now or
                    row.provider_safe_after and row.provider_safe_after > row.now):
                    raise CampaignGateError("campaign_ownership_uncertain")
                connection.execute(text("UPDATE observer_invocations SET state = 'failed' WHERE run_id = :run AND state = 'reserved'"),
                                   {"run": row.id})
                connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = 'executor_interrupted' WHERE run_id = :run AND state = 'running'"),
                                   {"run": row.id})
                connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND state = 'pending'"),
                                   {"run": row.id})
                connection.execute(text("""UPDATE publication_intents SET state = 'quarantined'
                    WHERE run_id = :run AND state NOT IN ('referenced', 'failed_integrity', 'quarantined')"""),
                    {"run": row.id})
                connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = 'executor_interrupted',
                    lease_owner = NULL, lease_expires_at = NULL WHERE id = :run AND state = 'running'"""),
                    {"run": row.id})
            return len(rows)

    def bind_evaluation_report(self, report_id: uuid.UUID, revision_id: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO evaluation_report_bindings (report_id, revision_id)
                VALUES (:report, :revision)"""), {"report": report_id, "revision": revision_id})

    def check_head_and_smoke(self, migrations_path: str) -> None:
        try:
            expected = ScriptDirectory(migrations_path).get_current_head()
            with self.engine.begin() as connection:
                actual = MigrationContext.configure(connection).get_current_revision()
            if actual != expected or expected is None:
                raise DatabaseGateError("database_migration_mismatch")
            with self.engine.connect() as connection:
                transaction = connection.begin()
                try:
                    marker = connection.execute(text("INSERT INTO startup_smoke (nonce) VALUES (gen_random_uuid()) RETURNING nonce")).scalar_one()
                    observed = connection.execute(text("SELECT nonce FROM startup_smoke WHERE nonce = :nonce"), {"nonce": marker}).scalar_one()
                    if observed != marker:
                        raise DatabaseGateError("database_smoke_failed")
                finally:
                    transaction.rollback()
        except DatabaseGateError:
            raise
        except Exception:
            raise DatabaseGateError("database_smoke_failed") from None

    def reconcile(self, artifacts: ArtifactStore | None = None, *, runtime: bool = False) -> None:
        observed_count = 0
        try:
            with self.engine.begin() as connection:
                locked = connection.execute(text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": LOCK_ID}).scalar_one()
                if not locked:
                    raise ReconciliationGateError("reconciliation_lock_unavailable")
                integrity_failed = bool(connection.execute(text(
                    "SELECT 1 FROM publication_intents WHERE state = 'failed_integrity' LIMIT 1")).first())
                rows = connection.execute(text("""SELECT i.id, i.state, i.run_id, i.sha256, i.size, i.final_key,
                    i.media_type
                    FROM publication_intents i
                    WHERE i.state NOT IN ('referenced', 'quarantined', 'failed_integrity')
                      AND NOT EXISTS (SELECT 1 FROM analysis_runs r
                          WHERE r.id = i.run_id AND r.purpose = 'comparison_campaign')
                      AND (:runtime = false OR i.run_id IS NOT NULL) FOR UPDATE OF i"""),
                    {"runtime": runtime}).all()
                observed_count = len(rows)
                def inspect_final(row):
                    status, creator = artifacts.inspect_reconciliation(row.final_key, row.sha256, row.size)
                    if status == "verified" and not connection.execute(text("""SELECT 1 FROM publication_intents
                        WHERE id = :creator AND sha256 = :hash AND size = :size AND final_key = :key"""),
                        {"creator": uuid.UUID(creator), "hash": row.sha256, "size": row.size,
                         "key": row.final_key}).first():
                        raise ArtifactGateError("artifact_integrity_failed")
                    return status

                for row in rows:
                    if row.run_id is not None:
                        run = connection.execute(text("""SELECT state, lease_expires_at > clock_timestamp() AS lease_live
                            FROM analysis_runs WHERE id = :id FOR UPDATE NOWAIT"""), {"id": row.run_id}).one()
                        if run.state == "running" and run.lease_live:
                            continue
                    if artifacts is None:
                        raise ReconciliationGateError("reconciliation_inspector_missing")
                    try:
                        if row.state == "pending_upload":
                            artifacts.inspect_reconciliation(f"tmp/{row.id}", creator=row.id)
                        elif row.state == "content_verified":
                            if row.sha256 is None or row.size is None or row.final_key != f"sha256/{row.sha256}":
                                raise ArtifactGateError("artifact_integrity_failed")
                            artifacts.inspect_reconciliation(f"tmp/{row.id}", row.sha256, row.size, row.id)
                            inspect_final(row)
                        elif row.state == "object_published":
                            if row.sha256 is None or row.size is None or row.final_key != f"sha256/{row.sha256}":
                                raise ArtifactGateError("artifact_integrity_failed")
                            if inspect_final(row) == "missing":
                                raise ArtifactGateError("artifact_integrity_failed")
                        else:
                            raise ReconciliationGateError("reconciliation_unknown_state")
                    except ArtifactGateError as exc:
                        if str(exc) != "artifact_integrity_failed":
                            raise ReconciliationGateError("reconciliation_artifact_unavailable") from None
                        connection.execute(text("""UPDATE publication_intents SET state = 'failed_integrity',
                            error_code = 'artifact_integrity_failed' WHERE id = :id"""), {"id": row.id})
                        integrity_failed = True
                        continue
                    reference = None
                    if row.state == "object_published" and row.run_id is not None:
                        reference = connection.execute(text("""SELECT 1 FROM artifact_metadata a
                            WHERE a.intent_id = :id AND a.run_id = :run AND a.key = :key AND a.sha256 = :hash
                              AND a.size = :size AND a.media_type = :media
                              AND (EXISTS (SELECT 1 FROM run_inputs i WHERE i.run_id = a.run_id AND i.artifact_id = a.id)
                                OR EXISTS (SELECT 1 FROM observer_invocations v
                                   WHERE v.run_id = a.run_id AND v.native_artifact_id = a.id)
                                OR EXISTS (SELECT 1 FROM result_projections p WHERE p.run_id = a.run_id
                                   AND p.snapshot->'evidence' @> jsonb_build_array(jsonb_build_object(
                                     'key', a.key, 'sha256', a.sha256, 'size', a.size))))"""),
                            {"id": row.id, "run": row.run_id, "key": row.final_key, "hash": row.sha256,
                             "size": row.size, "media": row.media_type}).first()
                    connection.execute(text("UPDATE publication_intents SET state = :state WHERE id = :id"),
                                       {"id": row.id, "state": "referenced" if reference else "quarantined"})
                if not runtime:
                    connection.execute(text("""UPDATE submission_requests SET state = 'failed', error_code = 'submission_interrupted'
                        WHERE state = 'publishing'"""))
                connection.execute(text("""INSERT INTO reconciliation_runs (started_at, completed_at, intent_count, status, error_code)
                    VALUES (clock_timestamp(), clock_timestamp(), :count, :status, :error)"""),
                    {"count": observed_count, "status": "failed" if integrity_failed else "succeeded",
                     "error": "reconciliation_integrity_failed" if integrity_failed else None})
            if integrity_failed:
                raise ReconciliationGateError("reconciliation_integrity_failed")
        except ReconciliationGateError as exc:
            if str(exc) != "reconciliation_integrity_failed":
                self._record_reconciliation_failure(str(exc), observed_count)
            raise
        except Exception:
            self._record_reconciliation_failure("reconciliation_gate_failed", observed_count)
            raise ReconciliationGateError("reconciliation_gate_failed") from None

    def _record_reconciliation_failure(self, code: str, intent_count: int) -> None:
        try:
            with self.engine.begin() as connection:
                connection.execute(text("INSERT INTO reconciliation_runs (started_at, completed_at, intent_count, status, error_code) VALUES (clock_timestamp(), clock_timestamp(), :count, 'failed', :code)"), {"count": intent_count, "code": code})
        except Exception:
            pass

    def recover(self) -> int:
        try:
            with self.engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '1s'"))
                rows = connection.execute(text("SELECT id, lease_owner, lease_expires_at, clock_timestamp() AS db_now FROM analysis_runs WHERE state = 'running' AND purpose != 'comparison_campaign' AND (lease_expires_at IS NULL OR lease_expires_at <= clock_timestamp()) FOR UPDATE NOWAIT")).all()
                for run_id, owner, expiry, db_now in rows:
                    if expiry is None or owner is None:
                        raise RecoveryGateError("recovery_unknown_ownership")
                    if expiry > db_now:
                        continue
                    updated = connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = 'executor_interrupted',
                        lease_owner = NULL, lease_expires_at = NULL WHERE id = :id AND state = 'running'
                        AND lease_owner = :owner AND lease_expires_at = :expiry
                        AND lease_expires_at <= clock_timestamp()"""),
                        {"id": run_id, "owner": owner, "expiry": expiry})
                    if updated.rowcount != 1:
                        raise RecoveryGateError("recovery_lease_changed")
                    connection.execute(text("UPDATE observer_invocations SET state = 'failed' WHERE run_id = :id AND state = 'reserved'"), {"id": run_id})
                    connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = 'executor_interrupted' WHERE run_id = :id AND state = 'running'"), {"id": run_id})
                    connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :id AND state = 'pending'"), {"id": run_id})
                return len(rows)
        except RecoveryGateError:
            raise
        except Exception:
            raise RecoveryGateError("recovery_gate_failed") from None

    def create_admission_runs(self, snapshot: dict, manifest: dict, fixtures: list[tuple[dict, bytes]], watchdog_seconds: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
        if watchdog_seconds <= 0:
            raise AdmissionStoreError("bootstrap_watchdog_invalid")
        profile_hash = digest(canonical_bytes(snapshot))
        manifest_hash = digest(canonical_bytes(manifest))
        profile_id, fixture_set_id = uuid.uuid4(), uuid.uuid4()
        run_ids = [uuid.uuid4() for _ in fixtures]
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO observer_profiles (id, status, profile_hash, snapshot) VALUES (:id, 'draft', :hash, CAST(:snapshot AS jsonb)) ON CONFLICT (profile_hash) DO NOTHING"),
                {"id": profile_id, "hash": profile_hash, "snapshot": json.dumps(snapshot)})
            profile_id = connection.execute(text("SELECT id FROM observer_profiles WHERE profile_hash = :hash AND status = 'draft'"), {"hash": profile_hash}).scalar_one()
            connection.execute(text("INSERT INTO admission_fixture_sets (id, manifest_hash, manifest) VALUES (:id, :hash, CAST(:manifest AS jsonb)) ON CONFLICT (manifest_hash) DO NOTHING"),
                {"id": fixture_set_id, "hash": manifest_hash, "manifest": json.dumps(manifest)})
            fixture_set_id = connection.execute(text("SELECT id FROM admission_fixture_sets WHERE manifest_hash = :hash"), {"hash": manifest_hash}).scalar_one()
            for run_id, (fixture, _) in zip(run_ids, fixtures):
                image = fixture["image"]
                connection.execute(text("""INSERT INTO analysis_runs
                    (id, state, purpose, profile_id, binding_kind, fixture_set_id, fixture_id, bootstrap_watchdog_seconds, profile_snapshot)
                    VALUES (:id, 'queued', 'profile_admission', :profile, 'profile_admission', :set_id, :fixture, :watchdog, CAST(:snapshot AS jsonb))"""),
                    {"id": run_id, "profile": profile_id, "set_id": fixture_set_id, "fixture": fixture["id"],
                     "watchdog": watchdog_seconds, "snapshot": json.dumps(snapshot)})
                connection.execute(text("""INSERT INTO run_inputs (run_id, ordinal, fixture_id, sha256, size, context)
                    VALUES (:run, 0, :fixture, :hash, :size, CAST(:context AS jsonb))"""),
                    {"run": run_id, "fixture": fixture["id"], "hash": image["sha256"], "size": image["size"],
                     "context": json.dumps(fixture["context"])})
                for ordinal, name in enumerate(STAGES):
                    connection.execute(text("INSERT INTO analysis_stages (run_id, ordinal, name, state) VALUES (:run, :ordinal, :name, 'pending')"),
                        {"run": run_id, "ordinal": ordinal, "name": name})
        return profile_id, run_ids

    def reserve_admission_invocation(self, run_id: uuid.UUID, input_bytes: bytes) -> uuid.UUID:
        invocation_id = uuid.uuid4()
        input_hash = digest(input_bytes)
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.profile_id, r.bootstrap_watchdog_seconds, r.profile_snapshot, i.sha256, i.size, i.input_id, p.status
                FROM analysis_runs r JOIN run_inputs i ON i.run_id = r.id JOIN observer_profiles p ON p.id = r.profile_id
                WHERE r.id = :id AND r.purpose = 'profile_admission' AND r.state = 'queued' FOR UPDATE OF r"""), {"id": run_id}).one_or_none()
            if not row or row.status != "draft" or row.sha256 != input_hash or row.size != len(input_bytes) or row.bootstrap_watchdog_seconds <= 0:
                raise AdmissionStoreError("admission_reservation_rejected")
            connection.execute(text("""UPDATE analysis_runs SET state = 'running', lease_owner = :owner,
                lease_expires_at = clock_timestamp() + (:watchdog * interval '1 second') WHERE id = :id"""),
                {"owner": str(invocation_id), "watchdog": row.bootstrap_watchdog_seconds, "id": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :id AND ordinal IN (0, 1)"), {"id": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :id AND ordinal = 2"), {"id": run_id})
            request_identity = (row.profile_snapshot["requested_model_identity"]["id"]
                                if row.profile_snapshot.get("kind") == "cloud_api" else "local-grounding-dino-cpu")
            connection.execute(text("""INSERT INTO observer_invocations
                (id, run_id, input_id, fence, profile_id, stage_ordinal, input_sha256, intended_request_identity, state)
                VALUES (:id, :run, :input_id, 1, :profile, 2, :hash, :identity, 'reserved')"""),
                {"id": invocation_id, "run": run_id, "input_id": row.input_id,
                 "profile": row.profile_id, "hash": input_hash, "identity": request_identity})
        return invocation_id

    def complete_invocation(self, run_id: uuid.UUID, invocation_id: uuid.UUID, result: dict) -> None:
        states = normalized_states(result["states"])
        with self.engine.begin() as connection:
            reservation = connection.execute(text("""SELECT r.state AS run_state, r.lease_owner,
                r.lease_expires_at > clock_timestamp() AS lease_live,
                r.profile_snapshot, r.profile_snapshot->'model_files'->>'model.safetensors' AS checkpoint_sha256,
                i.state AS invocation_state, i.fence
                FROM analysis_runs r JOIN observer_invocations i ON i.run_id = r.id
                WHERE r.id = :run AND i.id = :id FOR UPDATE OF r, i"""),
                {"run": run_id, "id": invocation_id}).one_or_none()
            if (not reservation or reservation.run_state != "running" or reservation.lease_owner != str(invocation_id)
                    or not reservation.lease_live or reservation.invocation_state != "reserved" or reservation.fence != 1):
                raise AdmissionStoreError("invocation_completion_rejected")
            snapshot = reservation.profile_snapshot
            if snapshot.get("kind") == "cloud_api":
                requested = snapshot["requested_model_identity"]["id"]
                identity_valid = (result.get("returned_model_identity") in (requested, requested + "/latest")
                                  and result.get("actual_device") == "remote_unreported"
                                  and isinstance(result.get("returned_request_identity"), str)
                                  and bool(result["returned_request_identity"])
                                  and result.get("preprocessing_revision") == cloud_api.PREPROCESSING_REVISION)
            else:
                identity_valid = (reservation.checkpoint_sha256
                    and result.get("returned_model_identity") == f"checkpoint-sha256:{reservation.checkpoint_sha256}"
                    and result.get("actual_device") == "cpu")
            if not identity_valid:
                raise AdmissionStoreError("observer_identity_or_device_invalid")
            changed = connection.execute(text("""UPDATE observer_invocations SET state = 'completed',
                returned_model_identity = :identity, returned_request_identity = :request_identity,
                actual_device = :device, preprocessing_revision = :preprocessing
                WHERE id = :id AND run_id = :run AND state = 'reserved' AND fence = 1"""),
                {"identity": result["returned_model_identity"], "device": result["actual_device"],
                 "request_identity": result.get("returned_request_identity"),
                 "preprocessing": result["preprocessing_revision"], "id": invocation_id, "run": run_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("invocation_completion_rejected")
            measured = connection.execute(text("""UPDATE analysis_runs SET latency_ms = :latency, peak_memory_bytes = :memory
                WHERE id = :run AND state = 'running' AND lease_owner = :owner
                  AND lease_expires_at > clock_timestamp()"""),
                {"latency": result["latency_ms"], "memory": result["peak_memory_bytes"],
                 "run": run_id, "owner": str(invocation_id)})
            if measured.rowcount != 1:
                raise AdmissionStoreError("invocation_completion_rejected")
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 2 AND state = 'running'"), {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'not_applicable' WHERE run_id = :run AND ordinal IN (3, 4) AND state = 'pending'"), {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 5 AND state = 'pending'"), {"run": run_id})
            input_id, input_hash = connection.execute(text("SELECT input_id, sha256 FROM run_inputs WHERE run_id = :run AND ordinal = 0"), {"run": run_id}).one()
            for name in CLASSES:
                connection.execute(text("""INSERT INTO observations (run_id, input_id, class_name, state, input_sha256, invocation_id)
                    VALUES (:run, :input_id, :name, :state, :hash, :invocation)"""),
                    {"run": run_id, "input_id": input_id, "name": name,
                     "state": states[name], "hash": input_hash, "invocation": invocation_id})

    def create_publication_intent(self, run_id: uuid.UUID, media_type: str, idempotency_key: str) -> uuid.UUID:
        intent_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO publication_intents (id, run_id, idempotency_key, media_type, state)
                VALUES (:id, :run, :key, :media, 'pending_upload')"""),
                {"id": intent_id, "run": run_id, "key": idempotency_key, "media": media_type})
        return intent_id

    def create_submission_intent(self, key: str) -> uuid.UUID:
        intent_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO publication_intents
                (id, idempotency_key, submission_key, media_type, state)
                VALUES (:id, :intent_key, :key, 'image/jpeg', 'pending_upload')"""),
                {"id": intent_id, "intent_key": f"submission-intent:{intent_id}", "key": key})
        return intent_id

    def publication_content_verified(self, intent_id: uuid.UUID, sha256: str, size: int, final_key: str) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE publication_intents SET state = 'content_verified',
                sha256 = :hash, size = :size, final_key = :key WHERE id = :id AND state = 'pending_upload'"""),
                {"hash": sha256, "size": size, "key": final_key, "id": intent_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("publication_state_changed")

    def publication_object_published(self, intent_id: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("UPDATE publication_intents SET state = 'object_published' WHERE id = :id AND state = 'content_verified'"), {"id": intent_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("publication_state_changed")

    def publication_failed_integrity(self, intent_id: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""UPDATE publication_intents SET state = 'failed_integrity',
                error_code = 'artifact_integrity_failed' WHERE id = :id AND state = 'content_verified'"""),
                {"id": intent_id})

    def finish_admission_run(self, run_id: uuid.UUID, invocation_id: uuid.UUID, native_intent: uuid.UUID, input_intent: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            intents = connection.execute(text("SELECT id, media_type, sha256, size, final_key FROM publication_intents WHERE id IN (:native, :input) AND run_id = :run AND state = 'object_published' FOR UPDATE"),
                {"native": native_intent, "input": input_intent, "run": run_id}).all()
            if len(intents) != 2:
                raise AdmissionStoreError("publication_incomplete")
            for row in intents:
                connection.execute(text("""INSERT INTO artifact_metadata (id, run_id, intent_id, key, sha256, size, media_type)
                    VALUES (:id, :run, :intent, :key, :hash, :size, :media)"""),
                    {"id": uuid.uuid4(), "run": run_id, "intent": row.id, "key": row.final_key,
                     "hash": row.sha256, "size": row.size, "media": row.media_type})
            native_artifact_id = connection.execute(text("SELECT id FROM artifact_metadata WHERE intent_id = :intent"), {"intent": native_intent}).scalar_one()
            connection.execute(text("UPDATE observer_invocations SET native_artifact_id = :artifact WHERE id = :id AND state = 'completed'"),
                {"artifact": native_artifact_id, "id": invocation_id})
            observations = connection.execute(text("SELECT class_name, state FROM observations WHERE run_id = :run"), {"run": run_id}).all()
            if len(observations) != 2:
                raise AdmissionStoreError("observation_incomplete")
            projection = {"outcome": "observations_only", "classes": dict(observations),
                "evidence": [{"key": row.final_key, "sha256": row.sha256, "size": row.size} for row in intents]}
            connection.execute(text("INSERT INTO result_projections (run_id, outcome, snapshot) VALUES (:run, 'observations_only', CAST(:snapshot AS jsonb))"),
                {"run": run_id, "snapshot": json.dumps(projection)})
            connection.execute(text("UPDATE publication_intents SET state = 'referenced' WHERE id IN (:native, :input)"),
                {"native": native_intent, "input": input_intent})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 5 AND state = 'running'"), {"run": run_id})
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL, lease_expires_at = NULL
                WHERE id = :run AND state = 'running' AND lease_expires_at > clock_timestamp()"""), {"run": run_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("admission_watchdog_expired")

    def fail_admission_run(self, run_id: uuid.UUID, code: str, failed_stage_ordinal: int | None = None) -> None:
        if not code.isidentifier():
            code = "admission_failed"
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = :code,
                lease_owner = NULL, lease_expires_at = NULL WHERE id = :run AND state IN ('queued', 'running')"""),
                {"run": run_id, "code": code})
            if changed.rowcount:
                stage_failure = connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = :code WHERE run_id = :run AND state = 'running'"), {"run": run_id, "code": code})
                if not stage_failure.rowcount:
                    if failed_stage_ordinal == 1:
                        connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 0 AND state = 'pending'"), {"run": run_id})
                    connection.execute(text("""UPDATE analysis_stages SET state = 'failed', reason = :code
                        WHERE run_id = :run AND ordinal = (SELECT min(ordinal) FROM analysis_stages WHERE run_id = :run AND state = 'pending')"""),
                        {"run": run_id, "code": code})
                connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND state = 'pending'"), {"run": run_id})

    def authorize_successor(self, profile_id: uuid.UUID, run_ids: list[uuid.UUID]) -> uuid.UUID:
        if not run_ids:
            raise AdmissionStoreError("admission_incomplete")
        with self.engine.begin() as connection:
            draft = connection.execute(text("SELECT snapshot FROM observer_profiles WHERE id = :id AND status = 'draft' FOR UPDATE"), {"id": profile_id}).one_or_none()
            if not draft:
                raise AdmissionStoreError("admission_draft_missing")
            if connection.execute(text("SELECT 1 FROM observer_profiles WHERE parent_id = :id AND status = 'admitted'"), {"id": profile_id}).first():
                raise AdmissionStoreError("admission_successor_exists")
            rows = connection.execute(text("""SELECT id, state, latency_ms, peak_memory_bytes FROM analysis_runs
                WHERE id = ANY(:ids) AND profile_id = :profile AND purpose = 'profile_admission' FOR UPDATE"""),
                {"ids": run_ids, "profile": profile_id}).all()
            cloud = draft.snapshot.get("kind") == "cloud_api"
            if len(rows) != len(run_ids) or any(row.state != "succeeded" or row.latency_ms is None
                                                   or (not cloud and row.peak_memory_bytes is None) for row in rows):
                raise AdmissionStoreError("admission_incomplete")
            fixtures = connection.execute(text("SELECT fixture_id, fixture_set_id FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": run_ids}).all()
            if len({row.fixture_set_id for row in fixtures}) != 1 or len({row.fixture_id for row in fixtures}) != len(run_ids):
                raise AdmissionStoreError("admission_incomplete")
            total = connection.execute(text("SELECT count(*) FROM admission_fixture_sets s, jsonb_array_elements(s.manifest->'fixtures') f WHERE s.id = :id"),
                {"id": fixtures[0].fixture_set_id}).scalar_one()
            if total != len(run_ids):
                raise AdmissionStoreError("admission_incomplete")
            actual_devices = connection.execute(text("SELECT actual_device, returned_model_identity, native_artifact_id FROM observer_invocations WHERE run_id = ANY(:ids)"), {"ids": run_ids}).all()
            expected_device = "remote_unreported" if cloud else "cpu"
            if len(actual_devices) != len(run_ids) or any(row.actual_device != expected_device or not row.returned_model_identity or not row.native_artifact_id for row in actual_devices):
                raise AdmissionStoreError("admission_incomplete")
            identities = {row.returned_model_identity for row in actual_devices}
            module = cloud_api if cloud else grounding_dino
            expected_adapter_hash = digest(Path(module.__file__).read_bytes())
            expected_lock_hash = digest((Path(__file__).resolve().parents[2] / "uv.lock").read_bytes())
            adapter = draft.snapshot.get("adapter", {})
            runtime = draft.snapshot.get("runtime", {})
            identity = draft.snapshot.get("requested_model_identity", {})
            requested_uri = identity.get("id")
            if (len(identities) != 1 or adapter.get("code") != ("yandex_ai_studio" if cloud else "grounding_dino")
                    or adapter.get("bundle_sha256") != expected_adapter_hash
                    or runtime.get("uv_lock_sha256") != expected_lock_hash
                    or runtime.get("device") != expected_device
                    or (requested_uri not in (identities | {value.removesuffix('/latest') for value in identities}) if cloud else
                        identity != {"id": grounding_dino.MODEL_ID, "revision": grounding_dino.MODEL_REVISION})):
                raise AdmissionStoreError("admission_identity_invalid")
            if cloud:
                evidence = draft.snapshot.get("owner_evidence")
                canary_hashes = [row.sha256 for row in connection.execute(text(
                    "SELECT sha256 FROM run_inputs WHERE run_id = ANY(:ids)"), {"ids": run_ids}).all()]
                backend_root = Path(__file__).resolve().parents[2]
                held_out_hashes, held_out_proof = cloud_api.read_held_out_scope(
                    backend_root.parent / "evaluation",
                    backend_root / "admission" / "exclusions" / "held_out_evaluation.json",
                    json.loads((backend_root / "admission" / "manifest.json").read_text()), canary_hashes)
                if (draft.snapshot.get("allowed_input_sha256") != sorted(canary_hashes + held_out_hashes)
                        or draft.snapshot.get("rights", {}).get("held_out") != held_out_proof):
                    raise AdmissionStoreError("cloud_upload_scope_invalid")
                cloud_api.validate_owner_evidence(evidence, canary_hashes, draft.snapshot["allowed_input_sha256"])
            latencies = sorted(row.latency_ms / 1000 for row in rows)
            p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
            image_timeout = max(2 * p95, 60)
            batch_timeout = max(2 * sum(latencies), 600)
            audit = {"run_ids": [str(value) for value in run_ids], "latency_seconds": latencies,
                "peak_memory_bytes": [row.peak_memory_bytes for row in rows], "actual_device": expected_device, "errors": []}
            audit_hash = digest(canonical_bytes(audit))
            snapshot = dict(draft.snapshot)
            snapshot["returned_model_identity"] = identities.pop()
            snapshot["identity_gap"] = ("hosted_model_revision_unpinnable" if cloud else
                "local checkpoint digest identifies loaded bytes; no remote model identity was returned")
            snapshot["audit_hash"] = audit_hash
            snapshot["audit_run_ids"] = audit["run_ids"]
            snapshot["runtime"] = {**snapshot["runtime"], "per_image_timeout_seconds": image_timeout,
                "batch_timeout_seconds": batch_timeout}
            successor_id = uuid.uuid4()
            snapshot["audit_uri"] = f"postgresql:observer_profiles/{successor_id}"
            snapshot["audit_report"] = audit
            successor_hash = digest(canonical_bytes(snapshot))
            connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
                VALUES (:id, :parent, 'admitted', :hash, CAST(:snapshot AS jsonb), :audit)"""),
                {"id": successor_id, "parent": profile_id, "hash": successor_hash,
                 "snapshot": json.dumps(snapshot), "audit": audit_hash})
            connection.execute(text("""INSERT INTO profile_authorizations
                (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
                VALUES (:id, 1, 'enabled', :reason, :audit, false)"""),
                {"id": successor_id, "audit": audit_hash,
                 "reason": "complete_cloud_admission" if cloud else "complete_cpu_admission"})
            return successor_id

    def require_authorized(self, profile_id: uuid.UUID, expected_revision: int | None = None) -> tuple[dict, int]:
        with self.engine.begin() as connection:
            return self._require_authorized(connection, profile_id, expected_revision)

    def _require_authorized(self, connection, profile_id: uuid.UUID,
                            expected_revision: int | None = None) -> tuple[dict, int]:
        row = connection.execute(text("""SELECT p.status, p.parent_id, p.profile_hash, p.snapshot, p.audit_hash,
            a.state, a.revision, a.audit_hash AS authorization_audit
            FROM observer_profiles p JOIN profile_authorizations a ON a.profile_id = p.id
            WHERE p.id = :id FOR UPDATE OF p, a"""), {"id": profile_id}).one_or_none()
        if not row or row.status != "admitted" or not row.audit_hash or row.state != "enabled" or row.authorization_audit != row.audit_hash:
            raise AdmissionStoreError("profile_unauthorized")
        if expected_revision is not None and row.revision != expected_revision:
            raise AdmissionStoreError("authorization_revision_changed")
        cloud = row.snapshot.get("kind") == "cloud_api"
        if row.snapshot.get("adapter", {}).get("code") != ("yandex_ai_studio" if cloud else "grounding_dino"):
            raise AdmissionStoreError("profile_unauthorized")
        run_ids = row.snapshot.get("audit_run_ids", [])
        if (not row.parent_id or not isinstance(run_ids, list) or not run_ids
                or not all(isinstance(value, str) for value in run_ids) or len(set(run_ids)) != len(run_ids)
                or digest(canonical_bytes(row.snapshot)) != row.profile_hash
                or digest(canonical_bytes(row.snapshot.get("audit_report"))) != row.audit_hash):
            raise AdmissionStoreError("profile_admission_evidence_missing")
        evidenced = connection.execute(text("""SELECT count(*) FROM analysis_runs r
            JOIN observer_invocations i ON i.run_id = r.id
            JOIN result_projections p ON p.run_id = r.id
            WHERE r.id = ANY(:ids) AND r.profile_id = :parent AND r.purpose = 'profile_admission'
              AND r.state = 'succeeded' AND i.state = 'completed' AND i.actual_device = :device
              AND i.returned_model_identity = :identity
              AND p.outcome = 'observations_only'"""), {"ids": [uuid.UUID(value) for value in run_ids],
                "parent": row.parent_id, "device": "remote_unreported" if cloud else "cpu",
                "identity": row.snapshot["returned_model_identity"]}).scalar_one()
        if evidenced != len(run_ids):
            raise AdmissionStoreError("profile_admission_evidence_missing")
        adapter_hash = digest(Path((cloud_api if cloud else grounding_dino).__file__).read_bytes())
        lock_hash = digest((Path(__file__).resolve().parents[2] / "uv.lock").read_bytes())
        if row.snapshot.get("adapter", {}).get("bundle_sha256") != adapter_hash or row.snapshot.get("runtime", {}).get("uv_lock_sha256") != lock_hash:
            raise AdmissionStoreError("profile_runtime_mismatch")
        if cloud:
            canary_hashes = [item.sha256 for item in connection.execute(text(
                "SELECT sha256 FROM run_inputs WHERE run_id = ANY(:ids)"),
                {"ids": [uuid.UUID(value) for value in run_ids]}).all()]
            try:
                cloud_api.validate_owner_evidence(row.snapshot.get("owner_evidence"),
                    canary_hashes, row.snapshot["allowed_input_sha256"])
            except cloud_api.CloudObserverError:
                raise AdmissionStoreError("profile_owner_evidence_expired") from None
        return row.snapshot, row.revision


    def revoke_authorization(self, profile_id: uuid.UUID, expected_revision: int, reason: str) -> None:
        if not reason.isidentifier():
            raise AdmissionStoreError("authorization_reason_invalid")
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE profile_authorizations SET state = 'revoked', revision = revision + 1,
                reason = :reason WHERE profile_id = :id AND revision = :expected AND state = 'enabled'"""),
                {"reason": reason, "id": profile_id, "expected": expected_revision})
            if changed.rowcount != 1:
                raise AdmissionStoreError("authorization_revision_changed")

    def begin_submission(self, key: str, request_hash: str, media_type: str) -> tuple[str, uuid.UUID | None, uuid.UUID | None, str | None]:
        intent_id = uuid.uuid4()
        with self.engine.begin() as connection:
            created = connection.execute(text("""INSERT INTO submission_requests (idempotency_key, request_hash, state)
                VALUES (:key, :hash, 'publishing') ON CONFLICT DO NOTHING RETURNING idempotency_key"""),
                {"key": key, "hash": request_hash}).first()
            row = connection.execute(text("SELECT * FROM submission_requests WHERE idempotency_key = :key FOR UPDATE"), {"key": key}).one()
            if row.request_hash != request_hash:
                raise AdmissionStoreError("idempotency_key_conflict")
            if not created:
                return row.state, row.run_id, row.intent_id, row.error_code
            connection.execute(text("""INSERT INTO publication_intents
                (id, idempotency_key, submission_key, media_type, state)
                VALUES (:id, :intent_key, :key, :media, 'pending_upload')"""),
                {"id": intent_id, "intent_key": f"submission-intent:{intent_id}", "key": key, "media": media_type})
            connection.execute(text("UPDATE submission_requests SET intent_id = :intent WHERE idempotency_key = :key"),
                {"intent": intent_id, "key": key})
            return "created", None, intent_id, None

    def fail_submission(self, key: str, code: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""UPDATE submission_requests SET state = 'failed', error_code = :code
                WHERE idempotency_key = :key AND state = 'publishing'"""), {"key": key, "code": code})

    def commit_submission(self, key: str, profile_id: uuid.UUID, revision: int, snapshot: dict,
                          context: dict, requested_classes: list[str], image_hash: str, image_size: int,
                          intent: str = "observation_only", stage: str | None = None) -> uuid.UUID:
        with self.engine.connect() as connection:
            intent_id = connection.execute(text("SELECT intent_id FROM submission_requests WHERE idempotency_key = :key"), {"key": key}).scalar_one()
        return self.commit_series_submission(key, profile_id, revision, snapshot, context, requested_classes,
                                             [(intent_id, image_hash, image_size)], intent, stage)

    def commit_series_submission(self, key: str, profile_id: uuid.UUID, revision: int, snapshot: dict,
                                 context: dict, requested_classes: list[str],
                                 manifest: list[tuple[uuid.UUID, str, int]],
                                 intent: str = "observation_only", stage: str | None = None) -> uuid.UUID:
        run_id = uuid.uuid4()
        with self.engine.begin() as connection:
            request = connection.execute(text("""SELECT * FROM submission_requests
                WHERE idempotency_key = :key FOR UPDATE"""), {"key": key}).one()
            if request.state != "publishing":
                raise AdmissionStoreError("submission_state_changed")
            if intent not in ("observation_only", "rule_evaluation") or (intent == "rule_evaluation" and stage != "excavation"):
                raise AdmissionStoreError("rule_not_applicable")
            authorization = connection.execute(text("""SELECT p.status, p.snapshot, a.state, a.revision FROM observer_profiles p
                JOIN profile_authorizations a ON a.profile_id = p.id WHERE p.id = :id FOR UPDATE OF a"""),
                {"id": profile_id}).one_or_none()
            if (not authorization or authorization.status != "admitted" or authorization.state != "enabled"
                    or authorization.revision != revision
                    or (snapshot.get("kind") == "cloud_api" and authorization.snapshot != snapshot)):
                raise AdmissionStoreError("profile_unauthorized")
            if snapshot.get("kind") == "cloud_api" and any(
                    item[1] not in snapshot.get("allowed_input_sha256", []) for item in manifest):
                raise AdmissionStoreError("cloud_image_not_authorized")
            if not manifest or manifest[0][0] != request.intent_id or len({item[0] for item in manifest}) != len(manifest):
                raise AdmissionStoreError("publication_incomplete")
            publications = []
            for intent_id, image_hash, image_size in manifest:
                publication = connection.execute(text("""SELECT sha256, size, final_key FROM publication_intents
                    WHERE id = :id AND submission_key = :key AND run_id IS NULL
                      AND state = 'object_published' FOR UPDATE"""),
                    {"id": intent_id, "key": key}).one_or_none()
                if not publication or publication.sha256 != image_hash or publication.size != image_size or publication.final_key != f"sha256/{image_hash}":
                    raise AdmissionStoreError("publication_incomplete")
                publications.append(publication)
            connection.execute(text("""INSERT INTO analysis_runs
                (id, state, purpose, profile_id, authorization_revision, binding_kind, profile_snapshot,
                 request_context, policy_snapshot, rule_snapshot, analysis_intent, stage_key,
                 taxonomy_snapshot, requested_classes)
                VALUES (:run, 'queued', 'ordinary', :profile, :revision, 'admitted_profile',
                    CAST(:snapshot AS jsonb), CAST(:context AS jsonb), CAST(:policy AS jsonb),
                    CAST(:rule AS jsonb), :intent, :stage,
                    CAST(:taxonomy AS jsonb), CAST(:classes AS jsonb))"""),
                {"run": run_id, "profile": profile_id, "revision": revision,
                 "snapshot": json.dumps(snapshot), "context": json.dumps(context),
                 "policy": json.dumps({"intent": intent, **(RULE_POLICY if intent == "rule_evaluation" else {"revision": "observations-only-v1"})}),
                 "rule": json.dumps(RULE) if intent == "rule_evaluation" else None,
                 "intent": intent, "stage": stage,
                 "taxonomy": json.dumps({"portable_classes": list(CLASSES), "revision": "presence-only-v1"}),
                 "classes": json.dumps(requested_classes)})
            for ordinal, ((intent_id, image_hash, image_size), publication) in enumerate(zip(manifest, publications)):
                artifact_id = uuid.uuid4()
                connection.execute(text("""INSERT INTO artifact_metadata (id, run_id, intent_id, key, sha256, size, media_type)
                    VALUES (:id, :run, :intent, :key, :hash, :size, 'image/jpeg')"""),
                    {"id": artifact_id, "run": run_id, "intent": intent_id, "key": publication.final_key,
                     "hash": image_hash, "size": image_size})
                connection.execute(text("""INSERT INTO run_inputs (run_id, ordinal, sha256, size, context, artifact_id)
                    VALUES (:run, :ordinal, :hash, :size, CAST(:context AS jsonb), :artifact)"""),
                    {"run": run_id, "ordinal": ordinal, "hash": image_hash, "size": image_size,
                     "context": json.dumps(context), "artifact": artifact_id})
                connection.execute(text("UPDATE publication_intents SET run_id = :run, state = 'referenced' WHERE id = :id"),
                    {"run": run_id, "id": intent_id})
            for ordinal, name in enumerate(STAGES):
                connection.execute(text("""INSERT INTO analysis_stages (run_id, ordinal, name, state)
                    VALUES (:run, :ordinal, :name, 'pending')"""),
                    {"run": run_id, "ordinal": ordinal, "name": name})
            connection.execute(text("UPDATE submission_requests SET run_id = :run, state = 'accepted' WHERE idempotency_key = :key"),
                {"run": run_id, "key": key})
        return run_id

    def claim_ordinary(self, profile_id: uuid.UUID, revision: int, lease_seconds: int) -> dict | None:
        owner = str(uuid.uuid4())
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.id, r.profile_snapshot, r.requested_classes, r.authorization_revision,
                i.sha256, i.size, a.key, a.id AS artifact_id, i.input_id, i.ordinal
                FROM analysis_runs r JOIN run_inputs i ON i.run_id = r.id AND i.ordinal = 0
                JOIN artifact_metadata a ON a.id = i.artifact_id
                JOIN profile_authorizations auth ON auth.profile_id = r.profile_id
                WHERE r.state = 'queued' AND r.purpose = 'ordinary' AND r.profile_id = :profile
                  AND r.authorization_revision = :revision AND auth.state = 'enabled' AND auth.revision = :revision
                ORDER BY r.id FOR UPDATE OF r SKIP LOCKED LIMIT 1"""),
                {"profile": profile_id, "revision": revision}).one_or_none()
            if not row:
                return None
            connection.execute(text("""UPDATE analysis_runs SET state = 'running', lease_owner = :owner,
                lease_expires_at = clock_timestamp() + (:seconds * interval '1 second') WHERE id = :run"""),
                {"run": row.id, "owner": owner, "seconds": lease_seconds})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 0"), {"run": row.id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 1"), {"run": row.id})
            frames = connection.execute(text("""SELECT i.input_id, i.ordinal, i.sha256, i.size,
                a.key, a.id AS artifact_id FROM run_inputs i JOIN artifact_metadata a ON a.id = i.artifact_id
                WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": row.id}).mappings().all()
            return {**row._mapping, "owner": owner, "frames": [dict(frame) for frame in frames]}

    def renew_ordinary(self, run_id: uuid.UUID, owner: str, revision: int, lease_seconds: int) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE analysis_runs r SET lease_expires_at = clock_timestamp() + (:seconds * interval '1 second')
                FROM profile_authorizations a WHERE r.id = :run AND r.profile_id = a.profile_id AND r.purpose = 'ordinary'
                AND r.state = 'running' AND r.lease_owner = :owner AND r.lease_expires_at > clock_timestamp()
                AND r.authorization_revision = :revision AND a.state = 'enabled' AND a.revision = :revision"""),
                {"run": run_id, "owner": owner, "revision": revision, "seconds": lease_seconds})
            if changed.rowcount != 1:
                raise AdmissionStoreError("ordinary_lease_rejected")

    def reserve_ordinary(self, run_id: uuid.UUID, owner: str, revision: int, image_hash: str,
                         call_provider: bool = True, input_id: uuid.UUID | None = None,
                         campaign: bool = False) -> uuid.UUID | None:
        invocation = uuid.uuid4()
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.state, r.lease_owner, r.lease_expires_at > clock_timestamp() AS live,
                r.authorization_revision, r.profile_snapshot, r.purpose,
                a.state AS auth_state, a.revision AS auth_revision, i.sha256, i.input_id
                FROM analysis_runs r JOIN profile_authorizations a ON a.profile_id = r.profile_id
                JOIN run_inputs i ON i.run_id = r.id AND i.input_id = COALESCE(:input_id, (SELECT input_id FROM run_inputs WHERE run_id = :run AND ordinal = 0))
                WHERE r.id = :run FOR UPDATE OF r, a"""), {"run": run_id, "input_id": input_id}).one_or_none()
            if (not row or row.state != "running" or row.lease_owner != owner or not row.live
                    or (row.purpose == 'comparison_campaign') != campaign
                    or row.authorization_revision != revision or row.sha256 != image_hash):
                raise AdmissionStoreError("ordinary_reservation_rejected")
            if row.auth_state != "enabled":
                raise AdmissionStoreError("profile_unauthorized" if campaign else "ordinary_reservation_rejected")
            if row.auth_revision != revision:
                raise AdmissionStoreError("authorization_revision_changed" if campaign else "ordinary_reservation_rejected")
            if row.profile_snapshot.get("kind") == "cloud_api" and image_hash not in row.profile_snapshot.get("allowed_input_sha256", []):
                raise AdmissionStoreError("cloud_image_not_authorized")
            if row.profile_snapshot.get("kind") == "cloud_api" and call_provider:
                try:
                    cloud_api.validate_owner_evidence(row.profile_snapshot.get("owner_evidence"),
                        row.profile_snapshot["owner_evidence"]["canary_image_sha256"],
                        row.profile_snapshot["allowed_input_sha256"])
                except (KeyError, cloud_api.CloudObserverError):
                    raise AdmissionStoreError("profile_owner_evidence_expired") from None
            existing = connection.execute(text("SELECT 1 FROM observations WHERE run_id = :run AND input_id = :input_id LIMIT 1"),
                                          {"run": run_id, "input_id": row.input_id}).first()
            if existing:
                raise AdmissionStoreError("ordinary_reservation_rejected")
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 1 AND state = 'running'"), {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 2 AND state = 'pending'"), {"run": run_id})
            if call_provider:
                if campaign:
                    timeout = float(row.profile_snapshot['runtime']['per_image_timeout_seconds'])
                    connection.execute(text("""UPDATE analysis_runs SET provider_safe_after =
                        GREATEST(COALESCE(provider_safe_after, clock_timestamp()),
                        clock_timestamp() + (:seconds * interval '1 second'))
                        WHERE id = :run AND lease_owner = :owner"""),
                        {"seconds": timeout + 15, "run": run_id, "owner": owner})
                request_identity = (row.profile_snapshot["requested_model_identity"]["id"]
                                    if row.profile_snapshot.get("kind") == "cloud_api" else "local-grounding-dino-cpu")
                connection.execute(text("""INSERT INTO observer_invocations
                    (id, run_id, input_id, fence, profile_id, authorization_revision, stage_ordinal, input_sha256,
                     intended_request_identity, state)
                    SELECT :id, :run, :input_id, 1, profile_id, :revision, 2, :hash, :identity, 'reserved'
                    FROM analysis_runs WHERE id = :run"""),
                    {"id": invocation, "run": run_id, "input_id": row.input_id,
                     "revision": revision, "hash": image_hash, "identity": request_identity})
        return invocation if call_provider else None

    def finish_ordinary(self, run_id: uuid.UUID, owner: str, revision: int, invocation: uuid.UUID | None,
                        result: dict | None, native_intent: uuid.UUID | None, observations: list[dict],
                        input_id: uuid.UUID | None = None, batch_deadline: float | None = None,
                        campaign: bool = False) -> None:
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.profile_snapshot, r.state, r.lease_owner,
                r.lease_expires_at > clock_timestamp() AS live, r.authorization_revision, r.purpose,
                a.state AS auth_state, a.revision AS auth_revision, i.state AS invocation_state
                FROM analysis_runs r JOIN profile_authorizations a ON a.profile_id = r.profile_id
                LEFT JOIN observer_invocations i ON i.run_id = r.id AND i.id = :invocation
                WHERE r.id = :run FOR UPDATE OF r, a"""), {"run": run_id, "invocation": invocation}).one_or_none()
            if (not row or row.state != "running" or row.lease_owner != owner or not row.live
                    or (row.purpose == 'comparison_campaign') != campaign
                    or row.authorization_revision != revision
                    or (not campaign and (row.auth_state != "enabled" or row.auth_revision != revision))):
                raise AdmissionStoreError("ordinary_completion_rejected")
            expected_classes = connection.execute(text("SELECT requested_classes FROM analysis_runs WHERE id = :run"), {"run": run_id}).scalar_one()
            source = connection.execute(text("""SELECT input_id, ordinal, artifact_id, sha256 FROM run_inputs
                WHERE run_id = :run AND input_id = COALESCE(:input_id,
                    (SELECT input_id FROM run_inputs WHERE run_id = :run AND ordinal = 0))"""),
                {"run": run_id, "input_id": input_id}).one_or_none()
            if source is None:
                raise AdmissionStoreError("ordinary_completion_rejected")
            source_artifact_id = source.artifact_id
            if (len(observations) != len(expected_classes)
                    or {item["class_name"] for item in observations} != set(expected_classes)
                    or any(item["source_artifact_id"] != str(source_artifact_id) for item in observations)
                    or connection.execute(text("SELECT 1 FROM observations WHERE run_id = :run AND input_id = :input_id LIMIT 1"),
                                          {"run": run_id, "input_id": source.input_id}).first() is not None
                    or (invocation is not None and connection.execute(text("SELECT input_id FROM observer_invocations WHERE id = :id"),
                        {"id": invocation}).scalar_one_or_none() != source.input_id)
                    or (result is None) != (invocation is None)
                    or (result is None and any(item["state"] not in ("insufficient_data", "not_analyzed") for item in observations))):
                raise AdmissionStoreError("observation_normalization_failed")
            native_artifact_id = None
            if result is not None:
                cloud = row.profile_snapshot.get("kind") == "cloud_api"
                expected = row.profile_snapshot["requested_model_identity"]["id"] if cloud else row.profile_snapshot["model_files"]["model.safetensors"]
                identity_valid = (result.get("returned_model_identity") in (expected, expected + "/latest")
                                  and isinstance(result.get("returned_request_identity"), str)
                                  and bool(result["returned_request_identity"])
                                  if cloud else result.get("returned_model_identity") == f"checkpoint-sha256:{expected}")
                if (row.invocation_state != "reserved" or not identity_valid
                        or result.get("actual_device") != ("remote_unreported" if cloud else "cpu")
                        or result.get("preprocessing_revision") != (cloud_api.PREPROCESSING_REVISION if cloud else grounding_dino.PREPROCESSING_REVISION)):
                    raise AdmissionStoreError("observer_identity_or_device_invalid")
                intent = connection.execute(text("""SELECT * FROM publication_intents WHERE id = :id AND run_id = :run
                    AND state = 'object_published' FOR UPDATE"""), {"id": native_intent, "run": run_id}).one_or_none()
                if not intent:
                    raise AdmissionStoreError("publication_incomplete")
                native_artifact_id = uuid.uuid4()
                connection.execute(text("""INSERT INTO artifact_metadata (id, run_id, intent_id, key, sha256, size, media_type)
                    VALUES (:id, :run, :intent, :key, :hash, :size, :media)"""),
                    {"id": native_artifact_id, "run": run_id, "intent": native_intent, "key": intent.final_key,
                     "hash": intent.sha256, "size": intent.size, "media": intent.media_type})
                connection.execute(text("UPDATE publication_intents SET state = 'referenced' WHERE id = :id"), {"id": native_intent})
                connection.execute(text("""UPDATE observer_invocations SET state = 'completed',
                    returned_model_identity = :identity, returned_request_identity = :request_identity,
                    actual_device = :device, preprocessing_revision = :pre,
                    native_artifact_id = :artifact WHERE id = :id AND state = 'reserved'"""),
                    {"identity": result["returned_model_identity"], "device": result["actual_device"], "pre": result["preprocessing_revision"],
                     "request_identity": result.get("returned_request_identity"),
                     "artifact": native_artifact_id, "id": invocation})
                connection.execute(text("""UPDATE analysis_runs SET latency_ms = COALESCE(latency_ms, 0) + :latency,
                    peak_memory_bytes = GREATEST(COALESCE(peak_memory_bytes, 0), COALESCE(:memory, 0)) WHERE id = :run"""),
                    {"latency": result["latency_ms"], "memory": result["peak_memory_bytes"], "run": run_id})
            for observation in observations:
                connection.execute(text("""INSERT INTO observations
                    (run_id, input_id, class_name, state, reason, input_sha256, invocation_id, source_artifact_id)
                    VALUES (:run, :input_id, :class_name, :state, :reason, :hash, :invocation, :source_artifact_id)"""),
                    {"run": run_id, "input_id": source.input_id, "hash": source.sha256,
                     "invocation": invocation, **observation})
            inputs = connection.execute(text("SELECT count(*) FROM run_inputs WHERE run_id = :run"), {"run": run_id}).scalar_one()
            completed = connection.execute(text("""SELECT count(DISTINCT input_id) FROM observations
                WHERE run_id = :run"""), {"run": run_id}).scalar_one()
            if completed != inputs:
                if batch_deadline is not None and monotonic() >= batch_deadline:
                    raise RuntimeError("observer_timeout")
                return
            if connection.execute(text("SELECT count(*) FROM observations WHERE run_id = :run"),
                                  {"run": run_id}).scalar_one() != inputs * len(expected_classes):
                raise AdmissionStoreError("observation_incomplete")
            if connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run AND state != 'completed'"),
                                  {"run": run_id}).scalar_one():
                raise AdmissionStoreError("observation_incomplete")
            calls = connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run"),
                                       {"run": run_id}).scalar_one()
            connection.execute(text("""UPDATE analysis_stages SET state = :state, reason = :reason
                WHERE run_id = :run AND ordinal = 2 AND state = 'running'"""),
                {"run": run_id, "state": "succeeded" if calls else "skipped",
                 "reason": None if calls else "no_assessable_frame_or_supported_class"})
            connection.execute(text("""UPDATE analysis_stages SET state = :state, reason = :reason
                WHERE run_id = :run AND ordinal = 3"""),
                {"run": run_id, "state": "succeeded" if inputs > 1 else "skipped",
                 "reason": None if inputs > 1 else "not_applicable"})
            binding = connection.execute(text("SELECT analysis_intent, policy_snapshot, rule_snapshot, request_context FROM analysis_runs WHERE id = :run"),
                                         {"run": run_id}).one()
            connection.execute(text("UPDATE analysis_stages SET state = :state, reason = :reason WHERE run_id = :run AND ordinal = 4"),
                               {"run": run_id, "state": "succeeded" if binding.analysis_intent == "rule_evaluation" else "skipped",
                                "reason": None if binding.analysis_intent == "rule_evaluation" else "not_applicable"})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 5"), {"run": run_id})
            evidence = connection.execute(text("""SELECT i.input_id, i.ordinal, o.class_name, o.state, o.reason,
                o.source_artifact_id, o.invocation_id FROM run_inputs i JOIN observations o
                ON o.run_id = i.run_id AND o.input_id = i.input_id
                WHERE i.run_id = :run ORDER BY i.ordinal, o.class_name"""), {"run": run_id}).mappings().all()
            usable = connection.execute(text("""SELECT i.input_id FROM run_inputs i JOIN observer_invocations v
                ON v.run_id = i.run_id AND v.input_id = i.input_id AND v.state = 'completed'
                WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": run_id}).scalars().all()
            unassessable_ids = {str(item["input_id"]) for item in evidence
                                if item["state"] == "insufficient_data"}
            usable_ids = [str(item) for item in usable if str(item) not in unassessable_ids]
            excavator_ids = [str(item["input_id"]) for item in evidence
                             if item["class_name"] == "excavator" and item["state"] == "detected"]
            dump_truck_ids = [str(item["input_id"]) for item in evidence
                              if item["class_name"] == "dump_truck" and item["state"] == "not_detected_in_frame"
                              and str(item["input_id"]) in usable_ids]
            area = connection.execute(text("SELECT request_context->>'observation_area' FROM analysis_runs WHERE id = :run"),
                                      {"run": run_id}).scalar_one()
            series = {"usable_count": len(usable_ids), "usable_input_ids": usable_ids,
                      "declared_observation_area": area,
                      "input_order": [str(item["input_id"]) for item in sorted(evidence, key=lambda item: item["ordinal"])
                                      if item["class_name"] == expected_classes[0]],
                      "excavator_supporting_input_ids": excavator_ids,
                      "dump_truck_persistence_input_ids": dump_truck_ids if len(usable_ids) > 1 and len(dump_truck_ids) == len(usable_ids) else [],
                      "dump_truck_persistence_text": (f"Самосвал не обнаружен ни в одном из {len(usable_ids)} пригодных кадров."
                          if "dump_truck" in expected_classes and len(usable_ids) > 1 and len(dump_truck_ids) == len(usable_ids) else None)}
            projection = {"outcome": "observations_only", "frames": [
                {**dict(item), "input_id": str(item["input_id"]),
                 "source_artifact_id": str(item["source_artifact_id"]),
                 "invocation_id": str(item["invocation_id"]) if item["invocation_id"] else None}
                for item in evidence], "series": series}
            if binding.analysis_intent == "rule_evaluation":
                projection.update(evaluate_rule(projection["frames"], usable_ids,
                                                binding.policy_snapshot, binding.rule_snapshot,
                                                binding.request_context))
            connection.execute(text("""INSERT INTO result_projections (run_id, outcome, snapshot)
                VALUES (:run, :outcome, CAST(:snapshot AS jsonb))"""),
                {"run": run_id, "outcome": projection["outcome"], "snapshot": json.dumps(projection)})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 5"), {"run": run_id})
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL,
                lease_expires_at = NULL WHERE id = :run AND state = 'running' AND lease_owner = :owner
                AND lease_expires_at > clock_timestamp()"""), {"run": run_id, "owner": owner})
            if changed.rowcount != 1:
                raise AdmissionStoreError("ordinary_completion_rejected")
            if batch_deadline is not None and monotonic() >= batch_deadline:
                raise RuntimeError("observer_timeout")

    def fail_ordinary(self, run_id: uuid.UUID, owner: str, code: str) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = :code,
                lease_owner = NULL, lease_expires_at = NULL WHERE id = :run AND state = 'running'
                AND lease_owner = :owner AND lease_expires_at > clock_timestamp()"""),
                {"run": run_id, "owner": owner, "code": code})
            if changed.rowcount:
                connection.execute(text("UPDATE observer_invocations SET state = 'failed' WHERE run_id = :run AND state = 'reserved'"), {"run": run_id})
                connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = :code WHERE run_id = :run AND state = 'running'"), {"run": run_id, "code": code})
                connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND state = 'pending'"), {"run": run_id})

    def fail_unauthorized_queued(self) -> None:
        with self.engine.begin() as connection:
            rows = connection.execute(text("""SELECT r.id FROM analysis_runs r
                LEFT JOIN profile_authorizations a ON a.profile_id = r.profile_id
                WHERE r.purpose = 'ordinary' AND r.state = 'queued'
                  AND (a.state IS DISTINCT FROM 'enabled' OR a.revision IS DISTINCT FROM r.authorization_revision)
                FOR UPDATE OF r SKIP LOCKED""")).scalars().all()
            for run_id in rows:
                connection.execute(text("UPDATE analysis_runs SET state = 'failed', error_code = 'profile_unauthorized' WHERE id = :run"), {"run": run_id})
                connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = 'profile_unauthorized' WHERE run_id = :run AND ordinal = 0"), {"run": run_id})
                connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND ordinal > 0"), {"run": run_id})

    def read_ordinary(self, run_id: uuid.UUID) -> dict | None:
        with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            row = connection.execute(text("""SELECT r.id, r.state, r.error_code, r.request_context, r.requested_classes,
                r.created_at, r.profile_id, r.authorization_revision, r.binding_kind, r.profile_snapshot,
                r.taxonomy_snapshot, r.analysis_intent, r.stage_key, r.policy_snapshot, r.rule_snapshot,
                r.retry_predecessor_id, successor.id AS retry_successor_id
                FROM analysis_runs r LEFT JOIN analysis_runs successor ON successor.retry_predecessor_id = r.id
                WHERE r.id = :id AND r.purpose = 'ordinary'"""), {"id": run_id}).one_or_none()
            if not row:
                return None
            stages = connection.execute(text("SELECT name, state, reason FROM analysis_stages WHERE run_id = :id ORDER BY ordinal"), {"id": run_id}).mappings().all()
            inputs = connection.execute(text("""SELECT input_id, ordinal, sha256, size, artifact_id
                FROM run_inputs WHERE run_id = :id ORDER BY ordinal"""), {"id": run_id}).mappings().all()
            observations = connection.execute(text("""SELECT o.class_name, o.state, o.reason, o.input_sha256,
                o.source_artifact_id, o.input_id, i.ordinal, o.invocation_id
                FROM observations o JOIN run_inputs i ON i.input_id = o.input_id
                WHERE o.run_id = :id ORDER BY i.ordinal, o.class_name"""), {"id": run_id}).mappings().all()
            projection = connection.execute(text("SELECT snapshot FROM result_projections WHERE run_id = :id"), {"id": run_id}).scalar_one_or_none()
            native = connection.execute(text("""SELECT a.id, a.sha256, a.size, i.input_id, i.id AS invocation_id,
                i.preprocessing_revision, i.authorization_revision, i.profile_id, r.ordinal
                FROM observer_invocations i JOIN artifact_metadata a ON a.id = i.native_artifact_id
                JOIN run_inputs r ON r.input_id = i.input_id
                WHERE i.run_id = :id ORDER BY r.ordinal"""), {"id": run_id}).mappings().all()
            return {"run_id": str(row.id), "state": row.state, "error_code": row.error_code,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "context": row.request_context, "requested_classes": row.requested_classes,
                    "profile_id": str(row.profile_id) if row.profile_id else None,
                    "authorization_revision": row.authorization_revision,
                    "binding_kind": row.binding_kind, "profile_snapshot": row.profile_snapshot,
                    "taxonomy_snapshot": row.taxonomy_snapshot,
                    "intent": row.analysis_intent or "observation_only",
                    "stage": row.stage_key or (row.request_context or {}).get("stage_id"),
                    "retry_predecessor_id": str(row.retry_predecessor_id) if row.retry_predecessor_id else None,
                    "retry_successor_id": str(row.retry_successor_id) if row.retry_successor_id else None,
                    "retry_of_run_id": str(row.retry_predecessor_id) if row.retry_predecessor_id else None,
                    "successor_run_id": str(row.retry_successor_id) if row.retry_successor_id else None,
                    "policy_snapshot": row.policy_snapshot, "rule_snapshot": row.rule_snapshot,
                    "stages": [dict(item) for item in stages],
                    "inputs": [{**item, "input_id": str(item["input_id"]),
                                "artifact_id": str(item["artifact_id"]) if item["artifact_id"] else None}
                               for item in inputs],
                    "observations": [{**item, "input_id": str(item["input_id"]),
                                      "source_artifact_id": str(item["source_artifact_id"]) if item["source_artifact_id"] else None,
                                      "invocation_id": str(item["invocation_id"]) if item["invocation_id"] else None}
                                     for item in observations],
                    "native_evidence": ({"artifact_id": str(native[0]["id"]), "sha256": native[0]["sha256"],
                                         "size": native[0]["size"]} if len(inputs) == 1 and native else None),
                    "native_evidence_by_frame": [{"artifact_id": str(item["id"]), "sha256": item["sha256"],
                                                  "size": item["size"], "ordinal": item["ordinal"],
                                                  "input_id": str(item["input_id"]), "invocation_id": str(item["invocation_id"]),
                                                  "profile_id": str(item["profile_id"]), "profile_revision": item["authorization_revision"],
                                                  "preprocessing_revision": item["preprocessing_revision"]} for item in native],
                    "outcome": projection["outcome"] if projection and row.state == "succeeded" else None,
                    "result_projection": projection if projection and row.state == "succeeded" else None}

    def list_ordinary(self, offset: int = 0) -> dict:
        with self.engine.connect() as connection:
            rows = connection.execute(text("""SELECT r.id, r.state, r.created_at,
                COALESCE(r.stage_key, r.request_context->>'stage_id') AS stage,
                r.analysis_intent, r.retry_predecessor_id, s.id AS retry_successor_id,
                CASE WHEN r.state = 'succeeded' THEN p.outcome END AS outcome
                FROM analysis_runs r
                LEFT JOIN analysis_runs s ON s.retry_predecessor_id = r.id
                LEFT JOIN result_projections p ON p.run_id = r.id
                WHERE r.purpose = 'ordinary' ORDER BY r.created_at DESC NULLS LAST, r.id DESC
                LIMIT 51 OFFSET :offset"""), {"offset": offset}).mappings().all()
        return {"runs": [{"id": str(row.id), "run_id": str(row.id), "state": row.state,
                 "created_at": row.created_at.isoformat() if row.created_at else None,
                 "stage": row.stage, "intent": row.analysis_intent or "observation_only",
                 "outcome": row.outcome,
                 "retry_predecessor_id": str(row.retry_predecessor_id) if row.retry_predecessor_id else None,
                 "retry_successor_id": str(row.retry_successor_id) if row.retry_successor_id else None,
                 "retry_of_run_id": str(row.retry_predecessor_id) if row.retry_predecessor_id else None,
                 "successor_run_id": str(row.retry_successor_id) if row.retry_successor_id else None}
                for row in rows[:50]], "next_offset": offset + 50 if len(rows) > 50 else None}

    def stage_summary(self) -> dict:
        with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            rows = connection.execute(text("""WITH latest_run AS (
                    SELECT r.id, r.state, r.created_at, NULL::jsonb AS snapshot, 'run' AS kind
                    FROM analysis_runs r
                    WHERE r.purpose = 'ordinary' AND (r.stage_key = 'excavation' OR (r.stage_key IS NULL AND r.request_context->>'stage_id' = 'excavation'))
                    ORDER BY r.created_at DESC NULLS LAST, r.id DESC LIMIT 1
                ), latest_result AS (
                    SELECT r.id, r.state, r.created_at, p.snapshot, 'result' AS kind
                    FROM analysis_runs r JOIN result_projections p ON p.run_id = r.id
                    WHERE r.purpose = 'ordinary' AND r.state = 'succeeded'
                      AND (r.stage_key = 'excavation' OR (r.stage_key IS NULL AND r.request_context->>'stage_id' = 'excavation'))
                    ORDER BY r.created_at DESC NULLS LAST, r.id DESC LIMIT 1
                ) SELECT * FROM latest_run UNION ALL SELECT * FROM latest_result""")).mappings().all()
        result = next((row for row in rows if row["kind"] == "result"), None)
        latest = next((row for row in rows if row["kind"] == "run"), None)
        newer = latest if latest and (not result or latest["id"] != result["id"]) else None

        def reference(row: dict | None) -> dict | None:
            return ({"run_id": str(row["id"]), "created_at": row["created_at"].isoformat() if row["created_at"] else None}
                    if row else None)

        return {"stages": [
            {"stage_id": "preparation", "name": "Подготовительные работы", "supported": False,
             "latest_result": None, "latest_lifecycle": None},
            {"stage_id": "excavation", "name": "Земляные работы котлована", "supported": True,
             "latest_result": {**reference(result), "projection": result["snapshot"]} if result else None,
             "latest_lifecycle": {**reference(newer), "state": newer["state"]} if newer else None},
            {"stage_id": "foundation", "name": "Устройство фундамента", "supported": False,
             "latest_result": None, "latest_lifecycle": None},
            {"stage_id": "monolithic", "name": "Монолитные работы", "supported": False,
             "latest_result": None, "latest_lifecycle": None},
        ]}

    def retry_ordinary(self, source_id: uuid.UUID, profile_id: uuid.UUID, revision: int,
                       snapshot: dict, artifacts: ArtifactStore) -> uuid.UUID:
        source_query = text("""SELECT * FROM analysis_runs WHERE id = :id AND purpose = 'ordinary'""")
        inputs_query = text("""SELECT i.ordinal, i.input_id, i.sha256, i.size, i.context,
            a.id AS artifact_id, a.key, a.media_type, a.sha256 AS artifact_sha256,
            a.size AS artifact_size FROM run_inputs i
            JOIN artifact_metadata a ON a.id = i.artifact_id AND a.run_id = i.run_id
            WHERE i.run_id = :id ORDER BY i.ordinal""")
        with self.engine.connect() as connection:
            preliminary = connection.execute(source_query, {"id": source_id}).mappings().one_or_none()
            if preliminary is None:
                raise AdmissionStoreError("run_not_found")
            if preliminary["state"] != "failed":
                raise AdmissionStoreError("retry_ineligible")
            existing = connection.execute(text("SELECT id FROM analysis_runs WHERE retry_predecessor_id = :id"),
                                          {"id": source_id}).scalar_one_or_none()
            if existing:
                return existing
            verified_inputs = [dict(item) for item in connection.execute(inputs_query, {"id": source_id}).mappings()]
        if not verified_inputs or any(item["ordinal"] != ordinal or item["media_type"] != "image/jpeg"
                                      or item["sha256"] != item["artifact_sha256"]
                                      or item["size"] != item["artifact_size"]
                                      for ordinal, item in enumerate(verified_inputs)):
            raise AdmissionStoreError("retry_source_unavailable")
        if snapshot.get("kind") == "cloud_api" and any(
                item["sha256"] not in snapshot.get("allowed_input_sha256", []) for item in verified_inputs):
            raise AdmissionStoreError("cloud_image_not_authorized")
        for item in verified_inputs:
            try:
                artifacts.read_verified(item["key"], item["sha256"], item["size"])
            except ArtifactGateError:
                raise AdmissionStoreError("retry_source_unavailable") from None
        with self.engine.begin() as connection:
            source = connection.execute(text("""SELECT * FROM analysis_runs
                WHERE id = :id AND purpose = 'ordinary' FOR UPDATE"""), {"id": source_id}).mappings().one_or_none()
            if source is None:
                raise AdmissionStoreError("run_not_found")
            if source["state"] != "failed":
                raise AdmissionStoreError("retry_ineligible")
            successor = connection.execute(text("SELECT id FROM analysis_runs WHERE retry_predecessor_id = :id"),
                                           {"id": source_id}).scalar_one_or_none()
            if successor:
                return successor
            inputs = [dict(item) for item in connection.execute(inputs_query, {"id": source_id}).mappings()]
            if dict(source) != dict(preliminary) or inputs != verified_inputs:
                raise AdmissionStoreError("retry_source_unavailable")
            authorization = connection.execute(text("""SELECT p.status, p.snapshot, p.profile_hash, p.audit_hash,
                a.audit_hash AS authorization_audit, a.state, a.revision FROM observer_profiles p
                JOIN profile_authorizations a ON a.profile_id = p.id
                WHERE p.id = :id FOR UPDATE OF p, a"""), {"id": profile_id}).one_or_none()
            if (not authorization or authorization.status != "admitted" or authorization.state != "enabled"
                    or authorization.revision != revision or authorization.snapshot != snapshot
                    or authorization.audit_hash != authorization.authorization_audit):
                raise AdmissionStoreError("profile_unauthorized")
            run_id = uuid.uuid4()
            connection.execute(text("""INSERT INTO analysis_runs
                (id, state, purpose, profile_id, authorization_revision, binding_kind, profile_snapshot,
                 request_context, policy_snapshot, rule_snapshot, analysis_intent, stage_key,
                 taxonomy_snapshot, requested_classes, retry_predecessor_id)
                VALUES (:id, 'queued', 'ordinary', :profile, :revision, 'admitted_profile',
                    CAST(:snapshot AS jsonb), CAST(:context AS jsonb), CAST(:policy AS jsonb),
                    CAST(:rule AS jsonb), :intent, :stage, CAST(:taxonomy AS jsonb), CAST(:classes AS jsonb), :source)"""),
                {"id": run_id, "profile": profile_id, "revision": revision, "snapshot": json.dumps(snapshot),
                 "context": json.dumps(source["request_context"]), "policy": json.dumps(source["policy_snapshot"]),
                 "rule": json.dumps(source["rule_snapshot"]) if source["rule_snapshot"] is not None else None,
                 "intent": source["analysis_intent"] or "observation_only", "stage": source["stage_key"],
                 "taxonomy": json.dumps(source["taxonomy_snapshot"]), "classes": json.dumps(source["requested_classes"]),
                 "source": source_id})
            for item in inputs:
                artifact_id = uuid.uuid4()
                connection.execute(text("""INSERT INTO artifact_metadata
                    (id, run_id, source_artifact_id, key, sha256, size, media_type)
                    VALUES (:id, :run, :source, :key, :sha, :size, :media)"""),
                    {"id": artifact_id, "run": run_id, "source": item["artifact_id"], "key": item["key"],
                     "sha": item["sha256"], "size": item["size"], "media": item["media_type"]})
                connection.execute(text("""INSERT INTO run_inputs
                    (run_id, ordinal, input_id, sha256, size, context, artifact_id)
                    VALUES (:run, :ordinal, :input, :sha, :size, CAST(:context AS jsonb), :artifact)"""),
                    {"run": run_id, "ordinal": item["ordinal"], "input": uuid.uuid4(),
                     "sha": item["sha256"], "size": item["size"], "context": json.dumps(item["context"]),
                     "artifact": artifact_id})
            for ordinal, name in enumerate(STAGES):
                connection.execute(text("""INSERT INTO analysis_stages (run_id, ordinal, name, state)
                    VALUES (:run, :ordinal, :name, 'pending')"""),
                    {"run": run_id, "ordinal": ordinal, "name": name})
            return run_id

    def resolve_run_artifact(self, run_id: uuid.UUID, artifact_id: uuid.UUID) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(text("""SELECT a.key, a.sha256, a.size, a.media_type FROM artifact_metadata a
                JOIN analysis_runs r ON r.id = a.run_id AND r.purpose = 'ordinary'
                WHERE a.run_id = :run AND a.id = :artifact AND
                  (EXISTS (SELECT 1 FROM run_inputs i WHERE i.run_id = :run AND i.artifact_id = a.id)
                   OR EXISTS (SELECT 1 FROM observer_invocations v WHERE v.run_id = :run AND v.native_artifact_id = a.id))"""),
                {"run": run_id, "artifact": artifact_id}).mappings().one_or_none()
            return dict(row) if row else None
