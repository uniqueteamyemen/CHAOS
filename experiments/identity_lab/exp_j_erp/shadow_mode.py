"""Offline read-only A/B/C shadow runner for sanitized Odoo export bundles."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, tempfile
from datetime import datetime, timezone, date
from decimal import Decimal
from pathlib import Path
from typing import Mapping

try:
    from .reconcile import aggregate_moves, match_counterpart_receipts
    from .hybrid_reconcile import match_hybrid
    from .uom import UomNormalizationError, index_uoms, normalize_to_reference, relation_id
except ImportError:
    from reconcile import aggregate_moves, match_counterpart_receipts
    from hybrid_reconcile import match_hybrid
    from uom import UomNormalizationError, index_uoms, normalize_to_reference, relation_id

REL_TOL = Decimal("0.02")
LOSS_THRESHOLD = Decimal("0.5")
DATE_WINDOW = 3

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def validate(bundle):
    if not isinstance(bundle, dict):
        raise ValueError("bundle_root_must_be_object")
    for key in ("moves", "uom_rows", "receipts"):
        if not isinstance(bundle.get(key), list):
            raise ValueError("missing_or_invalid_array:" + key)
    if not bundle["moves"] or not bundle["uom_rows"]:
        raise ValueError("moves_and_uom_rows_must_not_be_empty")
    return bundle

def legacy_a(shipments, receipts, uoms):
    """A's historical exact-key and candidate semantics with schema/UoM adaptation."""
    normalized = []
    for r in receipts:
        uom = uoms.get(relation_id(r.get("counterpart_uom_id")))
        try:
            if not uom:
                raise UomNormalizationError("receipt_uom_unresolved")
            qty, ref = normalize_to_reference(r.get("counterpart_qty"), uom, uoms,
                                              r.get("product_uom_category_id"))
            normalized.append({**r, "_qty": qty, "_ref": ref})
        except (UomNormalizationError, TypeError):
            normalized.append({**r, "_invalid": True})
    out = {}
    for s in shipments:
        sid, product = relation_id(s.get("picking_id")), relation_id(s.get("product_id"))
        source, dest = relation_id(s.get("location_id")), relation_id(s.get("location_dest_id"))
        ref, sent = relation_id(s.get("reference_uom_id")), Decimal(str(s.get("quantity", "0")))
        dates = s.get("dates") or []
        try:
            sent_date = date.fromisoformat(str(min(dates) if dates else s.get("date"))[:10])
        except (ValueError, TypeError):
            sent_date = None
        exact = [r for r in normalized if relation_id(r.get("source_picking_id")) == sid]
        if len(exact) == 1:
            r = exact[0]
            ok = (not r.get("_invalid") and relation_id(r.get("product_id")) == product
                  and relation_id(r.get("location_id")) == dest and r.get("_ref") == ref)
            out[sid] = {"state": "confirmed" if ok else "ambiguous",
                        "confirmed": ok, "loss_claim": bool(ok and sent-r["_qty"] > LOSS_THRESHOLD),
                        "receipt_ids": [relation_id(r.get("counterpart_picking_id"))], "issues": []}
            continue
        if len(exact) > 1:
            out[sid] = {"state":"ambiguous","confirmed":False,"loss_claim":False,"receipt_ids":[],"issues":[]}
            continue
        candidates = []
        for r in normalized:
            if r.get("_invalid") or r.get("_ref") != ref: continue
            if relation_id(r.get("product_id")) != product or relation_id(r.get("location_id")) != dest: continue
            rs = relation_id(r.get("from_entity"))
            if rs and source and rs != source: continue
            try:
                rd = date.fromisoformat(str(r.get("counterpart_date"))[:10])
                if sent_date is None or abs((rd-sent_date).days) > DATE_WINDOW: continue
            except (ValueError, TypeError): continue
            if abs(sent-r["_qty"]) <= abs(sent)*REL_TOL: candidates.append(r)
        out[sid] = {"state":"candidate" if len(candidates)==1 else "ambiguous" if candidates else "unmatched",
                    "confirmed":False,"loss_claim":False,
                    "receipt_ids":[relation_id(r.get("counterpart_picking_id")) for r in candidates],"issues":[]}
    return out

