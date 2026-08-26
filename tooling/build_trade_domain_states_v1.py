#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); Q=ROOT/'campaigns/agents/trade_v1/raw/comtrade_queries'; OUT=ROOT/'campaigns/agents/trade_v1'; OUT.mkdir(parents=True,exist_ok=True)
def main():
 rows=[]; success=0; failures=[]
 for sf in sorted(Q.glob('*.http_status.txt')):
  status=sf.read_text().strip(); base=sf.with_suffix('').with_suffix(''); jf=Path(str(base)+'.json'); req=Path(str(base)+'.request.txt')
  if status!='200': failures.append({'request':str(req.relative_to(ROOT)),'status':status}); continue
  success+=1
  try: payload=json.loads(jf.read_text())
  except Exception as e: failures.append({'request':str(req.relative_to(ROOT)),'status':'invalid_json','error':str(e)}); continue
  for r in payload.get('data',[]):
   rows.append({'pattern_id':'COMTRADE_TRADE_IMPORT_REPORTED_TOTAL_PARTNER_V1','domain':'trade','entity_id':str(r.get('reporterCode')),'entity_name':r.get('reporterDesc') or str(r.get('reporterCode')),'timestamp':int(r.get('refYear')),'native_frequency':'annual','state_label':'trade_import_reported_total_partner','state_probability':None,'source_observations':{'reporterCode':r.get('reporterCode'),'period':r.get('period'),'flowCode':r.get('flowCode'),'partnerCode':r.get('partnerCode'),'cmdCode':r.get('cmdCode'),'primaryValue_raw':r.get('primaryValue'),'qty_raw':r.get('qty'),'netWgt_raw':r.get('netWgt'),'isReported':r.get('isReported'),'isAggregate':r.get('isAggregate')},'lead_profile':{},'uncertainty':['bounded preview query','reporter and partner descriptions may be absent in preview response'],'failure_cases':['no trade disruption inferred','no percentage change or smoothing computed','missing years remain missing'],'edge_status':'not_testable','evidence_refs':[str(jf.relative_to(ROOT)),str(req.relative_to(ROOT))]})
 with (OUT/'TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl').open('w',encoding='utf8') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 df=pd.DataFrame(rows); summary={'adapter_id':'TRADE_COMTRADE_BOUNDED_PREVIEW_ADAPTER_V1','query_directory':str(Q.relative_to(ROOT)),'http_200_requests':success,'http_non_200_requests':len(failures),'records':len(rows),'reporters':int(df.entity_id.nunique()) if len(df) else 0,'years':sorted(df.timestamp.unique().tolist()) if len(df) else [],'native_frequency':'annual','trade_disruption_states':0,'transition_evidence_status':'not_testable_insufficient_multidimensional_coverage','raw_modified':False,'imputation':False,'source_aggregation':False,'failures':failures,'causal_claims_permitted':False}; (OUT/'TRADE_ADAPTER_RUN_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); (OUT/'TRADE_TRANSITION_EVIDENCE_V1.jsonl').write_text(json.dumps({'transition_id':'COMTRADE_TRADE_REPORTED_TO_TRADE_DISRUPTION_V1','source_state':'trade_import_reported_total_partner','target_state':'trade_disruption','lag':{'value':None,'unit':'not_defined','direction':'not_testable'},'split':'not_run','metric':None,'null_method':None,'p_value':None,'edge_status':'not_testable','causal_claim':False,'source_refs':['TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl'],'failure_cases':['preview data is sparse and single total-flow concept','commodity/partner network is not sufficiently covered','one request timed out','no disruption definition contract executed']},ensure_ascii=False)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
