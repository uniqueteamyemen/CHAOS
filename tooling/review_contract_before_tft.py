from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path('/home/ubuntu/CHAOS')
CONTRACT = ROOT / 'experimental_contracts/DATASET_CONFIGURATION_MACRO_PLUS_EIA_ENERGY_REVIEW_V1.json'
MATRIX = ROOT / 'catalog_first/readiness_gate/macro_plus_eia_energy/MACRO_PLUS_EIA_ENERGY_COMPLETE_140_RAW_2000_2024_WIDE.csv'
OUT = ROOT / 'experimental_contracts/CONTRACT_REVIEW_AUDIT_V1.json'

contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
df = pd.read_csv(MATRIX, dtype={'entity_code': str})
selected = [x['id'] for x in contract['input_columns']['exogenous_covariates']]
target = contract['target']['id']
all_vars = [target] + selected

checks = {}
checks['row_count'] = {'expected': 3500, 'observed': len(df), 'pass': len(df) == 3500}
checks['entity_count'] = {'expected': 140, 'observed': int(df['entity_code'].nunique()), 'pass': int(df['entity_code'].nunique()) == 140}
checks['year_set'] = {'expected': list(range(2000, 2025)), 'observed': sorted(df['year'].unique().tolist()), 'pass': sorted(df['year'].unique().tolist()) == list(range(2000, 2025))}
checks['selected_column_count'] = {'expected': 11, 'observed': len(all_vars), 'pass': len(all_vars) == 11}
checks['selected_columns_present'] = {'missing': [c for c in all_vars if c not in df.columns], 'pass': all(c in df.columns for c in all_vars)}
checks['selected_missing_cells'] = {'observed': int(df[all_vars].isna().sum().sum()), 'pass': int(df[all_vars].isna().sum().sum()) == 0}
checks['duplicate_entity_year_rows'] = {'observed': int(df.duplicated(['entity_code', 'year']).sum()), 'pass': int(df.duplicated(['entity_code', 'year']).sum()) == 0}
checks['sorted_entity_year'] = {'pass': df.equals(df.sort_values(['entity_code', 'year']).reset_index(drop=True))}

# Contract sequence arithmetic and temporal firewall checks; no data values are transformed.
seq = contract['temporal_contract']
split = contract['split']
expected_counts = {
    'train': (split['train']['target_years'][1] - split['train']['target_years'][0] + 1) * 140,
    'validation': (split['validation']['target_years'][1] - split['validation']['target_years'][0] + 1) * 140,
    'test': (split['test']['target_years'][1] - split['test']['target_years'][0] + 1) * 140,
}
checks['sequence_counts'] = {
    'expected_from_contract': {k: split[k]['sequence_count'] for k in expected_counts},
    'recomputed': expected_counts,
    'pass': all(split[k]['sequence_count'] == expected_counts[k] for k in expected_counts),
}
firewall_examples=[]
for target_year in [2006, 2015, 2016, 2019, 2020, 2024]:
    origin = target_year - 1
    encoder_years = list(range(origin - seq['encoder_length'] + 1, origin + 1))
    firewall_examples.append({'target_year': target_year, 'origin_year': origin, 'encoder_years': encoder_years, 'target_outside_encoder': target_year not in encoder_years, 'max_encoder_lt_target': max(encoder_years) < target_year})
checks['temporal_firewall_examples'] = {'examples': firewall_examples, 'pass': all(x['target_outside_encoder'] and x['max_encoder_lt_target'] for x in firewall_examples)}
checks['chronological_order'] = {
    'train_before_validation': split['train']['target_years'][1] < split['validation']['target_years'][0],
    'validation_before_test': split['validation']['target_years'][1] < split['test']['target_years'][0],
    'pass': split['train']['target_years'][1] < split['validation']['target_years'][0] < split['test']['target_years'][0],
}
checks['no_random_split'] = {'shuffle': split['shuffle'], 'random_entity_split': split['random_entity_split'], 'pass': not split['shuffle'] and not split['random_entity_split']}
checks['no_imputation'] = {'contract_mode': contract['missing_data_policy']['mode'], 'runtime_behavior': contract['missing_data_policy']['runtime_behavior'], 'pass': contract['missing_data_policy']['mode'] == 'no_imputation'}
checks['no_transformations'] = {'transformations': contract['transformations'], 'pass': all(v is False for k,v in contract['transformations'].items() if isinstance(v, bool))}
checks['training_gate'] = {'training_authorized': contract['training_authorized'], 'approval_required': contract['approval_required'], 'pass': contract['training_authorized'] is False and contract['approval_required'] is True}

# Hashes support reproducibility without executing a model.
def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''):
            h.update(b)
    return h.hexdigest()

result={
    'contract': str(CONTRACT.relative_to(ROOT)),
    'matrix': str(MATRIX.relative_to(ROOT)),
    'contract_sha256': sha256(CONTRACT),
    'matrix_sha256': sha256(MATRIX),
    'checks': checks,
    'all_automated_checks_pass': all(v.get('pass', False) for v in checks.values()),
    'training_run': False,
    'tft_run': False,
    'architecture_changed': False,
    'notes': [
      'This is a data/contract audit only.',
      'entity_code is a group identifier, not a numeric predictor; TFT architecture must declare this explicitly.',
      'All selected covariates are past observed covariates in this contract; no future-known exogenous variables are declared.',
      'Target scaling is not approved and must remain a pre-training decision gate.'
    ]
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'all_automated_checks_pass':result['all_automated_checks_pass'],'checks':{k:v['pass'] for k,v in checks.items()},'output':str(OUT)},ensure_ascii=False,indent=2))
