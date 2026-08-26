#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path('/home/ubuntu/CHAOS')
FILES=[ROOT/'experiments/macro_plus_eia_energy/transition_evidence_v1/TRANSITION_EVIDENCE_V1.jsonl',ROOT/'experiments/multi_domain_native_adapters_v1/TRANSITION_EVIDENCE_NATIVE_DOMAINS_V1.jsonl',ROOT/'experiments/multi_domain_native_edges_v1/TRANSITION_EVIDENCE_ECONOMIC_TO_CONFLICT_V1.jsonl',ROOT/'campaigns/agents/trade_v1/TRADE_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/agents/trade_v1/WDI_TRADE_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/agents/trade_v1/WDI_TRADE_TO_ECONOMIC_DETERIORATION_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/agents/institutions_policy_v1/WGI_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_WITHIN_DOMAIN_TRANSITION_EVIDENCE_V1_1.jsonl']
REQUIRED={'transition_id','source_state','target_state','lag','split','metric','null_method','p_value','entity_holdout','source_refs','edge_status','causal_claim','failure_cases'}
ALLOWED={'candidate','supported_predictive','unresolved','rejected','not_testable','provisionally_supported_descriptive','rejected_by_current_maxstat_null','not_supported_by_current_cross_domain_null','weak_or_unresolved_cross_domain_signal','rejected_as_additive_node','rejected_as_additive_mediator','rejected_for_out_of_sample_degradation','rejected_as_additive_within_domain_edge'}
def main():
 rows=[]; total=0
 for p in FILES:
  for line_no,line in enumerate(p.read_text().splitlines(),1):
   if not line.strip():continue
   total+=1; r=json.loads(line); missing=sorted(REQUIRED-set(r)); errors=[]
   if missing: errors.append('missing:'+','.join(missing))
   if r.get('edge_status') not in ALLOWED: errors.append('unknown_edge_status')
   if r.get('causal_claim') is not False: errors.append('causal_claim_must_be_false')
   if errors: raise SystemExit(f'{p}:{line_no}: {errors}')
  rows.append({'path':str(p.relative_to(ROOT)),'records':sum(1 for x in p.read_text().splitlines() if x.strip())})
 out={'validator_id':'CHAOS_TRANSITION_EVIDENCE_SCHEMA_VALIDATOR_V1','record_count':total,'files':rows,'causal_claims_allowed':False,'status':'pass'}; p=ROOT/'campaigns/CAMPAIGN_SHARED_GATE_V1/TRANSITION_EVIDENCE_SCHEMA_VALIDATION_V1.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
