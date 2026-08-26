#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, hashlib
ROOT=Path('/home/ubuntu/CHAOS')
REG=ROOT/'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'
GRAPH=ROOT/'experiments/macro_plus_eia_energy/evidence_graph_v1/EVIDENCE_GRAPH_V1.json'
OUT=ROOT/'experiments/macro_plus_eia_energy/pattern_compiler_v1'; OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 records=[json.loads(x) for x in REG.read_text().splitlines() if x.strip()]
 eligible=[]; research_only=[]
 for r in records:
  status=r.get('status','')
  if status=='supported_predictive': eligible.append({'pattern_id':r['pattern_id'],'status':'compiled_research_only','source_status':status,'statement':r.get('statement'),'causal_claim':False,'runtime_eligible':False,'evidence':r.get('evidence'), 'failure_cases':r.get('interpretation','')})
  elif status=='provisionally_supported_descriptive': research_only.append({'pattern_id':r['pattern_id'],'status':'compiled_research_only_candidate','source_status':status,'statement':r.get('statement'),'causal_claim':False,'runtime_eligible':False,'evidence':r.get('evidence'),'promotion_blocker':'descriptive provisional status requires further replication/OOS review'})
 artifact={'compiler_id':'CHAOS_PATTERN_COMPILER_V1','inputs':{'registry':str(REG.relative_to(ROOT)),'registry_sha256':sha(REG),'evidence_graph':str(GRAPH.relative_to(ROOT)),'evidence_graph_sha256':sha(GRAPH)},'eligible_supported_predictive':eligible,'research_only_candidates':research_only,'excluded_from_positive_composition':[r['pattern_id'] for r in records if r.get('status') not in ('supported_predictive','provisionally_supported_descriptive')],'rules':{'causal_claims_permitted':False,'runtime_eligible_default':False,'rejected_or_unresolved_positive_weight':False,'future_outcomes_in_detector':False,'retraining':False},'status':'research_only'}
 (OUT/'COMPILED_PATTERNS_V1.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
 summary={'compiler_id':artifact['compiler_id'],'supported_predictive_compiled':len(eligible),'provisional_research_only':len(research_only),'excluded':len(artifact['excluded_from_positive_composition']),'runtime_eligible':0,'causal_claims':0}
 (OUT/'PATTERN_COMPILER_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
