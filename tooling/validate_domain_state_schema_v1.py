#!/usr/bin/env python3
from pathlib import Path
import gzip,json
ROOT=Path('/home/ubuntu/CHAOS')
REQUIRED={'pattern_id','domain','entity_name','entity_id','timestamp','native_frequency','state_label','state_probability','source_observations','lead_profile','uncertainty','failure_cases','edge_status','evidence_refs'}
PATHS=[ROOT/'campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_DOMAIN_STATES_ANNUAL_SOURCE_YEARS_V1.jsonl',ROOT/'campaigns/agents/trade_v1/TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl',ROOT/'campaigns/agents/trade_v1/WDI_TRADE_DOMAIN_STATES_ANNUAL_V1.jsonl',ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_DOMAIN_STATES_SOURCE_WAVES_V1.jsonl',ROOT/'experiments/multi_domain_native_adapters_v1/USGS_EARTHQUAKE_DOMAIN_STATES_EVENT_V1.jsonl',ROOT/'experiments/multi_domain_native_adapters_v1/WHO_COVID_DOMAIN_STATES_DAILY_V1.jsonl.gz']
def read_first(p):
 opener=gzip.open if p.suffix=='.gz' else open
 with opener(p,'rt',encoding='utf8') as f:return json.loads(next(f))
def main():
 rows=[]
 for p in PATHS:
  x=read_first(p); missing=sorted(REQUIRED-set(x)); rows.append({'path':str(p.relative_to(ROOT)),'missing':missing,'native_frequency':x.get('native_frequency'),'edge_status':x.get('edge_status')})
  if missing: raise SystemExit(f'missing schema fields in {p}: {missing}')
 out={'validator_id':'CHAOS_DOMAIN_STATE_SCHEMA_VALIDATOR_V1','required_fields':sorted(REQUIRED),'files':rows,'status':'pass'}; p=ROOT/'campaigns/CAMPAIGN_SHARED_GATE_V1/DOMAIN_STATE_SCHEMA_VALIDATION_V1.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
