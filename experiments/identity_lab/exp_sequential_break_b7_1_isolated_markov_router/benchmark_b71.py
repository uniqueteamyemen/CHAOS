"""B-v7.1 isolated Markov/router/consensus benchmark: 26M dev, 27M holdout."""
from __future__ import annotations
import json, statistics, time
from pathlib import Path
import numpy as np
from experiments.identity_lab.exp_sequential_break_audit.benchmark_b3_audited import N, ONSET, generate_series
from experiments.identity_lab.exp_sequential_break_b6_spearman_ablation.benchmark_b6 import (
    CASES, classify, empty_counts, add_measurement, summarize_case
)
from experiments.identity_lab.exp_sequential_break_b61_sarp_sagp_factorial.engine_b61 import SurgicalFactorEngineB61
from experiments.identity_lab.exp_sequential_break_b7_1_isolated_markov_router.engine_b71 import InnovationSignCusumEngineB7

DEV_SEED=26_000_000
HOLD_SEED=27_000_000
TRIALS_DEV=500
TRIALS_HOLD=2000
HS=(7.0,7.5,8.0,8.5)
PENALTY=75
RESULTS_DIR=Path(__file__).resolve().parent/"results"
OUT=RESULTS_DIR/"b71_26m_27m_report.json"
DEV_CHECKPOINT=RESULTS_DIR/"b71_26m_development_checkpoint.json"

def fast_ref():
    return SurgicalFactorEngineB61(quiet_end=40,window_size=12,anomaly_z_thresh=3.8,
        winsor_cap=1.8,break_percent_thresh=85.0,resolution_horizon=14,
        return_to_baseline_z=1.5,persistence_z_thresh=1.45,
        correlation_method="pearson",innovation_drain=True,persistence_floor=False,
        heuristic_scale_guard=False)

def markov(h):
    return InnovationSignCusumEngineB7(quiet_end=40,window_size=12,anomaly_z_thresh=3.8,
        winsor_cap=1.8,cusum_threshold=h,structural_rho_bias_correction=True,
        resolution_horizon=14,return_to_baseline_z=1.5,persistence_z_thresh=1.45,
        correlation_method="pearson",innovation_drain=True,persistence_floor=False,
        heuristic_scale_guard=False)

def route_choice(x):
    q=np.asarray(x[:40],dtype=float)
    center=float(np.median(q))
    left=q[:-1]-center; right=q[1:]-center
    rho=float(np.corrcoef(left,right)[0,1]) if np.std(left)>1e-12 and np.std(right)>1e-12 else 0.0
    rho=0.0 if not np.isfinite(rho) else rho
    qdiff=np.diff(q)
    local=np.diff(np.asarray(x[40:52],dtype=float))
    def mad(v):
        m=float(np.median(v))
        return float(np.median(np.abs(v-m)))
    rvar=max(1.0,mad(local)/max(mad(qdiff),1e-12))
    return ("Fast_Ref" if rho<=0.45 and rvar<1.35 else "Markov_CUSUM"),rho,rvar

def analyze_router(x,h):
    choice,rho,rvar=route_choice(x)
    result=(fast_ref() if choice=="Fast_Ref" else markov(h)).analyze(x)
    result["diagnostics"].update({"router_choice":choice,"router_rho_raw":rho,"router_rvar":rvar})
    return result


def pending_opened_times(result):
    events=[]
    for structural in result["structural_breaks"]:
        events.extend(structural.get("resolved_pending_alerts",[]))
    events.extend(result["transient_anomalies"])
    events.extend(result["unresolved_alerts"])
    return tuple(sorted(int(event["time"]) for event in events))


def pending_channel_gate(evaluation):
    checks={}
    for name,metrics in evaluation["systems"].items():
        isolation=metrics["pending_channel_isolation"]
        accounting=metrics["pending_accounting"]
        checks[name]={
            "series_checked":isolation["series_checked"],
            "mismatched_series":isolation["mismatched_series"],
            "pending_times_match_fast_ref":isolation["matches_fast_ref"],
            "pending_accounting_holds":accounting["equation_holds"],
        }
    return {
        "passed":all(
            item["mismatched_series"]==0
            and item["pending_times_match_fast_ref"]
            and item["pending_accounting_holds"]
            for item in checks.values()
        ),
        "systems":checks,
    }


