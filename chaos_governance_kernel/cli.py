from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .core import load_manifest, validate_manifest, replay, build_graph, write_json, append_jsonl, utc_now, canonical_sha256
from .checks import audit_csv


def main(argv=None):
    ap=argparse.ArgumentParser(prog='chaos-governance', description='CHAOS Governance Kernel MVP')
    sub=ap.add_subparsers(dest='cmd',required=True)
    for name in ['validate','replay','graph']:
        p=sub.add_parser(name); p.add_argument('manifest',type=Path); p.add_argument('--source-root',type=Path,default=Path.cwd())
    p=sub.add_parser('data-audit'); p.add_argument('csv_path',type=Path); p.add_argument('--required',default=''); p.add_argument('--keys',default=''); p.add_argument('--year-column',default=''); p.add_argument('--frequency',default=''); p.add_argument('--predictors',default=''); p.add_argument('--target-prefixes',default='')
    sub.choices['replay'].add_argument('--check-only',action='store_true')
    p=sub.add_parser('record'); p.add_argument('manifest',type=Path); p.add_argument('--source-root',type=Path,default=Path.cwd()); p.add_argument('--ledger',type=Path)
    args=ap.parse_args(argv)
    if args.cmd=='data-audit': out=audit_csv(args.csv_path,args.required.split(',') if args.required else [],args.keys.split(',') if args.keys else None,args.year_column or None,args.frequency or None,args.predictors.split(',') if args.predictors else None,args.target_prefixes.split(',') if args.target_prefixes else None)
    elif args.cmd=='validate': out=validate_manifest(args.manifest,args.source_root)
    elif args.cmd=='replay': out=replay(args.manifest,args.source_root,args.check_only)
    elif args.cmd=='graph':
        out=build_graph(args.manifest,args.source_root); out_path=args.manifest.with_name(args.manifest.stem+'_EVIDENCE_GRAPH.json'); write_json(out_path,out); out['output']=str(out_path)
    else:
        m=load_manifest(args.manifest); validation=validate_manifest(args.manifest,args.source_root); out={'record_id':f"governance:{m.get('bundle_id',args.manifest.stem)}:{utc_now()}",'record_type':'governance_validation','manifest':str(args.manifest),'manifest_sha256':canonical_sha256(m),'validation':validation,'decision_status':m.get('decision_status'),'recorded_at':utc_now()}; ledger=args.ledger or args.manifest.with_name('PROVENANCE_LEDGER.jsonl'); append_jsonl(ledger,out); out['ledger']=str(ledger)
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)); return 0 if out.get('status',out.get('validation',{}).get('status')) in ('pass','ready') else 1
if __name__=='__main__': raise SystemExit(main())
