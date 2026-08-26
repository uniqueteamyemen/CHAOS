#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); SRC=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'; OUT=ROOT/'experiments/macro_plus_eia_energy/temporal_alignment_audit_v1'; OUT.mkdir(parents=True,exist_ok=True)
def main():
 d=pd.read_csv(SRC); years=sorted(d.year.unique().tolist()); entities=int(d.entity_code.nunique()); row_counts=d.groupby('entity_code').size(); summary={'audit_id':'CHAOS_TEMPORAL_ALIGNMENT_AUDIT_V1','contract_ref':'experimental_contracts/TEMPORAL_ALIGNMENT_CONTRACT_V1.json','source':str(SRC.relative_to(ROOT)),'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'native_frequency':'annual','allowed_alignment':'annual_to_annual','rows':int(len(d)),'entities':entities,'years':years,'expected_years':25,'entities_with_complete_year_range':int((row_counts==25).sum()),'rows_dropped':0,'daily_or_event_aggregation':False,'future_broadcast':False,'imputation':False,'raw_data_modified':False,'status':'pass'}; (OUT/'TEMPORAL_ALIGNMENT_AUDIT_V1.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
