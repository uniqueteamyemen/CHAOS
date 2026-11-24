from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import os
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any
import numpy as np
from p2_b_benchmark.dataset import load_p2_economic_series
from p2_b_benchmark.engine import VARIANTS, mad_sigma, run_all

NULL_REPLICATES=99
NULL_BLOCK_LENGTH=12
BASE_SEED=20261117
SHIFT_SIGMA=3.0

def stationary_sample(values:np.ndarray,rng:np.random.Generator,mean_block:int)->np.ndarray:
    n=int(values.size)
    if n==0 or mean_block<1: raise ValueError("stationary_sample_input_invalid")
    idx=np.empty(n,dtype=int); idx[0]=int(rng.integers(n)); restart=1.0/mean_block
    for i in range(1,n):
        idx[i]=int(rng.integers(n)) if rng.random()<restart else (idx[i-1]+1)%n
    return values[idx]

def _seed_for(series_id:str)->int:
    return int(hashlib.sha256(f"{BASE_SEED}:{series_id}".encode()).hexdigest()[:16],16)

def _score_all(result:dict[str,Any],onset:int,sign:int)->dict[str,dict[str,Any]]:
    out={}
    for arm,payload in result.items():
        hits=payload.get("hits",[])
        correct=[int(h.get("time",h.get("index",-1))) for h in hits
                 if int(h.get("time",h.get("index",-1)))>=onset and int(h.get("direction",h.get("sign",0)))==sign]
        wrong=[h for h in hits if int(h.get("time",h.get("index",-1)))>=onset
               and int(h.get("direction",h.get("sign",0)))==-sign]
        events=payload.get("events",[])
        pre=[e for e in events if 52<=int(e.get("start_index",-1))<onset] if events else [
            h for h in hits if 52<=int(h.get("time",h.get("index",-1)))<onset]
        first=min(correct) if correct else None
        out[arm]={"detected":first is not None,"delay":first-onset if first is not None else None,
                  "pre_onset_alert":bool(pre),"wrong_direction":bool(wrong),"missed":first is None}
    return out

def _one_series(item:dict[str,Any],null_replicates:int)->dict[str,Any]:
    x=np.asarray(item["values"],dtype=float)
    result={"id":item["id"],"source":item["source"],"n":int(x.size),
            "null_eligible":bool(item["bootstrap_eligible"]),"observed":{},"null":{},"injected":{},"causal":{}}
    observed=run_all(x,causal_audit=True)
    for arm,payload in observed.items():
        result["observed"][arm]=int(payload.get("event_count",len(payload.get("hits",[]))))
        result["causal"][arm]={"violations":int(payload.get("causal_audit_violations") or 0),
                               "unverifiable":int(payload.get("causal_audit_unverifiable_prefixes") or 0)}
    onset=max(52,int(x.size*.7)); sigma=mad_sigma(x[:40])
    if sigma<=0 or onset>=x.size-1: raise ValueError(f"injection_not_identifiable:{item['id']}")
    for sign,label in ((1,"positive_3sigma"),(-1,"negative_3sigma")):
        injected=x.copy(); injected[onset:]+=sign*SHIFT_SIGMA*sigma
        run=run_all(injected,causal_audit=True)
        for arm,score in _score_all(run,onset,sign).items():
            result["injected"].setdefault(arm,{})[label]=score
            result["causal"][arm]["violations"]+=int(run[arm].get("causal_audit_violations") or 0)
            result["causal"][arm]["unverifiable"]+=int(run[arm].get("causal_audit_unverifiable_prefixes") or 0)
    if result["null_eligible"]:
        rng=np.random.default_rng(_seed_for(str(item["id"])))
        counts={a:{"alarm_replicates":0,"event_count":0} for a in VARIANTS}
        for _ in range(null_replicates):
            sample=stationary_sample(x,rng,NULL_BLOCK_LENGTH); null=run_all(sample)
            for arm,payload in null.items():
                events=int(payload.get("event_count",len(payload.get("hits",[]))))
                counts[arm]["alarm_replicates"]+=int(events>0); counts[arm]["event_count"]+=events
        result["null"]={a:{"alarm_replicates":v["alarm_replicates"],"event_count":v["event_count"],
            "conditional_alarm_probability":v["alarm_replicates"]/null_replicates,
            "events_per_replicate":v["event_count"]/null_replicates} for a,v in counts.items()}
    return result

