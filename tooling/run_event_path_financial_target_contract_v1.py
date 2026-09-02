#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import asdict
import csv,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'structural_engine'))
from src.event_path_engine import AnnualPanelAdapter,EventPathEngine,build_states,build_transitions,build_windows,build_paths,write_artifacts
INPUT=ROOT/'data/raw/financial_world_bank_v1/WB_FS_AST_PRVT_GD_ZS_2000_2024.csv'
OUTPUT=ROOT/'experiments/event_path_financial_target_contract_v1'
COL='value'
def main():
    dataset=AnnualPanelAdapter(COL,domain='financial').load(INPUT)
    states=build_states(dataset.events); transitions=build_transitions(dataset.events,states); windows=build_windows(dataset.events,states,width=3); paths=build_paths(windows,states,transitions)
    target={}
    with INPUT.open(newline='',encoding='utf-8') as h:
        for r in csv.DictReader(h):
            target.setdefault(r['entity_code'],{})[int(r['year'])]=r['value']
    targets={e:{y+3:('1' if s.get(y+3)<v else '0') for y,v in s.items() if y+3 in s} for e,s in target.items()}
    engine=EventPathEngine(window_width=3,min_support=2,max_path_length=6)
    predictions,metrics=engine.rolling_oos_frozen_targets(states,dataset.events,targets,horizon=3,train_size=8)
    write_artifacts(OUTPUT,dataset,dataset.events,states,transitions,predictions,metrics); OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'WINDOWS.jsonl').write_text('\n'.join(json.dumps(asdict(x),ensure_ascii=False,sort_keys=True) for x in windows)+'\n',encoding='utf-8')
    (OUTPUT/'PATHS.jsonl').write_text('\n'.join(json.dumps(asdict(x),ensure_ascii=False,sort_keys=True) for x in paths)+'\n',encoding='utf-8')
    contract={'contract_id':'event-path-financial-raw-target-v1','source':'World Bank WDI API','indicator':'FS.AST.PRVT.GD.ZS','feature_at_t':'domestic credit to private sector (% of GDP)','raw_target_at_t_plus_3':'credit ratio at t+3 < credit ratio at t','window_width':3,'train_size':8,'min_support':2,'unsupported_paths':'abstain','no_future_target_in_source_states':True,'causal_claims_permitted':False}
    (OUTPUT/'CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report=['# Event-Path Financial Target Contract v1','','Financial third-domain run using the World Bank domestic-credit series and the same frozen target-aware engine.','',f'- Events: **{len(dataset.events)}**; entities: **{len({e.entity for e in dataset.events})}**; target rows: **{len(predictions)}**','- Feature: domestic credit to private sector (% of GDP) at t','- Raw target: ratio at t+3 is lower than at t','- Same engine: window_width=3, train_size=8, min_support=2; unsupported paths abstain','', '| Model | Accuracy | N | Coverage/rate |','|---|---:|---:|---:|']
    for name,v in metrics.items():
        if 'accuracy' in v: report.append(f"| {name} | {v['accuracy']:.4f} | {int(v['n'])} | coverage={v.get('coverage',1.0):.4f} |")
        else: report.append(f"| {name} | — | {int(v['n'])} | rate={v.get('rate',0.0):.4f} |")
    report += ['', '## Status','','`provisional_financial_transfer_only`','', 'Predictive diagnostic only; no causal or operational promotion.','']
    (OUTPUT/'REPORT_AR.md').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps({'events':len(dataset.events),'entities':len({e.entity for e in dataset.events}),'predictions':len(predictions),'metrics':metrics},ensure_ascii=False))
if __name__=='__main__': main()
