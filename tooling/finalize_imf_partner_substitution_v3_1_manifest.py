#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); d=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3_1'
def sha(rel):return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
refs=['experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3_1.json','campaigns/dual_track_v02/CHAOS_DUAL_TRACK_PROTOCOL_V0_2.json','experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_SELECTION_REGISTER_V2.csv','experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVATIONS_PROFILE_V2.json','experiments/multi_domain_native_adapters_v1/imf_imts_v2/IMF_IMTS_XG_OBSERVATION_SHARDS_MANIFEST_V2.json']
outs=[str(x.relative_to(ROOT)) for x in sorted(d.glob('*')) if x.is_file()]
outs += [str(x.relative_to(ROOT)) for x in sorted((d/'stability_runs').glob('SUMMARY_*.json')) if x.is_file()]
m={'run_id':'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_FULL_DISCOVERY_RUN','created_at_utc':datetime.now(timezone.utc).isoformat(),'contract_ref':refs[0],'contract_sha256':sha(refs[0]),'protocol_ref':refs[1],'protocol_sha256':sha(refs[1]),'code_ref':'tooling/run_imf_partner_substitution_v3_1.py','code_sha256':sha('tooling/run_imf_partner_substitution_v3_1.py'),'seed':271108,'stability_seeds':[271108,271109,271110,271111,271112],'null_replicates':{'block_permutation':10000,'rank_preserving':10000,'restricted_time_placebo':5000},'input_refs':refs[2:],'input_sha256':{x:sha(x) for x in refs[2:]},'output_refs':sorted(set(outs)),'status':'not_testable','research_only':True,'causal_validation_status':'not_run','runtime_eligible':False,'causal_claim':False,'raw_modified':False}
(d/'IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_RUN_MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':m['status'],'outputs':len(m['output_refs']),'contract_sha256':m['contract_sha256']},ensure_ascii=False,indent=2))
