from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.db.repo import Repository

JobHandler = Callable[
    [dict[str, Any], Callable[[str, int], Awaitable[None]]],
    Awaitable[dict[str, Any] | None],
]


class JobQueue:
    def __init__(self, repo: Repository, max_workers: int = 1):
        self.repo = repo
        self.max_workers = max(1, max_workers)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._handlers: dict[str, JobHandler] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._started = False

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self.max_workers):
            self._workers.append(asyncio.create_task(self._worker(i)))

    async def stop(self) -> None:
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._workers.clear()
        self._started = False

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)

    async def _worker(self, worker_idx: int) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                await self._run_job(job_id, worker_idx)
            finally:
                self._queue.task_done()

    async def _run_job(self, job_id: str, worker_idx: int) -> None:
        job = self.repo.get_job(job_id)
        if job is None:
            return
        if job["status"] == "cancelled":
            return
        handler = self._handlers.get(job["type"])
        if handler is None:
            self.repo.update_job(
                job_id,
                status="error",
                stage="error",
                progress_pct=100,
                error_text=f"No handler registered for '{job['type']}'.",
            )
            return

        self.repo.update_job(
            job_id,
            status="running",
            stage=f"worker_{worker_idx}_starting",
            progress_pct=2,
            error_text="",
        )

        async def progress(stage: str, pct: int) -> None:
            current = self.repo.get_job(job_id)
            if current is None:
                return
            if current["status"] == "cancelled":
                raise RuntimeError("Job was cancelled.")
            self.repo.update_job(job_id, stage=stage, progress_pct=pct)

        try:
            result = await handler(job, progress)
            self.repo.update_job(
                job_id,
                status="done",
                stage="completed",
                progress_pct=100,
                result=result or {},
                error_text="",
            )
        except Exception as exc:  # noqa: BLE001
            self.repo.update_job(
                job_id,
                status="error",
                stage="failed",
                progress_pct=100,
                error_text=str(exc),
            )

