#!/usr/bin/env python3
from pathlib import Path
import json,pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); SRC=ROOT/'campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_EDGE_METRICS.csv'; OUT=ROOT/'campaigns/agents/institutions_policy_v1'
def main():
 d=pd.read_csv(SRC); d['positive_n']=d.prevalence*d.n; d['negative_n']=(1-d.prevalence)*d.n; d['support_valid']=(d.positive_n>=10)&(d.negative_n>=10); d['ba_excess_over_trivial']=d.balanced_accuracy-0.5
 rows=[]
 for (dim,edge),g in d.groupby(['dimension','edge_id']):
  o=g[g.split.isin(['validation','confirmation'])]; valid=o[o.support_valid]; degenerate=int((~g.support_valid).sum()); max_excess=float(valid.ba_excess_over_trivial.max()) if len(valid) else None
  if edge=='institutional_decline_persistence' and (len(valid)<2 or degenerate>0): decision='not_testable_due_rare_target_or_split_support'
  elif edge=='institutional_continuity_persistence' and (max_excess is None or max_excess<0.10): decision='rejected_as_trivial_prevalence_persistence'
  else: decision='candidate_requires_independent_replication'
  rows.append({'dimension':dim,'edge_id':edge,'validation_confirmation_rows':int(len(o)),'valid_oos_rows':int(len(valid)),'degenerate_rows':degenerate,'max_oos_ba_excess_over_trivial':max_excess,'decision':decision})
 out={'evaluation_id':'CHAOS_WGI_EDGE_SUPPORT_GATE_V1','support_rule':'at least 10 positive and 10 negative targets per split','trivial_ba_reference':0.5,'rows':rows,'null_summary_reference':'WGI_INSTITUTIONAL_EDGE_MAXSTAT_NULL_SUMMARY.json','interpretation':'The raw WGI max-stat result is not promoted when the observed maximum is driven by degenerate target support or trivial prevalence persistence.','causal_claims_permitted':False,'positive_composer_edges':0,'status':'research_evidence_only'}; (OUT/'WGI_INSTITUTIONAL_EDGE_DECISION_V1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
