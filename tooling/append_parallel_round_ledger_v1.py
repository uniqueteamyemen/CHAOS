#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path('/home/ubuntu/CHAOS'); LEDGER=ROOT/'research_ledger/RESEARCH_LEDGER_V1.jsonl'
def digest(rel):
 p=ROOT/rel; return hashlib.sha256(p.read_bytes()).hexdigest()
def add(r):
 old=[json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
 if any(x['ledger_id']==r['ledger_id'] for x in old): raise SystemExit('duplicate '+r['ledger_id'])
 payload=json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')); r['record_hash']=hashlib.sha256(payload.encode()).hexdigest(); LEDGER.open('a',encoding='utf-8').write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
def main():
 now=datetime.now(timezone.utc).isoformat()
 add({'ledger_id':'ECONOMIC_DETERIORATION_TO_CONFLICT_V1','record_type':'transition_evidence','created_at_utc':now,'source_refs':['experimental_contracts/ECONOMIC_DETERIORATION_TO_CONFLICT_CONTRACT_V1.json','experiments/multi_domain_native_edges_v1/ECONOMIC_DETERIORATION_TO_CONFLICT_MAXSTAT_NULL_SUMMARY.json'],'contract_ref':'experimental_contracts/ECONOMIC_DETERIORATION_TO_CONFLICT_CONTRACT_V1.json','input_hashes':{x:digest(x) for x in ['experimental_contracts/ECONOMIC_DETERIORATION_TO_CONFLICT_CONTRACT_V1.json','catalog_first/readiness_gate/independent_sources/un_ama_2026/staged/UN_AMA_INDEPENDENT_GDP_GROWTH_POPULATION_PANEL.csv','catalog_first/readiness_gate/independent_sources/ucdp_organized_violence_cy_26_1/raw/UCDP_ORGANIZED_VIOLENCE_CY_26_1_RAW.zip']},'output_refs':['experiments/multi_domain_native_edges_v1/ECONOMIC_DETERIORATION_TO_CONFLICT_MAXSTAT_NULL_SUMMARY.json','experiments/multi_domain_native_edges_v1/TRANSITION_EVIDENCE_ECONOMIC_TO_CONFLICT_V1.jsonl'],'status':'rejected_by_current_maxstat_null','notes':'corrected run: joined 1962 rows, 56 entities, max-stat p=0.4532733633'})
 add({'ledger_id':'PARALLEL_EXECUTION_QA_V1','record_type':'qa','created_at_utc':now,'source_refs':['experiments/parallel_execution_qa/CHAOS_PARALLEL_EXECUTION_QA_V1.json','docs/PARALLEL_RESEARCH_EXECUTION_AR.md'],'contract_ref':'experimental_contracts/RESEARCH_LEDGER_CONTRACT_V1.json','input_hashes':{x:digest(x) for x in ['experiments/parallel_execution_qa/CHAOS_PARALLEL_EXECUTION_QA_V1.json','docs/PARALLEL_RESEARCH_EXECUTION_AR.md']},'output_refs':['experiments/parallel_execution_qa/CHAOS_PARALLEL_EXECUTION_QA_V1.json'],'status':'pass','notes':'raw immutable; native frequencies preserved; zero runtime-eligible patterns'})
if __name__=='__main__':main()
