#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
ROOT=Path('/home/ubuntu/CHAOS'); ledger=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
def sha(rel): return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
outputs=['campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json','experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json','experiments/macro_plus_eia_energy/pattern_compiler_v1/PATTERN_COMPILER_SUMMARY.json','experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_DEPENDENCE_V2_EXECUTION_DEVIATION_V1.json','experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVATION_SHARDS_MANIFEST_V2.json']
r={'ledger_id':'IMF_IMTS_PARTNER_DEPENDENCE_FINAL_QA_V2','record_type':'final_qa_and_governance','status':'pass','contract_ref':'experimental_contracts/IMF_IMTS_PARTNER_DEPENDENCE_CONTRACT_V2.json','created_at_utc':datetime.now(timezone.utc).isoformat(),'input_hashes':{x:sha(x) for x in outputs},'output_refs':outputs,'notes':'Final V2 closure: schema/domain validation, transition validation, supervisor admission, evidence graph, pattern compiler, final supervisor gate, and campaign QA all pass. Graph 57 nodes/58 edges; admitted supported-predictive records 2 (pre-existing), quarantined 27, runtime eligible 0, causal claims 0. V2 remains rejected and research-only; observation aggregate is ignored and reconstructible from tracked shards.'}
r['record_hash']=hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False).encode()).hexdigest(); existing={json.loads(x)['ledger_id'] for x in ledger.read_text().splitlines() if x.strip()};
if r['ledger_id'] not in existing:
 with ledger.open('a') as f:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 print(json.dumps({'appended':1,'ledger_id':r['ledger_id'],'record_hash':r['record_hash']},ensure_ascii=False,indent=2))
else: print(json.dumps({'appended':0,'already_present':1,'ledger_id':r['ledger_id']},ensure_ascii=False,indent=2))
