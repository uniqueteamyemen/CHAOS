from __future__ import annotations
import argparse, csv, hashlib, json, math, statistics, sys, tempfile, zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ARTIFACT_SHA256="5f5b0c571c1423caef4cfc9001271c8bea261f1b89e2ba0a341f733f677ed683"
PROVENANCE_ARTIFACT_SHA256="7b0fa5105c763b7ec917acacec4866457d8f96164ea3632712dea9edbd4e9467"
QUERY_FLOOR=4.5
BIN_WIDTH=0.1
MIN_N=50
GFT_MIN_FIT=90.0
WINDOW_YEARS=5
THRESHOLDS=(4.5,5.0,5.5,6.0)
KNOWN_EXCLUSION={
 "event_id":"nc21364840","associated_merged_event_id":"nc40157006",
 "disposition":"EXCLUDED_UPSTREAM_COMCAT_INDEX_MISMATCH",
 "basis":"External review identified this non-preferred ComCat product as an index mismatch for the merged event.",
 "handling":"Document only; do not re-fetch, re-add, or include in the accepted catalog or Mc calculations."
}

def sha256(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
 return h.hexdigest()

def read_json(path):
 with Path(path).open(encoding="utf-8") as f: return json.load(f)

def rows(path):
 with Path(path).open(encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))

def utc_year(value):
 dt=datetime.fromisoformat(value.replace("Z","+00:00"))
 if dt.tzinfo is None: raise ValueError("timestamp_without_timezone:"+value)
 return dt.astimezone(timezone.utc).year

def estimate_mc(values):
 mags=[round(float(x),1) for x in values]; n=len(mags)
 out={"event_count":n,"min_observed_magnitude":min(mags) if mags else None,
      "max_observed_magnitude":max(mags) if mags else None,"max_curvature_mc":None,
      "gft_mc":None,"gft_fit_percent_at_mc":None,"b_value_at_gft_mc":None,
      "mc_estimate":None,"status":"INSUFFICIENT_EVENTS"}
 if n<MIN_N: return out
 bins=Counter(mags); top=max(bins.values())
 maxc=min(m for m,c in bins.items() if c==top)
 out.update(max_curvature_mc=maxc,max_curvature_bin_count=top)
 candidates=[m for m in sorted(bins) if m>=maxc and sum(v>=m for v in mags)>=MIN_N]
 if len(bins)<4 or not candidates:
  out["status"]="INSUFFICIENT_MAGNITUDE_RESOLUTION"; return out
 picked=None
 for mc in candidates:
  tail=[m for m in mags if m>=mc]
  denom=statistics.fmean(tail)-(mc-BIN_WIDTH/2)
  if denom<=0: continue
  b=math.log10(math.e)/denom
  if not math.isfinite(b) or b<=0: continue
  axis=[i*BIN_WIDTH for i in range(round(mc/BIN_WIDTH),round(max(mags)/BIN_WIDTH)+1)]
  obs=[sum(v>=x-1e-9 for v in mags) for x in axis]
  pred=[len(tail)*10**(-b*(x-mc)) for x in axis]
  fit=100*(1-sum(abs(a-p) for a,p in zip(obs,pred))/sum(obs))
  if fit>=GFT_MIN_FIT:
   picked=(round(mc,1),fit,b); break
 if picked is None:
  out["status"]="GFT_NOT_PASSED"; return out
 gft,fit,b=picked; mc=max(maxc,gft)
 out.update(gft_mc=gft,gft_fit_percent_at_mc=round(fit,4),b_value_at_gft_mc=round(b,6),
            mc_estimate=round(mc,1),boundary_censored_at_query_floor=mc<=QUERY_FLOOR+1e-9,
            status="ESTIMATED_LEFT_TRUNCATION_BOUNDARY" if mc<=QUERY_FLOOR+1e-9 else "ESTIMATED_PENDING_REVIEW")
 return out

def windows(start,end):
 out=[]; s=start
 while s<=end:
  e=min(s+WINDOW_YEARS,end+1); out.append({"start_year":s,"end_year_exclusive":e}); s=e
 return out

