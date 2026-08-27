#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
ROOT=Path('/home/ubuntu/CHAOS'); LEDGER=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
files=[
 'experimental_contracts/dual_track_v02/TRADE_REGIME_TRANSITION_DISCOVERY_CONTRACT_V1.json',
 'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_SUMMARY_V1.json',
 'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl',
 'experiments/governance_mvp_v1/CHAOS_GOVERNANCE_MVP_V1_REPORT_AR.md',
 'experiments/governance_mvp_v1/trade_regime_transition_audit/GOVERNANCE_BUNDLE_MANIFEST_V1.json',
 'experiments/governance_mvp_v1/trade_regime_transition_audit/GOVERNANCE_BUNDLE_MANIFEST_V1_EVIDENCE_GRAPH.json',
 'experiments/governance_mvp_v1/trade_regime_transition_audit/GOVERNANCE_KERNEL_MVP_TEST_REPORT_V1.json',
 'campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json',
 'campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json'
]
def h(rel): return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
rec={'record_id':'CHAOS_GOVERNANCE_TRANSITION_20260827_V1','record_type':'governance_transition','timestamp':datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),'source':'CHAOS research closure','decision':'predictive_trade_search_closed_for_current_IMTS_questions; governance_kernel_mvp_active','predictive_status':'rejected','causal_claims':0,'runtime_eligible':0,'governance_kernel_test_status':'pass','raw_modified':False,'market_intelligence_engine_modified':False,'reason':'Final learned regime-transition attempt failed contractual admission: effect gain below threshold, rolling direction unstable, subwindow coverage insufficient, and null tests non-significant. Evidence is preserved; no further tuning on the same trade question.','artifacts':{rel:h(rel) for rel in files}}
rows=LEDGER.read_text().splitlines() if LEDGER.exists() else []
if not any(json.loads(x).get('record_id')==rec['record_id'] for x in rows if x.strip()):
 with LEDGER.open('a') as f:f.write(json.dumps(rec,ensure_ascii=False,sort_keys=True)+'\n')
 print(json.dumps({'appended':True,'record_id':rec['record_id']},ensure_ascii=False))
else: print(json.dumps({'appended':False,'record_id':rec['record_id']},ensure_ascii=False))
