#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); ledger=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'; refs=['campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json','experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_SUMMARY.json','campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/BROWSER_DEEP_RESEARCH_ROUND_REPORT_AR.md']
rec={'contract_ref':refs[0],'created_at_utc':datetime.now(timezone.utc).isoformat(),'input_hashes':{r:hashlib.sha256((ROOT/r).read_bytes()).hexdigest() for r in refs},'ledger_id':'CAMPAIGN_QA_REPORT_COMMITTED_BROWSER_ROUND_01','notes':'final report included; 34 QA artifacts; raw excluded; gate pass; 47 nodes/50 edges; 2 admitted supported_predictive; 23 quarantined; runtime 0; causal 0','output_refs':refs,'record_type':'qa_refresh','status':'pass'}
rec['record_hash']=hashlib.sha256(json.dumps(rec,sort_keys=True,ensure_ascii=False).encode()).hexdigest(); lines=ledger.read_text(encoding='utf8').splitlines(); ids={json.loads(x)['ledger_id'] for x in lines if x.strip()};
if rec['ledger_id'] not in ids: ledger.open('a',encoding='utf8').write(json.dumps(rec,ensure_ascii=False,sort_keys=True)+'\n'); print('appended',rec['ledger_id'])
else: print('already_present',rec['ledger_id'])
