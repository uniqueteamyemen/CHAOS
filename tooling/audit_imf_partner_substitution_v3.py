#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); d=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3'; metrics=pd.read_csv(d/'IMF_IMTS_PARTNER_SUBSTITUTION_METRICS_V3.csv'); events=pd.read_csv(d/'IMF_IMTS_PARTNER_SUBSTITUTION_EVENTS_V3.csv'); s=json.loads((d/'IMF_IMTS_PARTNER_SUBSTITUTION_SUMMARY_V3.json').read_text())
checks=[]
for split in ['fit','confirmation']:
 m=metrics[(metrics.split==split)&(metrics.variant=='primary_top1_displacement')]
 for _,r in m.iterrows():
  e=events[(events.split==split)&(events.horizon==r.horizon)&events.eligible_for_horizon]
  counts=e.groupby('reporter_id').size(); max_share=float(counts.max()/len(e)) if len(e) else None
  leave=[]
  for rid in counts.index:
   x=e[e.reporter_id!=rid]; leave.append({'reporter_id':rid,'rate':float((x.replacement.notna()).sum()/len(x)) if len(x) else None})
  checks.append({'split':split,'horizon':int(r.horizon),'events':int(r.events),'reporters':int(r.reporters_with_events),'persistence_rate':float(r.persistence_rate),'max_event_share':max_share,'top_reporter':str(counts.idxmax()) if len(counts) else None,'top_reporter_events':int(counts.max()) if len(counts) else 0,'leave_one_reporter_count':len(leave)})
# Contract adequacy review is separate from observed performance.
audit={'audit_id':'IMF_IMTS_PARTNER_SUBSTITUTION_V3_ELIGIBILITY_AUDIT','contract_ref':'experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3.json','summary_ref':'experiments/dual_track_v02/imf_partner_substitution_v3/IMF_IMTS_PARTNER_SUBSTITUTION_SUMMARY_V3.json','stability_ref':'experiments/dual_track_v02/imf_partner_substitution_v3/IMF_IMTS_PARTNER_SUBSTITUTION_STABILITY_SUMMARY_V3.json','checks':checks,'contract_adequacy':{'explicit_alpha_in_frozen_contract':False,'explicit_fdr_rule_for_this_family':False,'explicit_persistence_null_pass_rule':False,'causal_assignment_defined':False,'decision':'do_not_promote_until a new frozen contract or erratum pre-registers these rules; do not rewrite V3 contract.'},'observed_interpretation':{'fit_confirmation_direction_consistent':True,'confirmation_identity_null_non_degenerate':True,'time_placebo_recorded':True,'causal_claim':False,'causal_validation_status':'not_run','predictive_evidence_status':'candidate','runtime_status':'not_eligible'},'decision':'candidate_promising_but_not_admitted','reason':'The locked confirmation persistence contrast is positive and stable across seeds, but the frozen contract omitted explicit alpha/FDR/pass rules and the null tests primarily challenge identity order rather than a full temporal network model. Record as a promising descriptive/predictive candidate and require a new frozen contract before support admission or CVT.'}
(d/'IMF_IMTS_PARTNER_SUBSTITUTION_ELIGIBILITY_AUDIT_V3.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'decision':audit['decision'],'checks':len(checks)},ensure_ascii=False,indent=2))
