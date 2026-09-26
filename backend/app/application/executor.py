import asyncio
import hashlib
import uuid
import zipfile
import zlib
from pathlib import Path


from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import PostgresStore
from app.domain.comparison_campaign import CampaignGateError


class ClaimLoop:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.ready: asyncio.Event | None = None
        self.runtime_binding: tuple[uuid.UUID, int] | None = None
        self.store: PostgresStore | None = None
        self.artifacts: ArtifactStore | None = None

    def bind_runtime(self, store: PostgresStore, profile_id: uuid.UUID) -> None:
        _, authorization_revision = store.require_authorized(profile_id)
        self.runtime_binding = profile_id, authorization_revision
        self.store = store

    def start(self, ready: asyncio.Event, artifacts: ArtifactStore | None = None) -> None:
        if self.task is not None:
            raise RuntimeError("claim_loop_already_started")
        self.ready = ready
        self.artifacts = artifacts
        self.task = asyncio.create_task(self._run(ready))

    async def _renew(self, run_id: uuid.UUID, owner: str, revision: int,
                     campaign: bool = False) -> None:
        while True:
            await asyncio.sleep(10)
            if campaign:
                await asyncio.to_thread(self.store.renew_comparison, run_id, owner, revision, 30)
            else:
                await asyncio.to_thread(self.store.renew_ordinary, run_id, owner, revision, 30)

    async def _execute(self, work: dict, revision: int) -> None:
        if work["profile_snapshot"].get("kind") != "deepseek":
            await asyncio.to_thread(self.store.fail_ordinary, work["id"], work["owner"], "profile_retired")
            return
        from app.application.deepseek_runtime import execute
        await execute(self, work, revision)

    async def _run(self, ready: asyncio.Event) -> None:
        try:
            while ready.is_set():
                if self.store:
                    await asyncio.to_thread(self.store.fail_unauthorized_queued)
                    if await asyncio.to_thread(self.store.recover):
                        await asyncio.to_thread(self.store.reconcile, self.artifacts, runtime=True)
                if self.runtime_binding and self.artifacts:
                    profile_id, revision = self.runtime_binding
                    work = await asyncio.to_thread(self.store.claim_ordinary, profile_id, revision, 30)
                    if work:
                        await self._execute(work, revision)
                        if await asyncio.to_thread(self.store.recover):
                            await asyncio.to_thread(self.store.reconcile, self.artifacts, runtime=True)
                        continue
                await asyncio.sleep(1)
        except Exception:
            ready.clear()
            raise

    async def stop(self) -> None:
        if self.task is not None:
            self.ready.clear()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


def _verified_campaign_archive(source, manifest: dict) -> dict[int, bytes]:
    measured = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        measured.update(chunk)
    if measured.hexdigest() != manifest.get("source_archive_sha256"):
        raise CampaignGateError("archive_hash_mismatch")
    source.seek(0)
    images = {}
    try:
        with zipfile.ZipFile(source) as archive:
            for frame in manifest["frames"]:
                for kind in ("image", "label"):
                    item = frame[kind]
                    payload = archive.read(item["archive_member"])
                    if len(payload) != item["size"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                        raise CampaignGateError("archive_content_mismatch")
                    if kind == "image":
                        images[frame["ordinal"]] = payload
    except CampaignGateError:
        raise
    except (KeyError, OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error):
        raise CampaignGateError("archive_content_unavailable") from None
    return images


async def execute_comparison_campaign(store: PostgresStore, artifacts: ArtifactStore,
                                      campaign_id: uuid.UUID, archive_path: Path,
                                      snapshot_dir: str | None = None) -> dict:
    raise CampaignGateError("profile_retired")
