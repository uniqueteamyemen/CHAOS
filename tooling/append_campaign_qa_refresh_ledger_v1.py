#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); L=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
def main():
 r={'ledger_id':'CAMPAIGN_QA_REFRESH_ROUND_02','record_type':'qa_refresh','contract_ref':'campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json','input_hashes':{x:hashlib.sha256((ROOT/x).read_bytes()).hexdigest() for x in ['campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/AGENT_OUTPUT_INDEX_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json']},'output_refs':['campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/COMPOSITE_PATH_ADMISSION_DECISION_V1.json'],'status':'pass','notes':'22 QA artifacts; 0 admitted cross-domain edges; 0 runtime-eligible patterns; raw/frequency/causal gates pass'}
 old=[json.loads(x) for x in L.read_text().splitlines() if x.strip()]
 if not any(x.get('ledger_id')==r['ledger_id'] for x in old):
  r['created_at_utc']=datetime.now(timezone.utc).isoformat(); r['record_hash']=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); L.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 print('ledger_lines',sum(1 for x in L.read_text().splitlines() if x.strip()))
if __name__=='__main__':main()
