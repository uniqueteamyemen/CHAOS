#!/usr/bin/env python3
from pathlib import Path
import json
p=Path('/home/ubuntu/CHAOS/campaigns/agents/institutions_policy_v1/WGI_INSTITUTIONAL_DOMAIN_STATES_ANNUAL_SOURCE_YEARS_V1.jsonl')
ids=sorted({json.loads(line)['source_observations']['indicator_id'] for line in p.open() if line.strip()})
print('\n'.join(ids))
