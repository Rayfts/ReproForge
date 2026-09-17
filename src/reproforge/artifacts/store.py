from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reproforge.security.redaction import redact


@dataclass(frozen=True, slots=True)
class RunLayout:
    root: Path

    @classmethod
    def create(cls, base: Path, run_id: str) -> "RunLayout":
        root = base / ".reproforge" / "runs" / run_id
        for name in ("logs", "patches", "artifacts", "reproduction", "regression-test"):
            (root / name).mkdir(parents=True, exist_ok=True)
        return cls(root)

    @property
    def report_json(self) -> Path:
        return self.root / "report.json"

    @property
    def report_md(self) -> Path:
        return self.root / "report.md"

    @property
    def environment_json(self) -> Path:
        return self.root / "environment.json"

    @property
    def attempts_jsonl(self) -> Path:
        return self.root / "attempts.jsonl"

    @property
    def commands_jsonl(self) -> Path:
        return self.root / "commands.jsonl"

    def write_json(self, path: Path, payload: Any) -> None:
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

    def append_jsonl(self, path: Path, payload: Any) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")

    def write_log(self, name: str, text: str, *, secret_values: list[str]) -> Path:
        path = self.root / "logs" / name
        path.write_text(redact(text, secret_values=secret_values), encoding="utf-8")
        return path
