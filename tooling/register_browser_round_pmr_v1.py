#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path('/home/ubuntu/CHAOS'); REG=ROOT/'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'
def main():
 r={'pattern_id':'OECD_PMR_REGULATORY_REGIME_CHANGE_V1','status':'not_testable','statement':'PMR regulatory indicator at source wave to regulatory transition at next source wave','evidence':{'artifact':'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_TRANSITION_EVIDENCE_V1.jsonl','rows':4134,'entities':47,'waves':[1998,2003,2008,2013]},'causal_claim':False,'operational_promotion':False,'interpretation':'archive vintage has only four source-defined waves and no dated policy shock; no edge test admitted'}
 old=[json.loads(x) for x in REG.read_text().splitlines() if x.strip()]
 if not any(x.get('pattern_id')==r['pattern_id'] for x in old):REG.open('a',encoding='utf8').write(json.dumps(r,ensure_ascii=False)+'\n')
 print(json.dumps(r,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
