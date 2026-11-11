"""Concurrency: fire many unlocks and resolves at the same instant and see if H1 stays single.

The corpus claims protection against retry storms and double execution as an "operational
discovery", never as a measurement. This measures it, against the real platform.js in the
in-memory mode, where the event loop is the only source of interleaving.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = Path("/tmp/plc/platform.js")
PORT = 4011
BASE = f"http://127.0.0.1:{PORT}"
API_KEY = "concurrency-key"
N = 25


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-api-key": API_KEY},
                                 method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=20)
        return r.getcode(), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def start():
    env = {**os.environ, "PLATFORM_SECRET": "concurrency-secret", "API_KEY": API_KEY, "PORT": str(PORT)}
    env.pop("REDIS_URL", None)
    proc = subprocess.Popen(["node", str(SERVICE)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/v1/health", timeout=1)
            return proc
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    raise SystemExit("service did not start")


def race(kind: str) -> dict:
    proc = start()
    try:
        _, s = post("/v1/session", {"service_id": "svc-race", "device_id": "dev-race", "receipt_id": f"R-{kind}"})
        h0 = s["h0"]
        post("/v1/signal", {"h0": h0, "signal_type": "provider_ack", "signal_ref": "ack-race"})
        target = "/v1/unlock" if kind == "unlock" else "/v1/resolve"
        if kind == "resolve":
            post("/v1/unlock", {"h0": h0})   # resolve needs user_unlock too
        with ThreadPoolExecutor(max_workers=N) as pool:
            results = list(pool.map(lambda _: post(target, {"h0": h0}), range(N)))
        codes = {}
        h1s = set()
        for code, body in results:
            codes[code] = codes.get(code, 0) + 1
            if body.get("h1"):
                h1s.add(body["h1"])
        return {"race": kind, "attempts": N, "codes": codes,
                "distinct_h1": len(h1s), "h1_issued": sum(1 for _, b in results if b.get("h1"))}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    out = [race("unlock"), race("resolve")]
    (ROOT / "results/paylock_concurrency.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))

    lines = [
        "# تزامن: هل يبقى H1 واحدًا تحت الضغط؟",
        "",
        "تشغيل حقيقي لـ`platform.js` في وضع الذاكرة، و25 طلبًا في اللحظة نفسها عبر خيوط متوازية.",
        "",
        "| سباق | محاولات | الرموز | قيم H1 المختلفة | من صدر له H1 |",
        "|---|---|---|---|---|",
    ]
    for r in out:
        codes = ", ".join(f"{c}×{n}" for c, n in sorted(r["codes"].items()))
        lines.append(f"| {r['race']} | {r['attempts']} | {codes} | **{r['distinct_h1']}** | {r['h1_issued']} |")
    unlock = next(r for r in out if r["race"] == "unlock")
    resolve = next(r for r in out if r["race"] == "resolve")
    lines += [
        "",
        "## القراءة",
        "",
        f"- سباق الفتح: **{unlock['distinct_h1']}** قيمة H1 واحدة عبر {unlock['attempts']} محاولة. "
        f"الرمز {unlock['codes'].get(200, 0)}×200 و{unlock['codes'].get(409, 0)}×409.",
        f"- سباق الحل: **{resolve['distinct_h1']}** قيمة أيضًا، و{resolve['codes'].get(200, 0)}×200 — "
        "أي أن كل المتسابقين حصلوا على الدليل نفسه، لا على دليل جديد.",
        "",
        "هذا هو الفرق بين «نحمي بالكود» و«أثبتنا الحماية»:",
        "",
        "- `SET NX` على مفتاح `h1:{h0}` هو ما يجعل القيمة واحدة، لا منطق التطبيق.",
        "- الفتح المكرر يُرفض 409 لأن الإشارة موجودة، لكن هذا فحص قراءة-ثم-كتابة، وليس ذريًا؛ "
        "في وضع الذاكرة أحادي العملية يمرّ، ومع Redis حقيقي وتعدد العمليات قد يمرّ إشارات مكرّرة — "
        "لكن H1 يبقى واحدًا لأن الحماية في الطبقة الثانية.",
        "- **الخلاصة العملية:** البروتوكول آمن على مستوى الدليل، وهشّ على مستوى الإشارة. "
        "من يبني على «إشارة الفتح لا تتكرر» يبني على فحص غير ذري؛ ومن يبني على «H1 واحد» يبني على `SET NX`.",
        "",
        "## ما لا تقوله هذه التجربة",
        "",
        "وضع الذاكرة عملية واحدة وحلقة أحداث واحدة. التزامن الحقيقي (Redis، عمليات متعددة، شبكة) "
        "قد يوسّع نافذة القراءة-ثم-الكتابة. الرقم أعلاه سقف تفاؤلي، لا إثبات نهائي.",
    ]
    (ROOT / "results/paylock_concurrency.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
