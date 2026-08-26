#!/usr/bin/env python3
from pathlib import Path
import json,pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); OUT=ROOT/'experiments/parallel_execution_qa'; OUT.mkdir(parents=True,exist_ok=True)
def main():
 w=pd.read_csv(ROOT/'experiments/macro_plus_eia_energy/within_domain_edges_v1/WITHIN_DOMAIN_EDGE_METRICS.csv'); w=w[w.edge_id!='high_growth_gt_4_existing_baseline']; c=pd.read_csv(ROOT/'experiments/multi_domain_native_edges_v1/ECONOMIC_DETERIORATION_TO_CONFLICT_METRICS.csv'); rows=[]
 for edge,g in w.groupby('edge_id'):
  o=g[g.split.isin(['validation','confirmation'])]; rows.append({'edge_id':edge,'kind':'within_domain','max_ba_all_splits':float(g.balanced_accuracy.max()),'validation_ba_min':float(o[o.split=='validation'].balanced_accuracy.min()),'confirmation_ba_min':float(o[o.split=='confirmation'].balanced_accuracy.min()),'oos_ba_all_ge_0_5':bool((o.balanced_accuracy>=0.5).all()),'null_p':0.30134932533733133,'decision':'rejected_by_maxstat_null_and_no_baseline_addition'})
 o=c[c.split.isin(['validation','confirmation'])]; rows.append({'edge_id':'economic_deterioration_to_conflict','kind':'cross_domain','max_ba_all_splits':float(c.balanced_accuracy.max()),'validation_ba_min':float(o[o.split=='validation'].balanced_accuracy.min()),'confirmation_ba_min':float(o[o.split=='confirmation'].balanced_accuracy.min()),'oos_ba_all_ge_0_5':bool((o.balanced_accuracy>=0.5).all()),'null_p':0.45327336331834084,'decision':'rejected_by_maxstat_null'})
 out={'evaluation_id':'CHAOS_NEW_EDGES_OOS_NULL_STABILITY_V1','rows':rows,'rules':{'null_gate_required':True,'oos_stability_required':True,'baseline_addition_required':True,'causal_claims_permitted':False},'status':'research_evidence_only'}; (OUT/'NEW_EDGES_OOS_NULL_STABILITY_V1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
