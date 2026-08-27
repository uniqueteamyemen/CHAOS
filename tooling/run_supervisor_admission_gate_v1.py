#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'campaigns/CAMPAIGN_SHARED_GATE_V1'; OUT.mkdir(parents=True,exist_ok=True)
FILES=[ROOT/'experiments/macro_plus_eia_energy/transition_evidence_v1/TRANSITION_EVIDENCE_V1.jsonl',ROOT/'experiments/multi_domain_native_adapters_v1/TRANSITION_EVIDENCE_NATIVE_DOMAINS_V1.jsonl',ROOT/'experiments/multi_domain_native_edges_v1/TRANSITION_EVIDENCE_ECONOMIC_TO_CONFLICT_V1.jsonl',ROOT/'campaigns/agents/trade_v1/TRADE_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/agents/trade_v1/WDI_TRADE_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/agents/trade_v1/WDI_TRADE_TO_ECONOMIC_DETERIORATION_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/agents/institutions_policy_v1/WGI_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_WITHIN_DOMAIN_TRANSITION_EVIDENCE_V1_1.jsonl',ROOT/'experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPORT_TO_GDP_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'experiments/multi_domain_native_edges_v1/imf_partner_dependence_v1/IMF_IMTS_PARTNER_DEPENDENCE_TRANSITION_EVIDENCE_V1.jsonl',ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_DEPENDENCE_TRANSITION_EVIDENCE_V2.jsonl',ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3/IMF_IMTS_PARTNER_SUBSTITUTION_TRANSITION_EVIDENCE_V3.jsonl',ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3_1/IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_TRANSITION_EVIDENCE.jsonl',ROOT/'experiments/dual_track_v02/trade_network_adaptation_path_v1_1/TRADE_NETWORK_ADAPTATION_PATH_TRANSITION_EVIDENCE_V1_1.jsonl',ROOT/'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl']
ALLOWED={'candidate','supported_predictive','rejected','unresolved','not_testable','provisionally_supported_descriptive','rejected_by_current_maxstat_null','not_supported_by_current_cross_domain_null','weak_or_unresolved_cross_domain_signal','rejected_as_additive_node','rejected_as_additive_mediator','rejected_for_out_of_sample_degradation','rejected_as_additive_within_domain_edge'}
def main():
 admitted=[]; quarantined=[]; input_hashes={}
 for p in FILES:
  if not p.exists(): quarantined.append({'source_file':str(p.relative_to(ROOT)),'status':'not_testable','reason':'transition evidence file missing'}); continue
  input_hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
  for line in p.read_text().splitlines():
   if not line.strip():continue
   r=json.loads(line); errors=[]
   for k in ['transition_id','source_state','target_state','edge_status','causal_claim','source_refs','failure_cases']:
    if k not in r: errors.append('missing_'+k)
   if r.get('edge_status') not in ALLOWED: errors.append('unknown_status')
   if r.get('causal_claim') is True: errors.append('causal_claim_not_allowed')
   if not r.get('source_refs'): errors.append('missing_source_refs')
   if errors: quarantined.append({'record':r,'supervisor_errors':errors,'source_file':str(p.relative_to(ROOT))})
   elif r.get('edge_status')=='supported_predictive': admitted.append({'record':r,'supervisor_source_file':str(p.relative_to(ROOT))})
   else: quarantined.append({'record':r,'supervisor_reason':'status_not_eligible_for_positive_composition','source_file':str(p.relative_to(ROOT))})
 (OUT/'ADMITTED_SUPPORTED_TRANSITIONS_V1.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in admitted)+'\n' if admitted else '')
 (OUT/'QUARANTINED_TRANSITIONS_V1.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in quarantined)+'\n' if quarantined else '')
 summary={'gate_id':'CHAOS_SUPERVISOR_ADMISSION_GATE_V1','input_files':len(FILES),'admitted_supported_predictive_records':len(admitted),'quarantined_records':len(quarantined),'positive_composition_statuses':['supported_predictive'],'causal_claims_admitted':0,'missing_or_failed_inputs':sum(1 for x in quarantined if x.get('status')=='not_testable'),'input_hashes':input_hashes,'rules':{'rejected_positive_weight':False,'unresolved_positive_weight':False,'not_testable_positive_weight':False,'provisional_descriptive_positive_weight':False,'future_outcome_current_state':False},'status':'pass'}
 (OUT/'SUPERVISOR_GATE_DECISION_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
