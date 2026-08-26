#!/usr/bin/env python3
from pathlib import Path
import json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); RAW=ROOT/'catalog_first/readiness_gate/independent_sources/un_ama_2026/raw'; OUT=ROOT/'experiments/macro_plus_eia_energy/independent_source_screening'
for p in sorted(RAW.glob('*.xlsx')):
 x=pd.ExcelFile(p); info={'file':str(p.relative_to(ROOT)),'sheets':x.sheet_names,'sizes':{}}
 for s in x.sheet_names:
  df=pd.read_excel(p,sheet_name=s,header=None,nrows=8); info['sizes'][s]={'shape_head':list(df.shape),'head':df.fillna('').astype(str).values.tolist()}
 (OUT/(p.stem+'_INSPECTION.json')).write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(info,ensure_ascii=False,indent=2)[:8000])
