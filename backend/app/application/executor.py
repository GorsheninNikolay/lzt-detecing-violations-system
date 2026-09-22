import asyncio


class ClaimLoop:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None

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
