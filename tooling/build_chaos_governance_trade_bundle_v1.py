#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/governance_mvp_v1/trade_regime_transition_audit'; OUT.mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1024*1024): h.update(b)
 return h.hexdigest()
files=[
 ('contract','experimental_contracts/dual_track_v02/TRADE_REGIME_TRANSITION_DISCOVERY_CONTRACT_V1.json'),
 ('protocol','campaigns/dual_track_v02/CHAOS_DUAL_TRACK_PROTOCOL_V0_2.json'),
 ('state_panel','experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_STATE_PANEL_V1.csv'),
 ('events','experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_EVENTS_V1.csv'),
 ('rolling_metrics','experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_ROLLING_METRICS_V1.csv'),
 ('subwindows','experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_SUBWINDOWS_V1.csv'),
 ('null_summaries','experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_NULL_SUMMARIES_V1.json'),
 ('summary','experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_SUMMARY_V1.json'),
 ('transition_evidence','experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl'),
]
arts=[]
for role,rel in files:
 p=ROOT/rel; arts.append({'path':rel,'role':role,'sha256':sha(p),'bytes':p.stat().st_size})
# Replay rebuilds the deterministic TransitionEvidence artifact. It is declared but not executed by this builder.
out={'bundle_id':'CHAOS_GOVERNANCE_TRADE_REGIME_TRANSITION_V1','schema_version':'governance_bundle_v1','created_at':'2026-08-27T00:00:00Z','decision_status':'rejected','purpose':'MVP governance validation over a real CHAOS research run; no raw data copied or modified.','artifacts':arts,'decision':{'status':'rejected','positive_composer_weight':0,'runtime_eligible':False,'causal_claim':False,'reason':'Final predictive trade-regime attempt failed contractual admission criteria; preserved as auditable negative evidence.'},'replay':{'command':['python3','tooling/build_trade_regime_transition_transition_evidence_v1.py'],'cwd':'.','outputs':[{'path':'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl','sha256':arts[-1]['sha256']}],'mode':'deterministic_rebuild','raw_external':'IMTS raw remains outside Git and is not copied into governance bundle.'}}
(OUT/'GOVERNANCE_BUNDLE_MANIFEST_V1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps({'manifest':str(OUT/'GOVERNANCE_BUNDLE_MANIFEST_V1.json'),'artifact_count':len(arts),'decision_status':out['decision_status']},ensure_ascii=False,indent=2))
