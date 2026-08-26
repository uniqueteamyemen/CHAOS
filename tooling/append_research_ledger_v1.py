#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, sys
ROOT=Path('/home/ubuntu/CHAOS')
LEDGER=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
LEDGER.parent.mkdir(parents=True, exist_ok=True)
def sha256(path):
    p=ROOT/path
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
def append(record):
    existing=[]
    if LEDGER.exists():
        existing=[json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
    if any(x['ledger_id']==record['ledger_id'] for x in existing):
        raise SystemExit(f"duplicate ledger_id: {record['ledger_id']}")
    payload=json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    record['record_hash']=hashlib.sha256(payload.encode()).hexdigest()
    with LEDGER.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False,sort_keys=True)+'\n')
def main():
    now=datetime.now(timezone.utc).isoformat()
    append({'ledger_id':'LEDGER_CONTRACT_V1','record_type':'contract','created_at_utc':now,'source_refs':['experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json'],'contract_ref':'experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json','input_hashes':{'contract':sha256('experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json')},'output_refs':['research_ledger/RESEARCH_LEDGER_V1.jsonl'],'status':'active','notes':'Append-only ledger initialized.'})
    append({'ledger_id':'TEMPORAL_ALIGNMENT_CONTRACT_V1','record_type':'contract','created_at_utc':now,'source_refs':['experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json'],'contract_ref':'experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json','input_hashes':{'contract':sha256('experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json')},'output_refs':['research_ledger/RESEARCH_LEDGER_V1.jsonl'],'status':'active','notes':'Native frequency and explicit alignment rules initialized.'})
if __name__=='__main__':main()
