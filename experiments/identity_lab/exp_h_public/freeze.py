"""Freeze Experiment H: record hashes of its inputs and outputs, and refuse silent edits.

Experiment H is the first experiment on foreign data, and its value is that it reports what the
public ledger could NOT support. Rewriting its inputs to make the detectors pass would destroy
that finding. So: hash it, keep the manifest in the repo, and fail the suite if anything drifts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "exp_h_public"
RESULTS = ROOT / "results"
MANIFEST = LAB / "FROZEN.json"
WATCHED = [
    LAB / "data/stock_movements.csv",
    LAB / "data/products.csv",
    LAB / "public_ledger.py",
    RESULTS / "public_ledger.json",
    RESULTS / "public_ledger_report.md",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot() -> dict:
    return {str(p.relative_to(ROOT)): digest(p) for p in WATCHED if p.exists()}


def main(command: str = "verify") -> None:
    if command == "freeze":
        data = {"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "reason": "Experiment H reports a negative result and must not be edited to fit a hypothesis.",
                "files": snapshot()}
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"frozen": len(data["files"])}, ensure_ascii=False))
        return

    if not MANIFEST.exists():
        print("no manifest; run with 'freeze' first")
        raise SystemExit(1)
    frozen = json.loads(MANIFEST.read_text())["files"]
    now = snapshot()
    drift = []
    for path, old in frozen.items():
        if path not in now:
            drift.append(f"missing: {path}")
        elif now[path] != old:
            drift.append(f"changed: {path}")
    for path in now:
        if path not in frozen:
            drift.append(f"new file: {path}")

    if drift:
        print("EXPERIMENT H HAS DRIFTED:")
        for item in drift:
            print("  -", item)
        raise SystemExit(1)
    print(json.dumps({"h_frozen": True, "files": len(frozen)}))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "verify")
