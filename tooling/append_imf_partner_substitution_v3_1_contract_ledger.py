#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); ledger=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'; contract='experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3_1.json'; protocol='campaigns/dual_track_v02/CHAOS_DUAL_TRACK_PROTOCOL_V0_2.json'
def sha(rel): return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
r={'ledger_id':'IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3_1_FROZEN','record_type':'contract_freeze','status':'frozen_not_run','contract_ref':contract,'created_at_utc':datetime.now(timezone.utc).isoformat(),'input_hashes':{contract:sha(contract),protocol:sha(protocol),'experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3.json':sha('experimental_contracts/dual_track_v02/IMF_IMTS_PARTNER_SUBSTITUTION_CONTRACT_V3.json')},'output_refs':[contract,protocol],'notes':'V3.1 independently freezes shock, replacement, outcome, event unit, three out-of-sample baselines, block/time/rank-preserving nulls, FDR/Holm alpha, effect-size, subwindow stability, concentration, influential-reporter, coverage, provenance, and admission criteria. It is intentionally not run before review/approval; V3 remains unresolved and unchanged.'}
r['record_hash']=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); ids={json.loads(x)['ledger_id'] for x in ledger.read_text().splitlines() if x.strip()}
if r['ledger_id'] not in ids:
 ledger.open('a').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n'); print(json.dumps({'appended':True,'ledger_id':r['ledger_id'],'record_hash':r['record_hash'],'contract_sha256':r['input_hashes'][contract]},ensure_ascii=False,indent=2))
else: print(json.dumps({'appended':False,'ledger_id':r['ledger_id']},ensure_ascii=False,indent=2))
