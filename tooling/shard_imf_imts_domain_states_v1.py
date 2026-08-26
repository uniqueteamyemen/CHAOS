#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); src=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v1/IMF_IMTS_DOMAIN_STATES_ANNUAL_V1.jsonl'; out=ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v1/domain_state_shards'; out.mkdir(parents=True,exist_ok=True); handles={}; counts=defaultdict(int); hashes={}
try:
 with src.open(encoding='utf8') as f:
  for line in f:
   if not line.strip(): continue
   r=json.loads(line); e=str(r['entity_id']); p=out/f'IMF_IMTS_DOMAIN_STATES_{e}_ANNUAL_V1.jsonl';
   if e not in handles: handles[e]=p.open('w',encoding='utf8')
   handles[e].write(line); counts[e]+=1
finally:
 for h in handles.values(): h.close()
manifest=[]
for e in sorted(counts):
 p=out/f'IMF_IMTS_DOMAIN_STATES_{e}_ANNUAL_V1.jsonl'; manifest.append({'entity_id':e,'path':str(p.relative_to(ROOT)),'records':counts[e],'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
res={'source':str(src.relative_to(ROOT)),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_bytes':src.stat().st_size,'shard_count':len(manifest),'records':sum(counts.values()),'shards':manifest,'monolithic_policy':'full local derived file retained for validator/reproducibility but ignored by Git because it exceeds GitHub per-file limit','status':'sharded'}; (ROOT/'experiments/multi_domain_native_adapters_v1/imf_imts_v1/IMF_IMTS_DOMAIN_STATE_SHARDS_MANIFEST_V1.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(res,ensure_ascii=False,indent=2))
