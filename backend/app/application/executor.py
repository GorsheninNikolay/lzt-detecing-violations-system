import asyncio
import uuid

from app.adapters.postgres import PostgresStore


class ClaimLoop:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.runtime_binding: tuple[uuid.UUID, int] | None = None

    def bind_runtime(self, store: PostgresStore, profile_id: uuid.UUID) -> None:
        _, authorization_revision = store.require_authorized(profile_id)
        self.runtime_binding = profile_id, authorization_revision

    def start(self, ready: asyncio.Event) -> None:
        if self.task is not None:
            raise RuntimeError("claim_loop_already_started")
        self.task = asyncio.create_task(self._run(ready))

    async def _run(self, ready: asyncio.Event) -> None:
        try:
            while ready.is_set():
                # Run submission/claim contracts begin in Story 1.3.
                await asyncio.sleep(1)
        except Exception:
            ready.clear()
            raise

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
