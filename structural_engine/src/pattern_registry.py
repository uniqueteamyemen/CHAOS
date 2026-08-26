from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PatternRecord:
    pattern_id: str
    pattern_version: str
    status: str
    path_nodes: list[str]
    edges: list[dict[str, Any]]
    evidence_refs: list[str]
    training_window: dict[str, str]
    validation_window: dict[str, str] | None
    algorithm_metadata: dict[str, Any]
    validation_metadata: dict[str, Any]
    failure_cases: list[str] = field(default_factory=list)
    rejection_reason: str | None = None
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PatternRegistry:
    """Append-only JSONL registry for candidate, rejected, and golden patterns."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, status: str) -> Path:
        allowed = {"candidate", "rejected", "golden"}
        if status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return self.root / status / "patterns.jsonl"

    def append(self, record: PatternRecord) -> Path:
        path = self._path_for(record.status)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        return path

    def reject(self, record: PatternRecord, reason: str) -> Path:
        rejected = PatternRecord(
            **{**asdict(record), "status": "rejected", "rejection_reason": reason}
        )
        return self.append(rejected)

    def promote_to_golden(self, record: PatternRecord, *, validation_metadata: dict[str, Any]) -> Path:
        if record.status != "candidate":
            raise ValueError("only candidate patterns can be promoted")
        if not record.validation_window:
            raise ValueError("golden patterns require an out-of-sample validation window")
        promoted = PatternRecord(
            **{
                **asdict(record),
                "status": "golden",
                "validation_metadata": validation_metadata,
            }
        )
        return self.append(promoted)