def analyze_consensus(x,h):
    f=fast_ref().analyze(x)
    m=markov(h).analyze(x)

    # A Markov event is a single confirmation token: it can promote at most
    # one Fast_Ref provisional event. Process provisionals chronologically and
    # consume the earliest eligible same-direction Markov event within 35 steps.
    markov_events=sorted(
        enumerate(m["structural_breaks"]),
        key=lambda pair:int(pair[1]["detection_time"])
    )
    consumed_markov=set()
    confirmed=[]
    unconfirmed=[]
    for provisional in sorted(
        f["structural_breaks"],key=lambda e:int(e["detection_time"])
    ):
        t=int(provisional["detection_time"])
        d=int(provisional["direction"])
        partner=next(
            (
                (idx,event) for idx,event in markov_events
                if idx not in consumed_markov
                and int(event["direction"])==d
                and 0 <= int(event["detection_time"])-t <= 35
            ),
            None,
        )
        if partner is None:
            unconfirmed.append(provisional)
            continue
        idx,event=partner
        consumed_markov.add(idx)
        confirmation_time=int(event["detection_time"])
        confirmed.append({**provisional,"status":"CONFIRMED",
            "provisional_detection_time":t,
            "detection_time":confirmation_time,
            "confirmation_time":confirmation_time,
            "confirmation_delay":confirmation_time-t})

    # Pending alerts absorbed by an unconfirmed Fast_Ref event are not
    # structurally resolved in consensus mode. Reclassify them as unresolved.
    unconfirmed_pending=[]
    for provisional in unconfirmed:
        for pending in provisional.get("resolved_pending_alerts",[]):
            unconfirmed_pending.append({
                **pending,
                "status":"UNRESOLVED_UNCONFIRMED_PROVISIONAL",
                "provisional_break_time":int(provisional["detection_time"]),
                "provisional_direction":int(provisional["direction"]),
            })

    result={**f,"structural_breaks":confirmed}
    result["unresolved_alerts"]=[
        *f["unresolved_alerts"],*unconfirmed_pending
    ]
    lifecycle=dict(f["pending_lifecycle"])
    lifecycle["resolved_structural_count"]=sum(
        len(event.get("resolved_pending_alerts",[])) for event in confirmed
    )
    lifecycle["unresolved_count"]=(
        int(lifecycle["unresolved_count"])+len(unconfirmed_pending)
    )
    terminal=(
        int(lifecycle["resolved_structural_count"])
        +int(lifecycle["resolved_transient_count"])
        +int(lifecycle["unresolved_count"])
    )
    lifecycle["accounting_complete"]=(
        int(lifecycle["opened_count"])==terminal
    )
    if not lifecycle["accounting_complete"]:
        raise AssertionError(
            "consensus_pending_lifecycle_accounting_mismatch:"
            f"opened={lifecycle['opened_count']},terminal={terminal}"
        )
    result["pending_lifecycle"]=lifecycle
    result["diagnostics"]={**f.get("diagnostics",{}),
        "provisional_count":len(f["structural_breaks"]),
        "confirmed_count":len(confirmed),
        "unconfirmed_provisional_count":len(unconfirmed),
        "unconfirmed_pending_reclassified":len(unconfirmed_pending),
        "markov_confirmation_matching":"one_to_one",
        "promotion_rate_pct":round(100*len(confirmed)/len(f["structural_breaks"]),2)
            if f["structural_breaks"] else 0.0}
    return result

