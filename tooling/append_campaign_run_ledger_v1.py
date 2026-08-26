#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); LEDGER=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
def digest(rel):return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
def add(r):
 old=[json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
 if any(x.get('ledger_id')==r['ledger_id'] for x in old):return False
 r['created_at_utc']=datetime.now(timezone.utc).isoformat(); r['record_hash']=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); LEDGER.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n');return True
def main():
 rows=[
 {'ledger_id':'CAMPAIGN_BASELINE_V1','record_type':'campaign_baseline','contract_ref':'campaigns/CAMPAIGN_BASELINE_V1.json','input_hashes':{'experiments/macro_plus_eia_energy/RESEARCH_SNAPSHOT_V3.json':digest('experiments/macro_plus_eia_energy/RESEARCH_SNAPSHOT_V3.json'),'CHAOS_TERMINOLOGY_AND_RELATIONSHIPS.md':digest('CHAOS_TERMINOLOGY_AND_RELATIONSHIPS.md')},'output_refs':['campaigns/CAMPAIGN_BASELINE_V1.json','campaigns/AGENT_ORCHESTRATION_REGISTRY_V1.json','campaigns/CAMPAIGN_RUN_MANIFEST_V1.json'],'status':'frozen','notes':'supervisor-controlled open campaign baseline'},
 {'ledger_id':'WGI_INSTITUTIONS_AGENT_RUN_V1','record_type':'domain_adapter_and_edges','contract_ref':'experimental_contracts/WGI_INSTITUTIONAL_EDGE_CONTRACT_V1.json','input_hashes':{'catalog_first/readiness_gate/independent_sources/worldbank_wgi_2025/raw/WGI_CSV.zip':digest('catalog_first/readiness_gate/independent_sources/worldbank_wgi_2025/raw/WGI_CSV.zip')},'output_refs':['campaigns/agents/institutions_policy_v1/WGI_ADAPTER_RUN_SUMMARY.json','campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_EDGE_MAXSTAT_NULL_SUMMARY.json','campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_EDGE_DECISION_V1.json','campaigns/agents/institutions_policy_v1/WGI_TRANSITION_EVIDENCE_V1.jsonl'],'status':'no_positive_edge_admitted','notes':'5 rejected; 5 not_testable; no policy shock or leader deviation inferred'},
 {'ledger_id':'TRADE_AGENT_RUN_V1','record_type':'domain_adapter_readiness','contract_ref':'campaigns/AGENT_ORCHESTRATION_REGISTRY_V1.json','input_hashes':{'campaigns/agents/trade_v1/COMTRADE_BOUNDED_PROVENANCE_V1.json':digest('campaigns/agents/trade_v1/COMTRADE_BOUNDED_PROVENANCE_V1.json')},'output_refs':['campaigns/agents/trade_v1/TRADE_ADAPTER_RUN_SUMMARY.json','campaigns/agents/trade_v1/TRADE_TRANSITION_EVIDENCE_V1.jsonl'],'status':'not_testable_current_assets','notes':'124 successful annual preview records; 1 timeout; no multidimensional network edge'},
 {'ledger_id':'SUPERVISOR_ADMISSION_GATE_CAMPAIGN_RUN_01','record_type':'supervisor_gate','contract_ref':'campaigns/AGENT_ORCHESTRATION_REGISTRY_V1.json','input_hashes':{'campaigns/CAMPAIGN_RUN_MANIFEST_V1.json':digest('campaigns/CAMPAIGN_RUN_MANIFEST_V1.json')},'output_refs':['campaigns/CAMPAIGN_SHARED_GATE_V1/SUPERVISOR_GATE_DECISION_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/ADMITTED_SUPPORTED_TRANSITIONS_V1.jsonl','campaigns/CAMPAIGN_SHARED_GATE_V1/QUARANTINED_TRANSITIONS_V1.jsonl'],'status':'pass','notes':'only supported_predictive records admitted; no causal claims admitted'}]
 for r in rows:add(r)
 print('ledger_lines',sum(1 for x in LEDGER.read_text().splitlines() if x.strip()))
if __name__=='__main__':main()
