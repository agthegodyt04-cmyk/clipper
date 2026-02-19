from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .models import AssetKind, AssetRow, JobRow, JobStatus, JobType, ProjectRow


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._lock = threading.Lock()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    brand_name TEXT NOT NULL,
                    product TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    offer TEXT NOT NULL,
                    tone TEXT NOT NULL,
                    platform_targets_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_pct INTEGER NOT NULL DEFAULT 0,
                    stage TEXT NOT NULL DEFAULT 'queued',
                    params_json TEXT NOT NULL,
                    result_json TEXT,
                    error_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    job_id TEXT,
                    kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    meta_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id),
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                );
                CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
                CREATE INDEX IF NOT EXISTS idx_assets_job ON assets(job_id);
                """
            )

    def create_project(
        self,
        *,
        name: str,
        brand_name: str,
        product: str,
        audience: str,
        offer: str,
        tone: str,
        platform_targets: list[str],
    ) -> ProjectRow:
        row = {
            "id": str(uuid.uuid4()),
            "name": name,
            "brand_name": brand_name,
            "product": product,
            "audience": audience,
            "offer": offer,
            "tone": tone,
            "platform_targets": platform_targets,
            "created_at": _now_iso(),
        }
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO projects (
                    id, name, brand_name, product, audience, offer, tone,
                    platform_targets_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["name"],
                    row["brand_name"],
                    row["product"],
                    row["audience"],
                    row["offer"],
                    row["tone"],
                    json.dumps(row["platform_targets"]),
                    row["created_at"],
                ),
            )
        return row

    def get_project(self, project_id: str) -> ProjectRow | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return self._to_project(row)

    def list_projects(self) -> list[ProjectRow]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
        return [self._to_project(row) for row in rows]

    def create_job(self, *, project_id: str, job_type: JobType, params: dict) -> JobRow:
        row: JobRow = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "type": job_type,
            "status": "queued",
            "progress_pct": 0,
            "stage": "queued",
            "params": params,
            "result": None,
            "error_text": None,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, project_id, type, status, progress_pct, stage,
                    params_json, result_json, error_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["project_id"],
                    row["type"],
                    row["status"],
                    row["progress_pct"],
                    row["stage"],
                    json.dumps(row["params"]),
                    None,
                    row["error_text"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        return row

    def get_job(self, job_id: str) -> JobRow | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._to_job(row)

    def list_jobs(self, project_id: str | None = None) -> list[JobRow]:
        with self._conn() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC"
                ).fetchall()
        return [self._to_job(row) for row in rows]

    def update_job(
        self,
        job_id: str,
        *,
        status: JobStatus | None = None,
        progress_pct: int | None = None,
        stage: str | None = None,
        result: dict | None = None,
        error_text: str | None = None,
    ) -> JobRow | None:
        with self._lock, self._conn() as conn:
            current = conn.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if current is None:
                return None

            updates: list[str] = []
            values: list[Any] = []
            if status is not None:
                updates.append("status = ?")
                values.append(status)
            if progress_pct is not None:
                updates.append("progress_pct = ?")
                values.append(max(0, min(100, int(progress_pct))))
            if stage is not None:
                updates.append("stage = ?")
                values.append(stage)
            if result is not None:
                updates.append("result_json = ?")
                values.append(json.dumps(result))
            if error_text is not None:
                updates.append("error_text = ?")
                values.append(error_text)

            updates.append("updated_at = ?")
            values.append(_now_iso())
            values.append(job_id)

            conn.execute(
                f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
                tuple(values),
            )
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

        if row is None:
            return None
        return self._to_job(row)

    def cancel_job(self, job_id: str) -> JobRow | None:
        return self.update_job(job_id, status="cancelled", stage="cancelled")

    def create_asset(
        self,
        *,
        project_id: str,
        job_id: str | None,
        kind: AssetKind,
        path: str,
        meta: dict,
    ) -> AssetRow:
        row: AssetRow = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "job_id": job_id,
            "kind": kind,
            "path": path,
            "meta": meta,
            "created_at": _now_iso(),
        }
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO assets (id, project_id, job_id, kind, path, meta_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["project_id"],
                    row["job_id"],
                    row["kind"],
                    row["path"],
                    json.dumps(row["meta"]),
                    row["created_at"],
                ),
            )
        return row

    def get_asset(self, asset_id: str) -> AssetRow | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM assets WHERE id = ?",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return self._to_asset(row)

    def list_assets(
        self, *, project_id: str | None = None, job_id: str | None = None
    ) -> list[AssetRow]:
        query = "SELECT * FROM assets"
        values: list[Any] = []
        clauses: list[str] = []
        if project_id:
            clauses.append("project_id = ?")
            values.append(project_id)
        if job_id:
            clauses.append("job_id = ?")
            values.append(job_id)
        if clauses:
            query += f" WHERE {' AND '.join(clauses)}"
        query += " ORDER BY created_at DESC"

        with self._conn() as conn:
            rows = conn.execute(query, tuple(values)).fetchall()
        return [self._to_asset(row) for row in rows]

    @staticmethod
    def _to_project(row: sqlite3.Row) -> ProjectRow:
        return {
            "id": row["id"],
            "name": row["name"],
            "brand_name": row["brand_name"],
            "product": row["product"],
            "audience": row["audience"],
            "offer": row["offer"],
            "tone": row["tone"],
            "platform_targets": json.loads(row["platform_targets_json"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _to_job(row: sqlite3.Row) -> JobRow:
        result_json = row["result_json"]
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "type": row["type"],
            "status": row["status"],
            "progress_pct": row["progress_pct"],
            "stage": row["stage"],
            "params": json.loads(row["params_json"]),
            "result": json.loads(result_json) if result_json else None,
            "error_text": row["error_text"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _to_asset(row: sqlite3.Row) -> AssetRow:
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "job_id": row["job_id"],
            "kind": row["kind"],
            "path": row["path"],
            "meta": json.loads(row["meta_json"]),
            "created_at": row["created_at"],
        }

