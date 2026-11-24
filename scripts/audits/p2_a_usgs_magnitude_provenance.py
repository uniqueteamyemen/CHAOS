#!/usr/bin/env python3
"""Recover USGS preferred magnitude-source metadata for P2-A without rerunning P2.2."""
from __future__ import annotations
import argparse, csv, hashlib, io, json, math, sys, urllib.parse
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from real_data_stress_pipeline import run_pipeline as p2
from chaos_governance_kernel.core import append_research_ledger_record, canonical_sha256, utc_now
AUDIT_ID = "CHAOS-P2-A-USGS-MAGNITUDE-PROVENANCE-RECOVERY-V1"
LIMIT = 20000
SATURATION = LIMIT - 1

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def load_inputs(root):
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    if summary.get("audit_id") != "CHAOS-P2.2.3-DOMAIN-NULL-DECLUSTERING" or summary.get("status") != "completed" or not summary.get("required_source_gate", {}).get("passed"):
        raise ValueError("P2.2.3_source_artifact_gate_failed")
    catalogs, hashes = {}, {}
    for belt in summary["usgs_source_ingestion"]["belts"]:
        bid = belt["id"]
        path = root / "source_snapshots" / "derived" / f"{bid}_events.csv"
        actual = digest(path)
        if actual != belt["csv_sha256"]:
            raise ValueError(f"accepted_catalog_hash_mismatch:{bid}")
        rows = {}
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                eid = str(row.get("id") or "").strip()
                if not eid or eid in rows:
                    raise ValueError(f"accepted_catalog_id_missing_or_duplicate:{bid}")
                rows[eid] = {"time": row["time"], "mag": float(row["magnitude"]), "type": (row.get("mag_type") or "missing").lower()}
        if len(rows) != int(belt["events_accepted"]):
            raise ValueError(f"accepted_catalog_count_mismatch:{bid}")
        catalogs[bid], hashes[bid] = rows, actual
    if len(catalogs) != 5:
        raise ValueError("five_belt_source_set_required")
    return summary, catalogs, hashes

