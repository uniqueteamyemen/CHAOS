#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); LEDGER=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
refs=['campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json','experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json']
rec={'contract_ref':refs[0],'created_at_utc':datetime.now(timezone.utc).isoformat(),'input_hashes':{r:hashlib.sha256((ROOT/r).read_bytes()).hexdigest() for r in refs},'ledger_id':'CAMPAIGN_QA_FINAL_BROWSER_ROUND_01','notes':'31 QA artifacts; raw excluded from manifest; graph 47 nodes/50 edges; 2 admitted supported_predictive; 23 quarantined; 0 runtime-eligible; 0 causal claims','output_refs':refs,'record_type':'qa_refresh','status':'pass'}
rec['record_hash']=hashlib.sha256(json.dumps(rec,sort_keys=True,ensure_ascii=False).encode()).hexdigest(); lines=LEDGER.read_text(encoding='utf8').splitlines(); ids={json.loads(x)['ledger_id'] for x in lines if x.strip()}
if rec['ledger_id'] not in ids: LEDGER.open('a',encoding='utf8').write(json.dumps(rec,ensure_ascii=False,sort_keys=True)+'\n'); print(json.dumps({'appended':True,'ledger_id':rec['ledger_id']},ensure_ascii=False))
else: print(json.dumps({'appended':False,'ledger_id':rec['ledger_id']},ensure_ascii=False))
