#!/usr/bin/env python3
from pathlib import Path
from collections import Counter,defaultdict
import csv,json,hashlib
ROOT=Path('/home/ubuntu/CHAOS'); RAW=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/raw/imf_imts_15_per_reporter'; OUT=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v1'; OUT.mkdir(parents=True,exist_ok=True)
def main():
 rows=[]; source_files=[]; failures=[]
 for p in sorted(RAW.glob('IMF_IMTS_*_XG_MG_ALL_PARTNERS_2000_2024.csv')):
  source_files.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
  try:
   with p.open(newline='',encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
     if not r.get('TIME_PERIOD') or not r.get('OBS_VALUE'): continue
     reporter=r.get('COUNTRY',''); ind=r.get('INDICATOR',''); partner=r.get('COUNTERPART_COUNTRY',''); year=r.get('TIME_PERIOD')
     if not reporter or not ind or not partner or not year: continue
     rows.append({'pattern_id':'IMF_IMTS_SOURCE_OBSERVATION_STATE_V1','domain':'trade','entity_id':reporter,'entity_name':reporter,'timestamp':int(float(year)),'native_frequency':'annual','state_label':'trade_exports_goods_fob_usd' if ind=='XG_FOB_USD' else 'trade_imports_goods_fob_usd','state_probability':None,'source_observations':{'country':reporter,'indicator':ind,'counterpart_country':partner,'frequency':r.get('FREQUENCY'),'time_period':r.get('TIME_PERIOD'),'obs_value_raw':r.get('OBS_VALUE'),'scale_raw':r.get('SCALE'),'precision_raw':r.get('PRECISION'),'decimals_displayed_raw':r.get('DECIMALS_DISPLAYED'),'trade_flow':r.get('TRADE_FLOW'),'valuation':r.get('VALUATION'),'unit':r.get('UNIT'),'derivation_type':r.get('DERIVATION_TYPE'),'overlap':r.get('OVERLAP'),'status':r.get('STATUS')},'lead_profile':{},'uncertainty':['bounded 15-reporter extract','counterpart coverage is query/limit bounded','source metadata may include historical revisions'],'failure_cases':['no imputation','no normalization','no partner reconciliation','no trade disruption or causal shock inferred'],'edge_status':'not_testable','evidence_refs':[str(p.relative_to(ROOT)),'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_15_PER_REPORTER_ACQUISITION_SUMMARY_V1.json']})
  except Exception as e: failures.append({'path':str(p.relative_to(ROOT)),'error':repr(e)})
 out_jsonl=OUT/'IMF_IMTS_DOMAIN_STATES_ANNUAL_V1.jsonl'; out_csv=OUT/'IMF_IMTS_OBSERVED_RECORDS_2000_2024.csv'
 with out_jsonl.open('w',encoding='utf8') as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 fields=['country','indicator','counterpart_country','frequency','time_period','obs_value_raw','scale_raw','trade_flow','valuation','unit']
 with out_csv.open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
  for r in rows:
   o=r['source_observations']; w.writerow({k:o.get({'country':'country','indicator':'indicator','counterpart_country':'counterpart_country','frequency':'frequency','time_period':'time_period','obs_value_raw':'obs_value_raw','scale_raw':'scale_raw','trade_flow':'trade_flow','valuation':'valuation','unit':'unit'}[k]) for k in fields})
 counts=Counter((r['entity_id'],r['source_observations']['indicator']) for r in rows); years=defaultdict(set); partners=defaultdict(set)
 for r in rows: years[(r['entity_id'],r['source_observations']['indicator'])].add(r['timestamp']); partners[(r['entity_id'],r['source_observations']['indicator'])].add(r['source_observations']['counterpart_country'])
 summary={'adapter_id':'IMF_IMTS_SOURCE_NATIVE_ADAPTER_V1','source_id':'IMF.STA:IMTS','records':len(rows),'reporters':len(set(r['entity_id'] for r in rows)),'reporter_ids':sorted(set(r['entity_id'] for r in rows)),'indicators':sorted(set(r['source_observations']['indicator'] for r in rows)),'native_frequency':'annual','years':sorted(set(r['timestamp'] for r in rows)),'counterpart_countries':len(set(r['source_observations']['counterpart_country'] for r in rows)),'complete_2000_2024_reporter_indicator_series':sum(1 for k,v in years.items() if len(v)==25),'series_count':len(counts),'series_profile':{f'{k[0]}|{k[1]}':{'rows':counts[k],'years':sorted(years[k]),'counterparts':len(partners[k])} for k in sorted(counts)},'source_files':source_files,'failures':failures,'raw_modified':False,'imputation':False,'normalization':False,'source_averaging':False,'frequency_conversion':False,'edge_status':'not_testable_until_trade_edge_contract','causal_claims_permitted':False}; (OUT/'IMF_IMTS_ADAPTER_RUN_SUMMARY_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({k:v for k,v in summary.items() if k not in ['series_profile','source_files']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
