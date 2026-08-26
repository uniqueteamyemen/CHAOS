from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class CoverageEntry:
    variable_id: str
    source_id: str
    stream_type: str
    temporal_start_date: str | None
    temporal_end_date: str | None
    native_frequency: str
    missing_gaps_intervals: list[dict[str, str]] = field(default_factory=list)
    source_definition_shifts: list[dict[str, str]] = field(default_factory=list)
    provenance_refs: list[str] = field(default_factory=list)
    observation_count: int = 0
    status: str = "observed"
    notes: str = ""


@dataclass(frozen=True)
class SourceConflict:
    variable_id: str
    timestamp: str
    observations: list[dict[str, object]]
    conflict_type: str
    resolution: str = "unresolved_at_ingestion"


def write_coverage(entries: Iterable[CoverageEntry], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(entry) for entry in entries]
    for row in rows:
        row["missing_gaps_intervals"] = json.dumps(row["missing_gaps_intervals"], ensure_ascii=False)
        row["source_definition_shifts"] = json.dumps(row["source_definition_shifts"], ensure_ascii=False)
        row["provenance_refs"] = json.dumps(row["provenance_refs"], ensure_ascii=False)
    fields = list(rows[0]) if rows else [
        "variable_id", "source_id", "stream_type", "temporal_start_date", "temporal_end_date",
        "native_frequency", "missing_gaps_intervals", "source_definition_shifts",
        "provenance_refs", "observation_count", "status", "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_conflicts(conflicts: Iterable[SourceConflict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(asdict(conflict), ensure_ascii=False) for conflict in conflicts) + ("\n" if conflicts else ""),
        encoding="utf-8",
    )
