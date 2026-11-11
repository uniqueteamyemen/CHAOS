"""Pull the four PayLock integration reports, read-only, the moment the repository is readable.

No token. No writes. If the repository is private the API answers 404 and this script says so.

  python3 exp_a_h1/fetch_corpus.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exp_a_h1/corpus"
REPO = "uniqueteamyemen/paylock-core"
CANDIDATES = [
    "integration/experiments/medusa/MEDUSA_INTEGRATION_REPORT.md",
    "integration/experiments/stripe/stripe-subscriptions/OBSERVED_BEHAVIORS.md",
    "integration/experiments/stripe/digital-goods/OBSERVED_BEHAVIORS.md",
    "integration/experiments/vendure/OBSERVED_BEHAVIORS.md",
]
HEADERS = {"User-Agent": "chaos-identity-lab", "Accept": "application/vnd.github.raw+json"}


def get(path: str) -> tuple[int, bytes]:
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30)
        return r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()


def main() -> None:
    status = get("")[0]
    if status == 404:
        print(json.dumps({"repo": REPO, "readable": False,
                          "note": "private (or absent); GitHub returns 404 without authentication"},
                         ensure_ascii=False))
        return
    if status != 200:
        print(json.dumps({"repo": REPO, "readable": False, "status": status}, ensure_ascii=False))
        return

    OUT.mkdir(parents=True, exist_ok=True)
    found = []
    for path in CANDIDATES:
        code, body = get(path)
        if code == 200:
            target = OUT / path.replace("/", "__")
            target.write_bytes(body)
            found.append({"path": path, "bytes": len(body), "saved": str(target.relative_to(ROOT))})
        else:
            found.append({"path": path, "status": code})
    print(json.dumps({"repo": REPO, "readable": True, "files": found}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
