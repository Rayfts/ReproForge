from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StoredRun:
    run_id: str
    path: Path
    status: str
    created_at: str
    updated_at: str


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "runs.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def upsert(self, run_id: str, path: Path, status: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(run_id, path, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    path=excluded.path,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (run_id, str(path), status, now, now),
            )

    def get(self, run_id: str) -> StoredRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_id, path, status, created_at, updated_at FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredRun(
            run_id=str(row["run_id"]),
            path=Path(str(row["path"])),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    def recent(self, limit: int = 20) -> list[StoredRun]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, path, status, created_at, updated_at FROM runs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            StoredRun(
                run_id=str(row["run_id"]),
                path=Path(str(row["path"])),
                status=str(row["status"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )
            for row in rows
        ]
