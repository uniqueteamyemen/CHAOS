#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); L=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
def digest(rel):
 p=ROOT/rel; return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def add(r):
 old=[json.loads(x) for x in L.read_text().splitlines() if x.strip()]
 if any(x['ledger_id']==r['ledger_id'] for x in old): raise SystemExit('duplicate '+r['ledger_id'])
 payload=json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')); r['record_hash']=hashlib.sha256(payload.encode()).hexdigest(); L.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
def main():
 now=datetime.now(timezone.utc).isoformat()
 rows=[
  ('TEMPORAL_ALIGNMENT_AUDIT_V1','qa',['experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json'],['experiments/macro_plus_eia_energy/temporal_alignment_audit_v1/TEMPORAL_ALIGNMENT_AUDIT_V1.json'],'pass','annual-to-annual only; zero rows dropped'),
  ('WITHIN_DOMAIN_EDGES_V1','run',['experimental_contracts/WITHIN_DOMAIN_EDGE_CONTRACT_V1.json','catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'],['experiments/macro_plus_eia_energy/within_domain_edges_v1/WITHIN_DOMAIN_EDGE_METRICS.csv','experiments/macro_plus_eia_energy/within_domain_edges_v1/WITHIN_DOMAIN_EDGE_MAXSTAT_NULL_SUMMARY.json'],'research_evidence_only','three predeclared edges; current max-stat p=0.3013493253'),
  ('NATIVE_HEALTH_DISASTER_ADAPTERS_V1','domain_state',['experimental_contracts/HEALTH_DISASTER_ADAPTER_CONTRACT_V1.json','catalog_first/readiness_gate/independent_sources/NATIVE_SOURCE_PROVENANCE_MANIFEST_V1.json'],['experiments/multi_domain_native_adapters_v1/NATIVE_ADAPTERS_RUN_SUMMARY.json','experiments/multi_domain_native_adapters_v1/WHO_COVID_DOMAIN_STATES_DAILY_V1.jsonl.gz','experiments/multi_domain_native_adapters_v1/USGS_EARTHQUAKE_DOMAIN_STATES_EVENT_V1.jsonl'],'native_states_only','WHO daily and USGS event; no annualization or production shock inference'),
  ('EVIDENCE_GRAPH_V1','transition_evidence',['experiments/macro_plus_eia_energy/transition_evidence_v1/TRANSITION_EVIDENCE_V1.jsonl','experiments/multi_domain_native_adapters_v1/TRANSITION_EVIDENCE_NATIVE_DOMAINS_V1.jsonl','experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'],['experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_V1.json','experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json'],'active','20 nodes and 21 edges; causal claims zero'),
  ('PATTERN_COMPILER_V1','run',['experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_V1.json','experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'],['experiments/macro_plus_eia_energy/pattern_compiler_v1/COMPILED_PATTERNS_V1.json','experiments/macro_plus_eia_energy/pattern_compiler_v1/PATTERN_COMPILER_SUMMARY.json'],'research_only','zero runtime-eligible patterns; one provisional research candidate')]
 for lid,typ,src,out,status,note in rows:
  add({'ledger_id':lid,'record_type':typ,'created_at_utc':now,'source_refs':src,'contract_ref':src[0],'input_hashes':{x:digest(x) for x in src},'output_refs':out,'status':status,'notes':note})
if __name__=='__main__':main()
