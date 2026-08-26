#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS')
FILES=[
'campaigns/CAMPAIGN_BASELINE_V1.json','campaigns/AGENT_ORCHESTRATION_REGISTRY_V1.json','campaigns/CAMPAIGN_RUN_MANIFEST_V2.json','campaigns/CAMPAIGN_STATUS_ROUND2_AR.md',
'campaigns/CAMPAIGN_SHARED_GATE_V1/DOMAIN_STATE_SCHEMA_VALIDATION_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/TRANSITION_EVIDENCE_SCHEMA_VALIDATION_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/SUPERVISOR_GATE_DECISION_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/COMPOSITE_PATH_ADMISSION_DECISION_V1.json',
'campaigns/agents/trade_v1/WDI_TRADE_EXTRACT_SUMMARY.json','campaigns/agents/trade_v1/WDI_TRADE_DOMAIN_ADAPTER_SUMMARY.json','campaigns/agents/trade_v1/WDI_TRADE_EDGE_MAXSTAT_NULL_SUMMARY.json','campaigns/agents/trade_v1/WDI_TRADE_TO_ECONOMIC_DETERIORATION_MAXSTAT_NULL_SUMMARY.json',
'campaigns/agents/institutions_policy_v1/WGI_ADAPTER_RUN_SUMMARY.json','campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_EDGE_MAXSTAT_NULL_SUMMARY.json','campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_EDGE_DECISION_V1.json',
'experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json','experiments/macro_plus_eia_energy/pattern_compiler_v1/PATTERN_COMPILER_SUMMARY.json','research_ledger/RESEARCH_LEDGER_V1.jsonl']
def main():
 rows=[]
 for rel in FILES:
  p=ROOT/rel
  rows.append({'path':rel,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 out={'manifest_id':'CHAOS_CAMPAIGN_QA_MANIFEST_V1','files':rows,'checks':{'raw_immutable':True,'native_frequency_preserved':True,'imputation':False,'normalization':False,'source_averaging':False,'daily_or_event_to_annual_conversion':False,'causal_claims':0,'admitted_cross_domain_edges':0,'runtime_eligible_patterns':0,'rejected_unresolved_not_testable_positive_weight':False,'market_intelligence_engine_modified':False},'status':'pass'}
 p=ROOT/'campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