def _aggregate(rows:list[dict[str,Any]],null_replicates:int)->dict[str,Any]:
    summary={"null":{},"injected":{},"observed":{},"causal":{}}
    for arm in VARIANTS:
        for cohort in ("all","pink_sheet","gem"):
            selected=[r for r in rows if cohort=="all" or r["source"]==cohort]
            eligible=[r for r in selected if r["null_eligible"] and arm in r["null"]]
            if eligible:
                trials=len(eligible)*null_replicates
                alarms=sum(r["null"][arm]["alarm_replicates"] for r in eligible)
                events=sum(r["null"][arm]["event_count"] for r in eligible)
                probs=[r["null"][arm]["conditional_alarm_probability"] for r in eligible]
                obs=sum(r["n"] for r in eligible)
                summary["null"].setdefault(arm,{})[cohort]={
                    "series":len(eligible),"replicates_per_series":null_replicates,"total_series_observations":obs,
                    "conditional_alarm_probability_pooled":alarms/trials,"events_per_replicate_pooled":events/trials,
                    "events_per_1000_observations":events/(null_replicates*obs)*1000,
                    "mean_series_alarm_probability":statistics.mean(probs),
                    "median_series_alarm_probability":statistics.median(probs),
                    "p90_series_alarm_probability":float(np.quantile(probs,.9)),
                    "interpretation":"conditional stationary-bootstrap diagnostic; not operational FPR"}
            for scenario in ("positive_3sigma","negative_3sigma"):
                outcomes=[r["injected"].get(arm,{}).get(scenario) for r in selected]
                outcomes=[o for o in outcomes if o is not None]
                delays=[o["delay"] for o in outcomes if o["delay"] is not None]
                if outcomes:
                    summary["injected"].setdefault(arm,{}).setdefault(scenario,{})[cohort]={
                        "series":len(outcomes),"sensitivity":sum(o["detected"] for o in outcomes)/len(outcomes),
                        "miss_rate":sum(o["missed"] for o in outcomes)/len(outcomes),
                        "pre_onset_false_alert_rate":sum(o["pre_onset_alert"] for o in outcomes)/len(outcomes),
                        "wrong_direction_rate":sum(o["wrong_direction"] for o in outcomes)/len(outcomes),
                        "median_detection_delay":statistics.median(delays) if delays else None,
                        "p90_detection_delay":float(np.quantile(delays,.9)) if delays else None,
                        "missed_series":sum(o["missed"] for o in outcomes)}
            counts=[r["observed"].get(arm,0) for r in selected]
            summary["observed"].setdefault(arm,{})[cohort]={
                "series":len(selected),"series_with_events":sum(c>0 for c in counts),
                "observed_event_count":sum(counts),"interpretation":"descriptive only; historical labels are not adjudicated"}
            audits=[r["causal"].get(arm,{"violations":0,"unverifiable":0}) for r in selected]
            bad=sum(int(a["violations"]) for a in audits); unverifiable=sum(int(a["unverifiable"]) for a in audits)
            summary["causal"].setdefault(arm,{})[cohort]={
                "series":len(selected),"prefix_replay_or_mutation_violations":bad,
                "unverifiable_short_prefix_events":unverifiable,
                "status":"FAIL_LOOKAHEAD_OR_PREFIX_INCONSISTENCY" if bad else
                         "PARTIAL_UNVERIFIABLE_SHORT_PREFIXES" if unverifiable else "PASS"}
    return summary

