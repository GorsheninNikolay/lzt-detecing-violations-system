import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import DatabaseGateError, PostgresStore, ReconciliationGateError, RecoveryGateError
from app.application.executor import ClaimLoop
from app.config import Config


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
    app.state.claim_loop = claim_loop

    async def startup() -> None:
        migrations = str(Path(__file__).resolve().parents[1] / "migrations")
        for code, gate in (
            ("database_gate_failed", lambda: store.check_head_and_smoke(migrations)),
            ("artifact_gate_failed", artifacts.probe),
            ("reconciliation_gate_failed", store.reconcile),
            ("recovery_gate_failed", store.recover),
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
        state.code = "ready"
        state.ready.set()
        claim_loop.start(state.ready)
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

    return app


app = create_app()


def serve() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, workers=1)
