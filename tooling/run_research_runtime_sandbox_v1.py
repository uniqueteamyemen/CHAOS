#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json,hashlib
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS');INP=ROOT/'experiments/macro_plus_eia_energy/domain_state_v1/DOMAIN_STATES_V1.jsonl';OUT=ROOT/'experiments/macro_plus_eia_energy/research_runtime_sandbox_v1';OUT.mkdir(parents=True,exist_ok=True)
def main():
 rows=[]
 for r in pd.read_json(INP,lines=True).to_dict('records'):
  if r['pattern_id']!='AMA_HIGH_GROWTH_STATE_V1' or r['state_label']!='high_growth_gt_4pp':continue
  aid=hashlib.sha256(f"{r['pattern_id']}|{r['entity_id']}|{r['timestamp']}".encode()).hexdigest()[:20]
  rows.append({'alert_id':aid,'pattern_id':r['pattern_id'],'domain':r['domain'],'entity_id':r['entity_id'],'entity_name':r['entity_name'],'timestamp':r['timestamp'],'native_frequency':r['native_frequency'],'state_label':r['state_label'],'observed_values':r['source_observations'],'uncertainty':r['uncertainty'],'evidence_refs':r['evidence_refs'],'runtime_status':'research_only'})
 df=pd.DataFrame(rows);df.to_json(OUT/'RESEARCH_ALERTS_V1.jsonl',orient='records',lines=True,force_ascii=False);df.to_csv(OUT/'RESEARCH_ALERTS_V1.csv',index=False);summary={'sandbox_id':'CHAOS_RESEARCH_RUNTIME_SANDBOX_V1','input':str(INP.relative_to(ROOT)),'alerts':len(df),'entities':int(df.entity_id.nunique()),'years':sorted(df.timestamp.unique().tolist()),'future_outcome_in_alert':False,'retraining':False,'threshold_update':False,'external_send':False,'market_intelligence_engine_modified':False,'status':'research_only','pattern_id':'AMA_HIGH_GROWTH_STATE_V1','pattern_status':'provisionally_supported_descriptive','source_observation_only':True}
 (OUT/'RESEARCH_RUNTIME_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
