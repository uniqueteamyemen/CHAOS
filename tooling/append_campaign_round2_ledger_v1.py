#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); LEDGER=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
def h(rel):return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
def add(r):
 old=[json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
 if any(x.get('ledger_id')==r['ledger_id'] for x in old):return
 r['created_at_utc']=datetime.now(timezone.utc).isoformat(); r['record_hash']=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); LEDGER.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
def main():
 add({'ledger_id':'DOMAIN_STATE_SCHEMA_VALIDATION_CAMPAIGN_ROUND_01','record_type':'schema_qa','contract_ref':'experimental_contracts/DOMAIN_STATE_SCHEMA_V1.json','input_hashes':{'tooling/validate_domain_state_schema_v1.py':h('tooling/validate_domain_state_schema_v1.py')},'output_refs':['campaigns/CAMPAIGN_SHARED_GATE_V1/DOMAIN_STATE_SCHEMA_VALIDATION_V1.json'],'status':'pass','notes':'four native adapter outputs contain all required fields; native frequencies preserved'})
 add({'ledger_id':'WGI_SCHEMA_CONFORMANT_REBUILD_V1','record_type':'domain_adapter_rebuild','contract_ref':'experimental_contracts/DOMAIN_STATE_SCHEMA_V1.json','input_hashes':{'tooling/build_wgi_institutional_domain_states_v1.py':h('tooling/build_wgi_institutional_domain_states_v1.py')},'output_refs':['campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_DOMAIN_STATES_ANNUAL_SOURCE_YEARS_V1.jsonl','campaigns/agents/institutions_policy_v1/WGI_ADAPTER_RUN_SUMMARY.json'],'status':'pass','notes':'replaced non-schema regime_probability with state_probability and added pattern_id/lead_profile/edge_status'})
 add({'ledger_id':'NATIVE_ADAPTERS_SCHEMA_CONFORMANT_REBUILD_V1','record_type':'domain_adapter_rebuild','contract_ref':'experimental_contracts/DOMAIN_STATE_SCHEMA_V1.json','input_hashes':{'tooling/build_health_disaster_domain_states_v1.py':h('tooling/build_health_disaster_domain_states_v1.py'),'tooling/build_trade_domain_states_v1.py':h('tooling/build_trade_domain_states_v1.py')},'output_refs':['experiments/multi_domain_native_adapters_v1/NATIVE_ADAPTERS_RUN_SUMMARY.json','campaigns/agents/trade_v1/TRADE_ADAPTER_RUN_SUMMARY.json'],'status':'pass','notes':'WHO daily, USGS event, and Trade annual outputs conform to required schema'})
 add({'ledger_id':'EVIDENCE_GRAPH_CAMPAIGN_ROUND_02','record_type':'graph_rebuild','contract_ref':'experimental_contracts/TRANSITION_EVIDENCE_SCHEMA_V1.json','input_hashes':{'tooling/build_evidence_graph_v1.py':h('tooling/build_evidence_graph_v1.py')},'output_refs':['experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json','experiments/macro_plus_eia_energy/pattern_compiler_v1/PATTERN_COMPILER_SUMMARY.json'],'status':'pass','notes':'39 nodes, 44 edges, 0 causal claims, 0 runtime-eligible patterns; WGI and Trade records included'})
 print('ledger_lines',sum(1 for x in LEDGER.read_text().splitlines() if x.strip()))
if __name__=='__main__':main()