def run_b(shipments, receipts, uoms):
    out = {}
    for s in shipments:
        tol = abs(Decimal(str(s.get("quantity","0"))))*REL_TOL
        rows = match_counterpart_receipts([s], receipts, uoms, date_window_days=DATE_WINDOW,
                                           quantity_tolerance=tol)
        r = rows[0] if rows else {}
        sid = relation_id(s.get("picking_id"))
        out[sid] = {"state":r.get("state","unmatched"),"confirmed":bool(r.get("confirmed")),
                    "loss_claim":"loss" in (r.get("issues") or []),
                    "receipt_ids":list(r.get("candidate_receipt_ids") or []),
                    "issues":list(r.get("issues") or [])}
    return out

def run_c(shipments, receipts, uoms):
    rows = match_hybrid(shipments, receipts, uoms, date_window_days=DATE_WINDOW,
        candidate_quantity_tolerance_relative=REL_TOL,
        reconciliation_quantity_tolerance=Decimal("0.01"),
        loss_classification_threshold=LOSS_THRESHOLD)
    return {relation_id(r.get("picking_id")):{
        "state":r.get("state","unmatched"),"confirmed":bool(r.get("confirmed")),
        "loss_claim":bool(r.get("loss_claim")) or "loss" in (r.get("issues") or []),
        "receipt_ids":list(r.get("receipt_ids") or r.get("candidate_receipt_ids") or []),
        "issues":list(r.get("issues") or [])} for r in rows}

def summarize(rows):
    states = {}
    for r in rows.values():
        k = r.get("state","unmatched"); states[k] = states.get(k,0)+1
    return {"shipments_scored":len(rows),"confirmed":sum(bool(r.get("confirmed")) for r in rows.values()),
            "loss_claims":sum(bool(r.get("loss_claim")) for r in rows.values()),
            "candidate_cases":sum(r.get("state") in ("candidate","candidate_approximate","approximate_unique") for r in rows.values()),
            "ambiguous":states.get("ambiguous",0),"unmatched":states.get("unmatched",0),"states":states}

def run_shadow(bundle):
    bundle = validate(copy.deepcopy(bundle))
    snapshot = {"schema_version":bundle.get("schema_version","1.0"),
                "export_metadata":bundle.get("export_metadata",{}),
                "moves":bundle["moves"],"uom_rows":bundle["uom_rows"],"receipts":bundle["receipts"]}
    input_hash = digest(snapshot)
    results, movement_stats = {}, {}
    for engine in ("A","B","C"):
        moves = copy.deepcopy(snapshot["moves"])
        receipts = copy.deepcopy(snapshot["receipts"])
        uoms = index_uoms(copy.deepcopy(snapshot["uom_rows"]))
        shipments, movement_stats = aggregate_moves(moves,uoms)
        results[engine] = (legacy_a(shipments,receipts,uoms) if engine=="A" else
                           run_b(shipments,receipts,uoms) if engine=="B" else
                           run_c(shipments,receipts,uoms))
        if digest(snapshot) != input_hash: raise RuntimeError("input_snapshot_mutated")
    ids = sorted(set().union(*(set(results[e]) for e in ("A","B","C"))))
    disagreements, pairwise = [], {"A_vs_B":0,"A_vs_C":0,"B_vs_C":0}
    for sid in ids:
        states = {e:results[e].get(sid,{}).get("state","missing") for e in ("A","B","C")}
        for key,a,b in (("A_vs_B","A","B"),("A_vs_C","A","C"),("B_vs_C","B","C")):
            pairwise[key] += int(states[a] != states[b])
        confirmations = {e:bool(results[e].get(sid,{}).get("confirmed")) for e in ("A","B","C")}
        losses = {e:bool(results[e].get(sid,{}).get("loss_claim")) for e in ("A","B","C")}
        if len(set(states.values()))>1 or len(set(confirmations.values()))>1 or len(set(losses.values()))>1:
            disagreements.append({"picking_id":sid,"states":states,"confirmed":confirmations,"loss_claims":losses,
                "receipt_ids":{e:results[e].get(sid,{}).get("receipt_ids",[]) for e in ("A","B","C")}})
    return {"classification":"shadow_observation_not_ground_truth","snapshot":{"sha256":input_hash,
        "moves":len(snapshot["moves"]),"uom_rows":len(snapshot["uom_rows"]),"receipts":len(snapshot["receipts"])},
        "export_metadata":snapshot["export_metadata"],"movement_stats":movement_stats,
        "engine_summaries":{e:summarize(results[e]) for e in ("A","B","C")},
        "engine_configuration":{"A":{"candidate_tolerance":"2% relative","loss_threshold":"0.5 category reference units"},
            "B":{"quantity_tolerance":"2% relative, applied as absolute per shipment","loss_threshold":"same quantity_tolerance (coupled in B implementation)"},
            "C":{"candidate_tolerance":"2% relative","reconciliation_tolerance":"0.01 absolute reference units","loss_threshold":"0.5 category reference units"}},
        "pairwise_state_disagreements":pairwise,"disagreement_count":len(disagreements),
        "disagreements":disagreements,"results":results,
        "guardrails":{"odoo_connection_used":False,"writes_to_odoo":False,
            "source_records_modified":False,"engine_outputs_feed_other_engines":False,
            "automated_promotion_or_action":False}}