def evaluate(seed_base,trials,h,stage):
    names=("Fast_Ref","Markov_CUSUM","Deterministic_Auto_Router","Consensus_Staging_Mode")
    counts={name:{c[0]:{**empty_counts(),"delays_penalized":[],"provisional":0,"confirmed":0}
                  for c in CASES} for name in names}
    pending_audit={name:{"opened":0,"structural":0,"transient":0,"unresolved":0}
                   for name in names}
    pending_channel_audit={name:{"series_checked":0,"mismatched_series":0,
        "reference_opened_events":0,"system_opened_events":0}
        for name in names}
    for ci,(case,dist,rho,vjump,shift) in enumerate(CASES):
        for ti in range(trials):
            seed=seed_base+ci*10000+ti
            x=generate_series(np.random.default_rng(seed),dist=dist,rho=rho,
                var_jump=vjump,shift_sigma=shift,n=N,onset=ONSET)
            outputs={
                "Fast_Ref":fast_ref().analyze(x),
                "Markov_CUSUM":markov(h).analyze(x),
                "Deterministic_Auto_Router":analyze_router(x,h),
                "Consensus_Staging_Mode":analyze_consensus(x,h),
            }
            reference_pending_times=pending_opened_times(outputs["Fast_Ref"])
            for name,result in outputs.items():
                system_pending_times=pending_opened_times(result)
                audit=pending_channel_audit[name]
                audit["series_checked"]+=1
                audit["reference_opened_events"]+=len(reference_pending_times)
                audit["system_opened_events"]+=len(system_pending_times)
                if system_pending_times!=reference_pending_times:
                    audit["mismatched_series"]+=1
                metric=classify(result,shift)
                bucket=counts[name][case]
                add_measurement(bucket,metric)
                if shift!=0:
                    bucket["delays_penalized"].append(
                        PENALTY if metric["delay"] is None else int(metric["delay"]))
                life=result["pending_lifecycle"]
                pending_audit[name]["opened"]+=int(life["opened_count"])
                pending_audit[name]["structural"]+=int(life["resolved_structural_count"])
                pending_audit[name]["transient"]+=int(life["resolved_transient_count"])
                pending_audit[name]["unresolved"]+=int(life["unresolved_count"])
                if name=="Consensus_Staging_Mode":
                    bucket["provisional"]+=int(result["diagnostics"]["provisional_count"])
                    bucket["confirmed"]+=int(result["diagnostics"]["confirmed_count"])
    summaries={}
    for name in names:
        rows={}
        for case,dist,rho,vjump,shift in CASES:
            b=counts[name][case]
            row=summarize_case(shift,vjump,b,trials)
            row["confirmed_delay_median_penalty_75"]=(
                round(float(statistics.median(b["delays_penalized"])),2)
                if b["delays_penalized"] else None)
            row["provisional_events"]=b["provisional"]
            row["confirmed_events"]=b["confirmed"]
            row["promotion_rate_pct"]=round(100*b["confirmed"]/b["provisional"],2) if b["provisional"] else 0.0
            rows[case]=row
        nonlevel=[r for r in rows.values() if r["scenario_type"] in ("pure_null","variance_jump")]
        pure=[r for r in rows.values() if r["scenario_type"]=="pure_null"]
        shifts=[r for r in rows.values() if r["scenario_type"]=="level_shift"]
        structural=max(r["structural_rate"]["rate_pct"] for r in nonlevel)
        transient=max(r["transient_alert_rate"]["rate_pct"] for r in nonlevel)
        combined=max(r["combined_any_alert_rate"]["rate_pct"] for r in pure)
        combined_nonlevel=max(r["combined_any_alert_rate"]["rate_pct"] for r in nonlevel)
        sensitivity=round(statistics.mean(r["structural_rate"]["rate_pct"] for r in shifts),2)
        delay_values=[d for c,*_,sh in CASES if sh!=0 for d in counts[name][c]["delays_penalized"]]
        a=pending_audit[name]
        equation=a["opened"]==a["structural"]+a["transient"]+a["unresolved"]
        summaries[name]={
            "cases":rows,"confirmed_structural_fpr_pct":structural,
            "transient_fpr_pct":transient,"combined_fpr_pure_null_pct":combined,
            "combined_fpr_all_nonlevel_pct":combined_nonlevel,
            "mean_directional_sensitivity_pct":sensitivity,
            "confirmed_delay_mean_penalty_75":round(statistics.mean(delay_values),3) if delay_values else None,
            "pending_accounting":{"opened":a["opened"],"resolved_structural":a["structural"],
                "resolved_transient":a["transient"],"unresolved":a["unresolved"],
                "equation_holds":equation},
            "pending_channel_isolation":{
                "series_checked":pending_channel_audit[name]["series_checked"],
                "mismatched_series":pending_channel_audit[name]["mismatched_series"],
                "matches_fast_ref":pending_channel_audit[name]["mismatched_series"]==0,
                "reference_opened_events":pending_channel_audit[name]["reference_opened_events"],
                "system_opened_events":pending_channel_audit[name]["system_opened_events"]},
            "promotion_rate_pct":round(100*sum(counts[name][c]["confirmed"] for c,*_ in CASES)/
                max(1,sum(counts[name][c]["provisional"] for c,*_ in CASES)),2)
                if name=="Consensus_Staging_Mode" else None
        }
    return {"stage":stage,"seed_base":seed_base,"trials_per_case":trials,
        "case_count":len(CASES),"generated_series":len(CASES)*trials,
        "same_series_for_all_four_systems":True,"selected_markov_threshold":h,
        "systems":summaries}

