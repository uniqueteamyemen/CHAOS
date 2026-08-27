#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); ledger=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
refs=['experimental_contracts/dual_track_v02/TRADE_NETWORK_ADAPTATION_PATH_CONTRACT_V1_1.json','experiments/dual_track_v02/trade_network_adaptation_path_v1_1/TRADE_NETWORK_ADAPTATION_PATH_SUMMARY_V1.json','experiments/dual_track_v02/trade_network_adaptation_path_v1_1/TRADE_NETWORK_ADAPTATION_PATH_TRANSITION_EVIDENCE_V1_1.jsonl','experiments/dual_track_v02/trade_network_adaptation_path_v1_1/TRADE_NETWORK_ADAPTATION_PATH_RUN_MANIFEST_V1_1.json','experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl','experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json','experiments/macro_plus_eia_energy/pattern_compiler_v1/PATTERN_COMPILER_SUMMARY.json','campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json']
def sha(x):return hashlib.sha256((ROOT/x).read_bytes()).hexdigest()
r={'ledger_id':'TRADE_NETWORK_ADAPTATION_PATH_V1_1_GOVERNANCE_CLOSURE','record_type':'final_governance_closure','status':'rejected','created_at_utc':datetime.now(timezone.utc).isoformat(),'input_hashes':{x:sha(x) for x in refs},'output_refs':refs,'decision':'Path V1.1 is rejected after complete Event-Path execution. No causal validation, no runtime eligibility, no positive Composer weight, and host engine unchanged. Graph and final supervisor gate pass with only the two pre-existing supported-predictive records admitted.'}
r['record_hash']=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); ids={json.loads(x)['ledger_id'] for x in ledger.read_text().splitlines() if x.strip()}
if r['ledger_id'] not in ids: ledger.open('a').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n'); print(json.dumps({'appended':True,'ledger_id':r['ledger_id'],'record_hash':r['record_hash']},ensure_ascii=False,indent=2))
else:print(json.dumps({'appended':False,'ledger_id':r['ledger_id']},ensure_ascii=False,indent=2))
