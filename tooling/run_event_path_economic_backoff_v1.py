#!/usr/bin/env python3
from pathlib import Path
import csv,json,sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'structural_engine'))
from src.event_path_engine import AnnualPanelAdapter,EventPathEngine,build_states
INPUT=ROOT/'catalog_first/readiness_gate/ANNUAL_PANEL_RAW_WDI_IMF_UCDP_EIA_2000_2024.csv'; OUT=ROOT/'experiments/event_path_economic_target_contract_v1/BACKOFF.json'; COL='wdi__NY.GDP.MKTP.KD.ZG'
def main():
    growth={}
    with INPUT.open(newline='',encoding='utf-8') as h:
        for r in csv.DictReader(h):
            try: growth.setdefault(r['entity_code'],{})[int(r['year'])]=float(r[COL])
            except (ValueError,TypeError): pass
    targets={e:{y+3:('1' if s.get(y+3)<=v-2 else '0') for y,v in s.items() if v>4 and y+3 in s} for e,s in growth.items()}
    data=AnnualPanelAdapter(COL,domain='economic').load(INPUT); states=build_states(data.events); engine=EventPathEngine(window_width=3,min_support=2,max_path_length=6)
    _,metrics=engine.rolling_oos_frozen_targets_backoff(states,data.events,targets,horizon=3,train_size=8)
    out={'method':'within_entity_suffix_backoff','registered_widths':[3,2,1],'min_support':2,'metrics':metrics,'status':'diagnostic; no threshold tuning'}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__': main()
