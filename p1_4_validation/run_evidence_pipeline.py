"""P1.4 evidence-first calibration, diagnostic and bounded Pilot runner."""
from __future__ import annotations
import argparse, hashlib, json, math, os, sys, time
from pathlib import Path
from typing import Any
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from p1_4_validation.injection_runner import (
    build_injected_case, calibrate_threshold, deterministic_seed,
    evaluate_online_hits, focus_reset_rearm, generate_ar_null_trace,
    injection_grid, match_r_fpop_boundary, select_ar_model, wilson_upper
)
from p2_b_benchmark.dataset import load_p2_economic_series
from p2_b_benchmark.p2c_engine import (
    bocpd_detector, focus_detector, post_quiet_huber_detector, r_fpop_segment
)
from real_data_stress_pipeline.production_pipeline import candidate_sha256

POSITIONS=(.30,.50,.70)
REPS=1000
P0=.10
FOCUS_GRID=(15,20,25,30,35,40,45,50,60,75,90)
HUBER_GRID=(4,6,8,10,12,14,16,20,24,32)
FPOP_GRID=(.5,.75,1,1.2,1.4,1.6,2,3,4,6,8,12,16)

def finite(x):
    if x is None: return None
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError): return None

def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.ndarray): return [clean(v) for v in x.tolist()]
    if isinstance(x,np.integer): return int(x)
    if isinstance(x,np.bool_): return bool(x)
    if isinstance(x,(float,np.floating)): return finite(x)
    return x

