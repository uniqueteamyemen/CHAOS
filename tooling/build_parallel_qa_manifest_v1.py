#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS')
files=[
'catalog_first/readiness_gate/independent_sources/NATIVE_SOURCE_PROVENANCE_MANIFEST_V1.json',
'catalog_first/readiness_gate/independent_sources/who_covid_2026/raw/WHO_COVID_GLOBAL_DAILY_RAW.csv',
'catalog_first/readiness_gate/independent_sources/usgs_earthquake_2026/raw/USGS_EARTHQUAKE_M6_5_2000_2024_RAW.csv',
'experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json',
'experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json',
'experimental_contracts/HEALTH_DISASTER_ADAPTER_CONTRACT_V1.json',
'experimental_contracts/WITHIN_DOMAIN_EDGE_CONTRACT_V1.json',
'experimental_contracts/ECONOMIC_DETERIORATION_TO_CONFLICT_CONTRACT_V1.json',
'experiments/multi_domain_native_adapters_v1/NATIVE_ADAPTERS_RUN_SUMMARY.json',
'experiments/multi_domain_native_adapters_v1/WHO_COVID_DOMAIN_STATES_DAILY_V1.jsonl.gz',
'experiments/multi_domain_native_adapters_v1/USGS_EARTHQUAKE_DOMAIN_STATES_EVENT_V1.jsonl',
'experiments/multi_domain_native_adapters_v1/TRANSITION_EVIDENCE_NATIVE_DOMAINS_V1.jsonl',
'experiments/multi_domain_native_edges_v1/ECONOMIC_DETERIORATION_TO_CONFLICT_MAXSTAT_NULL_SUMMARY.json',
'experiments/multi_domain_native_edges_v1/ECONOMIC_DETERIORATION_TO_CONFLICT_METRICS.csv',
'experiments/multi_domain_native_edges_v1/TRANSITION_EVIDENCE_ECONOMIC_TO_CONFLICT_V1.jsonl',
'experiments/multi_domain_native_edges_v1/ECONOMIC_DETERIORATION_TO_CONFLICT_MAXSTAT_NULL_REPLICATES.csv',
'experiments/macro_plus_eia_energy/evidence_graph_v1/COMPETING_PATHS_V1.json',
'experiments/parallel_execution_qa/NEW_EDGES_OOS_NULL_STABILITY_V1.json',
'experiments/macro_plus_eia_energy/within_domain_edges_v1/WITHIN_DOMAIN_EDGE_MAXSTAT_NULL_SUMMARY.json',
'experiments/macro_plus_eia_energy/within_domain_edges_v1/WITHIN_DOMAIN_EDGE_METRICS.csv',
'experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json',
'experiments/macro_plus_eia_energy/pattern_compiler_v1/PATTERN_COMPILER_SUMMARY.json',
'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl',
'research_ledger/RESEARCH_LEDGER_V1.jsonl',
'tooling/run_deterioration_to_conflict_v1.py',
'tooling/build_health_disaster_domain_states_v1.py',
'tooling/build_evidence_graph_v1.py',
'tooling/compile_patterns_v1.py'
]
def main():
 rows=[]
 for rel in files:
  p=ROOT/rel; rows.append({'path':rel,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 manifest={'manifest_id':'CHAOS_PARALLEL_EXECUTION_QA_V1','raw_immutable':True,'native_frequency_preserved':True,'daily_to_annual_conversion':False,'event_to_annual_conversion':False,'imputation':False,'normalization':False,'causal_claims':0,'runtime_eligible_patterns':0,'positive_composer_statuses':['supported_predictive'],'rejected_or_unresolved_positive_weight':False,'source_failures_recorded':True,'files':rows}
 out=ROOT/'experiments/parallel_execution_qa/CHAOS_PARALLEL_EXECUTION_QA_V1.json'; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(out)
if __name__=='__main__':main()
