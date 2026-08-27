#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); d=ROOT/'experiments/dual_track_v02/trade_network_adaptation_path_v1_1'
def sha(rel):return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
inputs=['experimental_contracts/dual_track_v02/TRADE_NETWORK_ADAPTATION_PATH_CONTRACT_V1_1.json','campaigns/dual_track_v02/CHAOS_DUAL_TRACK_PROTOCOL_V0_2.json','experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv','experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVATION_SHARDS_MANIFEST_V2.json']
outputs=[str(x.relative_to(ROOT)) for x in sorted(d.glob('*')) if x.is_file()]
m={'run_id':'TRADE_NETWORK_ADAPTATION_PATH_V1_1_FULL_RUN','created_at_utc':datetime.now(timezone.utc).isoformat(),'contract_ref':inputs[0],'contract_sha256':sha(inputs[0]),'protocol_ref':inputs[1],'protocol_sha256':sha(inputs[1]),'code_ref':'tooling/run_trade_network_adaptation_path_v1_1.py','code_sha256':sha('tooling/run_trade_network_adaptation_path_v1_1.py'),'seed':271108,'null_replicates':{'block':2000,'rank':2000,'time':2000},'input_refs':inputs[2:],'input_sha256':{x:sha(x) for x in inputs[2:]},'output_refs':sorted(set(outputs)),'status':'rejected','research_only':True,'causal_validation_status':'not_run','runtime_eligible':False,'causal_claim':False,'raw_modified':False,'notes':['Event-path V1.1 used 170 events and 3375 states. Candidate was worse than all fit-only baselines on locked final block; no promotion.']}
(d/'TRADE_NETWORK_ADAPTATION_PATH_RUN_MANIFEST_V1_1.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':m['status'],'outputs':len(m['output_refs']),'contract_sha256':m['contract_sha256']},ensure_ascii=False,indent=2))
