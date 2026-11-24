from __future__ import annotations
import json, math, re
from typing import Any, Callable
import numpy as np

BASELINE_MODES = {"A_FAST":"fast","A_MARKOV_CUSUM":"markov_cusum","A_CONSENSUS":"consensus"}
PARALLEL_FUSION_ARMS = ("G","H","J","K","I")
VARIANTS = {**{a:{"kind":"break_detector_v1","mode":m} for a,m in BASELINE_MODES.items()},
"G":{"kind":"parallel_fusion","h":12.5,"transition":"reset"},
"H":{"kind":"parallel_fusion","h":12.5,"transition":"hold"},
"J":{"kind":"parallel_fusion","h":14.5,"transition":"hold"},
"K":{"kind":"parallel_fusion","h":15.5,"transition":"hold"},
"I":{"kind":"parallel_fusion","h":16.5,"transition":"hold"}}
_EXTENSION_RUNNERS: dict[str,Callable] = {}

def normalize_detector_key(name:str)->str:
    if not isinstance(name,str) or not name.strip(): raise ValueError("detector_name_must_be_nonempty_string")
    key=re.sub(r"[^A-Z0-9]+","_",name.strip().upper()).strip("_")
    if not key or not key[0].isalpha(): raise ValueError("detector_name_must_start_with_letter")
    return key

def register_detector(name:str,runner:Callable,*,family:str,version:str,description:str,parameters:dict|None=None)->str:
    key=normalize_detector_key(name)
    if key in VARIANTS or key in _EXTENSION_RUNNERS: raise ValueError(f"detector_arm_already_registered:{key}")
    if not callable(runner): raise TypeError("detector_runner_must_be_callable")
    if not all(isinstance(v,str) and v.strip() for v in (family,version,description)): raise ValueError("detector_family_version_description_required")
    meta={"kind":"extension","display_name":name.strip(),"family":family.strip(),"version":version.strip(),"description":description.strip(),"parameters":parameters or {}}
    json.dumps(meta,ensure_ascii=False,allow_nan=False)
    VARIANTS[key]=meta; _EXTENSION_RUNNERS[key]=runner
    return key

def _normalize_extension_result(raw:dict,size:int,arm:str)->dict:
    if not isinstance(raw,dict) or not isinstance(raw.get("hits"),list): raise TypeError(f"{arm}_runner_must_return_dict_with_hits_list")
    hits=[]
    for h in raw["hits"]:
        if not isinstance(h,dict): raise TypeError(f"{arm}_hit_must_be_dict")
        i=h.get("index",h.get("time")); s=h.get("sign",h.get("direction"))
        if isinstance(i,bool) or not isinstance(i,(int,np.integer)) or not 0<=int(i)<size: raise ValueError(f"{arm}_hit_index_invalid")
        if isinstance(s,bool) or int(s) not in (-1,1): raise ValueError(f"{arm}_hit_sign_invalid")
        item=dict(h); item.update(index=int(i),sign=int(s),detector=str(h.get("detector",arm))); hits.append(item)
    hits.sort(key=lambda h:(h["index"],h["sign"],h["detector"]))
    events=[]
    for e in raw.get("events",[]):
        if not isinstance(e,dict): raise TypeError(f"{arm}_event_must_be_dict")
        i=e.get("start_index",e.get("index")); s=e.get("sign",e.get("direction"))
        if isinstance(i,bool) or not isinstance(i,(int,np.integer)) or not 0<=int(i)<size: raise ValueError(f"{arm}_event_index_invalid")
        if isinstance(s,bool) or int(s) not in (-1,1): raise ValueError(f"{arm}_event_sign_invalid")
        item=dict(e); item.update(start_index=int(i),sign=int(s)); events.append(item)
    metadata=raw.get("metadata",{})
    if not isinstance(metadata,dict): raise TypeError(f"{arm}_metadata_must_be_dict")
    json.dumps(metadata,ensure_ascii=False,allow_nan=False)
    return {"hits":hits,"events":events,"metadata":metadata}

