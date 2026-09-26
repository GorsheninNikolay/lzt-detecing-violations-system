"""Persistent review signals and human stage confirmations."""

import hashlib
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text


router = APIRouter()
STAGES = {"excavation", "concreting", "roadwork"}
STATES = {"new", "in_progress", "closed"}


def _fingerprint(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, default=str, separators=(",", ":")).encode()).hexdigest()


def _insert_signal(connection, *, run_id, zone_id, revision_id, entry_id, kind, basis):
    connection.execute(text("""INSERT INTO site_signals
        (id,fingerprint,run_id,zone_id,revision_id,work_entry_id,kind,basis)
        VALUES (:id,:fingerprint,:run,:zone,:revision,:entry,:kind,CAST(:basis AS jsonb))
        ON CONFLICT (fingerprint) DO NOTHING"""),
        {"id": uuid.uuid4(), "fingerprint": _fingerprint(run_id, revision_id, entry_id, kind),
         "run": run_id, "zone": zone_id, "revision": revision_id, "entry": entry_id,
         "kind": kind, "basis": json.dumps(basis, default=str)})


@router.get("/signals")
def list_signals(request: Request, project_id: uuid.UUID | None = None,
                 zone_id: uuid.UUID | None = None, state: str | None = None):
    if state is not None and state not in STATES:
        return JSONResponse({"code": "invalid_signal_state"}, status_code=400)
    if not request.app.state.readiness.ready.is_set():
        return JSONResponse({"code": "service_not_ready"}, status_code=503)
    engine = request.app.state.store.engine
    with engine.begin() as connection:
        due = connection.execute(text("""SELECT z.id AS zone_id,r.id AS revision_id,e.id AS entry_id,
            e.ends_at,e.catalog_work_id FROM site_zones z
            JOIN LATERAL (SELECT id FROM zone_plan_revisions WHERE zone_id=z.id
                ORDER BY revision_number DESC LIMIT 1) r ON true
            JOIN zone_plan_entries e ON e.revision_id=r.id
            WHERE e.state <> 'completed' AND e.ends_at < clock_timestamp()
              AND (CAST(:zone AS uuid) IS NULL OR z.id=:zone)
              AND (CAST(:project AS uuid) IS NULL OR z.project_id=:project)"""),
            {"zone": zone_id, "project": project_id}).mappings().all()
        for item in due:
            _insert_signal(connection, run_id=None, zone_id=item["zone_id"],
                           revision_id=item["revision_id"], entry_id=item["entry_id"],
                           kind="completion_unconfirmed",
                           basis={"rule_revision": "plan-date-v1", "due_at": item["ends_at"],
                                  "catalog_work_id": item["catalog_work_id"],
                                  "recommendation": "Check completion with the site team."})
        rows = connection.execute(text("""SELECT s.id,s.run_id,s.zone_id,s.revision_id,s.work_entry_id,
            s.kind,s.state,s.basis,s.comment,s.created_at,
            p.name AS project_name,z.name AS zone_name,r.revision_number AS plan_revision_number,
            w.title AS work_title,
            CASE WHEN frame.input_id IS NULL THEN NULL ELSE jsonb_build_object(
                'input_id',frame.input_id,'ordinal',frame.ordinal,'artifact_id',frame.artifact_id)
            END AS preview
            FROM site_signals s JOIN site_zones z ON z.id=s.zone_id
            JOIN site_projects p ON p.id=z.project_id
            JOIN zone_plan_revisions r ON r.id=s.revision_id AND r.zone_id=z.id
            LEFT JOIN zone_plan_entries e ON e.id=s.work_entry_id AND e.revision_id=r.id
            LEFT JOIN catalog_works w ON w.id=e.catalog_work_id
            LEFT JOIN LATERAL (
                SELECT i.input_id,i.ordinal,a.id AS artifact_id FROM run_inputs i
                JOIN artifact_metadata a ON a.id=i.artifact_id AND a.run_id=i.run_id
                WHERE i.run_id=s.run_id
                ORDER BY CASE WHEN jsonb_exists(s.basis->'supporting_input_ids',i.input_id::text)
                    THEN 0 ELSE 1 END,i.ordinal LIMIT 1
            ) frame ON true
            WHERE (CAST(:zone AS uuid) IS NULL OR s.zone_id=:zone)
              AND (CAST(:project AS uuid) IS NULL OR z.project_id=:project)
              AND (CAST(:state AS text) IS NULL OR s.state=:state)
            ORDER BY s.created_at DESC,s.id DESC LIMIT 500"""),
            {"zone": zone_id, "project": project_id, "state": state}).mappings().all()
        count = connection.execute(text("""SELECT count(*) FROM site_signals s JOIN site_zones z ON z.id=s.zone_id
            WHERE s.state='new' AND (CAST(:zone AS uuid) IS NULL OR s.zone_id=:zone)
              AND (CAST(:project AS uuid) IS NULL OR z.project_id=:project)"""),
            {"zone": zone_id, "project": project_id}).scalar_one()
    return {"new_count": count, "signals": [{**dict(item),
            "id": str(item["id"]), "run_id": str(item["run_id"]) if item["run_id"] else None,
            "zone_id": str(item["zone_id"]), "revision_id": str(item["revision_id"]),
            "work_entry_id": str(item["work_entry_id"]) if item["work_entry_id"] else None,
            "created_at": item["created_at"].isoformat()} for item in rows]}