def canon(x):
    return (json.dumps(clean(x),ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()

def sha_bytes(x): return hashlib.sha256(x).hexdigest()
def sha_file(p): return sha_bytes(Path(p).read_bytes())
def safe_id(s): return hashlib.sha256(s.encode()).hexdigest()[:16]
def write_json(p,x):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp"); tmp.write_bytes(canon(x)); tmp.replace(p)
def live(deadline): return time.monotonic()<deadline

def failure_class(g):
    a=bool(g["adf_rejects_unit_root"]); k=bool(g["kpss_does_not_reject_level_stationarity"])
    if a and not k: return "ADF_PASS_KPSS_FAIL"
    if not a and not k: return "ADF_FAIL_KPSS_FAIL"
    if not a and k: return "ADF_FAIL_KPSS_PASS"
    raise ValueError("C1_MEMBER_UNEXPECTEDLY_PASSED_G1")

def load_g1(folder):
    rows={}
    files=sorted(Path(folder).glob("shard-*.json"))
    if len(files)!=4: raise ValueError(f"G1_SHARD_COUNT:{len(files)}")
    for path in files:
        for row in json.loads(path.read_text())["results"]:
            if row.get("source")!="gem": continue
            sid=str(row["id"])
            if sid in rows: raise ValueError(f"DUPLICATE_G1:{sid}")
            rows[sid]=row["g1"]
    if len(rows)!=458: raise ValueError(f"G1_COUNT:{len(rows)}")
    return rows

def load_inputs(a):
    manifest=json.loads(Path(a.manifest).read_text())
    protocol=json.loads(Path(a.protocol).read_text())
    selection=json.loads(Path(a.selection_json).read_text())
    if protocol.get("protocol_version")!="1.1.9": raise ValueError("PROTOCOL_VERSION_MISMATCH")
    frame=protocol.get("cohort_design",{}).get("selected_cohort_frame")
    if not isinstance(frame,dict): raise ValueError("FROZEN_SELECTED_COHORT_FRAME_MISSING")
    if frame.get("status")!="VERIFIED_SELECTION_ARTIFACT_NOT_EXECUTED":
        raise ValueError("SELECTED_COHORT_FRAME_STATUS_MISMATCH")
    if sha_file(a.prepared_zip)!=protocol["source_and_scope"]["prepared_artifact_sha256"]:
        raise ValueError("PREPARED_ARTIFACT_SHA_MISMATCH")
    meta=manifest["selection_artifact"]
    if sha_file(a.selection_json)!=meta["selection_json_sha256"]: raise ValueError("SELECTION_JSON_SHA_MISMATCH")
    if selection.get("protocol_id")!=protocol["protocol_id"]: raise ValueError("SELECTION_PROTOCOL_ID_MISMATCH")
    if selection.get("protocol_sha256")!=meta["protocol_sha256_at_selection"]:
        raise ValueError("SELECTION_FROZEN_PROTOCOL_SHA_MISMATCH")
    c1=sorted(str(x) for x in manifest["cohorts"]["C1"]["pilot_series_ids"])
    c2=sorted(str(x) for x in manifest["cohorts"]["C2"]["pilot_series_ids"])
    scope=manifest["pilot_scope"]
    scope_ids=sorted(str(x) for x in scope["series_ids"])
    if len(set(scope_ids))!=len(scope_ids): raise ValueError("DUPLICATE_SELECTED_COHORT_ID")
    if scope_ids!=sorted(c1+c2): raise ValueError("SELECTED_COHORT_FRAME_IDENTITY_MISMATCH")
    if frame.get("composition")!={"C1":len(c1),"C2":len(c2),"C3":0}:
        raise ValueError("PROTOCOL_COHORT_COMPOSITION_MISMATCH")
    if int(frame.get("selection_series_count",-1))!=len(scope_ids):
        raise ValueError("PROTOCOL_SELECTION_SERIES_COUNT_MISMATCH")
    if int(scope.get("series_count",-1))!=len(scope_ids):
        raise ValueError("MANIFEST_SELECTION_SERIES_COUNT_MISMATCH")
    if int(frame.get("run_cases_per_series",-1))!=int(scope["run_cases_per_series"]):
        raise ValueError("PROTOCOL_CASES_PER_SERIES_MISMATCH")
    if int(frame.get("source_selection_case_count",-1))!=int(scope["run_cases"]):
        raise ValueError("PROTOCOL_SELECTION_CASE_COUNT_MISMATCH")
    if int(frame.get("original_cases_per_series",0))+int(frame.get("injected_cases_per_series",0))!=int(frame["run_cases_per_series"]):
        raise ValueError("PROTOCOL_CASE_COMPOSITION_MISMATCH")
    selected_c1={str(r["series_id"]):r for r in selection["c1"]["pilot_series"]}
    selected_c2=sorted(str(r["series_id"]) for r in selection["c2"]["pilot_series"])
    if len(selected_c1)!=len(selection["c1"]["pilot_series"]) or c1!=sorted(selected_c1):
        raise ValueError("C1_IDENTITY_MISMATCH")
    if c2!=selected_c2: raise ValueError("C2_IDENTITY_MISMATCH")
    g1=load_g1(a.g1_shards_dir)
    missing_g1=sorted(set(c1)-set(g1))
    if missing_g1: raise ValueError(f"C1_G1_EVIDENCE_MISSING:{missing_g1}")
    classes={sid:failure_class(g1[sid]) for sid in c1}
    series,counts=load_p2_economic_series(a.prepared_zip)
    by_id={str(x["id"]):x for x in series}
    if len(by_id)!=509 or counts["series"]!=509: raise ValueError("ECONOMIC_UNIVERSE_MISMATCH")
    candidates={}
    for sid in c1:
        if sid not in by_id: raise ValueError(f"C1_SOURCE_MISSING:{sid}")
        digest=candidate_sha256(by_id[sid])
        if digest!=selected_c1[sid]["candidate_sha256"]: raise ValueError(f"C1_CANDIDATE_SHA_MISMATCH:{sid}")
        candidates[sid]=digest
    return {"manifest":manifest,"protocol":protocol,"selection":selection,"series":by_id,
      "c1_ids":c1,"c2_ids":c2,"selection_frame":frame,"classes":classes,
      "candidate_hashes":candidates,"counts":counts,
      "source_sha256":{"prepared_zip":sha_file(a.prepared_zip),"manifest":sha_file(a.manifest),
       "protocol":sha_file(a.protocol),"selection":sha_file(a.selection_json),
       "g1_shards":{p.name:sha_file(p) for p in sorted(Path(a.g1_shards_dir).glob("shard-*.json"))}}}
def seed_ledger(protocol,sid,pos,order,phase):
    return [deterministic_seed(protocol,sid,pos,order,phase,i) for i in range(REPS)]

def detector_maxima(trace):
    f=focus_detector(trace,threshold=1e100,return_score_trace=True)
    m=post_quiet_huber_detector(trace,scale_mode="mad",threshold=1e100,return_score_trace=True)
    b=post_quiet_huber_detector(trace,scale_mode="bartlett",threshold=1e100,return_score_trace=True)
    return {"FOCUS":finite(f.get("max_statistic")),
            "POST_QUIET_HUBER_MAD":finite(m.get("max_statistic")),
            "POST_QUIET_HUBER_BARTLETT":finite(b.get("max_statistic"))}

def p0_result(scores,threshold):
    values=[float(x) for x in scores if finite(x) is not None]
    alarms=sum(x>=float(threshold) for x in values)
    return {"valid_replicates":len(values),"alarm_traces":alarms,
            "p0":alarms/len(values) if values else None,
            "wilson_upper_95_one_sided":wilson_upper(alarms,len(values)),
            "status":"ESTIMABLE" if len(values)>=950 else "INCONCLUSIVE"}

def fpop_calibrate(dev,hold,deadline):
    grid=[]
    for mult in FPOP_GRID:
        if not live(deadline): return {"status":"PARTIAL_TIME_BUDGET","grid":grid}
        valid=alarms=0
        for trace in dev:
            if not live(deadline): return {"status":"PARTIAL_TIME_BUDGET","grid":grid}
            r=r_fpop_segment(trace,penalty_multiplier=float(mult))
            if r.get("status")!="OK": continue
            valid+=1; alarms+=int(bool(r.get("breakpoints")))
        upper=wilson_upper(alarms,valid)
        point={"penalty_multiplier":float(mult),"valid_replicates":valid,
               "alarm_traces":alarms,"p0":alarms/valid if valid else None,
               "wilson_upper_95_one_sided":upper}
        grid.append(point)
        if valid>=950 and upper is not None and upper<=P0:
            hv=ha=0
            for trace in hold:
                if not live(deadline):
                    return {"status":"PARTIAL_TIME_BUDGET","selected_development":point,"grid":grid}
                r=r_fpop_segment(trace,penalty_multiplier=float(mult))
                if r.get("status")!="OK": continue
                hv+=1; ha+=int(bool(r.get("breakpoints")))
            return {"status":"CALIBRATED","penalty_multiplier":float(mult),
                    "development":point,"holdout":p0_result([1.0 if i<ha else 0.0 for i in range(hv)],.5),
                    "grid":grid}
    return {"status":"NOT_CALIBRATABLE","reason":"NO_FROZEN_PENALTY_MET_DEVELOPMENT_P0","grid":grid}

def calibrate_series(sid,ctx,out,deadline):
    x=np.asarray(ctx["series"][sid]["values"],dtype=float); n=len(x)
    row={"series_id":sid,"cohort":"C1","g1_failure_class":ctx["classes"][sid],
         "candidate_sha256":ctx["candidate_hashes"][sid],"series_length":n,
         "protocol_version":ctx["protocol"]["protocol_version"],
         "protocol_sha256":ctx["source_sha256"]["protocol"],
         "source_sha256":ctx["source_sha256"],"positions":{},"calibration_status":"STARTED"}
    for pos in POSITIONS:
        if not live(deadline):
            row["calibration_status"]="PARTIAL_TIME_BUDGET"; break
        onset=int(math.floor(pos*n)); model=select_ar_model(x[:onset]); key=f"{pos:.2f}"
        pr={"position_fraction":pos,"break_index":onset,"ar_model_status":model.get("status"),
            "ar_model_reason":model.get("reason"),"ar_order":model.get("order"),
            "ar_coefficients":model.get("ar_coefficients"),"residual_sigma":model.get("residual_sigma"),
            "residual_pool_sha256":model.get("residual_pool_sha256"),"arms":{}}
        if model.get("status")!="OK":
            pr["status"]="NOT_ELIGIBLE"; pr["reason"]=model.get("reason")
            row["positions"][key]=pr; continue
        bank={phase:{arm:[] for arm in ("FOCUS","POST_QUIET_HUBER_MAD","POST_QUIET_HUBER_BARTLETT")}
              for phase in ("development","holdout")}
        ledgers={}; dev_traces=[]; hold_traces=[]
        for phase in ("development","holdout"):
            seeds=seed_ledger(ctx["protocol"]["protocol_version"],sid,pos,int(model["order"]),phase)
            ledgers[phase]=sha_bytes(canon(seeds))
            for seed in seeds:
                if not live(deadline):
                    pr["status"]="PARTIAL_TIME_BUDGET"; row["positions"][key]=pr
                    row["calibration_status"]="PARTIAL_TIME_BUDGET"
                    write_json(out/f"series-{safe_id(sid)}.json",row); return row
                trace=generate_ar_null_trace(model,x[:int(model["order"])],n,seed)
                (dev_traces if phase=="development" else hold_traces).append(trace)
                scores=detector_maxima(trace)
                for arm,score in scores.items():
                    if score is not None: bank[phase][arm].append(score)
        grids={"FOCUS":FOCUS_GRID,"POST_QUIET_HUBER_MAD":HUBER_GRID,"POST_QUIET_HUBER_BARTLETT":HUBER_GRID}
        for arm,grid in grids.items():
            dev=bank["development"][arm]; hold=bank["holdout"][arm]
            fit=calibrate_threshold(dev,grid,p0_target=P0,minimum_valid_replicates=950)
            threshold=fit.get("threshold") if fit.get("status")=="CALIBRATED" else None
            st=fit.get("status","INCONCLUSIVE")
            if arm=="FOCUS" and n<150: st="NOT_ELIGIBLE"
            pr["arms"][arm]={
              "status":st,"development":fit,"frozen_threshold":threshold,
              "holdout":p0_result(hold,float(threshold)) if threshold is not None else {"status":"NOT_CALIBRATED"},
              "development_max_statistics":dev,"holdout_max_statistics":hold,
              "development_seed_ledger_sha256":ledgers["development"],
              "holdout_seed_ledger_sha256":ledgers["holdout"],
              "valid_development_replicates":len(dev),"valid_holdout_replicates":len(hold)
            }
        if abs(pos-.30)<1e-9:
            pr["r_fpop_penalty"]=fpop_calibrate(dev_traces,hold_traces,deadline)
        pr["status"]=pr["arms"]["FOCUS"]["status"]
        row["positions"][key]=pr
        write_json(out/f"series-{safe_id(sid)}.json",row)
    if len(row["positions"])==3 and row["calibration_status"]=="STARTED": row["calibration_status"]="COMPLETE"
    elif row["calibration_status"]=="STARTED": row["calibration_status"]="PARTIAL"
    row["replay_command"]=(
      "python p1_4_validation/run_evidence_pipeline.py --phase calibrate "
      f"--series-id {sid} --prepared-zip /tmp/p2-prepared.zip "
      "--manifest p1_4_validation/cohort_manifest.json --protocol p1_4_validation/pilot_protocol.json "
      "--selection-json /tmp/cohort_selection.json --g1-shards-dir /tmp/p2-g1-shards "
      f"--output artifacts/p1_4/calibration/{safe_id(sid)} --budget-hours 5.5"
    )
    path=out/f"series-{safe_id(sid)}.json"; write_json(path,row); row["artifact_sha256"]=sha_file(path)
    return row

def load_calibrations(folder):
    rows={}
    for p in sorted(Path(folder).rglob("series-*.json")):
        x=json.loads(p.read_text()); sid=x["series_id"]
        if sid in rows: raise ValueError(f"DUPLICATE_CALIBRATION:{sid}")
        rows[sid]=x
    return rows

def aggregate_calibrations(rows,ctx,out):
    expected=set(ctx["c1_ids"])
    complete=sorted(sid for sid,x in rows.items() if x.get("calibration_status")=="COMPLETE"
                    and all(k in x.get("positions",{}) for k in ("0.30","0.50","0.70")))
    missing=sorted(expected-set(rows))
    report={"artifact_type":"P1_4_THRESHOLD_90_CALIBRATION",
      "status":"COMPLETE" if len(complete)==len(expected) and not missing else "PARTIAL",
      "planned_series":len(expected),"completed_series":len(complete),"missing_series_ids":missing,
      "null_replicates_per_series_position_phase":REPS,"positions":list(POSITIONS),
      "p0_target":P0,"protocol_sha256":ctx["source_sha256"]["protocol"],"series":rows}
    write_json(out/"calibration_results_all_strata.json",report)
    return report
def threshold_for(cal,sid,pos):
    row=cal["series"].get(sid,{}).get("positions",{}).get(f"{pos:.2f}",{})
    arm=row.get("arms",{}).get("FOCUS",{})
    if arm.get("status")=="CALIBRATED" and arm.get("frozen_threshold") is not None:
        return {"status":"CALIBRATED","threshold":arm["frozen_threshold"],"source":"THRESHOLD_90"}
    return {"status":"NOT_CALIBRATABLE","threshold":None,"source":None}

def rearm_overlap(context,cal,deadline):
    rows={}
    for sid in cal["series"]:
        if not live(deadline): break
        x=np.asarray(context["series"][sid]["values"],dtype=float)
        chosen=threshold_for(cal,sid,.30)
        if len(x)<150 or chosen["status"]!="CALIBRATED":
            rows[sid]={"status":"NOT_ELIGIBLE","reason":"FOCUS_MIN_N_150_REQUIRED" if len(x)<150 else "NO_FROZEN_ANCHOR_THRESHOLD"}
            continue
        onset=int(math.floor(.30*len(x))); model=select_ar_model(x[:onset])
        if model.get("status")!="OK": rows[sid]={"status":"NOT_ELIGIBLE","reason":model.get("reason")}; continue
        overlaps={f"{p:.2f}":0 for p in POSITIONS}; valid=invalid=hits=0; seeds=[]
        for rep in range(REPS):
            if not live(deadline): break
            seed=deterministic_seed(context["protocol"]["protocol_version"],sid,.30,int(model["order"]),"rearm",rep)
            seeds.append(seed)
            trace=generate_ar_null_trace(model,x[:int(model["order"])],len(x),seed)
            answer=focus_reset_rearm(trace,threshold=float(chosen["threshold"]))
            if answer.get("status")!="OK": invalid+=1; continue
            valid+=1; hits+=len(answer.get("hits",[])); intervals=answer.get("rearm_intervals",[])
            for pos in POSITIONS:
                point=int(math.floor(pos*len(x)))
                if any(int(w["start_inclusive"])<=point<int(w["end_exclusive"]) for w in intervals): overlaps[f"{pos:.2f}"]+=1
        rows[sid]={"status":"COMPLETE" if valid==REPS else ("INCONCLUSIVE" if valid<950 else "PARTIAL"),
          "threshold":chosen["threshold"],"threshold_source":chosen["source"],
          "planned_null_traces":REPS,"valid_null_traces":valid,"invalid_null_traces":invalid,
          "confirmed_hits":hits,"seed_ledger_sha256":sha_bytes(canon(seeds)),
          "overlap":{k:{"overlap_traces":v,"valid_traces":valid,"rate":v/valid if valid else None,
                        "status":"ESTIMABLE" if valid>=950 else "INCONCLUSIVE"} for k,v in overlaps.items()}}
    return {"artifact_type":"P1_4_REARM_OVERLAP_MEASUREMENT",
      "status":"COMPLETE" if len(rows)==len(cal["series"]) and all(x.get("status") in {"COMPLETE","NOT_ELIGIBLE"} for x in rows.values()) else "PARTIAL",
      "null_traces_per_series":REPS,"initial_calibration_observations":40,
      "post_hit_rearm_observations":20,"series":rows}

def reference_hits(values,mode):
    from structural_engine.isolated_break_detector_v1 import BreakDetectorV1
    result=BreakDetectorV1(mode=mode).analyze(values); hits=[]
    for event in result.get("structural_breaks",[]):
        t=event.get("detection_time"); sign=event.get("direction")
        if t is None or sign not in (-1,1): continue
        hits.append({"detection_index":int(t),"estimated_change_index":int(event.get("onset_time",event.get("start_index",t))),"sign":int(sign)})
    return {"status":"OK","hits":hits,"hit_count":len(hits)}

def detector_case(x,sid,case,cal,ctx):
    pos=float(case["position_fraction"]) if case.get("position_fraction") is not None else .30
    key=f"{pos:.2f}"; block=cal["series"][sid]["positions"].get(key,{})
    cfg=threshold_for(cal,sid,pos)
    out={"A_FAST":reference_hits(x,"fast"),"A_CONSENSUS":reference_hits(x,"consensus")}
    focus=None
    if cfg["status"]=="CALIBRATED":
        focus=focus_reset_rearm(x,threshold=float(cfg["threshold"]))
        item={"status":focus.get("status"),"threshold":cfg["threshold"],"source":cfg["source"],
              "hits":focus.get("hits",[]),"rearm_intervals":focus.get("rearm_intervals",[])}
        if case.get("true_break_index") is not None and focus.get("status")=="OK":
            item["outcome"]=evaluate_online_hits(focus.get("hits",[]),
              true_break_index=int(case["true_break_index"]),true_direction=int(case["direction"]),
              rearm_intervals=focus.get("rearm_intervals",[]))
        out["FOCUS"]=item
    else: out["FOCUS"]={"status":"NOT_ELIGIBLE","reason":"NO_FROZEN_POSITION_THRESHOLD"}
    for arm,mode in (("POST_QUIET_HUBER_MAD","mad"),("POST_QUIET_HUBER_BARTLETT","bartlett")):
        a=block.get("arms",{}).get(arm,{})
        threshold=a.get("frozen_threshold") if a.get("status")=="CALIBRATED" else None
        if threshold is None: out[arm]={"status":"NOT_ELIGIBLE","reason":"NO_FROZEN_POSITION_THRESHOLD"}; continue
        r=post_quiet_huber_detector(x,scale_mode=mode,threshold=float(threshold))
        z={"status":r.get("status"),"hits":r.get("hits",[]),"threshold":threshold}
        if case.get("true_break_index") is not None:
            z["outcome"]=evaluate_online_hits(r.get("hits",[]),true_break_index=int(case["true_break_index"]),true_direction=int(case["direction"]))
        out[arm]=z
    bocpd=bocpd_detector(x,diagnostics=True,export_posterior=True)
    feats=bocpd.get("posterior_feature_trace",[])
    out["BOCPD_FEATURES"]={"status":bocpd.get("status"),
      "posterior_pmf_sha256":bocpd.get("metadata",{}).get("posterior_pmf_trace_sha256"),
      "posterior_prefix_count":bocpd.get("metadata",{}).get("posterior_prefix_count",0),
      "role":"FEATURE_GENERATOR_NOT_INDEPENDENT_BINARY_DETECTOR",
      "feature_means":{k:(float(np.mean([float(v[k]) for v in feats])) if feats else None)
        for k in ("expected_run_length","run_length_variance","posterior_entropy","short_run_probability","change_probability","posterior_contrast_z")}}
    if case.get("true_break_index") is not None:
        confirmed=[]; corroboration=[]
        for hit in (focus or {}).get("hits",[]):
            t=int(hit["detection_index"])
            # Prefix ends at the online FOCuS detection; no future observations enter corroboration.
            pref=bocpd_detector(x[:t+1],diagnostics=False,export_posterior=True)
            trace=pref.get("posterior_feature_trace",[])
            last=[v for v in trace if int(v["index"])<=t][-5:]
            count=sum(float(v["short_run_probability"])>=.35 for v in last)
            ok=count>=3
            corroboration.append({"detection_index":t,"qualifying_prefixes":count,"required":3,"corroborated":ok})
            if ok: confirmed.append(hit)
        out["FOCUS_PLUS_BOCPD"]={"status":"OK" if cfg["status"]=="CALIBRATED" else "NOT_ELIGIBLE",
          "hits":confirmed,"corroboration":corroboration,
          "outcome":evaluate_online_hits(confirmed,true_break_index=int(case["true_break_index"]),
             true_direction=int(case["direction"]),rearm_intervals=(focus or {}).get("rearm_intervals",[])),
          "causal_prefix_policy":"Only observations through each FOCuS detection index are used."}
    penalty=block.get("r_fpop_penalty",{})
    multiplier=penalty.get("penalty_multiplier") if penalty.get("status")=="CALIBRATED" else None
    if multiplier is None: out["R-FPOP"]={"status":"NOT_ELIGIBLE","reason":"NO_FROZEN_NULL_PENALTY"}
    else:
        r=r_fpop_segment(x,penalty_multiplier=float(multiplier))
        f={"status":r.get("status"),"penalty_multiplier":multiplier,
           "breakpoints":r.get("breakpoints",[]),"role":"RETROSPECTIVE_SEGMENTER"}
        if case.get("true_break_index") is not None:
            f["outcome"]=match_r_fpop_boundary(r.get("breakpoints",[]),
             true_break_index=int(case["true_break_index"]),series_length=len(x))
        out["R-FPOP"]=f
    return out

def pilot_metrics(series_results):
    tools=("FOCUS","FOCUS_PLUS_BOCPD","POST_QUIET_HUBER_MAD","POST_QUIET_HUBER_BARTLETT","R-FPOP","A_FAST","A_CONSENSUS")
    output={}
    series_recalls={tool:{} for tool in tools}
    for sid,row in series_results.items():
        counts={tool:{"tp":0,"miss":0,"invalid":0,"not_eligible":0,"delay":[],"wrong_direction":0,"pre_onset":0} for tool in tools}
        for case in row["cases"]:
            if case.get("true_break_index") is None: continue
            outs=case.get("tool_outputs",{})
            for tool in tools:
                status=None; outcome=None
                if tool in ("A_FAST","A_CONSENSUS"):
                    hits=outs.get(tool,{}).get("hits",[])
                    correct=[h for h in hits if int(h["detection_index"])>=int(case["true_break_index"]) and int(h["sign"])==int(case["direction"])]
                    status="DETECTED" if correct else "MISSED"
                    if any(int(h["detection_index"])<int(case["true_break_index"]) for h in hits): counts[tool]["pre_onset"]+=1
                elif tool=="R-FPOP":
                    result=outs.get(tool,{}).get("outcome")
                    if result is None: continue
                    status="DETECTED" if result.get("matched") else "MISSED"
                else:
                    outcome=outs.get(tool,{}).get("outcome")
                    if outcome is None: continue
                    status=outcome.get("status")
                    counts[tool]["wrong_direction"]+=int(outcome.get("wrong_direction_alert_count",0))
                    counts[tool]["pre_onset"]+=int(outcome.get("pre_onset_alert_count",0))
                    if outcome.get("delay") is not None: counts[tool]["delay"].append(int(outcome["delay"]))
                if status=="DETECTED":
                    counts[tool]["tp"]+=1
                    if tool in ("A_FAST","A_CONSENSUS"):
                        detected=next((h for h in correct if int(h["detection_index"])>=int(case["true_break_index"])),None)
                        if detected: counts[tool]["delay"].append(int(detected["detection_index"])-int(case["true_break_index"]))
                elif status=="MISSED": counts[tool]["miss"]+=1
                elif status=="INVALID_INJECTION": counts[tool]["invalid"]+=1
                elif status=="NOT_ELIGIBLE": counts[tool]["not_eligible"]+=1
        for tool,c in counts.items():
            den=c["tp"]+c["miss"]
            if den>0: series_recalls[tool][sid]={"recall":c["tp"]/den,"tp":c["tp"],"eligible":den}
            c["median_delay"]=float(np.median(c["delay"])) if c["delay"] else None
            c["p90_delay"]=float(np.percentile(c["delay"],90)) if c["delay"] else None
            del c["delay"]
        row["metric_counts"]=counts
    rng=np.random.default_rng(20261125)
    for tool,rec in series_recalls.items():
        vals=np.asarray([r["recall"] for r in rec.values()],dtype=float)
        if len(vals)==0: output[tool]={"status":"NOT_ESTIMABLE","series_count":0}; continue
        boots=np.asarray([np.mean(rng.choice(vals,size=len(vals),replace=True)) for _ in range(2000)])
        output[tool]={"status":"ESTIMATED","per_series":rec,"series_count":len(vals),
          "mean_recall":float(np.mean(vals)),"median_recall":float(np.median(vals)),
          "iqr":[float(np.percentile(vals,25)),float(np.percentile(vals,75))],
          "series_cluster_bootstrap_95":[float(np.percentile(boots,2.5)),float(np.percentile(boots,97.5))],
          "bootstrap_replicates":2000,"independent_unit":"series"}
    common=sorted(set(series_recalls["FOCUS"])&set(series_recalls["FOCUS_PLUS_BOCPD"]))
    if common:
        d=np.asarray([series_recalls["FOCUS_PLUS_BOCPD"][s]["recall"]-series_recalls["FOCUS"][s]["recall"] for s in common])
        obs=abs(float(np.mean(d))); null=[abs(float(np.mean(d*rng.choice([-1.,1.],size=len(d))))) for _ in range(1000)]
        output["FOCUS_PLUS_BOCPD_incremental_value"]={"status":"ESTIMATED","paired_series":len(common),
          "mean_paired_recall_difference":float(np.mean(d)),
          "two_sided_series_sign_flip_p":float((1+sum(v>=obs for v in null))/(1+len(null))),
          "permutation_replicates":1000,"unit":"series"}
    else: output["FOCUS_PLUS_BOCPD_incremental_value"]={"status":"NOT_ESTIMABLE","paired_series":0}
    return output

def run_pilot(ctx,cal,out,deadline):
    cases_per_series=int(ctx["selection_frame"]["run_cases_per_series"])
    candidates=list(ctx["c1_ids"])
    chosen=[]
    for sid in candidates:
        if sid not in cal["series"]: continue
        if len(ctx["series"][sid]["values"])<150: continue
        if all(threshold_for(cal,sid,p)["status"]=="CALIBRATED" for p in POSITIONS): chosen.append(sid)
    # All actually eligible C1 IDs are included; no replacement and no fixed cap.
    if not chosen:
        final={"artifact_type":"P1_4_PILOT_RESULTS","status":"NOT_RUN",
          "candidate_series_ids":candidates,"selected_series_ids":[],"completed_series_ids":[],
          "eligible_series_count":0,"planned_cases_per_series":cases_per_series,
          "planned_cases":0,"processed_cases":0,"series":{},"metrics":pilot_metrics({})}
        write_json(out/"pilot_results.json",final)
        write_json(out/"pilot_run_manifest.json",{"manifest_id":"CHAOS_P1_4_PILOT_RUN_MANIFEST_V1",
          "protocol_version":ctx["protocol"]["protocol_version"],"protocol_sha256":ctx["source_sha256"]["protocol"],
          "source_sha256":ctx["source_sha256"],"source_commit":os.environ.get("GITHUB_SHA"),
          "workflow_run_id":os.environ.get("GITHUB_RUN_ID"),"workflow_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
          "candidate_series_ids":candidates,"selected_series_ids":[],"completed_series_ids":[],
          "planned_series_count":0,"planned_cases_per_series":cases_per_series,"planned_cases":0,
          "status":"NOT_RUN","reason":"NO_C1_SERIES_PASSED_CALIBRATION_AND_MINIMUM_LENGTH_GATES",
          "runner_sha256":sha_file(__file__),
          "p2c_engine_sha256":sha_file(ROOT/"p2_b_benchmark"/"p2c_engine.py"),
          "replay_command":"python p1_4_validation/run_evidence_pipeline.py --phase postprocess"})
        return final
    results={}; completed=[]; planned=len(chosen)*cases_per_series; processed=0
    for sid in chosen:
        if not live(deadline): break
        x=np.asarray(ctx["series"][sid]["values"],dtype=float)
        cases=[{"kind":"ORIGINAL","status":"PLANNED","values":x,"true_break_index":None,
          "position_fraction":None,"magnitude_sigma":None,"direction":None}]
        for injected in injection_grid(x):
            if injected.get("status")!="OK":
                cases.append({"kind":"INJECTION","status":"NOT_ELIGIBLE","values":None,
                  "reason":injected.get("reason"),"true_break_index":injected.get("true_break_index"),
                  "position_fraction":None,"magnitude_sigma":None,"direction":None})
            else:
                cases.append({"kind":"INJECTION","status":"PLANNED","values":injected["values"],
                  "true_break_index":injected["true_break_index"],"position_fraction":injected["position_fraction"],
                  "magnitude_sigma":injected["magnitude_sigma"],"direction":injected["direction"]})
        if len(cases)!=cases_per_series: raise ValueError("PILOT_CASE_COUNT_DOES_NOT_MATCH_FROZEN_PROTOCOL")
        case_rows=[]
        for i,case in enumerate(cases):
            if not live(deadline): break
            if case["status"]=="NOT_ELIGIBLE":
                case_rows.append({"case_index":i,"kind":"INJECTION","status":"NOT_ELIGIBLE","reason":case["reason"]})
                processed+=1; continue
            output=detector_case(np.asarray(case["values"],dtype=float),sid,case,cal,ctx)
            case_rows.append({"case_index":i,"kind":case["kind"],"status":"EXECUTED",
              "true_break_index":case.get("true_break_index"),"position_fraction":case.get("position_fraction"),
              "magnitude_sigma":case.get("magnitude_sigma"),"direction":case.get("direction"),
              "tool_outputs":output})
            processed+=1
        results[sid]={"g1_failure_class":ctx["classes"][sid],"series_length":len(x),
          "candidate_sha256":ctx["candidate_hashes"][sid],"case_count":len(case_rows),"cases":case_rows}
        write_json(out/"pilot_results_partial.json",{"artifact_type":"P1_4_PILOT_RESULTS","status":"PILOT_PARTIAL",
          "candidate_series_ids":candidates,"selected_series_ids":chosen,"completed_series_ids":completed,
          "eligible_series_count":len(chosen),"planned_cases_per_series":cases_per_series,
          "planned_cases":planned,"processed_cases":processed,"series":results})
        if len(case_rows)==cases_per_series: completed.append(sid)
    status="COMPLETE" if len(completed)==len(chosen) else "PILOT_PARTIAL"
    final={"artifact_type":"P1_4_PILOT_RESULTS","status":status,"candidate_series_ids":candidates,
      "selected_series_ids":chosen,"completed_series_ids":completed,"eligible_series_count":len(chosen),
      "planned_cases_per_series":cases_per_series,"planned_cases":planned,"processed_cases":processed,
      "series":results,"metrics":pilot_metrics(results)}
    write_json(out/"pilot_results.json",final)
    manifest={"manifest_id":"CHAOS_P1_4_PILOT_RUN_MANIFEST_V1",
      "protocol_version":ctx["protocol"]["protocol_version"],"protocol_sha256":ctx["source_sha256"]["protocol"],
      "source_sha256":ctx["source_sha256"],"source_commit":os.environ.get("GITHUB_SHA"),
      "workflow_run_id":os.environ.get("GITHUB_RUN_ID"),"workflow_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
      "candidate_series_ids":candidates,"selected_series_ids":chosen,"completed_series_ids":completed,
      "failure_classes":{s:ctx["classes"][s] for s in chosen},"planned_series_count":len(chosen),
      "planned_cases_per_series":cases_per_series,"planned_cases":planned,"processed_cases":processed,
      "status":status,"runner_sha256":sha_file(__file__),
      "p2c_engine_sha256":sha_file(ROOT/"p2_b_benchmark"/"p2c_engine.py"),
      "replay_command":"python p1_4_validation/run_evidence_pipeline.py --phase postprocess"}
    write_json(out/"pilot_run_manifest.json",manifest)
    return final
def write_inventory(out):
    inventory={}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name not in ("artifact_sha256_inventory.json","SHA256SUMS.txt"):
            inventory[p.relative_to(out).as_posix()]=sha_file(p)
    write_json(out/"artifact_sha256_inventory.json",inventory)

def postprocess(ctx,cal_dir,out,deadline):
    out.mkdir(parents=True,exist_ok=True)
    rows={}
    for p in cal_dir.rglob("series-*.json"):
        x=json.loads(p.read_text()); sid=x["series_id"]
        if sid in rows: raise ValueError(f"DUPLICATE_CALIBRATION:{sid}")
        rows[sid]=x
    expected=set(ctx["c1_ids"])
    unexpected=sorted(set(rows)-expected)
    if unexpected: raise ValueError(f"UNEXPECTED_CALIBRATION_ID:{unexpected}")
    complete=sum(x.get("calibration_status")=="COMPLETE" for x in rows.values())
    missing=sorted(expected-set(rows))
    calibration_complete=(complete==len(expected) and not missing)
    cal={"artifact_type":"P1_4_THRESHOLD_90_CALIBRATION",
      "status":"COMPLETE" if calibration_complete else "PARTIAL",
      "planned_series":len(expected),"completed_series":complete,
      "missing_series_ids":missing,"replicates_per_phase":REPS,
      "positions":list(POSITIONS),"p0_target":P0,
      "protocol_sha256":ctx["source_sha256"]["protocol"],"series":rows}
    write_json(out/"calibration_results_all_strata.json",cal)
    if cal["status"]=="COMPLETE":
        rearm=rearm_overlap(ctx,cal,deadline)
    else:
        rearm={"artifact_type":"P1_4_REARM_OVERLAP_MEASUREMENT","status":"NOT_RUN",
          "reason":"THRESHOLD_90_CALIBRATION_INCOMPLETE","series":{}}
    write_json(out/"rearm_overlap_results.json",rearm)
    if cal["status"]=="COMPLETE" and live(deadline):
        pilot=run_pilot(ctx,cal,out,deadline)
    else:
        pilot={"status":"NOT_RUN","completed_series_ids":[]}
        write_json(out/"pilot_results.json",{"artifact_type":"P1_4_PILOT_RESULTS","status":"NOT_RUN",
          "candidate_series_count":len(ctx["c1_ids"]),"selected_series_ids":[],
          "planned_series_count":None,
          "planned_cases_per_series":int(ctx["selection_frame"]["run_cases_per_series"]),
          "planned_cases":None,"series":{}})
        write_json(out/"pilot_run_manifest.json",{"manifest_id":"CHAOS_P1_4_PILOT_RUN_MANIFEST_V1",
          "status":"NOT_RUN","reason":"CALIBRATION_INCOMPLETE_OR_BUDGET_EXHAUSTED",
          "source_commit":os.environ.get("GITHUB_SHA"),"workflow_run_id":os.environ.get("GITHUB_RUN_ID"),
          "protocol_version":ctx["protocol"]["protocol_version"],
          "protocol_sha256":ctx["source_sha256"]["protocol"],
          "source_sha256":ctx["source_sha256"],"candidate_series_ids":ctx["c1_ids"],
          "selected_series_ids":[],
          "replay_command":"python p1_4_validation/run_evidence_pipeline.py --phase postprocess"})
    decision="PARTIAL_VALIDATION" if pilot.get("completed_series_ids") else "INCONCLUSIVE"
    report={"artifact_type":"P1_4_ENGINE_PILOT_DECISION","decision":decision,
      "scope":"C1_FROZEN_PILOT_ONLY",
      "reason":"C1-only detector comparator Pilot; C2 and C3 remain unvalidated. No production authorization.",
      "calibration_status":cal["status"],"rearm_status":rearm.get("status"),
      "pilot_status":pilot.get("status"),
      "threshold_200_extension":"NOT_EXECUTED_ENGINE_SCOPE",
      "track_b_diagnostics":"NOT_EXECUTED_ENGINE_SCOPE",
      "C2_executed":False,"C3_status":"PENDING_EXTERNAL_EVIDENCE",
      "source_commit":os.environ.get("GITHUB_SHA"),"run_id":os.environ.get("GITHUB_RUN_ID"),
      "protocol_sha256":ctx["source_sha256"]["protocol"],
      "replay_command":"python p1_4_validation/run_evidence_pipeline.py --phase postprocess"}
    write_json(out/"p1_4_engine_pilot_decision.json",report)
    write_json(out/"execution_summary.json",{"calibration":cal["status"],
      "candidate_c1_series":len(expected),"completed_calibration_series":complete,
      "missing_calibration_series":missing,"rearm":rearm.get("status"),
      "pilot":pilot.get("status"),"decision":decision,
      "threshold_200_extension":"NOT_EXECUTED_ENGINE_SCOPE",
      "track_b_diagnostics":"NOT_EXECUTED_ENGINE_SCOPE"})
    write_inventory(out)
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--phase",choices=("calibrate","postprocess"),required=True)
    ap.add_argument("--series-id")
    ap.add_argument("--prepared-zip",required=True)
    ap.add_argument("--manifest",required=True)
    ap.add_argument("--protocol",required=True)
    ap.add_argument("--selection-json",required=True)
    ap.add_argument("--g1-shards-dir",required=True)
    ap.add_argument("--calibration-dir")
    ap.add_argument("--output",required=True)
    ap.add_argument("--budget-hours",type=float,default=5.5)
    a=ap.parse_args()
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+min(a.budget_hours*3600,330*60)
    ctx=load_inputs(a)
    if a.phase=="calibrate":
        if a.series_id not in ctx["classes"]: raise ValueError("SERIES_NOT_IN_FROZEN_C1_PILOT")
        row=calibrate_series(a.series_id,ctx,out,deadline)
        write_json(out/"calibration_job_manifest.json",{
          "series_id":a.series_id,"status":row.get("calibration_status"),
          "source_commit":os.environ.get("GITHUB_SHA"),
          "workflow_run_id":os.environ.get("GITHUB_RUN_ID"),
          "protocol_sha256":ctx["source_sha256"]["protocol"],
          "replay_command":row.get("replay_command")})
        return 0
    if not a.calibration_dir: raise ValueError("CALIBRATION_DIR_REQUIRED")
    preflight={"artifact_type":"P1_4_EVIDENCE_PIPELINE_PREFLIGHT","status":"PASS",
      "C1_count":len(ctx["classes"]),"C2_pilot_count":len(ctx["manifest"]["cohorts"]["C2"]["pilot_series_ids"]),
      "C1_failure_class_counts":{c:sum(v==c for v in ctx["classes"].values()) for c in
        ("ADF_PASS_KPSS_FAIL","ADF_FAIL_KPSS_FAIL","ADF_FAIL_KPSS_PASS")},
      "C3_status":ctx["manifest"]["cohorts"]["C3"]["status"],"source_sha256":ctx["source_sha256"],
      "raw_values_written_to_output":False,"A_FAST_A_CONSENSUS_modified":False}
    write_json(out/"integrity_report.json",preflight)
    postprocess(ctx,Path(a.calibration_dir),out,deadline)
    return 0

if __name__=="__main__": raise SystemExit(main())
