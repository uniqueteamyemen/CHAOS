#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,requests
ROOT=Path('/home/ubuntu/CHAOS'); RAW=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/raw/imf_imts_query_variants'; RAW.mkdir(parents=True,exist_ok=True)
BASE='https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IMTS/1.0.0/USA.XG_FOB_USD.*.A'
QS=[('dates_full_encoded_plus', '?c[TIME_PERIOD]=ge:2000-01-01%2Ble:2024-12-31&attributes=all&detail=full&includeHistory=true&limit=100'),('dates_dataonly_encoded_plus','?c[TIME_PERIOD]=ge:2000-01-01%2Ble:2024-12-31&attributes=all&detail=dataonly&limit=100'),('start_end_params','?startPeriod=2000-01-01&endPeriod=2024-12-31&attributes=all&detail=full&limit=100')]
def main():
 allsum=[]
 for name,qs in QS:
  url=BASE+qs; now=datetime.now(timezone.utc).isoformat(); r=requests.get(url,timeout=180,headers={'User-Agent':'CHAOS-research-acquisition/1.0','Accept':'application/vnd.sdmx.data+csv;version=2.0'}); b=r.content; p=RAW/f'{name}.csv'; p.write_bytes(b); sha=hashlib.sha256(b).hexdigest(); (RAW/f'{name}.url.txt').write_text(url+'\n'); summary={'name':name,'url':url,'retrieved_at_utc':now,'status_code':r.status_code,'content_type':r.headers.get('content-type'),'bytes':len(b),'sha256':sha,'raw_path':str(p.relative_to(ROOT)),'lines':b.count(b'\n'),'status':'downloaded_response' if r.ok else 'endpoint_error'}; (RAW/f'{name}.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); allsum.append(summary)
 print(json.dumps(allsum,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
