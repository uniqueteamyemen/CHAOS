"""Run the real PayLock Core locally and record a real trace.

The deployed Railway instance answers `404 Application not found`, so the only way to get a
trace is to run the actual service. `platform.js` is the unmodified file from
`paylock-core`, fetched read-only; it has a built-in in-memory fallback when `REDIS_URL`
is absent, which is exactly what a reproducible run needs.

Nothing is written to the repository. Only the local copy is executed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = Path("/tmp/plc/platform.js")
PORT = 3999
BASE = f"http://127.0.0.1:{PORT}"
API_KEY = "local-test-key"
STEPS: list[dict] = []


def call(action, method, path, body=None, headers=None, note=""):
    data = None if body is None else json.dumps(body).encode()
    hdrs = {"Content-Type": "application/json", "x-api-key": API_KEY}
    hdrs.update(headers or {})
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    try:
        r = urllib.request.urlopen(req, timeout=15)
        code, raw = r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read()
    except Exception as e:  # noqa: BLE001
        code, raw = 0, json.dumps({"error": str(e)}).encode()
    try:
        parsed = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        parsed = {"raw": raw[:200].decode("utf-8", "replace")}
    STEPS.append({"step": len(STEPS) + 1, "ts": ts, "action": action, "path": path,
                  "code": code, "body": parsed, "note": note})
    return parsed


def main() -> None:
    env = {**os.environ, "PLATFORM_SECRET": "local-secret", "API_KEY": API_KEY, "PORT": str(PORT)}
    env.pop("REDIS_URL", None)
    proc = subprocess.Popen(["node", str(SERVICE)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(BASE + "/v1/health", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.2)
        else:
            print("service did not start", proc.stdout.read()[:500])
            return

        call("health", "GET", "/v1/health", note="pre-flight")

        # A. a full, valid lifecycle
        s1 = call("create", "POST", "/v1/session",
                  {"service_id": "svc-1", "device_id": "dev-1", "receipt_id": "R-A"},
                  note="session with receipt R-A")
        h0 = s1.get("h0", "missing")
        call("duplicate_receipt", "POST", "/v1/session",
             {"service_id": "svc-1", "device_id": "dev-1", "receipt_id": "R-A"},
             note="same receipt again")
        call("resolve_before_signals", "POST", "/v1/resolve", {"h0": h0}, note="no signals yet")
        call("signal_provider_ack", "POST", "/v1/signal",
             {"h0": h0, "signal_type": "provider_ack", "signal_ref": "ack-1"})
        call("resolve_missing_unlock", "POST", "/v1/resolve", {"h0": h0}, note="ack only")
        call("unlock", "POST", "/v1/unlock", {"h0": h0, "device_fingerprint": "fp-1"})
        call("unlock_replay", "POST", "/v1/unlock", {"h0": h0, "device_fingerprint": "fp-1"})
        call("resolve_after", "POST", "/v1/resolve", {"h0": h0})
        call("resolve_again", "POST", "/v1/resolve", {"h0": h0})

        # B. unlock before acknowledgement — what does the gate actually hold?
        s2 = call("create_no_receipt", "POST", "/v1/session", {"service_id": "svc-2", "device_id": "dev-2"})
        h0b = s2.get("h0", "missing")
        call("unlock_before_ack", "POST", "/v1/unlock", {"h0": h0b},
             note="no provider_ack yet: does unlock still succeed?")
        call("resolve_without_ack", "POST", "/v1/resolve", {"h0": h0b}, note="must fail")

        # C. cancellation closes the session
        s3 = call("create_cancel_case", "POST", "/v1/session",
                  {"service_id": "svc-3", "device_id": "dev-3", "receipt_id": "R-C"})
        h0c = s3.get("h0", "missing")
        call("cancel", "POST", "/v1/webhook/cancel",
             {"h0": h0c, "receipt_id": "R-C", "reason": "test"})
        call("unlock_after_cancel", "POST", "/v1/unlock", {"h0": h0c})
        call("resolve_after_cancel", "POST", "/v1/resolve", {"h0": h0c})

        # D. malformed and unknown
        call("missing_fields", "POST", "/v1/session", {"service_id": "x"})
        call("unknown_h0", "POST", "/v1/resolve", {"h0": "0" * 64})
        call("no_api_key", "POST", "/v1/resolve", {"h0": h0}, headers={"x-api-key": "wrong"})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    out = ROOT / "results/paylock_live_trace.jsonl"
    out.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in STEPS) + "\n", encoding="utf-8")
    print(json.dumps([(s["action"], s["code"]) for s in STEPS], ensure_ascii=False))


if __name__ == "__main__":
    main()
