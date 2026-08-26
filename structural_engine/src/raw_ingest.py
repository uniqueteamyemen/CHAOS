from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import requests


@dataclass(frozen=True)
class RetrievalRecord:
    source_id: str
    url: str
    retrieved_at_utc: str
    http_status: int
    content_type: str
    byte_length: int
    sha256: str
    raw_path: str
    request_headers: dict[str, str]
    response_headers: dict[str, str]
    query_parameters: dict[str, str]


class ImmutableRawStore:
    """Stores response bytes exactly as received; never transforms or fills data."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def persist(
        self,
        *,
        source_id: str,
        url: str,
        payload: bytes,
        http_status: int,
        content_type: str = "",
        request_headers: Mapping[str, str] | None = None,
        response_headers: Mapping[str, str] | None = None,
        query_parameters: Mapping[str, str] | None = None,
        suffix: str = ".bin",
    ) -> RetrievalRecord:
        retrieved = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        digest = hashlib.sha256(payload).hexdigest()
        filename = f"{retrieved}_{source_id}_{digest[:16]}{suffix}"
        raw_path = self.root / filename
        raw_path.write_bytes(payload)
        record = RetrievalRecord(
            source_id=source_id,
            url=url,
            retrieved_at_utc=retrieved,
            http_status=http_status,
            content_type=content_type,
            byte_length=len(payload),
            sha256=digest,
            raw_path=str(raw_path),
            request_headers=dict(request_headers or {}),
            response_headers=dict(response_headers or {}),
            query_parameters={str(k): str(v) for k, v in (query_parameters or {}).items()},
        )
        (raw_path.with_suffix(raw_path.suffix + ".provenance.json")).write_text(
            json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return record

    def fetch_and_persist(
        self,
        *,
        source_id: str,
        url: str,
        params: Mapping[str, str] | None = None,
        suffix: str = ".bin",
        timeout_seconds: int = 60,
    ) -> RetrievalRecord:
        response = requests.get(url, params=params, timeout=timeout_seconds)
        return self.persist(
            source_id=source_id,
            url=response.url,
            payload=response.content,
            http_status=response.status_code,
            content_type=response.headers.get("content-type", ""),
            response_headers=dict(response.headers),
            query_parameters=params,
            suffix=suffix,
        )


def verify_record(record: RetrievalRecord) -> bool:
    path = Path(record.raw_path)
    return path.exists() and path.stat().st_size == record.byte_length and hashlib.sha256(path.read_bytes()).hexdigest() == record.sha256


if __name__ == "__main__":
    raise SystemExit("Import ImmutableRawStore from a collector; no network call is made by this module directly.")