def parse_csv(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    required = {"id", "time", "mag", "magType", "magSource"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("USGS_CSV_MAG_SOURCE_FIELD_MISSING")
    return list(reader)

def fetch_window(belt, start, end, raw_dir, manifest, depth=0):
    params = {"format":"csv", "starttime":start, "endtime":end, "minmagnitude":p2.MAG,
              "minlatitude":belt["minlatitude"], "maxlatitude":belt["maxlatitude"],
              "minlongitude":belt["minlongitude"], "maxlongitude":belt["maxlongitude"],
              "orderby":"time-asc", "limit":LIMIT}
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode(params)
    data = p2.get(url, p2.USGS_RETRIES, p2.USGS_TIMEOUT)
    path = raw_dir / belt["id"] / f"{start.replace(':', '_')}_{end.replace(':', '_')}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    rows = parse_csv(data)
    manifest.append({"path":path.relative_to(raw_dir.parent).as_posix(),
                     "sha256":hashlib.sha256(data).hexdigest(),"url":url,"parameters":params,
                     "api_boundary_semantics":"START_AND_END_INCLUSIVE","response_rows":len(rows),
                     "saturated":len(rows)>=SATURATION})
    if len(rows) >= SATURATION:
        a=datetime.fromisoformat(start.replace("Z","+00:00")); b=datetime.fromisoformat(end.replace("Z","+00:00"))
        if (b-a).total_seconds()<86400 or depth>=12:
            raise RuntimeError(f"USGS_CSV_SATURATED:{belt['id']}:{start}:{end}")
        mid=(a+(b-a)/2).strftime("%Y-%m-%dT%H:%M:%S")
        return fetch_window(belt,start,mid,raw_dir,manifest,depth+1)+fetch_window(belt,mid,end,raw_dir,manifest,depth+1)
    return rows

def normalized(value):
    value=str(value or "").strip()
    return "missing" if value.casefold() in {"","nan","none","null","unknown","--","—"} else value

def reconcile(belt_id, accepted, rows, out_dir):
    by_id, conflicts, mismatches = {}, [], []
    for row in rows:
        item={"time":str(row.get("time") or "").strip(),"mag":str(row.get("mag") or "").strip(),
              "type":str(row.get("magType") or "").strip().lower(),
              "mag_source":normalized(row.get("magSource")),"network":normalized(row.get("net"))}
        eid=str(row.get("id") or "").strip()
        if not eid:
            conflicts.append({"reason":"CSV_EVENT_ID_MISSING"}); continue
        if eid in by_id and by_id[eid] != item:
            conflicts.append({"event_id":eid,"reason":"CONFLICTING_OVERLAP_RECORDS"})
        else:
            by_id[eid]=item
    enriched, missing = [], []
    for eid, event in accepted.items():
        source=by_id.get(eid)
        if source is None:
            missing.append(eid); continue
        try:
            mag=float(source["mag"])
        except ValueError:
            mismatches.append({"event_id":eid,"reason":"CSV_MAG_INVALID"}); continue
        if not math.isclose(mag,event["mag"],rel_tol=0,abs_tol=.001):
            mismatches.append({"event_id":eid,"reason":"MAGNITUDE_MISMATCH"})
        if source["type"] != event["type"]:
            mismatches.append({"event_id":eid,"reason":"MAG_TYPE_MISMATCH"})
        try:
            t0=datetime.fromisoformat(event["time"].replace("Z","+00:00")).timestamp()
            t1=datetime.fromisoformat(source["time"].replace("Z","+00:00")).timestamp()
            if abs(t0-t1)>.001: mismatches.append({"event_id":eid,"reason":"ORIGIN_TIME_MISMATCH"})
        except ValueError:
            mismatches.append({"event_id":eid,"reason":"ORIGIN_TIME_INVALID"})
        enriched.append({"event_id":eid,"time":event["time"],"magnitude":event["mag"],
                         "mag_type":event["type"],"mag_source":source["mag_source"],"network":source["network"]})
    target=out_dir/"by_belt"/f"{belt_id}_magnitude_provenance.csv"
    target.parent.mkdir(parents=True,exist_ok=True)
    fields=["event_id","time","magnitude","mag_type","mag_source","network"]
    with target.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(enriched)
    counts=Counter(r["mag_source"] for r in enriched); missing_source=counts.get("missing",0)
    type_counts=Counter(r["mag_type"] for r in enriched); missing_type=type_counts.get("missing",0)
    status=("FAIL_RECONCILIATION" if missing or conflicts or mismatches else
            "PARTIAL_MAG_SOURCE_MISSING_REQUIRES_REVIEW" if missing_source else
            "MAGNITUDE_TYPE_MISSING_REQUIRES_REVIEW" if missing_type else
            "SOURCE_OR_MAG_TYPE_MIXTURE_REQUIRES_STRATIFICATION" if len(counts)>1 or len(type_counts)>1 else
            "SOURCE_HOMOGENEOUS_CANDIDATE_PENDING_CALIBRATION")
    return {"belt_id":belt_id,"accepted_events":len(accepted),"matched_events":len(enriched),
            "missing_event_ids":len(missing),"missing_event_ids_sample":missing[:25],
            "magnitude_source_counts":dict(sorted(counts.items())),"magnitude_source_missing_events":missing_source,
            "magnitude_type_counts":dict(sorted(type_counts.items())),"magnitude_type_missing_events":missing_type,
            "network_counts":dict(sorted(Counter(r["network"] for r in enriched).items())),
            "extra_query_rows":len(set(by_id)-set(accepted)),"conflicts":conflicts,"mismatches":mismatches,
            "output_path":target.relative_to(out_dir).as_posix(),"output_sha256":digest(target),"status":status}

def ledger_record(kind, contract, sources, hashes, outputs, status, notes, extra=None):
    payload={"record_type":kind,"created_at_utc":utc_now(),"source_refs":sources,"contract_ref":contract,
             "input_hashes":hashes,"output_refs":outputs,"status":status,"notes":notes}
    payload.update(extra or {})
    return {"ledger_id":"ledger:v1:sha256:"+canonical_sha256(payload),**payload}

def run(source_root,out_dir,ledger_path,run_id,attempt):
    source_root,out_dir,ledger_path=source_root.resolve(),out_dir.resolve(),ledger_path.resolve()
    source_summary,catalogs,input_hashes=load_inputs(source_root)
    raw_dir=out_dir/"raw_csv"; requests=[]; belts=[]
    for belt in p2.BELTS:
        start=f"{p2.Y0}-01-01T00:00:00"; end=f"{p2.Y1+1}-01-01T00:00:00"
        rows=fetch_window(belt,start,end,raw_dir,requests)
        belts.append(reconcile(belt["id"],catalogs[belt["id"]],rows,out_dir))
    reconcile_ok=all(b["status"]!="FAIL_RECONCILIATION" for b in belts)
    source_complete=all(b["magnitude_source_missing_events"]==0 for b in belts)
    type_complete=all(b["magnitude_type_missing_events"]==0 for b in belts)
    homogeneous=all(len(b["magnitude_source_counts"])<=1 and len(b["magnitude_type_counts"])<=1 for b in belts)
    gate=("BLOCKED_RECONCILIATION_FAILURE" if not reconcile_ok else
          "BLOCKED_MAG_SOURCE_MISSING" if not source_complete else
          "BLOCKED_MAGNITUDE_TYPE_MISSING" if not type_complete else
          "READY_FOR_Mc_CANDIDATE_ANALYSIS" if homogeneous else
          "READY_FOR_STRATIFIED_Mc_CANDIDATE_ANALYSIS")
    result={"audit_id":AUDIT_ID,"status":"COMPLETED" if reconcile_ok else "COMPLETED_WITH_RECONCILIATION_FAILURES",
            "source_artifact":{"audit_id":source_summary["audit_id"],"repository_commit":source_summary.get("repository_commit"),
                               "run_id":str(run_id),"run_attempt":str(attempt),
                               "artifact_name":f"chaos-p2-domain-null-{run_id}-{attempt}"},
            "source_catalog_hashes":input_hashes,
            "query_policy":{"format":"USGS FDSN CSV","required_field":"magSource","query_start_inclusive":True,
                            "query_end_inclusive":True,"analysis_window":"[start,end)",
                            "minimum_magnitude_query_threshold":p2.MAG,"threshold_is_not_Mc":True,
                            "limit":LIMIT,"split_overlap":"deduplicate by event ID; conflicts fail closed"},
            "raw_query_snapshots":requests,"belts":belts,"reconciliation_passed":reconcile_ok,
            "magnitude_source_complete":source_complete,"magnitude_type_complete":type_complete,
            "magnitude_source_and_type_homogeneous_by_belt":homogeneous,
            "p2_a_mc_gate":gate,"scientific_decision":"UNRESOLVED",
            "immutability":{"input_artifact_modified":False,"historical_p2_2_outputs_modified":False,
                            "detector_modified":False,"experiments_archive_modified":False}}
    out_dir.mkdir(parents=True,exist_ok=True)
    summary_path=out_dir/"P2_A_MAGNITUDE_PROVENANCE_SUMMARY.json"
    summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    contract="real_data_stress_pipeline/contracts/p2_a_magnitude_provenance_recovery_v1.json"
    refs=[summary_path.relative_to(out_dir).as_posix()]+[b["output_path"] for b in belts]+[r["path"] for r in requests]
    source_ref=f"GitHub Actions artifact: chaos-p2-domain-null-{run_id}-{attempt}"
    ledger_path.parent.mkdir(parents=True,exist_ok=True)
    run_rec=ledger_record("run",contract,[source_ref],{f"usgs:{k}":v for k,v in input_hashes.items()},refs,
                          "UNRESOLVED",{"audit_id":AUDIT_ID,"reconciliation_passed":reconcile_ok,
                          "magnitude_source_complete":source_complete,"p2_a_mc_gate":gate})
    appended=[append_research_ledger_record(ledger_path,run_rec)]
    for belt in belts:
        rec=ledger_record("pattern_decision",contract,
            [f"USGS accepted catalog:{belt['belt_id']}","USGS CSV magSource reconciliation"],
            {f"usgs:{belt['belt_id']}":input_hashes[belt["belt_id"]]},[belt["output_path"]],"UNRESOLVED",
            {"belt_id":belt["belt_id"],"provenance_status":belt["status"],
             "missing_mag_source_events":belt["magnitude_source_missing_events"]},
            {"decision_context":{"input_disposition":"ABSTAIN","hypothesis_transition":"UNRESOLVED",
             "contract_refs":[contract,"real_data_stress_pipeline/contracts/seismic_null_model_contract_v1.json"]}})
        appended.append(append_research_ledger_record(ledger_path,rec))
    result["research_ledger"]={"path":str(ledger_path),"append_results":appended}
    summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,default=Path("artifacts/p2_a/magnitude_provenance"))
    ap.add_argument("--ledger-path",type=Path,default=Path("governance/ledger/RESEARCH_LEDGER_V1.jsonl"))
    ap.add_argument("--source-run-id",required=True)
    ap.add_argument("--source-run-attempt",default="1")
    args=ap.parse_args()
    result=run(args.source_root,args.output_dir,args.ledger_path,args.source_run_id,args.source_run_attempt)
    print(json.dumps({k:result[k] for k in ("audit_id","status","reconciliation_passed","magnitude_source_complete","p2_a_mc_gate")},ensure_ascii=False))
    return 0 if result["reconciliation_passed"] else 2

if __name__=="__main__":
    raise SystemExit(main())
