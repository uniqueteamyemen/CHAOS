"""Deterministic temporal-window and concurrent heterogeneous-UoM stress test."""
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
try:
 from ..exp_j_erp.reconcile import aggregate_moves, match_counterpart_receipts
except ImportError:
 from exp_j_erp.reconcile import aggregate_moves, match_counterpart_receipts

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/"results"
SEED=20261113
UOMS={
 "unit":{"id":"unit","category_id":"count","factor":"1","uom_type":"reference"},
 "box":{"id":"box","category_id":"count","factor":"0.1","uom_type":"bigger"},
 "kg":{"id":"kg","category_id":"weight","factor":"1","uom_type":"reference"},
 "g":{"id":"g","category_id":"weight","factor":"1000","uom_type":"smaller"},
}

def build_window_dataset():
 shipments=[]; receipts=[]; truth={}
 start=date(2026,1,1); delays=(0,1,2,3,5,7,9); quantities=(10,20,30)
 for i in range(70):
  weight=i%2==1; product="SKU-WEIGHT" if weight else "SKU-COUNT"
  category="weight" if weight else "count"; ref="kg" if weight else "unit"
  day=start+timedelta(days=(i//2)*2); qty=Decimal(str(quantities[(i//2)%3]))
  out=f"OUT-{i:03d}"; rid=f"IN-TRUE-{i:03d}"
  shipments.append({"picking_id":out,"product_id":product,"location_id":"WH-A","location_dest_id":"WH-B","reference_uom_id":ref,"quantity":str(qty),"dates":[day.isoformat()]})
  rday=day+timedelta(days=delays[(i//2)%len(delays)])
  if weight:
   ruom="g" if i%4 else "kg"; rqty=qty*Decimal("1000") if ruom=="g" else qty
  else:
   ruom="box" if i%6==0 else "unit"; rqty=qty/Decimal("10") if ruom=="box" else qty
  receipts.append({"counterpart_picking_id":rid,"product_id":product,"location_id":"WH-B","counterpart_qty":str(rqty),"counterpart_uom_id":ruom,"product_uom_category_id":category,"counterpart_date":rday.isoformat(),"counterpart_system":"independent_receiving_wms","counterpart_source":f"labelled_{i}","recorded_at":rday.isoformat()+"T10:00:00"})
  truth[out]=rid
 for j in range(14):
  src=shipments[(j*5+3)%len(shipments)]; day=date.fromisoformat(src["dates"][0])
  weight=src["product_id"]=="SKU-WEIGHT"; qty=Decimal(src["quantity"]); rday=day+timedelta(days=(j%5)+1)
  receipts.append({"counterpart_picking_id":f"IN-DECOY-{j:03d}","product_id":src["product_id"],"location_id":"WH-B","counterpart_qty":str(qty*Decimal("1000") if weight else qty),"counterpart_uom_id":"g" if weight else "unit","product_uom_category_id":"weight" if weight else "count","counterpart_date":rday.isoformat(),"counterpart_system":"independent_receiving_wms","counterpart_source":f"decoy_{j}","recorded_at":rday.isoformat()+"T10:00:00"})
 return {"shipments":shipments,"receipts":receipts,"truth":truth}

def score_window(ds,window):
 matches=match_counterpart_receipts(ds["shipments"],ds["receipts"],UOMS,date_window_days=window)
 tp=fp=fn=amb=unmatched=true_in_ambiguous=ambiguous_without_truth=candidate_hits=0
 for row in matches:
  expected=ds["truth"][row["picking_id"]]
  candidate_ids=set(row.get("candidate_receipt_ids") or [])
  predicted=row.get("counterpart_picking_id") if row["state"]=="approximate_unique" else None
  if expected in candidate_ids or predicted==expected: candidate_hits+=1
  if predicted==expected: tp+=1
  elif predicted is not None: fp+=1; fn+=1
  else:
   fn+=1
   if row["state"]=="ambiguous":
    amb+=1
    if expected in candidate_ids: true_in_ambiguous+=1
    else: ambiguous_without_truth+=1
   else: unmatched+=1
 p=tp/(tp+fp) if tp+fp else 0.0; r=tp/(tp+fn) if tp+fn else 0.0
 f1=2*p*r/(p+r) if p+r else 0.0; n=len(ds["truth"])
 return {"window_days":window,"tp":tp,"fp":fp,"fn":fn,"ambiguous":amb,"unmatched":unmatched,"precision":round(p,6),"resolved_recall":round(r,6),"candidate_recall":round(candidate_hits/n,6),"f1":round(f1,6),"resolved_coverage":round((tp+fp)/n,6),"ambiguity_rate":round(amb/n,6),"true_receipt_inside_ambiguous_set":true_in_ambiguous,"ambiguous_without_true_receipt":ambiguous_without_truth,"n":n}

def build_complexity_case():
 moves=[
 {"id":1,"picking_id":"OUT-A","product_id":"P-WEIGHT","location_id":"A","location_dest_id":"B","product_uom":"kg","product_uom_category_id":"weight","quantity":"2","product_uom_qty":"2","state":"done","reference":"PO-A","date":"2026-02-01"},
 {"id":2,"picking_id":"OUT-A","product_id":"P-COUNT","location_id":"A","location_dest_id":"B","product_uom":"unit","product_uom_category_id":"count","quantity":"100","product_uom_qty":"100","state":"done","reference":"PO-A","date":"2026-02-01"},
 {"id":3,"picking_id":"OUT-B","product_id":"P-WEIGHT","location_id":"A","location_dest_id":"B","product_uom":"g","product_uom_category_id":"weight","quantity":"1500","product_uom_qty":"1500","state":"done","reference":"PO-B","date":"2026-02-02"},
 {"id":4,"picking_id":"OUT-B","product_id":"P-COUNT","location_id":"A","location_dest_id":"B","product_uom":"box","product_uom_category_id":"count","quantity":"5","product_uom_qty":"5","state":"done","reference":"PO-B","date":"2026-02-02"},
 {"id":5,"picking_id":"OUT-C","product_id":"P-WEIGHT","location_id":"A","location_dest_id":"C","product_uom":"kg","product_uom_category_id":"weight","quantity":"1","product_uom_qty":"1","state":"done","reference":"PO-C","date":"2026-02-02"}]
 movements,stats=aggregate_moves(moves,UOMS)
 receipts=[
 {"counterpart_picking_id":"IN-A-W","product_id":"P-WEIGHT","location_id":"B","counterpart_qty":"2000","counterpart_uom_id":"g","product_uom_category_id":"weight","counterpart_date":"2026-02-03","counterpart_system":"receiver_wms","counterpart_source":"receipt-A-W","recorded_at":"2026-02-03T10:00:00"},
 {"counterpart_picking_id":"IN-A-C","product_id":"P-COUNT","location_id":"B","counterpart_qty":"10","counterpart_uom_id":"box","product_uom_category_id":"count","counterpart_date":"2026-02-03","counterpart_system":"receiver_wms","counterpart_source":"receipt-A-C","recorded_at":"2026-02-03T10:01:00"},
 {"counterpart_picking_id":"IN-B-W","product_id":"P-WEIGHT","location_id":"B","counterpart_qty":"1500","counterpart_uom_id":"g","product_uom_category_id":"weight","counterpart_date":"2026-02-04","counterpart_system":"receiver_wms","counterpart_source":"receipt-B-W","recorded_at":"2026-02-04T10:00:00"},
 {"counterpart_picking_id":"IN-B-C","product_id":"P-COUNT","location_id":"B","counterpart_qty":"50","counterpart_uom_id":"unit","product_uom_category_id":"count","counterpart_date":"2026-02-04","counterpart_system":"receiver_wms","counterpart_source":"receipt-B-C","recorded_at":"2026-02-04T10:01:00"},
 {"counterpart_picking_id":"IN-DECOY-C","product_id":"P-WEIGHT","location_id":"C","counterpart_qty":"2","counterpart_uom_id":"kg","product_uom_category_id":"weight","counterpart_date":"2026-02-03","counterpart_system":"receiver_wms","counterpart_source":"decoy","recorded_at":"2026-02-03T11:00:00"}]
 return {"movement_stats":stats,"movements":movements,"receipt_matches":match_counterpart_receipts(movements,receipts,UOMS,date_window_days=3)}

def run():
 ds=build_window_dataset(); curve=[score_window(ds,w) for w in range(11)]; complex_case=build_complexity_case()
 result={"experiment":"M_precision_recall_window_and_concurrent_uom","classification":"synthetic_labelled_algorithm_stress_test_not_operational_validation","seed":SEED,"dataset":{"shipments":70,"true_receipts":70,"receipt_records":len(ds["receipts"]),"hard_negative_receipts":14},"curve":curve,"complexity_case":complex_case,"metric_definitions":{"precision":"TP/(TP+FP)","resolved_recall":"TP/(TP+FN); ambiguous and unmatched are unresolved FN","candidate_recall":"fraction where the true receipt is present in the candidate set, including ambiguous sets","f1":"2*P*R/(P+R)","resolved_coverage":"(TP+FP)/N","ambiguity_rate":"ambiguous/N"},"limitations":["Synthetic labels score controlled matcher behavior only; no operational accuracy estimate.","Wider windows may increase candidate recall while increasing ambiguity and false matches.","Approximate candidates remain unconfirmed and cannot generate loss events."]}
 RESULTS.mkdir(parents=True,exist_ok=True)
 (RESULTS/"precision_recall_curve.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
 lines=["# Experiment M — Temporal precision/recall and concurrent UoM stress","","> Synthetic labelled algorithm stress test only; not operational validation.","","Precision = TP/(TP+FP); resolved recall = TP/(TP+FN). Ambiguous/unmatched records are unresolved FN. Candidate recall also counts true receipts inside ambiguous candidate sets.","F1 = 2PR/(P+R); coverage = (TP+FP)/N.","","| Window days | TP | FP | FN | Ambiguous | Unmatched | Precision | Resolved recall | Candidate recall | F1 | Coverage |","|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
 for x in curve: lines.append(f"| {x['window_days']} | {x['tp']} | {x['fp']} | {x['fn']} | {x['ambiguous']} | {x['unmatched']} | {x['precision']:.3f} | {x['resolved_recall']:.3f} | {x['candidate_recall']:.3f} | {x['f1']:.3f} | {x['resolved_coverage']:.3f} |")
 lines += ["","## Concurrent multi-shipment / heterogeneous-UoM case","",json.dumps(complex_case,indent=2),"","## Limitations"]+["- "+x for x in result["limitations"]]
 (RESULTS/"precision_recall_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
 return result

if __name__=="__main__":
 r=run(); print(json.dumps({"curve":r["curve"],"complexity_matches":r["complexity_case"]["receipt_matches"]},indent=2))
