#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path('/home/ubuntu/CHAOS'); REG=ROOT/'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'; SUM=ROOT/'experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_STABILITY_NULL_SENSITIVITY_V1_1.json'
def main():
 s=json.loads(SUM.read_text()); r={'pattern_id':'OECD_PMR_WITHIN_DOMAIN_DIRECTIONAL_CONCENTRATION_DEPENDENCY_AWARE_V1_1','status':'rejected','statement':'PMR source-wave directional concentration as a dependency-aware within-domain pattern','evidence':{'artifact':str(SUM.relative_to(ROOT)),'observed_max_stat':s['observed_max_stat'],'common_wave_exact_p_value':s['common_wave_exact_p_value'],'cluster_bootstrap_q025':s['cluster_bootstrap_max_q025'],'cluster_bootstrap_q975':s['cluster_bootstrap_max_q975']},'causal_claim':False,'operational_promotion':False,'interpretation':'common-wave permutation null is not exceeded (p=1.0); cluster bootstrap includes observed statistic; four waves do not support OOS promotion'}
 ids={json.loads(x)['pattern_id'] for x in REG.read_text().splitlines() if x.strip()}
 if r['pattern_id'] not in ids: REG.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False)+'\n'); print('appended',r['pattern_id'])
 else: print('already_present',r['pattern_id'])
if __name__=='__main__': main()
