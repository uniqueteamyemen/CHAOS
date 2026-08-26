#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZipFile
import json,hashlib
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS');Z=ROOT/'catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip';OUT=ROOT/'experiments/macro_plus_eia_energy/independent_source_screening'
def sha(p):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
with ZipFile(Z) as z:
 n=z.namelist()[0]
 with z.open(n) as f:
  head=pd.read_csv(f,nrows=5)
  meta={'zip':str(Z.relative_to(ROOT)),'zip_sha256':sha(Z),'member':n,'member_uncompressed_bytes':z.getinfo(n).file_size,'columns':head.columns.tolist(),'sample':head.astype(str).to_dict('records')}
  print(json.dumps(meta,ensure_ascii=False,indent=2)[:16000])
(OUT/'UCDP_ORGANIZED_VIOLENCE_CY_26_1_INSPECTION.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