def write_run(report, output_root):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = "shadow-"+stamp+"-"+report["snapshot"]["sha256"][:12]
    folder = output_root/run_id
    folder.mkdir(parents=True,exist_ok=False)
    metadata = report.get("export_metadata", {})
    independent = metadata.get("independent_counterparty_evidence") is True
    receipt_label = ("Independent receipt records: " if independent
                     else "Receipt/candidate rows (independence unverified): ")
    source_class = str(metadata.get("source_classification", "unspecified"))
    source_line = "Source classification: " + source_class
    if metadata.get("is_odoo_export") is False:
        source_line += " (not an Odoo export)"
    md = ["# ERP A/B/C Shadow Mode Report","","Classification: shadow observation; not ground-truth accuracy.","",
          source_line,
          "Input SHA-256: "+report["snapshot"]["sha256"],"Moves: "+str(report["snapshot"]["moves"]),
          "UoM rows: "+str(report["snapshot"]["uom_rows"]),
          receipt_label+str(report["snapshot"]["receipts"]),"",
          "| Metric | A | B | C |","|---|---:|---:|---:|"]
    for k in ("shipments_scored","confirmed","loss_claims","candidate_cases","ambiguous","unmatched"):
        md.append("| "+k+" | "+" | ".join(str(report["engine_summaries"][e][k]) for e in ("A","B","C"))+" |")
    md += ["","Engine threshold configuration:","- A: 2% candidate tolerance; 0.5 category-reference-unit loss threshold.","- B: 2% per-shipment tolerance is passed to the shared quantity_tolerance parameter and therefore also controls loss classification.","- C: 2% candidate tolerance; 0.01 absolute reconciliation tolerance; 0.5 category-reference-unit loss threshold.","","Pairwise state disagreements:"] + ["- "+k+": "+str(v) for k,v in report["pairwise_state_disagreements"].items()]
    md += ["","Total shipments with disagreement: "+str(report["disagreement_count"]),"",
           "Safety: no Odoo connection, no Odoo writes, no source mutation, no automated promotion."]
    files = {"shadow_report.json":json.dumps(report,indent=2,ensure_ascii=False),
             "comparison.md":"\n".join(md)+"\n",
             "manifest.json":json.dumps({"run_id":run_id,"mode":"shadow_read_only",
               "created_at_utc":datetime.now(timezone.utc).isoformat(),
               "input_sha256":report["snapshot"]["sha256"],"writes_to_odoo":False},indent=2)}
    for name, text in files.items():
        fd,tmp = tempfile.mkstemp(dir=folder,prefix=".tmp-")
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                f.write(text); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,folder/name)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    return folder

def main():
    p=argparse.ArgumentParser(description="Offline read-only A/B/C ERP shadow runner")
    p.add_argument("--input",required=True,type=Path,help="Sanitized export bundle JSON")
    p.add_argument("--output-root",type=Path,default=Path("shadow_runs"))
    args=p.parse_args()
    report=run_shadow(json.loads(args.input.read_text(encoding="utf-8")))
    folder=write_run(report,args.output_root)
    print(json.dumps({"status":"completed","mode":"shadow_read_only","run_dir":str(folder),
        "input_sha256":report["snapshot"]["sha256"],"shipments":report["snapshot"]["moves"],
        "disagreements":report["disagreement_count"],"writes_to_odoo":False},indent=2))

if __name__=="__main__": main()
