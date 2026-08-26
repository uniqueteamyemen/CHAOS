#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,requests
ROOT=Path('/home/ubuntu/CHAOS'); RAW=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/raw/oecd_pmr_2013'; RAW.mkdir(parents=True,exist_ok=True)
URL='https://sdmx.oecd.org/archive/rest/data/OECD,DF_PMR,/all?dimensionAtObservation=AllDimensions&format=csvfilewithlabels'
def main():
 out=RAW/'OECD_DF_PMR_UNFILTERED.csv'; req=RAW/'OECD_DF_PMR_UNFILTERED.request.txt'; headers=RAW/'OECD_DF_PMR_UNFILTERED.headers.json'; now=datetime.now(timezone.utc).isoformat(); r=requests.get(URL,timeout=120,headers={'User-Agent':'CHAOS-research-acquisition/1.0'}); r.raise_for_status(); out.write_bytes(r.content); req.write_text(URL+'\n'); headers.write_text(json.dumps({'status_code':r.status_code,'content_type':r.headers.get('content-type'),'content_length_header':r.headers.get('content-length'),'retrieved_at_utc':now,'url':URL},indent=2)+'\n'); sha=hashlib.sha256(r.content).hexdigest(); (RAW/'OECD_DF_PMR_UNFILTERED.csv.sha256').write_text(f'{sha}  {out.name}\n'); summary={'source_id':'OECD_DF_PMR_ARCHIVE_V1','official_url':URL,'retrieved_at_utc':now,'status_code':r.status_code,'bytes':len(r.content),'sha256':sha,'raw_path':str(out.relative_to(ROOT)),'raw_immutable':True,'transformed':False,'imputed':False,'status':'downloaded_official_sdmx'}; (ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_ACQUISITION_SUMMARY_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
