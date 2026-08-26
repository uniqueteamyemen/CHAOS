#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
ROOT=Path('/home/ubuntu/CHAOS'); D=ROOT/'campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_EDGE_DECISION_V1.json'; MET=ROOT/'campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_EDGE_METRICS.csv'; REG=ROOT/'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'; OUT=ROOT/'campaigns/agents/institutions_policy_v1/WGI_TRANSITION_EVIDENCE_V1.jsonl'
def main():
 dec=json.loads(D.read_text()); records=[]
 for r in dec['rows']:
  status='rejected' if r['decision'].startswith('rejected') else 'not_testable'
  pid=f"WGI_{r['dimension']}_{r['edge_id']}_V1"; records.append({'transition_id':pid,'source_state':r['edge_id']+'_source','target_state':r['edge_id']+'_target','lag':{'values':[1,2],'unit':'source_observation_steps','direction':'forward'},'split':'validation_confirmation','metric':{'max_oos_ba_excess_over_trivial':r['max_oos_ba_excess_over_trivial'],'valid_oos_rows':r['valid_oos_rows'],'degenerate_rows':r['degenerate_rows']},'null_method':'within-entity label permutation; 2000 reps; max-stat across dimensions/edges/leads/splits','p_value':None,'entity_holdout':False,'source_refs':['WGI_INSTITUTIONAL_EDGE_METRICS.csv','WGI_INSTITUTIONAL_EDGE_MAXSTAT_NULL_SUMMARY.json'],'edge_status':status,'causal_claim':False,'failure_cases':[r['decision'],'WGI estimate is composite perception-based measurement','no policy shock or leader deviation inferred']})
 OUT.write_text('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in records)+'\n')
 old=[json.loads(x) for x in REG.read_text().splitlines() if x.strip()]
 for x in records:
  if any(y['pattern_id']==x['transition_id'] for y in old): continue
  reg={'pattern_id':x['transition_id'],'status':x['edge_status'],'statement':f"WGI {x['source_state']} to {x['target_state']}",'evidence':{'transition_artifact':str(OUT.relative_to(ROOT)),'decision_artifact':str(D.relative_to(ROOT)),'metrics_artifact':str(MET.relative_to(ROOT))},'causal_claim':False,'operational_promotion':False,'interpretation':x['failure_cases']}
  with REG.open('a',encoding='utf8') as f:f.write(json.dumps(reg,ensure_ascii=False)+'\n')
 summary={'registered':len(records),'status_counts':{},'positive_composer_edges':0,'source_sha256':hashlib.sha256(D.read_bytes()).hexdigest()}
 for x in records:summary['status_counts'][x['edge_status']]=summary['status_counts'].get(x['edge_status'],0)+1
 (ROOT/'campaigns/agents/institutions_policy_v1/WGI_REGISTRATION_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
