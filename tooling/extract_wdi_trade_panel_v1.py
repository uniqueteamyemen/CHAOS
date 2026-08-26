#!/usr/bin/env python3
from pathlib import Path
import hashlib,zipfile,json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); SRC=Path('/home/ubuntu/market_intelligence_workspace/catalog_first/raw/worldbank/wdi/WDI_CSV.zip'); OUT=ROOT/'campaigns/agents/trade_v1'; OUT.mkdir(parents=True,exist_ok=True)
CODES=['NE.TRD.GNFS.ZS','NE.EXP.GNFS.ZS','NE.IMP.GNFS.ZS','TX.VAL.MRCH.CD.WT','TM.VAL.MRCH.CD.WT']
def main():
 if not SRC.exists(): raise SystemExit(f'missing external WDI bulk: {SRC}')
 with zipfile.ZipFile(SRC) as zf:
  with zf.open('WDISeries.csv') as f: meta=pd.read_csv(f)
  with zf.open('WDICSV.csv') as f: wide=pd.read_csv(f)
 meta=meta[meta['Series Code'].isin(CODES)].copy(); years=[str(y) for y in range(2000,2025) if str(y) in wide.columns]; wide=wide[wide['Indicator Code'].isin(CODES)][['Country Name','Country Code','Indicator Name','Indicator Code']+years]
 long=wide.melt(id_vars=['Country Name','Country Code','Indicator Name','Indicator Code'],var_name='year',value_name='value_raw'); long['year']=long.year.astype(int); long['value_raw']=pd.to_numeric(long.value_raw,errors='coerce'); long=long.dropna(subset=['value_raw']).sort_values(['Country Code','Indicator Code','year'])
 long.to_csv(OUT/'WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv',index=False)
 summary={'extract_id':'WDI_TRADE_EXTRACT_V1','external_raw_path':str(SRC),'external_raw_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'indicator_codes':CODES,'metadata_rows':int(len(meta)),'observed_rows':int(len(long)),'entities':int(long['Country Code'].nunique()),'years':sorted(long.year.unique().tolist()),'frequency':'annual','raw_copied_to_chaos':False,'transformations':False,'imputation':False,'source_averaging':False,'provenance_ref':'WDI_CSV.zip/WDICSV.csv + WDISeries.csv','status':'ready_for_trade_domain_states'}
 (OUT/'WDI_TRADE_EXTRACT_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); meta.to_csv(OUT/'WDI_TRADE_SELECTED_SERIES_METADATA.csv',index=False); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
