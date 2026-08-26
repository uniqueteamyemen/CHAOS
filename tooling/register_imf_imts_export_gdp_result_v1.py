#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path('/home/ubuntu/CHAOS'); REG=ROOT/'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'; SUM=ROOT/'experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPORT_TO_GDP_NULL_SUMMARY_V1.json'; EVID=ROOT/'experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPORT_TO_GDP_TRANSITION_EVIDENCE_V1.jsonl'
def main():
 s=json.loads(SUM.read_text()); e=json.loads(EVID.read_text()); r={'pattern_id':'IMF_IMTS_EXPORT_CONTRACTION_TO_GDP_V1','status':e['edge_status'],'statement':'IMF IMTS raw reporter-to-world export contraction precedes material GDP deterioration','evidence':{'artifact':str(SUM.relative_to(ROOT)),'confirmation_max_risk_difference':s['observed_confirmation_max_risk_difference'],'null_p_value':s['p_value'],'validation_selected_horizon_risk_difference':s['validation_at_selected_horizon'],'coverage_pass':s['minimum_coverage_pass']},'causal_claim':False,'operational_promotion':False,'interpretation':'confirmation risk difference is negative and null p is near one; no positive predictive support; source-separated trade edge remains research-only'}
 ids={json.loads(x)['pattern_id'] for x in REG.read_text().splitlines() if x.strip()}
 if r['pattern_id'] not in ids: REG.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False)+'\n'); print('appended',r['pattern_id'])
 else: print('already_present',r['pattern_id'])
if __name__=='__main__':main()
