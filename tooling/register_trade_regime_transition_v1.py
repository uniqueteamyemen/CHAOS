#!/usr/bin/env python3
from pathlib import Path
import json,hashlib
ROOT=Path('/home/ubuntu/CHAOS'); REG=ROOT/'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'; E=ROOT/'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl'
r=json.loads(E.read_text().splitlines()[0]); rec={'pattern_id':'TRADE_REGIME_TRANSITION_DISCOVERY_V1','status':'rejected','domain':'trade','statement':'Fit-only learned multi-dimensional trade regime transition did not meet locked out-of-sample admission criteria.','outcome_family':'trade_regime_transition','causal_claim':False,'evidence':{'artifact':str(E.relative_to(ROOT)),'sha256':hashlib.sha256(E.read_bytes()).hexdigest(),'edge_status':r['edge_status']},'interpretation':'Final predictive attempt on current IMTS trade observations closed. No further predictive tuning on the same trade data/question.','runtime_eligible':False,'positive_composer_weight':0}
existing=REG.read_text().splitlines() if REG.exists() else []
if not any(json.loads(x).get('pattern_id')==rec['pattern_id'] for x in existing if x.strip()):
 with REG.open('a') as f:f.write(json.dumps(rec,ensure_ascii=False,sort_keys=True)+'\n')
 print(json.dumps({'appended':True,'pattern_id':rec['pattern_id']},ensure_ascii=False))
else: print(json.dumps({'appended':False,'pattern_id':rec['pattern_id'],'reason':'already_exists'},ensure_ascii=False))
