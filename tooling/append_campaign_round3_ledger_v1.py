#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); LEDGER=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
def h(rel):return hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
def add(r):
 old=[json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
 if any(x.get('ledger_id')==r['ledger_id'] for x in old):return
 r['created_at_utc']=datetime.now(timezone.utc).isoformat(); r['record_hash']=hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest(); LEDGER.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
def main():
 add({'ledger_id':'WDI_TRADE_PANEL_EXTRACT_V1','record_type':'source_extract','contract_ref':'experimental_contracts/WDI_TRADE_EDGE_CONTRACT_V1.json','input_hashes':{'campaigns/agents/trade_v1/WDI_TRADE_EXTRACT_SUMMARY.json':h('campaigns/agents/trade_v1/WDI_TRADE_EXTRACT_SUMMARY.json')},'output_refs':['campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv','campaigns/agents/trade_v1/WDI_TRADE_SELECTED_SERIES_METADATA.csv'],'status':'ready','notes':'29,004 observations, 259 entities, five WDI trade series; external bulk raw preserved outside CHAOS'})
 add({'ledger_id':'WDI_TRADE_INTERNAL_EDGE_RUN_V1','record_type':'transition_evidence','contract_ref':'experimental_contracts/WDI_TRADE_EDGE_CONTRACT_V1.json','input_hashes':{'campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv':h('campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv')},'output_refs':['campaigns/agents/trade_v1/WDI_TRADE_EDGE_MAXSTAT_NULL_SUMMARY.json','campaigns/agents/trade_v1/WDI_TRADE_TRANSITION_EVIDENCE_V1.jsonl'],'status':'rejected','notes':'max-stat p=0.4547726137; validation advantage failed confirmation'})
 add({'ledger_id':'WDI_TRADE_TO_ECONOMIC_EDGE_RUN_V1','record_type':'transition_evidence','contract_ref':'experimental_contracts/WDI_TRADE_TO_ECONOMIC_DETERIORATION_CONTRACT_V1.json','input_hashes':{'campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv':h('campaigns/agents/trade_v1/WDI_TRADE_OBSERVED_RECORDS_2000_2024.csv')},'output_refs':['campaigns/agents/trade_v1/WDI_TRADE_TO_ECONOMIC_DETERIORATION_MAXSTAT_NULL_SUMMARY.json','campaigns/agents/trade_v1/WDI_TRADE_TO_ECONOMIC_DETERIORATION_TRANSITION_EVIDENCE_V1.jsonl'],'status':'rejected','notes':'max-stat p=0.5897051474; no positive composition weight'})
 add({'ledger_id':'CAMPAIGN_FINAL_SUPERVISOR_GATE_ROUND_01','record_type':'supervisor_gate','contract_ref':'campaigns/CAMPAIGN_BASELINE_V1.json','input_hashes':{'campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json':h('campaigns/CAMPAIGN_SHARED_GATE_V1/FINAL_SUPERVISOR_ELIGIBILITY_GATE_V1.json')},'output_refs':['campaigns/CAMPAIGN_SHARED_GATE_V1/COMPOSITE_PATH_ADMISSION_DECISION_V1.json','campaigns/CAMPAIGN_SHARED_GATE_V1/CAMPAIGN_QA_MANIFEST_V1.json'],'status':'pass','notes':'0 admitted cross-domain edges; 0 runtime-eligible patterns; 0 causal claims'})
 print('ledger_lines',sum(1 for x in LEDGER.read_text().splitlines() if x.strip()))
if __name__=='__main__':main()
