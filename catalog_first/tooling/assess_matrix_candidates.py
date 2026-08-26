from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

ROOT=Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE=ROOT/'readiness_gate'
panel=pd.read_csv(GATE/'ANNUAL_PANEL_RAW_WDI_IMF_2000_2024.csv')
sets={
 'core_economic_social': [
   'wdi__NY.GDP.MKTP.KD.ZG','wdi__FP.CPI.TOTL.ZG','wdi__SL.UEM.TOTL.ZS','wdi__SP.POP.TOTL',
   'imf__NGDP_RPCH','imf__PCPI','imf__BCA_NGDPD','imf__GGXWDG_NGDP'
 ],
 'core_plus_trade': [
   'wdi__NY.GDP.MKTP.KD.ZG','wdi__FP.CPI.TOTL.ZG','wdi__SL.UEM.TOTL.ZS','wdi__SP.POP.TOTL',
   'wdi__NE.EXP.GNFS.KD.ZG','wdi__NE.IMP.GNFS.KD.ZG','imf__NGDP_RPCH','imf__PCPI','imf__TM_RPCH','imf__TX_RPCH'
 ],
 'macro_with_levels': [
   'wdi__NY.GDP.MKTP.KD.ZG','wdi__NY.GDP.PCAP.KD','wdi__FP.CPI.TOTL.ZG','wdi__SP.POP.TOTL','wdi__PA.NUS.PPP',
   'imf__NGDP_RPCH','imf__PCPI','imf__PPPEX','imf__BCA_NGDPD'
 ],
}
result={}
for name, cols in sets.items():
  subset=panel[['entity_code','year']+cols].copy()
  missing=subset[cols].isna()
  full=(~missing.any(axis=1)).groupby(subset['entity_code']).all()
  entity_any=(~missing.all(axis=1)).groupby(subset['entity_code']).any()
  expected=len(subset)*len(cols)
  observed=int(subset[cols].notna().sum().sum())
  missing_cells=expected-observed
  result[name]={
   'variables':cols,'variable_count':len(cols),'entity_count':int(panel['entity_code'].nunique()),'rows':len(subset),
   'expected_value_cells':expected,'observed_value_cells':observed,'missing_value_cells':missing_cells,
   'cell_coverage_ratio':round(observed/expected,6),'entities_with_any_value':int(entity_any.sum()),
   'entities_complete_all_selected_variables_for_all_25_years':int(full.sum()),
   'complete_entity_codes':sorted(full[full].index.tolist()),
   'strict_complete_rows':int(full.sum()*25),
   'no_transformations_or_imputation':True,
  }
(GATE/'FIRST_MATRIX_CANDIDATE_READINESS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name,v in result.items():
 print(name, 'coverage',v['cell_coverage_ratio'],'complete_entities',v['entities_complete_all_selected_variables_for_all_25_years'],'missing_cells',v['missing_value_cells'])
