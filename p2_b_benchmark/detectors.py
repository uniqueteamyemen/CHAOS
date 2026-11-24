"""Independent P2-B detector candidates. Two named methods are explicitly adaptations.

FOCuS and R-FPOP implementations are documented research-inspired candidates, not
claims of exact reference-code or paper-conformance. BOCPD is a normal predictive
online run-length model; Post-Quiet Huber and Bartlett LRV are independent
robust-residual and HAC-standardized-residual detectors.
"""
from __future__ import annotations
import math
import numpy as np
from .engine import mad_sigma, register_detector

QUIET = 40
EPS = 1e-12

def _base(values):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or x.size <= QUIET or not np.all(np.isfinite(x)):
        raise ValueError("detector_requires_finite_1d_series_longer_than_40")
    q = x[:QUIET]
    scale = mad_sigma(q)
    return x, float(np.median(q)), float(scale)

def _abstain(scale):
    return not math.isfinite(scale) or scale <= 0

def focus(values):
    """FOCuS-inspired bounded multi-window online likelihood scan."""
    x, centre, scale = _base(values)
    if _abstain(scale): return {"hits": [], "metadata": {"status":"ABSTAIN","reason":"ZERO_QUIET_SCALE"}}
    windows=(4,8,12,20,32,52)
    hits=[]; last=-10**9
    for t in range(QUIET,len(x)):
        best=(0.0,0)
        for w in windows:
            seg=x[max(QUIET,t-w+1):t+1]-centre
            if seg.size<3: continue
            total=float(np.sum(seg)); score=abs(total)/(scale*math.sqrt(seg.size)+EPS)
            if score>best[0]: best=(score,1 if total>=0 else -1)
        if best[0]>=4.25 and t-last>=8:
            hits.append({"index":t,"sign":best[1],"detector":"focus_scan","score":best[0]}); last=t
    return {"hits":hits,"metadata":{"status":"OK","claim":"FOCuS-inspired bounded candidate scan","windows":list(windows),"threshold":4.25}}

def rfpop(values):
    """R-FPOP-inspired online robust segmentation with irrevocable first-crossing alerts.

    Segment-cost improvements are evaluated on bounded candidate split points.
    Once a split crosses the penalty, the alert is emitted immediately and
    cannot be revised by later observations. This causal adaptation is not
    represented as exact reference R-FPOP.
    """
    x, centre, scale = _base(values)
    if _abstain(scale):
        return {"hits": [], "metadata": {"status": "ABSTAIN", "reason": "ZERO_QUIET_SCALE"}}
    y = np.clip((x - centre) / scale, -4.0, 4.0)
    prefix = np.concatenate(([0.0], np.cumsum(y, dtype=float)))
    prefix2 = np.concatenate(([0.0], np.cumsum(y * y, dtype=float)))

    def segment_sse(start, end):
        count = end - start
        if count <= 0:
            return 0.0
        total = prefix[end] - prefix[start]
        total2 = prefix2[end] - prefix2[start]
        return max(0.0, float(total2 - total * total / count))

    hits = []
    candidates = [QUIET]
    min_seg = 8
    penalty = 8.0 * math.log(max(len(x), 2))
    last_emitted_end = QUIET
    for t in range(QUIET + 2 * min_seg - 1, len(x)):
        split = t - min_seg + 1
        if split >= last_emitted_end + min_seg:
            candidates.append(split)
        candidates = candidates[-80:]
        base_loss = segment_sse(last_emitted_end, t + 1)
        best_gain = 0.0
        best_split = None
        for s in candidates:
            if s < last_emitted_end + min_seg or (t + 1) - s < min_seg:
                continue
            gain = (base_loss - segment_sse(last_emitted_end, s)
                    - segment_sse(s, t + 1) - penalty)
            if gain > best_gain:
                best_gain, best_split = gain, s
        # Emit at the first time a candidate split becomes significant.
        # Do not revise this decision as the right-hand segment grows.
        if best_split is not None:
            left_mean = (prefix[best_split] - prefix[last_emitted_end]) / (best_split - last_emitted_end)
            right_mean = (prefix[t + 1] - prefix[best_split]) / (t + 1 - best_split)
            hits.append({
                "index": t, "sign": 1 if right_mean >= left_mean else -1,
                "detector": "rfpop_robust_segment", "gain": float(best_gain),
                "split_index": int(best_split),
            })
            last_emitted_end = t + 1
            candidates = [last_emitted_end]
    return {
        "hits": hits,
        "metadata": {
            "status": "OK", "claim": "R-FPOP-inspired bounded winsorized segmentation with irrevocable alerts",
            "loss": "winsorized_quadratic", "winsor_cap_sigma": 4.0,
            "penalty": penalty, "min_segment": min_seg, "candidate_cap": 80,
            "decision_policy": "first_crossing_irrevocable",
        },
    }

