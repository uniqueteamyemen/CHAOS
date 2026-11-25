from __future__ import annotations
import csv
from pathlib import Path
from typing import Any


def audit_csv(path: Path, required_columns: list[str], key_columns: list[str] | None = None, year_column: str | None = None, expected_frequency: str | None = None, predictor_columns: list[str] | None = None, target_prefixes: list[str] | None = None) -> dict[str, Any]:
    failures=[]; row_count=0; columns=[]; years=[]; seen=set(); null_counts={}
    with path.open('r',encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f); columns=reader.fieldnames or []
        missing=[c for c in required_columns if c not in columns]
        if missing: failures.append({'reason':'missing_required_columns','columns':missing})
        for row in reader:
            row_count+=1
            for c,v in row.items():
                if v in ('',None): null_counts[c]=null_counts.get(c,0)+1
            if key_columns:
                key=tuple(row.get(c) for c in key_columns)
                if key in seen: failures.append({'reason':'duplicate_key','key':key})
                seen.add(key)
            if year_column and row.get(year_column):
                try: years.append(int(float(row[year_column])))
                except ValueError: failures.append({'reason':'invalid_year','value':row[year_column]})
    if year_column and years and any(y<1900 or y>2100 for y in years): failures.append({'reason':'year_out_of_range','min':min(years),'max':max(years)})
    if expected_frequency == 'annual' and year_column and years:
        # Annual is a declared metadata contract; repeated keys are the actual frequency failure.
        by_key={}
        for k in seen:
            entity=k[:-1] if key_columns and len(key_columns)>1 else k
            by_key.setdefault(entity,[]).append(k[-1] if key_columns else None)
        bad=[(k,sorted(v)) for k,v in by_key.items() if len(v)!=len(set(v))]
        if bad: failures.append({'reason':'annual_frequency_duplicate_period','examples':bad[:5]})
    if predictor_columns and target_prefixes:
        leaked=[c for c in predictor_columns if any(c.startswith(p) for p in target_prefixes)]
        if leaked: failures.append({'reason':'target_leakage_in_predictors','columns':leaked})
    return {'path':str(path),'columns':columns,'row_count':row_count,'year_min':min(years) if years else None,'year_max':max(years) if years else None,'null_counts':null_counts,'required_columns_present':not any(x.get('reason')=='missing_required_columns' for x in failures),'expected_frequency':expected_frequency,'status':'pass' if not failures else 'fail','failures':failures}