@router.patch("/signals/{signal_id}")
def update_signal(signal_id: uuid.UUID, request: Request, body: dict):
    if not request.app.state.readiness.ready.is_set():
        return JSONResponse({"code": "service_not_ready"}, status_code=503)
    state, comment = body.get("state"), body.get("comment", "")
    if state not in STATES or not isinstance(comment, str) or len(comment) > 2000:
        return JSONResponse({"code": "invalid_signal_update"}, status_code=400)
    with request.app.state.store.engine.begin() as connection:
        row = connection.execute(text("""UPDATE site_signals SET state=:state,comment=:comment,updated_at=clock_timestamp()
            WHERE id=:id RETURNING id,state,comment"""),
            {"id": signal_id, "state": state, "comment": comment}).first()
    return ({"id": str(row.id), "state": row.state, "comment": row.comment} if row else
            JSONResponse({"code": "signal_not_found"}, status_code=404))


@router.post("/runs/{run_id}/confirm-stage")
def confirm_stage(run_id: uuid.UUID, request: Request, body: dict):
    if not request.app.state.readiness.ready.is_set():
        return JSONResponse({"code": "service_not_ready"}, status_code=503)
    stage, comment = body.get("stage"), body.get("comment", "")
    if stage not in STAGES or not isinstance(comment, str) or len(comment) > 2000:
        return JSONResponse({"code": "invalid_stage_confirmation"}, status_code=400)
    with request.app.state.store.engine.begin() as connection:
        run = connection.execute(text("""SELECT r.state,b.zone_id,b.revision_id,b.frame_times
            FROM analysis_runs r LEFT JOIN run_plan_bindings b ON b.run_id=r.id
            WHERE r.id=:run AND r.purpose='ordinary' FOR UPDATE OF r"""),
            {"run": run_id}).mappings().one_or_none()
        if not run:
            return JSONResponse({"code": "run_not_found"}, status_code=404)
        if run["state"] != "succeeded":
            return JSONResponse({"code": "run_not_complete"}, status_code=409)
        prior = connection.execute(text("SELECT stage,comment FROM stage_confirmations WHERE run_id=:run"),
                                   {"run": run_id}).first()
        if prior:
            if prior.stage != stage or prior.comment != comment:
                return JSONResponse({"code": "stage_already_confirmed"}, status_code=409)
            return {"run_id": str(run_id), "stage": stage, "comment": comment}
        connection.execute(text("""INSERT INTO stage_confirmations(run_id,stage,comment)
            VALUES (:run,:stage,:comment)"""), {"run": run_id, "stage": stage, "comment": comment})
        if run["revision_id"]:
            entries = connection.execute(text("""SELECT id,stage_key,starts_at,ends_at FROM zone_plan_entries
                WHERE revision_id=:revision AND state='active' AND stage_key IS NOT NULL"""),
                {"revision": run["revision_id"]}).mappings().all()
            active = [entry for entry in entries if all(entry["starts_at"] <= datetime.fromisoformat(value)
                      <= entry["ends_at"] for value in run["frame_times"])]
            if active and stage not in {entry["stage_key"] for entry in active}:
                _insert_signal(connection, run_id=run_id, zone_id=run["zone_id"],
                               revision_id=run["revision_id"], entry_id=None,
                               kind="stage_plan_mismatch",
                               basis={"rule_revision": "confirmed-stage-v1", "confirmed_stage": stage,
                                      "planned_stages": sorted({entry["stage_key"] for entry in active}),
                                      "recommendation": "Review the active zone plan."})
    return {"run_id": str(run_id), "stage": stage, "comment": comment}
