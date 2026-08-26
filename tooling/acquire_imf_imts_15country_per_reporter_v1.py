#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,requests,time
ROOT=Path('/home/ubuntu/CHAOS'); RAW=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/raw/imf_imts_15_per_reporter'; RAW.mkdir(parents=True,exist_ok=True)
COUNTRIES=['USA','CHN','DEU','JPN','IND','GBR','FRA','ITA','CAN','KOR','BRA','MEX','SAU','TUR','ZAF']; INDICATORS=['XG_FOB_USD','MG_FOB_USD']; SUMMARY=[]
for country in COUNTRIES:
 key=f'{country}.'+'+'.join(INDICATORS)+'.*.A'; url='https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IMTS/1.0.0/'+key+'?c[TIME_PERIOD]=ge:2000-01-01%2Ble:2024-12-31&attributes=all&detail=full&includeHistory=true&limit=5000'; now=datetime.now(timezone.utc).isoformat();
 try:
  r=requests.get(url,timeout=300,headers={'User-Agent':'CHAOS-research-acquisition/1.0','Accept':'application/vnd.sdmx.data+csv;version=2.0'}); b=r.content
  p=RAW/f'IMF_IMTS_{country}_XG_MG_ALL_PARTNERS_2000_2024.csv'; p.write_bytes(b); sha=hashlib.sha256(b).hexdigest(); (RAW/f'{country}.url.txt').write_text(url+'\n'); (RAW/f'{country}.headers.json').write_text(json.dumps({'status_code':r.status_code,'content_type':r.headers.get('content-type'),'content_length':r.headers.get('content-length'),'retrieved_at_utc':now,'url':r.url},ensure_ascii=False,indent=2)+'\n'); SUMMARY.append({'country':country,'status_code':r.status_code,'bytes':len(b),'sha256':sha,'raw_path':str(p.relative_to(ROOT)),'lines':b.count(b'\n'),'status':'downloaded_response' if r.ok else 'endpoint_error'})
 except Exception as e: SUMMARY.append({'country':country,'status':'request_error','error':repr(e)}); print(json.dumps(SUMMARY[-1],ensure_ascii=False),flush=True)
 print(json.dumps(SUMMARY[-1],ensure_ascii=False),flush=True)
 time.sleep(0.5)
result={'source_id':'IMF.STA:IMTS','official_dataset_url':'https://data.imf.org/en/datasets/IMF.STA:IMTS','retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'countries':COUNTRIES,'indicators':INDICATORS,'frequency':'A','period':'2000-2024','counterpart_country':'*','limit':5000,'responses':SUMMARY,'status':'per_reporter_bounded_acquisition_complete'}; (ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_15_PER_REPORTER_ACQUISITION_SUMMARY_V1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2))
