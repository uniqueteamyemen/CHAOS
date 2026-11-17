"""Auditable HTTP acquisition for World Bank and USGS official endpoints."""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "artifacts" / "real_data_stress" / "raw"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slug(value: str, max_length: int = 100) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return (value or "source")[:max_length]


def build_session(retry_attempts: int = 6) -> requests.Session:
    retry = Retry(
        total=retry_attempts,
        connect=retry_attempts,
        read=retry_attempts,
        status=retry_attempts,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET",)),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "CHAOS-Real-Data-Stress-Pipeline/1.0 (reproducible research; contact: uniqueteamyemen)",
        "Accept": "application/json, application/geo+json, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, */*",
    })
    return session


@dataclass
class Snapshot:
    source_id: str
    url: str
    params: dict[str, Any]
    retrieved_at_utc: str
    http_status: int
    content_type: str | None
    byte_count: int
    sha256: str
    raw_path: str
    etag: str | None = None
    last_modified: str | None = None


class SourceFetcher:
    def __init__(
        self,
        raw_root: Path = RAW_ROOT,
        retry_attempts: int = 6,
        timeout_seconds: int = 90,
        session: requests.Session | None = None,
    ) -> None:
        self.raw_root = raw_root
        self.timeout = timeout_seconds
        self.session = session or build_session(retry_attempts)
        self.snapshots: list[Snapshot] = []

    def get_bytes(
        self,
        source_id: str,
        url: str,
        params: dict[str, Any] | None = None,
        extension: str = "json",
        subdirectory: str | None = None,
    ) -> tuple[bytes, Snapshot]:
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        content = response.content
        if not content:
            raise ValueError(f"empty_source_response:{source_id}:{response.url}")

        folder = self.raw_root / slug(subdirectory or source_id)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        file_name = f"{slug(source_id)}_{stamp}.{slug(extension, 12)}"
        path = folder / file_name
        path.write_bytes(content)

        snapshot = Snapshot(
            source_id=source_id,
            url=response.url,
            params=dict(params or {}),
            retrieved_at_utc=utc_now(),
            http_status=response.status_code,
            content_type=response.headers.get("Content-Type"),
            byte_count=len(content),
            sha256=sha256_bytes(content),
            raw_path=str(path.relative_to(ROOT)),
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )
        self.snapshots.append(snapshot)
        return content, snapshot

    def get_json(
        self,
        source_id: str,
        url: str,
        params: dict[str, Any] | None = None,
        subdirectory: str | None = None,
    ) -> tuple[Any, Snapshot]:
        raw, snapshot = self.get_bytes(
            source_id=source_id,
            url=url,
            params=params,
            extension="json",
            subdirectory=subdirectory,
        )
        try:
            payload = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid_json_response:{source_id}:{exc}") from exc
        return payload, snapshot

    def get_file(
        self,
        source_id: str,
        url: str,
        params: dict[str, Any] | None = None,
        extension: str = "bin",
        subdirectory: str | None = None,
    ) -> tuple[Path, Snapshot]:
        _, snapshot = self.get_bytes(
            source_id=source_id,
            url=url,
            params=params,
            extension=extension,
            subdirectory=subdirectory,
        )
        return ROOT / snapshot.raw_path, snapshot

    def export_manifest(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.snapshots]


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