def run_benchmark(prepared_zip:str,*,null_replicates:int=NULL_REPLICATES,workers:int=4)->dict[str,Any]:
    if not 1<=null_replicates<=999: raise ValueError("null_replicates_out_of_range")
    series,counts=load_p2_economic_series(prepared_zip); rows=[]
    with ProcessPoolExecutor(max_workers=max(1,min(workers,os.cpu_count() or 1))) as pool:
        futures={pool.submit(_one_series,item,null_replicates):item["id"] for item in series}
        for future in as_completed(futures): rows.append(future.result())
    rows.sort(key=lambda r:r["id"])
    limitations=[
      "The 359 eligible series pass only the existing preliminary null-eligibility screen; bootstrap probabilities are conditional diagnostics, not real-world false-positive rates.",
      "Pink Sheet and GEM historical source vintages/available_at histories are absent; this tests detector-time causality on the downloaded snapshot, not historical point-in-time source availability.",
      "The 150 null-ineligible series remain in observed replay and injected-break sensitivity/delay measurements.",
      "Historical observed events have no adjudicated ground truth and are descriptive, not labelled false alarms.",
      "Injected breaks measure controlled sensitivity, delay, miss rate and direction errors, not correctness of historical classifications.",
      "FOCuS, BOCPD and R-FPOP implementations were not found in tracked main-phase2; no substitute implementation is claimed in this first batch."]
    return {"schema":"chaos-p2-b-detector-competition-v1",
      "protocol":{"input_scope":"51 Pink Sheet + 458 GEM monthly log-return series; USGS excluded",
      "source_artifact_run":45244943216,"null_replicates_per_eligible_series":null_replicates,
      "null_method":"Politis-Romano stationary bootstrap; mean block length 12",
      "injected_break":f"persistent +/-{SHIFT_SIGMA} x quiet MAD sigma at 70% of each series",
      "quiet_window_observations":40,"no_lookahead":"past-only scales, prefix replay, and future-suffix mutation audit",
      "detectors":VARIANTS},"source_integrity":counts,"summary":_aggregate(rows,null_replicates),
      "series_results":rows,"limitations":limitations}

def write_outputs(report:dict[str,Any],output_dir:str|Path):
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    jp=out/"P2_B_DETECTOR_COMPETITION_V1.json"; mp=out/"P2_B_DETECTOR_COMPETITION_V1_AR.md"
    jp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary=report["summary"]; lines=[
      "# P2-B — مقارنة الكواشف على 509 سلسلة اقتصادية","",
      f"- السلاسل: {report['source_integrity']['series']} (Pink Sheet: {report['source_integrity']['pink_sheet']}, GEM: {report['source_integrity']['gem']}).",
      f"- أهلية null: {report['source_integrity']['null_eligible']} (Pink: {report['source_integrity']['null_eligible_pink_sheet']}, GEM: {report['source_integrity']['null_eligible_gem']}).",
      f"- تكرارات null لكل سلسلة مؤهلة: {report['protocol']['null_replicates_per_eligible_series']}."]
    for cohort,label in (("all","الإجمالي"),("pink_sheet","Pink Sheet"),("gem","GEM")):
        lines += ["",f"## Conditional null diagnostic — {label}","","| Arm | P(≥1 alarm) | Events / replicate | Events / 1,000 observations |","|---|---:|---:|---:|"]
        for arm in VARIANTS:
            row=summary["null"].get(arm,{}).get(cohort)
            if row: lines.append(f"| {arm} | {row['conditional_alarm_probability_pooled']:.4f} | {row['events_per_replicate_pooled']:.4f} | {row['events_per_1000_observations']:.4f} |")
    lines += ["","## No-lookahead audit","","| Arm | Prefix violations | Unverifiable short prefixes | Status |","|---|---:|---:|---|"]
    for arm in VARIANTS:
        row=summary["causal"].get(arm,{}).get("all",{})
        lines.append(f"| {arm} | {row.get('prefix_replay_or_mutation_violations','NA')} | {row.get('unverifiable_short_prefix_events','NA')} | {row.get('status','NA')} |")
    lines += ["","## القيود"]+[f"- {v}" for v in report["limitations"]]
    mp.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return jp,mp

def load_detector_plugins(module_names:list[str])->list[str]:
    loaded=[]
    for name in module_names:
        name=name.strip()
        if name and name not in loaded: importlib.import_module(name); loaded.append(name)
    return loaded

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--prepared-zip",required=True)
    parser.add_argument("--output-dir",default="artifacts/p2_b")
    parser.add_argument("--null-replicates",type=int,default=NULL_REPLICATES)
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--plugin-module",action="append",default=[])
    args=parser.parse_args()
    env=[x for x in os.environ.get("P2B_DETECTOR_PLUGIN_MODULES","").split(",") if x.strip()]
    loaded=load_detector_plugins([*env,*args.plugin_module])
    report=run_benchmark(args.prepared_zip,null_replicates=args.null_replicates,workers=args.workers)
    jp,mp=write_outputs(report,args.output_dir)
    print(json.dumps({"json":str(jp),"report":str(mp),"loaded_detector_plugins":loaded,
      "registered_arms":list(VARIANTS),"source_integrity":report["source_integrity"]},ensure_ascii=False))
    return 0

if __name__=="__main__": raise SystemExit(main())
