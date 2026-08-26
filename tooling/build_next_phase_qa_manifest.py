#!/usr/bin/env python3
"""Create a deterministic QA manifest for the completed CHAOS next-phase artifacts."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path('/home/ubuntu/CHAOS')
EXP = ROOT / 'experiments' / 'macro_plus_eia_energy'
NEXT = EXP / 'next_phase'
REPORT = NEXT / 'report'


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def artifact(path: Path) -> dict:
    return {'path': rel(path), 'bytes': path.stat().st_size, 'sha256': sha256(path)}


def git_hash(path: Path, revision: str) -> str | None:
    try:
        data = subprocess.check_output(['git', 'show', f'{revision}:{rel(path)}'], cwd=ROOT)
    except subprocess.CalledProcessError:
        return None
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    campaign = json.loads((NEXT / 'CAMPAIGN_RUN_RESULTS.json').read_text(encoding='utf-8'))
    summary = json.loads((REPORT / 'NEXT_PHASE_REPORT_SUMMARY.json').read_text(encoding='utf-8'))
    metrics_rows = (NEXT / 'CAMPAIGN_METRICS_SUMMARY.csv').read_text(encoding='utf-8').strip().splitlines()
    registry_rows = (NEXT / 'NEXT_PHASE_EXPERIMENT_REGISTRY.jsonl').read_text(encoding='utf-8').strip().splitlines()
    run_dirs = sorted(p for p in NEXT.iterdir() if p.is_dir() and (p / 'checkpoints').is_dir())
    checkpoints = sorted(p for p in NEXT.rglob('*.ckpt'))
    figures = sorted((REPORT / 'figures').glob('*.png'))
    raw_paths = [
        EXP.parent.parent / 'catalog_first' / 'readiness_gate' / 'macro_plus_eia_energy' / 'MACRO_PLUS_EIA_ENERGY_RAW_2000_2024_WIDE.csv',
        EXP.parent.parent / 'catalog_first' / 'readiness_gate' / 'macro_plus_eia_energy' / 'MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv',
    ]
    raw_integrity = []
    for path in raw_paths:
        current = sha256(path) if path.exists() else None
        head = git_hash(path, 'HEAD') if path.exists() else None
        raw_integrity.append({
            'path': rel(path),
            'exists': path.exists(),
            'current_sha256': current,
            'head_sha256': head,
            'matches_HEAD': current == head if current and head else None,
        })
    large_files = []
    for path in ROOT.rglob('*'):
        if path.is_file() and path.stat().st_size > 90 * 1024 * 1024:
            large_files.append({'path': rel(path), 'bytes': path.stat().st_size})
    manifest = {
        'manifest_type': 'CHAOS_next_phase_qa',
        'generated_from': {
            'campaign': rel(NEXT / 'CAMPAIGN_RUN_RESULTS.json'),
            'report_summary': rel(REPORT / 'NEXT_PHASE_REPORT_SUMMARY.json'),
        },
        'campaign': {
            'campaign_result_count': len(campaign.get('results', [])),
            'campaign_failure_count': len(campaign.get('failures', [])),
            'status_values': sorted({r.get('status') for r in campaign.get('results', [])}),
            'family_counts': {family: sum(r.get('family') == family for r in campaign.get('results', [])) for family in sorted({r.get('family') for r in campaign.get('results', [])})},
            'all_test_used_for_selection_false': all(r.get('test_used_for_selection') is False for r in campaign.get('results', [])),
            'all_raw_data_modified_false': all(r.get('raw_data_modified') is False for r in campaign.get('results', [])),
            'all_imputation_false': all(r.get('imputation') is False for r in campaign.get('results', [])),
            'all_transformations_false': all(r.get('transformations') is False for r in campaign.get('results', [])),
        },
        'report_summary': summary,
        'artifact_counts': {
            'run_directories': len(run_dirs),
            'checkpoints': len(checkpoints),
            'figures': len(figures),
            'metrics_csv_data_rows': len(metrics_rows) - 1,
            'registry_jsonl_records': len(registry_rows),
        },
        'raw_integrity': raw_integrity,
        'large_files_over_90MB': large_files,
        'figures': [artifact(p) for p in figures],
        'checkpoints': [artifact(p) for p in checkpoints],
        'qa_pass_conditions': {
            'expected_campaign_runs_17': len(campaign.get('results', [])) == 17,
            'expected_campaign_failures_0': len(campaign.get('failures', [])) == 0,
            'expected_figures_4': len(figures) == 4,
            'expected_run_directories_17': len(run_dirs) == 17,
            'expected_checkpoints_17': len(checkpoints) == 17,
            'expected_registry_records_18_including_reference': len(registry_rows) == 18,
            'no_files_over_90MB': len(large_files) == 0,
            'reverse_extraction_not_run': summary.get('reverse_extraction_run') is False,
            'surrogate_not_run': summary.get('surrogate_run') is False,
            'raw_data_modified_false': summary.get('raw_data_modified') is False,
        },
    }
    out = NEXT / 'NEXT_PHASE_QA_MANIFEST.json'
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({
        'output': rel(out),
        'campaign_runs': len(campaign.get('results', [])),
        'failures': len(campaign.get('failures', [])),
        'run_directories': len(run_dirs),
        'checkpoints': len(checkpoints),
        'figures': len(figures),
        'registry_records': len(registry_rows),
        'large_files_over_90MB': len(large_files),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
