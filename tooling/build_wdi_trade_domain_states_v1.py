#!/usr/bin/env python3
from pathlib import Path
import json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); SRC=ROOT/'campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv'; OUT=ROOT/'campaigns/agents/trade_v1'
def main():
 d=pd.read_csv(SRC); rows=[]
 for _,r in d.iterrows():
  rows.append({'pattern_id':f"WDI_TRADE_MEASUREMENT_{r['Indicator Code']}_V1",'domain':'trade','entity_id':r['Country Code'],'entity_name':r['Country Name'],'timestamp':int(r['year']),'native_frequency':'annual','state_label':'trade_measurement_observed','state_probability':None,'source_observations':{'indicator_id':r['Indicator Code'],'indicator_name':r['Indicator Name'],'value_raw':float(r['value_raw'])},'lead_profile':{},'uncertainty':['WDI source-defined indicator','missing years remain missing','trade values and shares are not reconciled across indicators'],'failure_cases':['no disruption inferred','no partner or commodity network inferred from aggregate indicator'],'edge_status':'not_testable','evidence_refs':['WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv','WDI_CSV.zip/WDICSV.csv']})
 out=OUT/'WDI_TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl'
 with out.open('w',encoding='utf8') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
 summary={'adapter_id':'WDI_TRADE_DOMAIN_STATE_ADAPTER_V1','input':str(SRC.relative_to(ROOT)),'records':len(rows),'entities':int(d['Country Code'].nunique()),'years':sorted(d.year.unique().tolist()),'indicators':sorted(d['Indicator Code'].unique().tolist()),'native_frequency':'annual','raw_modified':False,'imputation':False,'source_averaging':False,'status':'ready_for_within_domain_edge_contract'}
 (OUT/'WDI_TRADE_DOMAIN_ADAPTER_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
