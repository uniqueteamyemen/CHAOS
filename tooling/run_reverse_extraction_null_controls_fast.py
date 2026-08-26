#!/usr/bin/env python3
"""Fast deterministic null controls for the frozen reverse-extraction candidate."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_reverse_extraction_discovery import (
    CONTRACT_PATH,
    add_split,
    binary_metrics,
    load_panel,
    make_origin_frame,
    path_mask,
    thresholds_from_fit,
)

ROOT = Path('/home/ubuntu/CHAOS')
OUT = ROOT / 'experiments' / 'macro_plus_eia_energy' / 'reverse_extraction_v1_draft'
SEED = 460
REPLICATES = 5000
EVAL_SPLITS = ('discovery_inner', 'validation')
CONTROL_NAMES = (
    'label_permutation_within_entity_and_split',
    'support_matched_random_trigger_within_entity_and_split',
    'temporal_cyclic_shift_placebo_within_entity_and_split',
)


def metric_arrays(y: np.ndarray, trigger: np.ndarray, entity: np.ndarray, years: np.ndarray) -> dict:
    y = y.astype(bool)
    trigger = trigger.astype(bool)
    tp = int(np.sum(trigger & y)); tn = int(np.sum(~trigger & ~y))
    fp = int(np.sum(trigger & ~y)); fn = int(np.sum(~trigger & y))
    support = int(trigger.sum()); positives = int(y.sum()); negatives = int((~y).sum())
    precision = tp / support if support else 0.0
    recall = tp / positives if positives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    tpr = tp / positives if positives else 0.0; tnr = tn / negatives if negatives else 0.0
    return {
        'n_origins': int(len(y)), 'support': support, 'positive_outcomes': positives,
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
        'precision': precision, 'recall': recall, 'f1': f1,
        'balanced_accuracy': (tpr + tnr) / 2,
        'false_alarm_rate': fp / negatives if negatives else 0.0,
        'entity_coverage': int(np.unique(entity[trigger]).size) if support else 0,
        'year_coverage': int(np.unique(years[trigger]).size) if support else 0,
        'lead_time_years': 1.0,
    }


def prepare_split(origins: pd.DataFrame, split: str, clauses: tuple, thresholds: dict) -> dict:
    subset = origins[(origins['split'] == split) & origins['outcome_t_plus_1'].notna()].copy()
    observed = path_mask(subset, clauses, thresholds).to_numpy(dtype=bool)
    entity = subset['entity_code'].to_numpy()
    years = subset['origin_year'].to_numpy(dtype=int)
    y = subset['outcome_t_plus_1'].astype(int).to_numpy()
    groups = [np.flatnonzero(entity == e) for e in np.unique(entity)]
    return {'subset': subset, 'observed': observed, 'entity': entity, 'years': years, 'y': y, 'groups': groups}


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    selected_path = json.loads((OUT / 'FROZEN_SELECTED_PATH.json').read_text(encoding='utf-8'))
    reverse = {'low_or_negative': 'low', 'middle': 'mid', 'high_or_nonnegative': 'high'}
    clauses = tuple((c['feature'], int(c['lag']), reverse[c['state']]) for c in selected_path['clauses'])
    origins = add_split(make_origin_frame(load_panel()))
    thresholds = thresholds_from_fit(origins)
    data = {split: prepare_split(origins, split, clauses, thresholds) for split in EVAL_SPLITS}
    observed_rows = []
    for split in EVAL_SPLITS:
        d = data[split]
        observed_rows.append({'control': 'observed_frozen_candidate', 'replicate': -1, 'split': split, **metric_arrays(d['y'], d['observed'], d['entity'], d['years'])})
    pd.DataFrame(observed_rows).to_csv(OUT / 'NULL_CONTROL_OBSERVED_METRICS.csv', index=False)

    rng = np.random.default_rng(SEED)
    records = []
    for replicate in range(REPLICATES):
        for split in EVAL_SPLITS:
            d = data[split]; y = d['y']; observed = d['observed']; entity = d['entity']; years = d['years']; groups = d['groups']
            y_perm = y.copy()
            for idx in groups:
                y_perm[idx] = rng.permutation(y_perm[idx])
            records.append({'control': CONTROL_NAMES[0], 'replicate': replicate, 'split': split, **metric_arrays(y_perm, observed, entity, years)})
            random_trigger = np.zeros(len(y), dtype=bool)
            for idx in groups:
                k = int(observed[idx].sum())
                if k:
                    random_trigger[rng.choice(idx, size=k, replace=False)] = True
            records.append({'control': CONTROL_NAMES[1], 'replicate': replicate, 'split': split, **metric_arrays(y, random_trigger, entity, years)})
            shifted = np.zeros(len(y), dtype=bool)
            for idx in groups:
                values = observed[idx]
                shifted[idx] = values if len(idx) <= 1 else np.roll(values, int(rng.integers(1, len(idx))))
            records.append({'control': CONTROL_NAMES[2], 'replicate': replicate, 'split': split, **metric_arrays(y, shifted, entity, years)})
    nulls = pd.DataFrame.from_records(records)
    nulls.to_csv(OUT / 'NULL_CONTROL_REPLICATE_METRICS.csv', index=False)

    observed_df = pd.DataFrame(observed_rows)
    summaries = []
    for _, obs in observed_df.iterrows():
        sample_split = nulls[nulls['split'] == obs['split']]
        for control in CONTROL_NAMES:
            sample = sample_split[sample_split['control'] == control]
            summaries.append({
                'control': control, 'split': obs['split'], 'replicates': int(len(sample)),
                'observed_balanced_accuracy': float(obs['balanced_accuracy']), 'observed_f1': float(obs['f1']),
                'null_balanced_accuracy_mean': float(sample['balanced_accuracy'].mean()), 'null_balanced_accuracy_sd': float(sample['balanced_accuracy'].std(ddof=1)),
                'null_balanced_accuracy_q025': float(sample['balanced_accuracy'].quantile(0.025)), 'null_balanced_accuracy_q500': float(sample['balanced_accuracy'].quantile(0.5)), 'null_balanced_accuracy_q975': float(sample['balanced_accuracy'].quantile(0.975)),
                'null_f1_mean': float(sample['f1'].mean()), 'null_f1_sd': float(sample['f1'].std(ddof=1)),
                'null_f1_q025': float(sample['f1'].quantile(0.025)), 'null_f1_q500': float(sample['f1'].quantile(0.5)), 'null_f1_q975': float(sample['f1'].quantile(0.975)),
                'p_balanced_accuracy_upper': float((1 + int((sample['balanced_accuracy'] >= obs['balanced_accuracy']).sum())) / (REPLICATES + 1)),
                'p_f1_upper': float((1 + int((sample['f1'] >= obs['f1']).sum())) / (REPLICATES + 1)),
            })
    pd.DataFrame(summaries).to_csv(OUT / 'NULL_CONTROL_SUMMARY.csv', index=False)
    run_summary = {
        'run_id': 'reverse_extraction_null_controls_v1', 'contract': str(CONTRACT_PATH.relative_to(ROOT)),
        'candidate_run': 'reverse_extraction_v1_draft_symbolic', 'candidate_rule_id': selected_path['rule_id'],
        'seed': SEED, 'replicates_per_control_per_split': REPLICATES, 'controls': list(CONTROL_NAMES),
        'evaluated_splits': list(EVAL_SPLITS), 'locked_test_executed': False, 'null_test_years_included': False,
        'raw_data_modified': False, 'imputation': False, 'normalization': False,
        'p_value_rule': contract['null_plan']['p_value_rule'],
        'decision': 'null_evidence_only; no operational promotion and no causal interpretation',
    }
    (OUT / 'NULL_CONTROL_RUN_SUMMARY.json').write_text(json.dumps(run_summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'run_id': run_summary['run_id'], 'candidate_rule_id': selected_path['rule_id'], 'replicates_per_control_per_split': REPLICATES, 'controls': list(CONTROL_NAMES), 'evaluated_splits': list(EVAL_SPLITS), 'rows_saved': len(nulls), 'locked_test_executed': False, 'null_test_years_included': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
