#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 exp_a_h1/h1.py
python3 exp_a_h1/identifiability.py
python3 exp_a_h1/audit_corpus.py
python3 exp_b_stock/stock.py
python3 exp_b_stock/false_alarm.py
python3 exp_c_eia/oil.py
python3 exp_c_eia/analyse.py
python3 exp_d_relational/relational.py
python3 exp_e_robustness/robustness.py
python3 exp_f_engine/engine.py
python3 exp_g_real/mirror_trade.py
python3 exp_h_public/public_ledger.py
python3 exp_h_public/derive_lab_ledger.py
python3 exp_h_public/freeze.py verify
python3 exp_j_erp/run_erp.py
python3 exp_j_erp/run_reconcile.py
python3 -m unittest exp_j_erp.test_erp_reconcile -v
python3 exp_g_real/bias_holdout.py
if command -v node >/dev/null 2>&1; then python3 exp_i_platform/run_cycle.py; fi
python3 - <<'PY'
import json, glob, sys
from pathlib import Path
sys.path.insert(0, ".")
from lib.identity import check_event
schema = json.loads(Path("schemas/residual_event_v1.schema.json").read_text())
bad = 0
for f in sorted(glob.glob("results/*events*.jsonl")):
    for line in Path(f).read_text().splitlines():
        ev = json.loads(line)
        p = check_event(ev, schema)
        if p:
            bad += 1
            print(f, ev.get("event_id"), p)
print("events validated against schema, problems:", bad)
PY
