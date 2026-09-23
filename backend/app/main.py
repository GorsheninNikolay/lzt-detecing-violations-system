import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import AdmissionStoreError, DatabaseGateError, PostgresStore, ReconciliationGateError, RecoveryGateError
from app.application.executor import ClaimLoop
from app.application.submission import SubmissionError, submit, submit_series
from app.config import Config
from app.profiles.grounding_dino import verify_snapshot


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
            ("recovery_gate_failed", store.recover),
            ("reconciliation_gate_failed", store.reconcile),
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
            if not config.observer_snapshot_dir:
                state.code = "observer_snapshot_missing"
                return
            try:
                snapshot, _ = store.require_authorized(uuid.UUID(runtime_profile))
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

    @app.get("/runs/{run_id}")
    async def read_run(run_id: str) -> JSONResponse:
        try:
            identifier = uuid.UUID(run_id)
        except ValueError:
            return JSONResponse({"code": "run_not_found"}, status_code=404)
        run = await asyncio.to_thread(app.state.store.read_ordinary, identifier)
        return JSONResponse(run if run else {"code": "run_not_found"}, status_code=200 if run else 404)

    return app


app = create_app()


def serve() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, workers=1)
