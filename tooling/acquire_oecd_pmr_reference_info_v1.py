#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,requests
ROOT=Path('/home/ubuntu/CHAOS'); RAW=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/raw/oecd_pmr_2013'; URL='https://sdmx.oecd.org/archive/rest/v2/data/dataflow/OECD/DF_PMR/~/?attributes=msd&measures=none&dimensionAtObservation=AllDimensions&format=csvfilewithlabels'
def main():
 p=RAW/'OECD_DF_PMR_REFERENCE_INFO.csv'; r=requests.get(URL,timeout=120,headers={'User-Agent':'CHAOS-research-acquisition/1.0'}); r.raise_for_status(); p.write_bytes(r.content); s=hashlib.sha256(r.content).hexdigest(); (RAW/'OECD_DF_PMR_REFERENCE_INFO.csv.sha256').write_text(f'{s}  {p.name}\n'); summary={'source_id':'OECD_DF_PMR_REFERENCE_INFO_V1','official_url':URL,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'status_code':r.status_code,'bytes':len(r.content),'sha256':s,'raw_path':str(p.relative_to(ROOT)),'raw_immutable':True,'status':'downloaded_official_reference_info'}; (ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_REFERENCE_INFO_SUMMARY_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