def choose(dev):
    rows=[]
    for h in HS:
        m=dev[str(h)]["systems"]["Markov_CUSUM"]
        fpr=max(m["confirmed_structural_fpr_pct"],m["transient_fpr_pct"],m["combined_fpr_pure_null_pct"],m["combined_fpr_all_nonlevel_pct"])
        rows.append((fpr,-m["mean_directional_sensitivity_pct"],m["confirmed_delay_mean_penalty_75"],h))
    return sorted(rows)[0][3],rows

def main():
    started=time.perf_counter()
    dev={}
    for h in HS:
        print(f"26M development: Markov H={h}",flush=True)
        dev[str(h)]=evaluate(DEV_SEED,TRIALS_DEV,h,"development_26M")
        pending_gate=pending_channel_gate(dev[str(h)])
        checkpoint={
            "experiment":"B-v7.1 development checkpoint",
            "branch":"experiment/b7-1-isolated-markov-router",
            "seed":DEV_SEED,"trials_per_case":TRIALS_DEV,"cases":len(CASES),
            "completed_thresholds":[float(v) for v in dev],
            "remaining_thresholds":[v for v in HS if str(v) not in dev],
            "pending_channel_isolation_gate":pending_gate,
            "development":dev,
        }
        DEV_CHECKPOINT.parent.mkdir(parents=True,exist_ok=True)
        DEV_CHECKPOINT.write_text(
            json.dumps(checkpoint,indent=2,ensure_ascii=False)+"\n",
            encoding="utf-8"
        )
        if not pending_gate["passed"]:
            raise AssertionError(
                "development_pending_channel_isolation_failed:"
                +json.dumps(pending_gate,sort_keys=True)
            )
    selected,ranking=choose(dev)
    print(f"Selected H={selected}; development ranking={ranking}",flush=True)
    hold=evaluate(HOLD_SEED,TRIALS_HOLD,selected,"isolated_validation_27M")
    report={"experiment":"B-v7.1 Channel Isolation, Markov Sign-CUSUM & Auto-Router",
        "branch":"experiment/b7-1-isolated-markov-router",
        "base_commit":"a2a443e516701ac868f68020c8cf2d997982bb1a",
        "reference_commit":"1f3f369f9c0b67344954d288c99d923d5b9b5c22",
        "seeds":{"development":DEV_SEED,"validation":HOLD_SEED},
        "trials_per_case":{"development":TRIALS_DEV,"validation":TRIALS_HOLD},
        "cases":8,"miss_delay_penalty":PENALTY,"development_thresholds":list(HS),
        "selected_markov_threshold":selected,"development_ranking":ranking,
        "development_pending_channel_isolation":{
            "all_thresholds_passed":all(
                pending_channel_gate(dev[str(h)])["passed"] for h in HS
            ),
            "by_threshold":{
                str(h):pending_channel_gate(dev[str(h)]) for h in HS
            }
        },
        "validation_pending_channel_isolation":pending_channel_gate(hold),
        "development":dev,"validation_27M":hold,
        "elapsed_seconds":round(time.perf_counter()-started,2)}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("\n=== B-v7.1 FINAL 27M VALIDATION ===",flush=True)
    for name,m in hold["systems"].items():
        print(f"{name} | Confirmed Structural FPR={m['confirmed_structural_fpr_pct']:.2f}%"
            f" | Transient FPR={m['transient_fpr_pct']:.2f}%"
            f" | Combined FPR(null)={m['combined_fpr_pure_null_pct']:.2f}%"
            f" | Combined FPR(nonlevel)={m['combined_fpr_all_nonlevel_pct']:.2f}%"
            f" | Mean Directional Sensitivity={m['mean_directional_sensitivity_pct']:.2f}%"
            f" | Confirmed Delay(mean, miss=75)={m['confirmed_delay_mean_penalty_75']}"
            f" | Promotion={m['promotion_rate_pct']}%"
            f" | PENDING={m['pending_accounting']}",flush=True)
    print(f"REPORT={OUT}",flush=True)
if __name__=="__main__":
    main()