def run_registered_detector(values,arm:str,*,causal_audit:bool=False)->dict:
    if arm not in _EXTENSION_RUNNERS: raise ValueError(f"unknown_extension_detector:{arm}")
    x=np.asarray(values,dtype=float)
    if x.ndim!=1 or x.size<1 or not np.all(np.isfinite(x)): raise ValueError("extension_input_must_be_finite_1d")
    runner=_EXTENSION_RUNNERS[arm]; normalized=_normalize_extension_result(runner(x.copy()),x.size,arm); violations=0
    if causal_audit:
        for h in normalized["hits"]:
            t=h["index"]; p=_normalize_extension_result(runner(x[:t+1].copy()),t+1,arm)
            if not any(q["index"]==t and q["sign"]==h["sign"] and q["detector"]==h["detector"] for q in p["hits"]): violations+=1
        for e in normalized["events"]:
            t=e["start_index"]; p=_normalize_extension_result(runner(x[:t+1].copy()),t+1,arm)
            if not any(q["start_index"]==t and q["sign"]==e["sign"] for q in p["events"]): violations+=1
    return {"hits":normalized["hits"],"events":normalized["events"],"event_count":len(normalized["events"]) or len(normalized["hits"]),
            "causal_audit_violations":violations if causal_audit else None,
            "causal_audit_unverifiable_prefixes":0 if causal_audit else None,"transition_periods":0,"metadata":normalized["metadata"]}

def mad_sigma(values)->float:
    a=np.asarray(values,dtype=float)
    if not a.size or not np.all(np.isfinite(a)): return 0.0
    return float(1.4826*np.median(np.abs(a-np.median(a))))

def _rolling_sigma(x:np.ndarray,window:int,min_points:int=8):
    out=[]
    for i in range(x.size):
        prior=x[max(0,i-window):i]
        if prior.size<min_points: out.append(None)
        else:
            s=mad_sigma(prior); out.append(s if s>0 and math.isfinite(s) else None)
    return out

def run_parallel_fusion(values,*,variant:str,quiet_points:int=40)->dict:
    if variant not in PARALLEL_FUSION_ARMS: raise ValueError(f"unknown_parallel_fusion_variant:{variant}")
    x=np.asarray(values,dtype=float)
    if x.ndim!=1 or x.size<60 or not np.all(np.isfinite(x)): raise ValueError("series_must_be_finite_1d_with_at_least_60_points")
    if quiet_points<8 or quiet_points>=x.size: raise ValueError("quiet_window_invalid")
    quiet=x[:quiet_points]; bias=float(np.median(quiet)); sigma=mad_sigma(quiet)
    if not math.isfinite(sigma) or sigma<=0: raise ValueError("quiet_sigma_must_be_positive")
    short=_rolling_sigma(x,12); long=_rolling_sigma(x,52); cap=2*sigma; high_gate=1.5*sigma
    transitions=[s is not None and l is not None and l>0 and s>1.2*l for s,l in zip(short,long)]
    hits=[]; streak=[]; streak_sign=None
    for i,v in enumerate(x):
        ss=short[i]; high=ss is not None and ss>high_gate; scale=ss if high else long[i]
        if scale is None or scale<=0: streak=[]; streak_sign=None; continue
        z=float(v-bias); threshold=0 if high else 3*min(scale,cap); required=13 if high else 3
        sign=1 if z>0 else -1 if z<0 else 0
        if sign and abs(z)>=threshold:
            if streak_sign is not None and sign!=streak_sign: streak=[]
            streak.append(i); streak_sign=sign
        else: streak=[]; streak_sign=None
        if len(streak)>=required:
            hits.append({"index":i,"sign":sign,"detector":"sign_run","priority":1}); streak=[]; streak_sign=None
    pos=neg=0.0; h=float(VARIANTS[variant]["h"])
    for i,v in enumerate(x):
        scale=long[i]
        if scale is None or scale<=0: continue
        if transitions[i]:
            if VARIANTS[variant]["transition"]=="reset": pos=neg=0.0
            continue
        z=float(v-bias); pos=max(0.0,pos+z-.5*scale); neg=max(0.0,neg-z-.5*scale); threshold=h*scale
        if pos>threshold: hits.append({"index":i,"sign":1,"detector":"cusum_positive","priority":2}); pos=0.0
        if neg>threshold: hits.append({"index":i,"sign":-1,"detector":"cusum_negative","priority":2}); neg=0.0
    hits.sort(key=lambda q:(q["index"],q["priority"],q["detector"]))
    events=[]; active=None; calm=0; last={}; by_index={}
    for hit in hits: by_index.setdefault(hit["index"],[]).append(hit)
    for i,v in enumerate(x):
        scale=long[i] if long[i] is not None else sigma; z=float(v-bias)
        calm=calm+1 if abs(z)<=.5*scale else 0
        for hit in by_index.get(i,[]):
            sign=hit["sign"]
            if active is None or sign!=active["sign"] or calm>=6:
                last={}; active={"start_index":i,"end_index":i,"sign":sign,"detectors":[],"evidence":[]}; events.append(active)
            key=(hit["detector"],sign); item=dict(hit); prev=last.get(key)
            if prev is not None and i-prev<26: item["notification_suppressed"]="same_event_directional_cooldown"
            last[key]=i; active["evidence"].append(item)
            if hit["detector"] not in active["detectors"]: active["detectors"].append(hit["detector"])
            active["end_index"]=i; calm=0
    for e in events: e["evidence_count"]=len(e["evidence"])
    return {"variant":variant,"hits":hits,"events":events,"quiet_bias":bias,"quiet_sigma":sigma,"transition_periods":sum(transitions)}

