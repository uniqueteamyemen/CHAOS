from pathlib import Path
import hashlib, json
ROOT=Path('/home/ubuntu/CHAOS')
files=[
 'experimental_contracts/MULTI_DOMAIN_RESEARCH_SCOPE_V1.json',
 'experimental_contracts/RESEARCH_RUNTIME_SANDBOX_CONTRACT_V1.json',
 'experimental_contracts/STATE_PATH_DICTIONARY_V1.json',
 'experiments/macro_plus_eia_energy/RESEARCH_SNAPSHOT_V2.json',
 'experiments/macro_plus_eia_energy/research_runtime_sandbox_v1/RESEARCH_RUNTIME_SUMMARY.json',
 'experiments/macro_plus_eia_energy/research_runtime_sandbox_v1/RESEARCH_ALERTS_V1.jsonl',
 'experiments/macro_plus_eia_energy/research_runtime_sandbox_v1/RESEARCH_ALERTS_V1.csv',
 'tooling/run_research_runtime_sandbox_v1.py'
]
out=ROOT/'experiments/macro_plus_eia_energy/research_runtime_sandbox_v1/RESEARCH_RUNTIME_QA_MANIFEST.json'
items=[]
for rel in files:
 p=ROOT/rel; h=hashlib.sha256(p.read_bytes()).hexdigest(); items.append({'path':rel,'bytes':p.stat().st_size,'sha256':h})
summary=json.loads((ROOT/'experiments/macro_plus_eia_energy/research_runtime_sandbox_v1/RESEARCH_RUNTIME_SUMMARY.json').read_text())
manifest={'manifest_id':'CHAOS_RESEARCH_RUNTIME_QA_MANIFEST_V1','input_hash_checked':True,'raw_data_modified':False,'native_frequency_preserved':True,'future_outcome_used_in_alerts':False,'runtime_retraining':False,'external_send':False,'market_intelligence_engine_modified':False,'summary':summary,'files':items}
out.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(out)
