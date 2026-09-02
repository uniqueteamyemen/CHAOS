#!/usr/bin/env python3
from __future__ import annotations
from collections import Counter
import csv,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'structural_engine'))
from src.event_path_engine import AnnualPanelAdapter,EventPathEngine,build_states
INPUT=ROOT/'catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv'; OUTPUT=ROOT/'experiments/event_path_economic_target_contract_v1/COVERAGE_AUDIT.json'; COL='wdi__NY.GDP.MKTP.KD.ZG'
def main():
    growth={}
    with INPUT.open(newline='',encoding='utf-8') as h:
        for r in csv.DictReader(h):
            try: growth.setdefault(r['entity_code'],{})[int(r['year'])]=float(r[COL])
            except (ValueError,TypeError): pass
    targets={}
    for e,s in growth.items():
        for y,v in s.items():
            if v>4 and y+3 in s: targets.setdefault(e,{})[y+3]='1' if s[y+3]<=v-2 else '0'
    data=AnnualPanelAdapter(COL,domain='economic').load(INPUT); states=build_states(data.events); event_by={e.event_id:e for e in data.events}; by={}
    for st in states: by.setdefault(event_by[st.event_id].entity,[]).append(st)
    support=Counter(); rows=0; covered=0; signatures=Counter(); state_pair_counts=Counter()
    for entity,series in by.items():
        series.sort(key=lambda st:int(float(event_by[st.event_id].timestamp))); tm=targets.get(entity,{})
        for i in range(8,len(series)):
            year=int(float(event_by[series[i].event_id].timestamp));
            if year+3 not in tm: continue
            train=series[:i]; sig=tuple(st.label for st in train[-3:]); n=0
            for end in range(2,len(train)-1):
                sy=int(float(event_by[train[end].event_id].timestamp));
                if sy+3<year and sy+3 in tm and tuple(st.label for st in train[end-2:end+1])==sig: n+=1
            support[n]+=1; signatures[sig]+=1; rows+=1; covered += n>=2
    out={'rows':rows,'covered':covered,'coverage':covered/rows if rows else 0,'abstention':1-covered/rows if rows else 0,'support_distribution':dict(sorted(support.items())),'unique_current_signatures':len(signatures),'current_signature_recurrence':{'once':sum(v==1 for v in signatures.values()),'twice':sum(v==2 for v in signatures.values()),'three_or_more':sum(v>=3 for v in signatures.values())},'interpretation':'Coverage loss is caused by unsupported exact state signatures; this is a diagnostic, not permission to lower min_support.'}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__': main()
