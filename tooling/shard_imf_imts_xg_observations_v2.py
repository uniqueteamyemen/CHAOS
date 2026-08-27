#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); src=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVED_RECORDS_2000_2024.csv'; out=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/observations_shards'; out.mkdir(parents=True,exist_ok=True); df=pd.read_csv(src,low_memory=False); rows=[]
for country,g in df.groupby('country',sort=True):
 p=out/f'IMF_IMTS_XG_{country}_2000_2024.csv'; g.to_csv(p,index=False); rows.append({'reporter_id':country,'rows':int(len(g)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'path':str(p.relative_to(ROOT))})
manifest={'source_artifact':str(src.relative_to(ROOT)),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'shard_count':len(rows),'row_count':int(len(df)),'reporter_count':int(df.country.nunique()),'shards':rows,'reconstruction_order':'sort by reporter_id and concatenate shards; no values changed','raw_modified':False}; (ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVATION_SHARDS_MANIFEST_V2.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'shards':len(rows),'rows':len(df),'total_bytes':sum(x['bytes'] for x in rows),'max_shard_bytes':max(x['bytes'] for x in rows),'manifest_path':'experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVATION_SHARDS_MANIFEST_V2.json'},ensure_ascii=False,indent=2))
