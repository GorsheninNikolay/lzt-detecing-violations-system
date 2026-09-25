import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.adapters.artifacts import ArtifactGateError, ArtifactStore
from app.adapters.postgres import AdmissionStoreError, DatabaseGateError, PostgresStore, ReconciliationGateError, RecoveryGateError
from app.application.executor import ClaimLoop
from app.application.submission import SubmissionError, submit, submit_series
from app.domain.rule import ANALYSIS_CHOICES
from app.domain.comparison_campaign import CampaignGateError
from app.config import Config
from app.profiles.grounding_dino import verify_snapshot
from app.profiles.cloud_api import CloudObserver


MAX_HTTP_BODY_BYTES = 25_100_000
MAX_SERIES_HTTP_BODY_BYTES = 200_000_000


class Readiness:
    def __init__(self) -> None:
        self.ready = asyncio.Event()
        self.code = "startup_pending"

    def require(self) -> None:
        if not self.ready.is_set():
            raise RuntimeError("service_not_ready")


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = Config.from_env()
    store = PostgresStore(config.database_url)
    artifacts = ArtifactStore(config)
    state = app.state.readiness
    claim_loop = ClaimLoop()
    claim_loop.store = store
    app.state.claim_loop = claim_loop
    app.state.store = store
    app.state.artifacts = artifacts

    async def startup() -> None:
        migrations = str(Path(__file__).resolve().parents[1] / "migrations")
        for code, gate in (
            ("database_gate_failed", lambda: store.check_head_and_smoke(migrations)),
            ("artifact_gate_failed", artifacts.probe),
            ("reconciliation_gate_failed", lambda: store.reconcile(artifacts)),
            ("recovery_gate_failed", store.recover),
            ("reconciliation_gate_failed", lambda: store.reconcile(artifacts)),
        ):
            try:
                await asyncio.to_thread(gate)
            except DatabaseGateError as exc:
                state.code = str(exc)
                return
            except (ReconciliationGateError, RecoveryGateError) as exc:
                state.code = str(exc)
                return
            except Exception:
                state.code = code
                return
        runtime_profile = os.getenv("OBSERVER_PROFILE_ID")
        if runtime_profile:
            try:
                claim_loop.bind_runtime(store, uuid.UUID(runtime_profile))
            except (ValueError, AdmissionStoreError):
                state.code = "profile_unauthorized"
                return
            try:
                snapshot, _ = store.require_authorized(uuid.UUID(runtime_profile))
                if snapshot.get("kind") == "cloud_api":
                    CloudObserver(snapshot, config.cloud_api_key)
                else:
                    if not config.observer_snapshot_dir:
                        state.code = "observer_snapshot_missing"
                        return
                    await asyncio.to_thread(verify_snapshot, Path(config.observer_snapshot_dir), snapshot["model_files"])
            except Exception:
                state.code = "observer_snapshot_invalid"
                return
        state.code = "ready"
        state.ready.set()
        claim_loop.start(state.ready, artifacts, config.observer_snapshot_dir)
        def loop_finished(task: asyncio.Task) -> None:
            if state.ready.is_set():
                state.ready.clear()
                state.code = "claim_loop_failed"

        claim_loop.task.add_done_callback(loop_finished)

    app.state.startup_task = asyncio.create_task(startup())
    try:
        yield
    finally:
        state.ready.clear()
        app.state.startup_task.cancel()
        try:
            await app.state.startup_task
        except asyncio.CancelledError:
            pass
        await claim_loop.stop()
        store.close()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.state.readiness = Readiness()

    @app.get("/health/live")
    def live() -> dict[str, bool]:
        return {"live": True}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        state = app.state.readiness
        result = {"ready": state.ready.is_set(), "code": state.code}
        return JSONResponse(result, status_code=200 if result["ready"] else 503)

    @app.get("/analysis-choices")
    def analysis_choices() -> dict:
        return ANALYSIS_CHOICES

    @app.post("/runs/single-image")
    @app.post("/runs/series")
    async def submit_single_image(request: Request) -> JSONResponse:
        series = request.url.path == "/runs/series"
        if not app.state.readiness.ready.is_set():
            return JSONResponse({"code": "service_not_ready"}, status_code=503)
        binding = app.state.claim_loop.runtime_binding
        if binding is None:
            return JSONResponse({"code": "profile_unauthorized"}, status_code=503)
        try:
            payload = bytearray()
            async for chunk in request.stream():
                if len(payload) + len(chunk) > (MAX_SERIES_HTTP_BODY_BYTES if series else MAX_HTTP_BODY_BYTES):
                    return JSONResponse({"code": "invalid_image_file"}, status_code=400)
                payload.extend(chunk)
            body = json.loads(payload)
        except ValueError:
            return JSONResponse({"code": "invalid_request"}, status_code=400)
        try:
            key = request.headers.get("Idempotency-Key")
            snapshot, revision = await asyncio.to_thread(app.state.store.require_authorized, binding[0], binding[1])
            status, run_id = await asyncio.to_thread(submit_series if series else submit,
                app.state.store, app.state.artifacts,
                key, body, binding[0], revision, snapshot)
            if run_id:
                current = await asyncio.to_thread(app.state.store.read_ordinary, run_id)
                return JSONResponse({"run_id": str(run_id), "state": current["state"]}, status_code=202)
            return JSONResponse({"code": "submission_in_progress"}, status_code=202)
        except SubmissionError as exc:
            code = str(exc)
            status = (202 if code == "submission_in_progress" else
                      409 if code == "idempotency_key_conflict" else
                      503 if code in {"submission_publication_failed", "submission_interrupted"} else 400)
            return JSONResponse({"code": code}, status_code=status)
        except AdmissionStoreError:
            return JSONResponse({"code": "profile_unauthorized"}, status_code=503)
        except Exception:
            return JSONResponse({"code": "submission_unavailable"}, status_code=503)

    @app.get("/stages/summary")
    async def stage_summary() -> JSONResponse:
        try:
            return JSONResponse(await asyncio.to_thread(app.state.store.stage_summary))
        except Exception:
            return JSONResponse({"code": "stage_summary_unavailable"}, status_code=503)

    @app.get("/readiness")
    async def read_readiness() -> JSONResponse:
        headers = {"Cache-Control": "no-store"}
        try:
            report = await asyncio.to_thread(app.state.store.read_latest_evaluation_report, app.state.artifacts)
            return JSONResponse(report if report else {"code": "evaluation_report_missing"},
                                status_code=200 if report else 404, headers=headers)
        except (ArtifactGateError, CampaignGateError):
            return JSONResponse({"code": "evaluation_report_unavailable"}, status_code=503, headers=headers)
        except Exception:
            return JSONResponse({"code": "readiness_unavailable"}, status_code=503, headers=headers)

    @app.get("/provider-comparison")
    async def read_provider_comparison() -> JSONResponse:
        headers = {"Cache-Control": "no-store"}
        try:
            comparison = await asyncio.to_thread(app.state.store.read_latest_provider_comparison)
            return JSONResponse(comparison if comparison else {"code": "provider_comparison_missing"},
                                status_code=200 if comparison else 404, headers=headers)
        except Exception:
            return JSONResponse({"code": "provider_comparison_unavailable"}, status_code=503, headers=headers)

    @app.get("/runs/{run_id}")
    async def read_run(run_id: str) -> JSONResponse:
        headers = {"Cache-Control": "no-store"}
        try:
            identifier = uuid.UUID(run_id)
        except ValueError:
            return JSONResponse({"code": "run_not_found"}, status_code=404, headers=headers)
        try:
            run = await asyncio.to_thread(app.state.store.read_ordinary, identifier)
            if run is None:
                run = await asyncio.to_thread(app.state.store.read_run, identifier, "comparison_campaign")
        except Exception:
            return JSONResponse({"code": "run_unavailable"}, status_code=503, headers=headers)
        if run and run.get("purpose", "ordinary") == "ordinary":
            binding = app.state.claim_loop.runtime_binding
            run["retry_eligible"] = False
            if run["state"] == "failed" and not run["retry_successor_id"] and binding and app.state.readiness.ready.is_set():
                try:
                    snapshot, _ = await asyncio.to_thread(app.state.store.require_authorized, binding[0], binding[1])
                    if snapshot.get("kind") == "cloud_api":
                        CloudObserver(snapshot, Config.from_env().cloud_api_key)
                    else:
                        await asyncio.to_thread(verify_snapshot, Path(app.state.claim_loop.snapshot_dir), snapshot["model_files"])
                    run["retry_eligible"] = True
                    run["retry_profile_id"] = str(binding[0])
                    run["retry_authorization_revision"] = binding[1]
                except Exception:
                    pass
        return JSONResponse(run if run else {"code": "run_not_found"}, status_code=200 if run else 404,
                            headers=headers)

    @app.get("/runs")
    async def list_runs(request: Request) -> JSONResponse:
        raw_offset = request.query_params.get("offset", "0")
        if not raw_offset.isdecimal() or len(raw_offset) > 9:
            return JSONResponse({"code": "invalid_history_offset"}, status_code=400)
        return JSONResponse(await asyncio.to_thread(app.state.store.list_ordinary, int(raw_offset)))

    @app.post("/runs/{run_id}/retry")
    async def retry_run(run_id: str) -> JSONResponse:
        try:
            identifier = uuid.UUID(run_id)
        except ValueError:
            return JSONResponse({"code": "run_not_found"}, status_code=404)
        source = await asyncio.to_thread(app.state.store.read_ordinary, identifier)
        if source is None:
            return JSONResponse({"code": "run_not_found"}, status_code=404)
        if source["state"] != "failed":
            return JSONResponse({"code": "retry_ineligible"}, status_code=409)
        if source["retry_successor_id"]:
            return JSONResponse({"run_id": source["retry_successor_id"]}, status_code=202)
        if not app.state.readiness.ready.is_set():
            return JSONResponse({"code": "service_not_ready"}, status_code=503)
        binding = app.state.claim_loop.runtime_binding
        if binding is None:
            return JSONResponse({"code": "profile_unauthorized"}, status_code=503)
        try:
            snapshot, revision = await asyncio.to_thread(app.state.store.require_authorized, binding[0], binding[1])
            if snapshot.get("kind") == "cloud_api":
                CloudObserver(snapshot, Config.from_env().cloud_api_key)
            else:
                await asyncio.to_thread(verify_snapshot, Path(app.state.claim_loop.snapshot_dir), snapshot["model_files"])
            successor = await asyncio.to_thread(app.state.store.retry_ordinary, identifier, binding[0], revision,
                                                snapshot, app.state.artifacts)
            return JSONResponse({"run_id": str(successor)}, status_code=202)
        except AdmissionStoreError as exc:
            code = str(exc)
            return JSONResponse({"code": code}, status_code=404 if code == "run_not_found" else
                                409 if code in {"retry_ineligible", "retry_source_unavailable"} else 503)
        except Exception:
            return JSONResponse({"code": "retry_unavailable"}, status_code=503)

    @app.get("/runs/{run_id}/artifacts/{artifact_id}")
    async def read_run_artifact(run_id: str, artifact_id: str) -> Response:
        headers = {"Cache-Control": "no-store"}
        try:
            run, artifact = uuid.UUID(run_id), uuid.UUID(artifact_id)
        except ValueError:
            return JSONResponse({"code": "artifact_not_found"}, status_code=404, headers=headers)
        try:
            metadata = await asyncio.to_thread(app.state.store.resolve_run_artifact, run, artifact)
        except Exception:
            return JSONResponse({"code": "artifact_unavailable"}, status_code=503, headers=headers)
        if metadata is None:
            return JSONResponse({"code": "artifact_not_found"}, status_code=404, headers=headers)
        try:
            body = await asyncio.to_thread(app.state.artifacts.read_verified,
                                           metadata["key"], metadata["sha256"], metadata["size"])
        except ArtifactGateError as exc:
            code = str(exc)
            return JSONResponse({"code": code}, status_code=409 if code == "artifact_integrity_failed" else 503,
                                headers=headers)
        return Response(body, media_type=metadata["media_type"], headers=headers)

    return app


app = create_app()


def serve() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, workers=1)
