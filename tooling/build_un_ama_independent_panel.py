#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS');RAW=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/raw';OUT=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/staged';OUT.mkdir(parents=True,exist_ok=True)
G=RAW/'AMA_GDP_GROWTH_ALL_COUNTRIES_RAW.xlsx';P=RAW/'AMA_EXCHANGE_RATES_POPULATION_ALL_COUNTRIES_RAW.xlsx'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def read_ama(p):
 raw=pd.read_excel(p,sheet_name=0,header=None)
 header=raw.iloc[2].tolist(); df=raw.iloc[3:].copy(); df.columns=header; df=df.rename(columns={c:str(c).replace('.0','') for c in df.columns}); return df

def main():
 g=read_ama(G);p=read_ama(P)
 indicators=sorted(g['IndicatorName'].dropna().astype(str).unique().tolist());pd.DataFrame({'IndicatorName':indicators}).to_csv(OUT/'AMA_GROWTH_INDICATOR_CATALOG.csv',index=False)
 # First exact/near matches, printed before strict extraction.
 print('growth indicator matches:',[x for x in indicators if 'gross domestic product' in x.lower()][:20])
 print('population columns:',p.columns.tolist()[:12])
 # The population workbook uses IndicatorName or Item; inspect columns and rows.
 pop_col='Measure' if 'Measure' in p.columns else ('IndicatorName' if 'IndicatorName' in p.columns else ('Item' if 'Item' in p.columns else None))
 if pop_col: print('population indicator matches:',p[pop_col].dropna().astype(str).unique()[:20].tolist())
 growth_rows=g[g['IndicatorName'].astype(str).str.strip().str.lower().eq('gross domestic product (gdp)')].copy()
 if len(growth_rows)==0: raise SystemExit('GDP row not found')
 # Population file structure is inspected; select population row by indicator/item text.
 if pop_col is None: raise SystemExit('population indicator column not found')
 pop_rows=p[p[pop_col].astype(str).str.strip().str.lower().eq('population')].copy()
 if len(pop_rows)==0:
  pop_rows=p[p[pop_col].astype(str).str.contains('population',case=False,na=False)].copy()
  pop_rows=pop_rows[pop_rows[pop_col].astype(str).str.lower().str.fullmatch('population',na=False)]
 if len(pop_rows)==0: raise SystemExit('Population row not found')
 years=[str(y) for y in range(1971,2025) if str(y) in g.columns]
 long_g=growth_rows[['CountryID','Country','IndicatorName']+years].melt(id_vars=['CountryID','Country','IndicatorName'],var_name='year',value_name='ama_gdp_growth_pct')
 p_years=[str(y) for y in range(1970,2025) if str(y) in p.columns]
 idcols=[c for c in ['CountryID','Country',pop_col] if c in p.columns]
 long_p=pop_rows[idcols+p_years].melt(id_vars=idcols,var_name='year',value_name='ama_population')
 long_p=long_p.rename(columns={pop_col:'PopulationIndicator'})
 panel=long_g.merge(long_p,on=['CountryID','Country','year'],how='outer');panel['year']=pd.to_numeric(panel['year'],errors='coerce').astype('Int64');panel=panel.sort_values(['CountryID','year']).reset_index(drop=True)
 panel.to_csv(OUT/'UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv',index=False)
 meta={'source':'UN Statistics Division National Accounts Main Aggregates','upload_date':'January 2026','growth_file':str(G.relative_to(ROOT)),'population_file':str(P.relative_to(ROOT)),'growth_file_sha256':sha(G),'population_file_sha256':sha(P),'growth_indicator':'Gross domestic product','population_indicator':'Population','native_frequency':'annual','years':{'growth':[int(panel.year.min()),int(panel.year.max())],'panel':[int(panel.year.min()),int(panel.year.max())]},'rows':len(panel),'countries':int(panel.CountryID.nunique()),'columns':panel.columns.tolist(),'selection':'exact indicator rows; no imputation, normalization, reconciliation, or source averaging','staging_is_derived':True}
 (OUT/'UN_AMA_PANEL_PROVENANCE.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n');print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
