#!/usr/bin/env python3
from __future__ import annotations
import csv, json, random, statistics
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'structural_engine'))
from src.event_path_engine import AnnualPanelAdapter, EventPathEngine, build_states
INPUT=ROOT/'catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv'
OUTPUT=ROOT/'experiments/event_path_economic_target_contract_v1/NULL.json'
COL='wdi__NY.GDP.MKTP.KD.ZG'
def main():
    rows=[]
    with INPUT.open(newline='',encoding='utf-8') as h:
        for r in csv.DictReader(h):
            try: rows.append((r['entity_code'],int(r['year']),float(r[COL])))
            except (ValueError,TypeError): pass
    growth={}
    for e,y,v in rows: growth.setdefault(e,{})[y]=v
    target={}
    for e,s in growth.items():
        for y,v in s.items():
            f=s.get(y+3)
            if v>4 and f is not None: target.setdefault(e,{})[y+3]='1' if f<=v-2 else '0'
    data=AnnualPanelAdapter(COL,domain='economic').load(INPUT)
    states=build_states(data.events); engine=EventPathEngine(window_width=3,min_support=2,max_path_length=6)
    _,m=engine.rolling_oos_frozen_targets(states,data.events,target,horizon=3,train_size=8)
    real=m['path_model']['accuracy']-m['majority_baseline']['accuracy']
    rng=random.Random(20260828); lifts=[]; cover=[]
    for _ in range(1000):
        shuffled={}
        for e, vals in target.items():
            years=list(vals); labels=[vals[y] for y in years]; rng.shuffle(labels); shuffled[e]=dict(zip(years,labels))
        _,mm=engine.rolling_oos_frozen_targets(states,data.events,shuffled,horizon=3,train_size=8)
        lifts.append(mm['path_model']['accuracy']-mm['majority_baseline']['accuracy']); cover.append(mm['path_model']['coverage'])
    out={'repetitions':1000,'seed':20260828,'observed':{'lift':real,'path_accuracy':m['path_model']['accuracy'],'majority_accuracy':m['majority_baseline']['accuracy'],'coverage':m['path_model']['coverage']},'null':{'lift_mean':statistics.fmean(lifts),'lift_std':statistics.pstdev(lifts),'lift_p95':sorted(lifts)[949],'p_ge_observed':(1+sum(x>=real for x in lifts))/1001,'coverage_mean':statistics.fmean(cover),'coverage_std':statistics.pstdev(cover)},'interpretation':'positive separation requires observed lift above null distribution with adequate coverage'}
    OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__': main()
