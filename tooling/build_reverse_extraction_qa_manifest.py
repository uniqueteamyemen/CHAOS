#!/usr/bin/env python3
"""Build a QA manifest for the draft reverse-extraction discovery/replay."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path('/home/ubuntu/CHAOS')
OUT = ROOT / 'experiments' / 'macro_plus_eia_energy' / 'reverse_extraction_v1_draft'
PANEL = ROOT / 'catalog_first' / 'readiness_gate' / 'macro_plus_eia_energy' / 'MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
RAW = ROOT / 'catalog_first' / 'readiness_gate' / 'macro_plus_eia_energy' / 'MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha256(path: Path) -> str | None:
    try:
        content = subprocess.check_output(['git', 'show', f'HEAD:{path.relative_to(ROOT)}'], cwd=ROOT)
    except subprocess.CalledProcessError:
        return None
    return hashlib.sha256(content).hexdigest()


def artifact(path: Path) -> dict:
    return {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size, 'sha256': sha256(path)}


def main() -> None:
    summary = json.loads((OUT / 'RUN_SUMMARY.json').read_text(encoding='utf-8'))
    path = json.loads((OUT / 'FROZEN_SELECTED_PATH.json').read_text(encoding='utf-8'))
    rows = list(csv.DictReader((OUT / 'FROZEN_PATH_REPLAY_ORIGINS.csv').open(encoding='utf-8', newline='')))
    metrics = list(csv.DictReader((OUT / 'FROZEN_PATH_METRICS_BY_SPLIT.csv').open(encoding='utf-8', newline='')))
    replay_splits = sorted({r['split'] for r in rows})
    replay_years = [int(r['origin_year']) for r in rows]
    key_files = [
        OUT / 'RUN_SUMMARY.json', OUT / 'FROZEN_SELECTED_PATH.json', OUT / 'FROZEN_MULTINODE_PATH.json',
        OUT / 'FROZEN_PATH_METRICS_BY_SPLIT.csv', OUT / 'MULTINODE_PATH_METRICS_BY_SPLIT.csv',
        OUT / 'BASELINE_CLASSIFICATION_COMPARISON.csv', OUT / 'DISCOVERY_UNIVARIATE_SHORTLIST.csv',
        OUT / 'DISCOVERY_INNER_TOP_PATHS.csv', OUT / 'FROZEN_PATH_REPLAY_ORIGINS.csv',
        OUT / 'run.log',
    ]
    manifest = {
        'manifest_type': 'CHAOS_reverse_extraction_v1_draft_qa',
        'run_id': summary['run_id'],
        'contract': summary['contract'],
        'panel': summary['panel'],
        'selected_status': path['status'],
        'selected_rule_id': path['rule_id'],
        'candidate_paths_generated': summary['candidate_paths_generated'],
        'inner_supported_paths': summary['inner_supported_paths'],
        'replay': {
            'row_count': len(rows),
            'splits': replay_splits,
            'max_origin_year': max(replay_years),
            'contains_locked_test_split': 'locked_test_deferred' in replay_splits,
            'metrics_rows': len(metrics),
        },
        'raw_integrity': {
            'panel_current_sha256': sha256(PANEL),
            'panel_head_sha256': git_blob_sha256(PANEL),
            'raw_current_sha256': sha256(RAW),
            'raw_head_sha256': git_blob_sha256(RAW),
            'panel_matches_HEAD': sha256(PANEL) == git_blob_sha256(PANEL),
            'raw_matches_HEAD': sha256(RAW) == git_blob_sha256(RAW),
        },
        'execution_flags': {
            'locked_test_executed': summary['locked_test_executed'],
            'null_executed': summary['null_executed'],
            'raw_data_modified': summary['raw_data_modified'],
            'imputation': summary['imputation'],
            'normalization': summary['normalization'],
            'causal_claim': path['causal_claim'],
        },
        'qa_pass_conditions': {
            'selected_path_status_is_not_validated': path['status'] != 'reconstructed_validation_only',
            'candidate_paths_positive': summary['candidate_paths_generated'] > 0,
            'replay_has_fit_inner_validation_only': set(replay_splits) == {'discovery_fit', 'discovery_inner', 'validation'},
            'replay_max_origin_2019': max(replay_years) == 2019,
            'locked_test_false': summary['locked_test_executed'] is False and path['locked_test_run'] is False,
            'null_false': summary['null_executed'] is False and path['null_run'] is False,
            'raw_unchanged': summary['raw_data_modified'] is False,
            'no_imputation_or_normalization': summary['imputation'] is False and summary['normalization'] is False,
            'panel_matches_HEAD': sha256(PANEL) == git_blob_sha256(PANEL),
            'raw_matches_HEAD': sha256(RAW) == git_blob_sha256(RAW),
        },
        'artifacts': [artifact(p) for p in key_files if p.exists()],
    }
    output = OUT / 'REVERSE_EXTRACTION_QA_MANIFEST.json'
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'output': str(output.relative_to(ROOT)),
        'selected_status': path['status'],
        'candidate_paths': summary['candidate_paths_generated'],
        'replay_rows': len(rows),
        'replay_splits': replay_splits,
        'max_origin_year': max(replay_years),
        'locked_test_executed': summary['locked_test_executed'],
        'null_executed': summary['null_executed'],
        'qa_all_true': all(manifest['qa_pass_conditions'].values()),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
