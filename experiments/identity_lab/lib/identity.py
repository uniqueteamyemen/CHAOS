"""Shared machinery for the CHAOS identity lab.

Two objects only:
  * an identity (zero parameters) and its residual
  * a residual event (attributed, versioned, adjudicable)

Nothing here estimates a coefficient. Nothing here fits a model.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

REQUIRED_EVENT_FIELDS = [
    "event_id", "identity_id", "identity_version", "entity", "time",
    "native_frequency", "magnitude", "attributed_term", "classification",
    "detector", "adjudication", "evidence_refs",
]


def mad_sigma(values: list[float]) -> float:
    """Robust scale. Never use the standard deviation of a window that may hide a break."""
    if not values:
        return 0.0
    m = statistics.median(values)
    mad = statistics.median([abs(v - m) for v in values])
    return 1.4826 * mad


def stock_residuals(rows: list[dict]) -> list[dict]:
    """closing_expected = opening + arrivals - dispensed - expired; residual = expected - counted."""
    out = []
    for r in rows:
        expected = r["opening"] + r["arrivals"] - r["dispensed"] - r["expired"]
        out.append({**r, "expected": expected, "residual": expected - r["closing"]})
    return out


def detect_sign_runs(series: list[dict], sigma: float, k: float, run_len: int) -> list[dict]:
    """Rule: run_len consecutive residuals, same sign, each beyond k*sigma.

    Deliberately dumb and auditable: no model, no likelihood, no parameters fitted to the data.
    """
    events, run = [], []
    for row in series:
        r = row["residual"]
        if sigma > 0 and abs(r) >= k * sigma:
            if run and (r > 0) != (run[-1] > 0):
                run = [r]
            else:
                run.append(r)
        else:
            run = []
        if len(run) >= run_len:
            events.append(
                {
                    "detect_at": row["time"],
                    "run_len": len(run),
                    "mean_residual": sum(run) / len(run),
                    "first_in_run": row["time"],
                }
            )
            run = []
    return events


def cusum(series: list[dict], sigma: float, k_sigma: float = 0.5, h_sigma: float = 5.0) -> list[dict]:
    """Two-sided CUSUM, kept only as a cross-check on the sign-run rule."""
    if sigma <= 0:
        return []
    k, h = k_sigma * sigma, h_sigma * sigma
    pos = neg = 0.0
    hits = []
    for row in series:
        r = row["residual"]
        pos = max(0.0, pos + r - k)
        neg = min(0.0, neg + r + k)
        if pos > h or -neg > h:
            hits.append({"detect_at": row["time"], "side": "leak" if pos > h else "surplus"})
            pos = neg = 0.0
    return hits


def make_event(
    identity_id: str,
    identity_version: int,
    entity: str,
    time: str,
    value: float,
    unit: str,
    attributed_term: str | None,
    classification: str,
    rule: str,
    params: dict,
    evidence_refs: list[str],
    cumulative: float | None = None,
    frequency: str = "monthly",
) -> dict:
    digest = hashlib.sha256(
        f"{identity_id}|{identity_version}|{entity}|{time}|{value}".encode()
    ).hexdigest()[:16]
    return {
        "event_id": digest,
        "identity_id": identity_id,
        "identity_version": identity_version,
        "entity": entity,
        "time": time,
        "native_frequency": frequency,
        "magnitude": {"value": round(value, 6), "unit": unit},
        "cumulative_magnitude": None if cumulative is None else round(cumulative, 6),
        "attributed_term": attributed_term,
        "classification": classification,
        "detector": {"rule": rule, "params": params},
        "adjudication": {"status": "unreviewed", "reviewer": None, "reviewed_at": None, "note": None},
        "evidence_refs": evidence_refs,
    }


def check_event(event: dict, schema: dict) -> list[str]:
    """Light structural check against the published schema (no external dependency)."""
    problems = []
    for field in schema["required"]:
        if field not in event:
            problems.append(f"missing field: {field}")
    extra = set(event) - set(schema["properties"])
    if extra:
        problems.append(f"unexpected fields: {sorted(extra)}")
    if event.get("classification") not in schema["properties"]["classification"]["enum"]:
        problems.append("bad classification")
    if event.get("magnitude") and set(event["magnitude"]) != {"value", "unit"}:
        problems.append("bad magnitude shape")
    return problems


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[idx]