def bocpd(values):
    """Bayesian online change-point detection with a Gaussian predictive model."""
    x, centre, scale = _base(values)
    if _abstain(scale): return {"hits": [], "metadata": {"status":"ABSTAIN","reason":"ZERO_QUIET_SCALE"}}
    hazard=1/80.0; obs_var=scale*scale; prior_var=4*obs_var
    probs=np.array([1.0]); means=np.array([centre]); variances=np.array([prior_var])
    hits=[]; threshold=0.08
    for t in range(QUIET,len(x)):
        v=float(x[t]); pred=variances+obs_var
        logp=-0.5*(np.log(2*math.pi*pred)+(v-means)**2/pred); logp-=float(np.max(logp))
        like=np.exp(logp); grow=probs*like*(1-hazard); cp=float(np.sum(probs*like*hazard))
        nxt=np.concatenate(([cp],grow)); total=float(nxt.sum())
        if not math.isfinite(total) or total<=0:
            probs=np.array([1.]); means=np.array([centre]); variances=np.array([prior_var]); continue
        probs=nxt/total
        means=np.concatenate(([centre],(variances*v+obs_var*means)/pred))[:257]
        variances=np.concatenate(([prior_var],(variances*obs_var)/pred))[:257]
        probs=probs[:257]; probs/=float(probs.sum())
        cp_prob=float(probs[0])
        if cp_prob>=threshold and (not hits or t-hits[-1]["index"]>=10):
            hits.append({"index":t,"sign":1 if v>=centre else -1,"detector":"bocpd_change_probability","change_probability":cp_prob})
    return {"hits":hits,"metadata":{"status":"OK","hazard":hazard,"threshold":threshold,"run_length_cap":256,"model":"Gaussian predictive"}}

def post_quiet_huber(values):
    """Robust Huber-clipped residual run detector following the quiet calibration."""
    x, centre, scale = _base(values)
    if _abstain(scale): return {"hits": [], "metadata": {"status":"ABSTAIN","reason":"ZERO_QUIET_SCALE"}}
    clipped=np.clip((x-centre)/scale,-1.5,1.5); hits=[]
    run_sign=0; run_start=None; score=0.0
    for t in range(QUIET,len(x)):
        r=float(clipped[t]); sign=1 if r>0 else -1 if r<0 else 0
        if not sign or (run_sign and sign!=run_sign):
            run_sign,run_start,score=sign,(t if sign else None),(abs(r) if sign else 0.0)
        else:
            run_sign=sign; score+=abs(r)
        if run_start is not None and t-run_start+1>=5 and score>=6:
            hits.append({"index":t,"sign":run_sign,"detector":"post_quiet_huber_run","clipped_score":score})
            run_sign,run_start,score=0,None,0.0
    return {"hits":hits,"metadata":{"status":"OK","clip_sigma":1.5,"min_run":5,"score_threshold":6}}

def bartlett_lrv(values):
    """Bartlett-kernel HAC long-run-variance studentized residual detector."""
    x, centre, scale = _base(values)
    if _abstain(scale): return {"hits": [], "metadata": {"status":"ABSTAIN","reason":"ZERO_QUIET_SCALE"}}
    y=x-centre; window=24; min_points=16; threshold=2.25; hits=[]
    for t in range(QUIET,len(x)):
        prior=y[max(QUIET,t-window):t]
        if prior.size<min_points: continue
        demeaned=prior-float(np.mean(prior)); gamma0=float(np.dot(demeaned,demeaned)/prior.size)
        if gamma0<=0: continue
        lrv=gamma0; bw=max(1,int(math.sqrt(prior.size)))
        for lag in range(1,min(bw,prior.size-1)+1):
            cov=float(np.dot(demeaned[lag:],demeaned[:-lag])/prior.size)
            lrv+=2*(1-lag/(bw+1))*cov
        se=math.sqrt(max(lrv,EPS)/prior.size); score=float(y[t])/(se+EPS)
        if abs(score)>=threshold:
            hits.append({"index":t,"sign":1 if score>0 else -1,"detector":"bartlett_lrv_hac","studentized_residual":score})
    return {"hits":hits,"metadata":{"status":"OK","window":window,"min_points":min_points,"threshold":threshold,"kernel":"Bartlett","bandwidth":"floor_sqrt_n"}}

def register_all():
    specs=[
      ("FOCuS",focus,"online changepoint scan","FOCuS-inspired bounded multi-window candidate scan"),
      ("R-FPOP",rfpop,"robust functional pruning","R-FPOP-inspired bounded robust segmentation"),
      ("BOCPD",bocpd,"bayesian online changepoint","Gaussian predictive Bayesian online run-length model"),
      ("Post-Quiet Huber",post_quiet_huber,"robust residual detector","Huber-clipped post-quiet signed residual run"),
      ("Bartlett LRV",bartlett_lrv,"long-run variance detector","Bartlett-kernel HAC studentized residual"),
    ]
    for name,fn,family,description in specs:
        register_detector(name,fn,family=family,version="1.0.0",description=description,
                          parameters={"quiet_points":QUIET})

REGISTERED_ARMS=register_all()
