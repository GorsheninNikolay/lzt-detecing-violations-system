import os
import json
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.postgres import PostgresStore
from app.application.site import router as site_router
from app.application.signals import router as signals_router


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="isolated PostgreSQL required")
def test_catalog_plan_and_due_signal_round_trip():
    store = PostgresStore(os.environ["TEST_DATABASE_URL"])
    app = FastAPI()
    app.include_router(site_router)
    app.include_router(signals_router)
    app.state.store = store
    app.state.readiness = type("Ready", (), {"ready": type("Event", (), {"is_set": lambda self: True})()})()
    try:
        with TestClient(app) as client:
            catalog = client.get("/catalog/works")
            assert catalog.status_code == 200, catalog.text
            works = catalog.json()["works"]
            assert len(works) == 377
            assert next(work for work in works if work["source_row"] == 46)["code"] == "12.3."
            project = client.post("/projects", json={"name": f"Test {uuid4()}", "timezone": "Europe/Moscow"})
            assert project.status_code == 201, project.text
            project_id = project.json()["id"]
            zone = client.post(f"/projects/{project_id}/zones", json={"name": "North"})
            assert zone.status_code == 201, zone.text
            zone_id = zone.json()["id"]
            entry = {"catalog_work_id": works[0]["id"], "start_at": "2020-01-01T00:00:00+03:00",
                     "end_at": "2020-01-02T00:00:00+03:00", "state": "active",
                     "stage_key": "excavation", "expected_equipment": ["excavator"],
                     "allowed_equipment": [], "excluded_equipment": ["road_roller"]}
            other_entry = {**entry, "catalog_work_id": works[1]["id"]}
            revision = client.put(f"/zones/{zone_id}/plan", json={"expected_revision": 0,
                                                                   "entries": [entry, other_entry]})
            assert revision.status_code == 200, revision.text
            plan = client.get(f"/zones/{zone_id}/plan").json()
            assert plan["revision_number"] == 1 and len(plan["entries"]) == 2
            assert all(item["stage_key"] == "excavation" for item in plan["entries"])
            store.validate_plan_binding({"project_id": project_id, "zone_id": zone_id,
                                         "plan_revision_id": plan["revision_id"]})
            assert client.put(f"/zones/{zone_id}/plan", json={"expected_revision": 0,
                                                               "entries": []}).status_code == 409
            first = client.get(f"/signals?zone_id={zone_id}").json()
            second = client.get(f"/signals?zone_id={zone_id}").json()
            assert first["new_count"] == second["new_count"] == 2
            assert len(first["signals"]) == len(second["signals"]) == 2
            titles = {item["id"]: next(work["title"] for work in works
                                          if work["id"] == item["catalog_work_id"])
                      for item in plan["entries"]}
            assert {item["work_title"] for item in first["signals"]} == set(titles.values())
            assert all(item["project_name"] == project.json()["name"] and item["zone_name"] == "North"
                       and item["plan_revision_number"] == 1 and item["preview"] is None
                       and item["work_title"] == titles[item["work_entry_id"]]
                       for item in first["signals"])
            signal_id = first["signals"][0]["id"]
            update = client.patch(f"/signals/{signal_id}", json={"state": "in_progress", "comment": "Checking"})
            assert update.status_code == 200, update.text
            assert client.get(f"/signals?zone_id={zone_id}").json()["new_count"] == 1
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE site_projects SET name='Renamed project' WHERE id=:id"),
                                   {"id": project_id})
                connection.execute(text("UPDATE site_zones SET name='Renamed zone' WHERE id=:id"),
                                   {"id": zone_id})
            newer = client.put(f"/zones/{zone_id}/plan", json={"expected_revision": 1,
                                                                 "entries": [{**entry, "end_at": "2035-01-02T00:00:00+03:00"}]})
            assert newer.status_code == 200, newer.text
            assert client.get(f"/zones/{zone_id}/plan").json()["revision_id"] == newer.json()["revision_id"]
            assert client.get(f"/zones/{zone_id}/plan?revision=1").json()["revision_id"] == plan["revision_id"]
            historical = client.get(f"/signals?zone_id={zone_id}").json()["signals"]
            assert all(item["project_name"] == "Renamed project" and item["zone_name"] == "Renamed zone"
                       and item["plan_revision_number"] == 1 and item["revision_id"] == plan["revision_id"]
                       for item in historical)

            run_id, signal_id = uuid4(), uuid4()
            inputs = [uuid4() for _ in range(3)]
            artifacts = [uuid4(), uuid4()]
            with store.engine.begin() as connection:
                connection.execute(text("""INSERT INTO analysis_runs (id,state,purpose,analysis_intent)
                    VALUES (:id,'queued','ordinary','observation_only')"""), {"id": run_id})
                for ordinal, artifact_id in ((0, artifacts[0]), (2, artifacts[1])):
                    intent_id = uuid4()
                    digest = str(ordinal) * 64
                    connection.execute(text("""INSERT INTO publication_intents
                        (id,state,idempotency_key,media_type,run_id)
                        VALUES (:id,'referenced',:key,'image/jpeg',:run)"""),
                        {"id": intent_id, "key": f"signal-preview-{intent_id}", "run": run_id})
                    connection.execute(text("""INSERT INTO artifact_metadata
                        (id,run_id,intent_id,key,sha256,size,media_type)
                        VALUES (:id,:run,:intent,:key,:digest,1,'image/jpeg')"""),
                        {"id": artifact_id, "run": run_id, "intent": intent_id,
                         "key": f"sha256/{digest}", "digest": digest})
                for ordinal, input_id in enumerate(inputs):
                    connection.execute(text("""INSERT INTO run_inputs
                        (run_id,ordinal,input_id,sha256,size,context,artifact_id)
                        VALUES (:run,:ordinal,:input,:digest,1,'{}'::jsonb,:artifact)"""),
                        {"run": run_id, "ordinal": ordinal, "input": input_id,
                         "digest": str(ordinal) * 64,
                         "artifact": artifacts[0] if ordinal == 0 else artifacts[1] if ordinal == 2 else None})
                connection.execute(text("""INSERT INTO site_signals
                    (id,fingerprint,run_id,zone_id,revision_id,kind,basis)
                    VALUES (:id,:fingerprint,:run,:zone,:revision,'stage_plan_mismatch',CAST(:basis AS jsonb))"""),
                    {"id": signal_id, "fingerprint": f"preview-{signal_id}", "run": run_id,
                     "zone": zone_id, "revision": plan["revision_id"],
                     "basis": json.dumps({"supporting_input_ids": [str(inputs[1]), str(inputs[2])]})})
            linked = next(item for item in client.get(f"/signals?zone_id={zone_id}").json()["signals"]
                          if item["id"] == str(signal_id))
            assert linked["work_title"] is None
            assert linked["preview"] == {"input_id": str(inputs[2]), "ordinal": 2,
                                         "artifact_id": str(artifacts[1])}
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE run_inputs SET artifact_id=NULL WHERE run_id=:run AND ordinal=2"),
                                   {"run": run_id})
            fallback = next(item for item in client.get(f"/signals?zone_id={zone_id}").json()["signals"]
                            if item["id"] == str(signal_id))
            assert fallback["preview"] == {"input_id": str(inputs[0]), "ordinal": 0,
                                           "artifact_id": str(artifacts[0])}
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE run_inputs SET artifact_id=NULL WHERE run_id=:run AND ordinal=0"),
                                   {"run": run_id})
            unavailable = next(item for item in client.get(f"/signals?zone_id={zone_id}").json()["signals"]
                               if item["id"] == str(signal_id))
            assert unavailable["preview"] is None
            with pytest.raises(DatabaseError), store.engine.begin() as connection:
                connection.execute(text("UPDATE zone_plan_revisions SET revision_number=2 WHERE id=:id"),
                                   {"id": plan["revision_id"]})
            with pytest.raises(DatabaseError), store.engine.begin() as connection:
                connection.execute(text("UPDATE site_signals SET basis='{}'::jsonb WHERE id=:id"),
                                   {"id": signal_id})
    finally:
        store.close()
