#!/usr/bin/env python3
from pathlib import Path
import re,json
src=Path('/tmp/imts_resource_probe.bin'); out=Path('/home/ubuntu/CHAOS/campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/IMF_IMTS_API_ROUTE_ANALYSIS_V1.json'); t=src.read_text(errors='ignore'); patterns=[]
for pat in [r'https?://[^"\'\\ ]+',r'[^"\'\\ ]{0,120}(?:download|Download|SDMX|sdmx|api|API)[^"\'\\ ]{0,180}']:
 for m in re.finditer(pat,t): patterns.append(m.group(0))
patterns=sorted(set(patterns)); out.write_text(json.dumps({'source':'/tmp/imts_resource_probe.bin','bytes':src.stat().st_size,'matches':patterns[:500],'status':'route_analysis_complete'},ensure_ascii=False,indent=2)+'\n'); print(json.dumps({'match_count':len(patterns),'matches':patterns[:80]},ensure_ascii=False,indent=2))