def sensitivity(events,mc):
 vals=[e["magnitude"] for e in events]; m=mc.get("mc_estimate"); boundary=mc.get("boundary_censored_at_query_floor",False); out=[]
 for t in THRESHOLDS:
  n=sum(v>=t-1e-9 for v in vals)
  if m is None: gate="UNRESOLVED_MC_NOT_ESTIMABLE"
  elif boundary: gate="UNRESOLVED_LEFT_TRUNCATED_AT_QUERY_FLOOR" if t<=QUERY_FLOOR else "CANDIDATE_ABOVE_CATALOG_FLOOR_NOT_CERTIFIED"
  elif t+1e-9<m: gate="NOT_SUPPORTED_BELOW_ESTIMATED_MC"
  else: gate="CANDIDATE_SUPPORTED_BY_POINT_ESTIMATE_PENDING_REVIEW"
  out.append({"analysis_threshold":t,"events_retained":n,"retained_fraction":round(n/len(vals),6) if vals else None,
              "threshold_gate":gate,"threshold_is_not_an_mc_estimate":True})
 return out

def analyze(source_zip,prov_zip,config_dir,output_dir):
 source_digest=sha256(source_zip); prov_digest=sha256(prov_zip)
 if source_digest!=SOURCE_ARTIFACT_SHA256: raise ValueError("source_artifact_sha256_mismatch:"+source_digest)
 if prov_digest!=PROVENANCE_ARTIFACT_SHA256: raise ValueError("provenance_artifact_sha256_mismatch:"+prov_digest)
 with tempfile.TemporaryDirectory(prefix="p2a-mc-") as tmp:
  root=Path(tmp); src=root/"source"; prov=root/"provenance"; src.mkdir(); prov.mkdir()
  for archive,dest,label in [(source_zip,src,"source"),(prov_zip,prov,"provenance")]:
   with zipfile.ZipFile(archive) as z:
    bad=z.testzip()
    if bad: raise ValueError(label+"_zip_crc_failure:"+bad)
    z.extractall(dest)
  source_summary=read_json(src/"summary.json")
  provenance_summary=read_json(prov/"artifacts/p2_a/magnitude_provenance/P2_A_MAGNITUDE_PROVENANCE_SUMMARY.json")
  config=Path(config_dir)
  belts_cfg=read_json(config/"seismic_belts.json")
  pipeline_cfg=read_json(config/"pipeline.json")
  if abs(float(belts_cfg["minimum_magnitude"])-QUERY_FLOOR)>1e-9 or abs(float(pipeline_cfg["usgs"]["minimum_magnitude"])-QUERY_FLOOR)>1e-9:
   raise ValueError("configured_query_floor_differs_from_pinned_4_5_contract")
  configured={b["id"]:b for b in belts_cfg["belts"]}
  recovered={b["belt_id"]:b for b in provenance_summary["belts"]}
  source_manifest={b["belt_id"]:b for b in source_summary["seismic_belts"]}
  if set(configured)!=set(recovered) or set(configured)!=set(source_manifest): raise ValueError("belt_set_mismatch")
  joined={}; belt_audit={}
  for belt_id in sorted(configured):
   src_path=src/f"source_snapshots/derived/{belt_id}_events.csv"
   prov_path=prov/f"artifacts/p2_a/magnitude_provenance/by_belt/{belt_id}_magnitude_provenance.csv"
   source_hash=sha256(src_path); prov_hash=sha256(prov_path)
   if source_hash!=provenance_summary["source_catalog_hashes"].get(belt_id) or source_hash!=source_manifest[belt_id]["source_catalog_csv_sha256"]:
    raise ValueError("source_catalog_sha256_mismatch:"+belt_id)
   if prov_hash!=recovered[belt_id]["output_sha256"]: raise ValueError("provenance_csv_sha256_mismatch:"+belt_id)
   raw=rows(src_path); metadata=rows(prov_path)
   rmap={r["id"]:r for r in raw}; pmap={r["event_id"]:r for r in metadata}
   if len(rmap)!=len(raw) or len(pmap)!=len(metadata) or set(rmap)!=set(pmap): raise ValueError("event_id_join_not_one_to_one:"+belt_id)
   if len(raw)!=int(recovered[belt_id]["accepted_events"]): raise ValueError("accepted_event_count_mismatch:"+belt_id)
   events=[]
   for eid,r in rmap.items():
    p=pmap[eid]
    t0=datetime.fromisoformat(r["time"].replace("Z","+00:00")); t1=datetime.fromisoformat(p["time"].replace("Z","+00:00"))
    if abs((t0-t1).total_seconds())>.001 or abs(float(r["magnitude"])-float(p["magnitude"]))>.001:
     raise ValueError("time_or_magnitude_mismatch:"+belt_id+":"+eid)
    if (r["mag_type"] or "").strip().lower()!=(p["mag_type"] or "").strip().lower(): raise ValueError("magnitude_type_mismatch:"+eid)
    source=(p.get("mag_source") or "").strip().lower(); kind=(p.get("mag_type") or "").strip().lower()
    if not source or source=="missing" or not kind or kind=="missing": raise ValueError("missing_provenance:"+eid)
    mag=float(p["magnitude"])
    if not math.isfinite(mag) or mag<QUERY_FLOOR-.001: raise ValueError("below_catalog_floor:"+eid)
    events.append({"event_id":eid,"time":p["time"],"year":utc_year(p["time"]),"magnitude":mag,
                   "mag_source":source,"mag_type":kind,"network":(p.get("network") or "").strip().lower()})
   joined[belt_id]=events
   belt_audit[belt_id]={"accepted_catalog_events":len(raw),"provenance_events":len(metadata),
    "one_to_one_join_passed":True,"source_catalog_sha256":source_hash,"provenance_csv_sha256":prov_hash,
    "distinct_mag_sources":len({e["mag_source"] for e in events}),"distinct_mag_types":len({e["mag_type"] for e in events})}
  all_ids={e["event_id"] for es in joined.values() for e in es}
  if KNOWN_EXCLUSION["event_id"] in all_ids: raise ValueError("known_exclusion_entered_accepted_catalog")
  extra=[x for b in provenance_summary["belts"] for x in b.get("extra_query_rows",[]) if x.get("event_id")==KNOWN_EXCLUSION["event_id"]]
  if len(extra)!=1 or extra[0].get("reason")!="EVENT_NOT_PRESENT_IN_ACCEPTED_CATALOG": raise ValueError("known_exclusion_missing_or_changed")
  total=sum(map(len,joined.values()))
  if total!=94730: raise ValueError("accepted_catalog_total_mismatch:"+str(total))
  windows_cfg=windows(int(belts_cfg["start_year"]),int(belts_cfg["end_year"]))
  names={b["id"]:b["name"] for b in belts_cfg["belts"]}
  belt_results=[]
  for belt_id,events in sorted(joined.items()):
   buckets=defaultdict(list)
   for e in events:
    for w in windows_cfg:
     if w["start_year"]<=e["year"]<w["end_year_exclusive"]:
      buckets[(w["start_year"],w["end_year_exclusive"],e["mag_source"],e["mag_type"])].append(e); break
   strata=[]
   for (start,end,source,kind),items in sorted(buckets.items()):
    mc=estimate_mc([e["magnitude"] for e in items])
    strata.append({"time_window":{"start_year":start,"end_year_exclusive":end},"mag_source":source,"mag_type":kind,
      "event_count":len(items),"network_counts":dict(sorted(Counter(e["network"] for e in items).items())),
      "mc":mc,"threshold_sensitivity":sensitivity(items,mc)})
   rollup=[]
   for i,t in enumerate(THRESHOLDS):
    selected=[s["threshold_sensitivity"][i] for s in strata]
    rollup.append({"analysis_threshold":t,"strata_count":len(selected),
     "events_retained_across_strata":sum(x["events_retained"] for x in selected),
     "gate_counts":dict(sorted(Counter(x["threshold_gate"] for x in selected).items()))})
   belt_results.append({"belt_id":belt_id,"belt_name":names[belt_id],"accepted_events":len(events),
    "strata_count":len(strata),"estimable_strata_count":sum(s["mc"]["mc_estimate"] is not None for s in strata),
    "unresolved_strata_count":sum(s["mc"]["mc_estimate"] is None for s in strata),
    "threshold_sensitivity_rollup":rollup,"strata":strata})
  payload={
   "schema_version":"chaos.p2a.mc_assessment.v1","generated_at_utc":datetime.now(timezone.utc).isoformat(),
   "status":"COMPLETED_SCREENING_WITH_UNRESOLVED_SCIENTIFIC_DECISION",
   "artifact_inputs":{"source":{"run_id":45244943216,"artifact_id":14863135742,"sha256":source_digest,"source_commit":source_summary.get("repository_commit"),"archive_sha256_verified":True},
    "magnitude_provenance":{"run_id":45421531702,"artifact_id":14934058860,"sha256":prov_digest,"archive_sha256_verified":True}},
   "config_inputs":{"seismic_belts_json_sha256":sha256(config/"seismic_belts.json"),"pipeline_json_sha256":sha256(config/"pipeline.json"),
    "loaded_as_json_without_importing_run_pipeline":True},
   "input_validation":{"total_accepted_events":total,"catalog_join_validation":"PASS","belts":belt_audit,
    "known_exclusion":KNOWN_EXCLUSION,"known_exclusion_present_in_recovery_audit":True,"known_exclusion_absent_from_accepted_catalog":True},
   "provenance_summary_gate":{"reconciliation_passed":provenance_summary["reconciliation_passed"],
    "magnitude_source_complete":provenance_summary["magnitude_source_complete"],"magnitude_type_complete":provenance_summary["magnitude_type_complete"],
    "accepted_event_count":total,"extra_query_row_count":sum(b["extra_query_row_count"] for b in provenance_summary["belts"])},
   "analysis":{"method":{"name":"MAXC plus Gutenberg-Richter goodness-of-fit (GFT-90)","version":"1.0.0",
     "magnitude_bin_width":BIN_WIDTH,"minimum_events_for_point_estimate":MIN_N,"gft_acceptance_percent":GFT_MIN_FIT,
     "combination_rule":"Mc = max(MAXC, lowest GFT candidate passing 90% fit)","time_window_years":WINDOW_YEARS,
     "threshold_sensitivity":list(THRESHOLDS),"query_floor":QUERY_FLOOR,"query_floor_is_not_mc":True,
     "no_uncertainty_interval_claimed":True,"point_estimates_are_not_scientific_acceptance":True,
     "limitations":["Catalog is left-truncated at M>=4.5; Mc below 4.5 cannot be estimated from these inputs.",
      "MAXC/GFT point estimates are screening outputs, not accepted completeness declarations.",
      "No magnitude-scale conversion or pooling occurs across magSource or magType strata.",
      "Threshold sensitivity filters counts and gates against the base point estimate; it does not re-estimate Mc on artificially truncated subsets.",
      "Five-year UTC windows are fixed non-overlapping windows and do not assert within-window stationarity.",
      "Sparse or GFT-failing strata remain unresolved; no pooled fallback is used."]},
    "time_windows":windows_cfg,"belts":belt_results,"sensitivity_thresholds":list(THRESHOLDS),
    "catalog_minimum_magnitude_from_config":float(belts_cfg["minimum_magnitude"]),
    "pipeline_config_seismic_null_policy":pipeline_cfg["stationarity"]["seismic_null_policy"],
    "n1_etas_fit_performed":False,"zaliapin_randomization_performed":False,
    "scientific_decision":"UNRESOLVED_PENDING_REVIEW"},
   "immutability":{"experiments_tree_modified":False,"BreakDetectorV1_modified":False,"run_pipeline_imported":False,
    "governance_ledger_modified":False,"source_artifacts_modified":False,"n1_or_etas_fitted":False,"zaliapin_started":False}
  }
 out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
 (out/"P2_A_MC_STRATIFIED_RESULTS.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
 return payload

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--source-archive",required=True); ap.add_argument("--provenance-archive",required=True)
 ap.add_argument("--config-dir",default="real_data_stress_pipeline/config")
 ap.add_argument("--output-dir",default="artifacts/p2_a/mc_assessment")
 a=ap.parse_args()
 try:
  result=analyze(a.source_archive,a.provenance_archive,a.config_dir,a.output_dir)
  print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True),flush=True); return 0
 except Exception as exc:
  print(json.dumps({"status":"FAILED_CLOSED","error":str(exc)},ensure_ascii=False),file=sys.stderr,flush=True); return 2

if __name__=="__main__": raise SystemExit(main())
