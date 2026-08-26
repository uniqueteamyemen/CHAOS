#!/usr/bin/env python3
"""Build a compact JSONL registry from completed next-phase runs and the v1.1 baseline reference."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/home/ubuntu/CHAOS')
EXP = ROOT / 'experiments' / 'macro_plus_eia_energy'
NEXT = EXP / 'next_phase'
CAMPAIGN = NEXT / 'CAMPAIGN_RUN_RESULTS.json'
BASELINE = EXP / 'TFT_TRAINING_SUMMARY.json'
OUT = NEXT / 'NEXT_PHASE_EXPERIMENT_REGISTRY.jsonl'


def compact_run(run: dict) -> dict:
    return {
        'record_type': 'experiment_run',
        'run_id': run.get('run_id'),
        'family': run.get('family'),
        'status': run.get('status'),
        'seed': run.get('seed'),
        'encoder_length': run.get('encoder_length'),
        'support_start_target_year': run.get('support_start_target_year'),
        'target_years': {
            'train': run.get('train_target_years'),
            'validation': run.get('validation_target_years'),
            'test': run.get('test_target_years'),
        },
        'feature_count': len(run.get('feature_columns', [])),
        'feature_columns': run.get('feature_columns', []),
        'feature_columns_original': run.get('feature_columns_original', []),
        'window_counts': run.get('window_counts'),
        'best_checkpoint': run.get('best_checkpoint'),
        'best_epoch': run.get('best_epoch'),
        'validation_metrics': run.get('validation_metrics'),
        'test_metrics': run.get('test_metrics'),
        'test_used_for_selection': run.get('test_used_for_selection'),
        'raw_data_modified': run.get('raw_data_modified'),
        'imputation': run.get('imputation'),
        'transformations': run.get('transformations'),
        'model_params': run.get('model_params'),
        'evidence_role': 'exploratory_run',
    }


def compact_baseline(summary: dict) -> dict:
    return {
        'record_type': 'reference_run',
        'run_id': summary.get('experiment_id'),
        'family': 'full_matrix_baseline_v1_1_reference',
        'status': 'completed',
        'seed': 17,
        'encoder_length': 5,
        'support_start_target_year': 2006,
        'target_years': {
            'train': [2006, 2015],
            'validation': [2016, 2019],
            'test': [2020, 2024],
        },
        'feature_count': 11,
        'feature_columns': [
            'wdi__NY_GDP_MKTP_KD_ZG', 'wdi__NY_GDP_PCAP_KD',
            'wdi__FP_CPI_TOTL_ZG', 'wdi__SP_POP_TOTL', 'wdi__PA_NUS_PPP',
            'imf__NGDP_RPCH', 'imf__PCPI', 'imf__PPPEX', 'imf__BCA_NGDPD',
            'eia__energy_consumption_per_capita',
            'eia__energy_consumption_per_gdp',
        ],
        'checkpoint': summary.get('checkpoint'),
        'validation_metrics': {
            'split': 'validation',
            'note': 'Validation metrics are recorded in the baseline campaign artifacts; this summary exposes the locked test metrics.'
        },
        'test_metrics': summary.get('metrics'),
        'selection': {
            'checkpoint_selected_by': summary.get('checkpoint_selected_by'),
            'test_evaluation_locked': summary.get('test_evaluation_locked'),
        },
        'raw_data_modified': False,
        'imputation': False,
        'transformations': False,
        'model_params_note': 'Reference baseline was trained with max_epochs=50; new next-phase arms use max_epochs=25.',
        'evidence_role': 'full_matrix_reference_not_retrained',
    }


def main() -> None:
    campaign = json.loads(CAMPAIGN.read_text(encoding='utf-8'))
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    runs = campaign.get('results', [])
    with OUT.open('w', encoding='utf-8') as handle:
        handle.write(json.dumps(compact_baseline(baseline), ensure_ascii=False, sort_keys=True) + '\n')
        for run in runs:
            handle.write(json.dumps(compact_run(run), ensure_ascii=False, sort_keys=True) + '\n')
    print(json.dumps({
        'output': str(OUT.relative_to(ROOT)),
        'reference_records': 1,
        'campaign_records': len(runs),
        'failures_in_campaign': len(campaign.get('failures', [])),
        'reverse_extraction_run': False,
        'surrogate_run': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
