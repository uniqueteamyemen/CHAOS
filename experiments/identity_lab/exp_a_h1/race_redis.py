"""Race test against the unmodified platform.js, with a network store that has real latency."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = Path("/tmp/plc/platform.js")
REDIS_PORT, APP_PORT, N = 6391, 4013, 40
BASE = f"http://127.0.0.1:{APP_PORT}"
KEY = "race-key"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-api-key": KEY},
                                 method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.getcode(), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def wait_http(url, tries=80):
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    return False


def main() -> None:
    redis = subprocess.Popen([sys.executable, str(ROOT / "exp_a_h1/miniredis.py"), str(REDIS_PORT)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1.0)
    env = {**os.environ, "PLATFORM_SECRET": "race-secret", "API_KEY": KEY,
           "PORT": str(APP_PORT), "REDIS_URL": f"redis://127.0.0.1:{REDIS_PORT}"}
    app = subprocess.Popen(["node", str(SERVICE)], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        if not wait_http(BASE + "/v1/health"):
            print("app did not start:", app.stdout.read()[:400])
            return
        _, s = post("/v1/session", {"service_id": "svc", "device_id": "dev", "receipt_id": "R-1"})
        h0 = s["h0"]
        post("/v1/signal", {"h0": h0, "signal_type": "provider_ack", "signal_ref": "ack"})

        with ThreadPoolExecutor(max_workers=N) as pool:
            results = list(pool.map(lambda _: post("/v1/unlock", {"h0": h0}), range(N)))

        codes = {}
        h1s = set()
        for code, body in results:
            codes[code] = codes.get(code, 0) + 1
            if body.get("h1"):
                h1s.add(body["h1"])
        out = {"attempts": N, "codes": codes, "distinct_h1": len(h1s),
               "unlock_200": codes.get(200, 0), "rejected_409": codes.get(409, 0)}
        (ROOT / "results/paylock_race_redis.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(json.dumps(out, ensure_ascii=False))
    finally:
        app.terminate()
        redis.terminate()


if __name__ == "__main__":
    main()