def audit_parallel_prefix_invariance(values,variant:str)->int:
    x=np.asarray(values,dtype=float); cut=max(60,int(x.size*.65))
    if cut>=x.size: return 0
    altered=x.copy(); altered[cut:]=altered[cut:][::-1]*-1.7+.31
    a=run_parallel_fusion(x[:cut],variant=variant); b=run_parallel_fusion(altered,variant=variant)
    ht=lambda rows:[(int(h["index"]),int(h["sign"]),str(h["detector"])) for h in rows if int(h["index"])<cut]
    def et(rows):
        out=[]
        for e in rows:
            ev=[q for q in e["evidence"] if q["index"]<cut]
            if ev: out.append((e["start_index"],e["sign"],tuple((q["index"],q["sign"],q["detector"],q.get("notification_suppressed")) for q in ev)))
        return out
    return int(ht(a["hits"])!=ht(b["hits"]) or et(a["events"])!=et(b["events"]))

def run_baseline(values,*,causal_audit:bool=False)->dict:
    x=np.asarray(values,dtype=float)
    from structural_engine.isolated_break_detector_v1 import BreakDetectorV1
    out={}
    for arm,mode in BASELINE_MODES.items():
        result=BreakDetectorV1(mode=mode).analyze(x); events=[]; violations=0; unverifiable=0
        for event in result.get("structural_breaks",[]):
            dt=event.get("detection_time")
            if dt is None: continue
            t=int(dt); direction=int(event.get("direction",0)); events.append({"time":t,"direction":direction})
            if causal_audit:
                if t<0 or t>=x.size: violations+=1; continue
                minimum=BreakDetectorV1.MIN_FULL_CONSENSUS_LENGTH if mode=="consensus" else BreakDetectorV1.MIN_SERIES_LENGTH
                if t+1<minimum: unverifiable+=1; continue
                pref=BreakDetectorV1(mode=mode).analyze(x[:t+1])
                if not any(int(c.get("detection_time",-1))==t and int(c.get("direction",0))==direction for c in pref.get("structural_breaks",[])): violations+=1
        out[arm]={"hits":events,"event_count":len(events),"causal_audit_violations":violations if causal_audit else None,
                  "causal_audit_unverifiable_prefixes":unverifiable if causal_audit else None}
    return out

def run_all(values,*,causal_audit:bool=False)->dict:
    out=run_baseline(values,causal_audit=causal_audit)
    for arm in PARALLEL_FUSION_ARMS:
        r=run_parallel_fusion(values,variant=arm)
        out[arm]={"hits":r["hits"],"events":r["events"],"event_count":len(r["events"]),"transition_periods":r["transition_periods"],
                  "causal_audit_violations":audit_parallel_prefix_invariance(values,arm) if causal_audit else None,
                  "causal_audit_unverifiable_prefixes":0 if causal_audit else None}
    for arm in tuple(_EXTENSION_RUNNERS): out[arm]=run_registered_detector(values,arm,causal_audit=causal_audit)
    return out

def score_injected(result,*,onset:int,sign:int)->dict:
    out={}
    for arm,payload in result.items():
        hits=payload.get("hits",[])
        correct=[int(h.get("time",h.get("index",-1))) for h in hits if int(h.get("time",h.get("index",-1)))>=onset and int(h.get("direction",h.get("sign",0)))==sign]
        wrong=[h for h in hits if int(h.get("time",h.get("index",-1)))>=onset and int(h.get("direction",h.get("sign",0)))==-sign]
        pre=[h for h in hits if 52<=int(h.get("time",h.get("index",-1)))<onset]
        first=min(correct) if correct else None
        out[arm]={"detected":first is not None,"delay":first-onset if first is not None else None,"pre_onset_alert":bool(pre),"wrong_direction":bool(wrong),"missed":first is None}
    return out
