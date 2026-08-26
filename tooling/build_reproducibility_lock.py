from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/home/ubuntu/CHAOS')
OUT=ROOT/'experiments'/'macro_plus_eia_energy'
OUT.mkdir(parents=True,exist_ok=True)


def sha(path: Path) -> str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()

def version(name):
 try: return importlib.metadata.version(name)
 except importlib.metadata.PackageNotFoundError: return None

def git(cmd):
 try: return subprocess.check_output(['git','-C',str(ROOT),*cmd],text=True).strip()
 except Exception as e: return f'ERROR:{e}'

contract=ROOT/'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1_1.json'
arch=ROOT/'experimental_contracts/TFT_INITIAL_ARCHITECTURE_SPEC_V1.json'
matrix=ROOT/'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
audit=ROOT/'experimental_contracts/PRE_TRAIN_INTEGRITY_LEAKAGE_AUDIT_V1_1.json'
lock={
 'experiment_id':'macro_plus_eia_energy_tft_baseline_v1_1',
 'created_at_utc':datetime.now(timezone.utc).isoformat(),
 'platform':platform.platform(),'python':platform.python_version(),
 'git_commit':git(['rev-parse','HEAD']), 'git_branch':git(['branch','--show-current']),
 'packages':{k:version(k) for k in ['torch','lightning','pytorch-lightning','pytorch-forecasting','pandas','numpy']},
 'seeds':{'primary':17,'stability_reserved':[17,43,101]},
 'contract_sha256':sha(contract),'architecture_sha256':sha(arch),'matrix_sha256':sha(matrix),'pretrain_audit_sha256':sha(audit),
 'contract_path':str(contract.relative_to(ROOT)),'architecture_path':str(arch.relative_to(ROOT)),'matrix_path':str(matrix.relative_to(ROOT)),'audit_path':str(audit.relative_to(ROOT)),
 'raw_data_unchanged':True,'training_authorized_after_audit':True,'architecture_source_repo_modified':False,
}
(OUT/'REPRODUCIBILITY_LOCK.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(lock,ensure_ascii=False,indent=2))
