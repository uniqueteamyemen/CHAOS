#!/usr/bin/env python3
"""Discovery-only reverse extraction and frozen validation replay for CHAOS.

This is a symbolic, auditable first pass. It does not run locked test, nulls, or
promote a pattern. Raw values remain unchanged; state thresholds are derived
from discovery_fit only and stored with the selected path.
"""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path('/home/ubuntu/CHAOS')
CONTRACT_PATH = ROOT / 'experimental_contracts' / 'REVERSE_EXTRACTION_CONTRACT_V1_DRAFT.json'
PANEL_PATH = ROOT / 'catalog_first' / 'readiness_gate' / 'macro_plus_eia_energy' / 'MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
OUT = ROOT / 'experiments' / 'macro_plus_eia_energy' / 'reverse_extraction_v1_draft'
OUT.mkdir(parents=True, exist_ok=True)

TARGET = 'wdi__NY_GDP_MKTP_KD_ZG'
FEATURES = [
    'wdi__NY_GDP_MKTP_KD_ZG', 'wdi__NY_GDP_PCAP_KD',
    'wdi__FP_CPI_TOTL_ZG', 'wdi__SP_POP_TOTL', 'wdi__PA_NUS_PPP',
    'imf__NGDP_RPCH', 'imf__PCPI', 'imf__PPPEX', 'imf__BCA_NGDPD',
    'eia__energy_consumption_per_capita',
    'eia__energy_consumption_per_gdp',
]
ZERO_STATE_FEATURES = {'wdi__NY_GDP_MKTP_KD_ZG', 'imf__NGDP_RPCH'}
LAGS = [2, 1, 0]
STATE_NAMES = {'low': 'low_or_negative', 'mid': 'middle', 'high': 'high_or_nonnegative'}


def load_panel() -> pd.DataFrame:
    df = pd.read_csv(PANEL_PATH)
    df = df.rename(columns={c: c.replace('.', '_') for c in df.columns})
    expected = {'entity_code', 'year', TARGET, *FEATURES}
    missing = expected.difference(df.columns)
    if missing:
        raise ValueError(f'missing columns after safe aliasing: {sorted(missing)}')
    return df.sort_values(['entity_code', 'year']).reset_index(drop=True)


def make_origin_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df[['entity_code', 'year'] + FEATURES].copy()
    next_target = out.groupby('entity_code')[TARGET].shift(-1)
    out['target_t_plus_1'] = next_target
    out['outcome_t_plus_1'] = next_target.lt(0).where(next_target.notna(), pd.NA).astype('Int64')
    out = out.rename(columns={'year': 'origin_year'})
    for feature in FEATURES:
        for lag in LAGS:
            out[f'{feature}__lag{lag}'] = out.groupby('entity_code')[feature].shift(lag)
    return out


def thresholds_from_fit(df: pd.DataFrame) -> dict:
    thresholds = {}
    fit = df[df.origin_year.between(2006, 2012)].copy()
    for feature in FEATURES:
        vals = fit[feature].dropna().astype(float)
        if feature in ZERO_STATE_FEATURES:
            thresholds[feature] = {'method': 'zero_sign', 'q33': 0.0, 'q67': 0.0}
        else:
            thresholds[feature] = {
                'method': 'fit_q33_q67',
                'q33': float(vals.quantile(1 / 3)),
                'q67': float(vals.quantile(2 / 3)),
            }
    return thresholds


def state_mask(series: pd.Series, feature: str, state: str, thresholds: dict) -> pd.Series:
    t = thresholds[feature]
    if t['method'] == 'zero_sign':
        if state == 'low':
            return series <= 0
        if state == 'high':
            return series > 0
        return pd.Series(False, index=series.index)
    if state == 'low':
        return series <= t['q33']
    if state == 'mid':
        return (series > t['q33']) & (series <= t['q67'])
    return series > t['q67']


def clause_mask(df: pd.DataFrame, clause: tuple, thresholds: dict) -> pd.Series:
    feature, lag, state = clause
    return state_mask(df[f'{feature}__lag{lag}'], feature, state, thresholds)


def path_mask(df: pd.DataFrame, clauses: tuple, thresholds: dict) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for clause in clauses:
        mask &= clause_mask(df, clause, thresholds)
    return mask


def binary_metrics(df: pd.DataFrame, trigger: pd.Series) -> dict:
    valid = df['outcome_t_plus_1'].notna() & trigger.notna()
    y = df.loc[valid, 'outcome_t_plus_1'].astype(int).to_numpy()
    p = trigger.loc[valid].astype(bool).to_numpy()
    tp = int(((p == 1) & (y == 1)).sum())
    tn = int(((p == 0) & (y == 0)).sum())
    fp = int(((p == 1) & (y == 0)).sum())
    fn = int(((p == 0) & (y == 1)).sum())
    support = int(p.sum())
    positives = int(y.sum())
    negatives = int((y == 0).sum())
    precision = tp / support if support else 0.0
    recall = tp / positives if positives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    tpr = tp / positives if positives else 0.0
    tnr = tn / negatives if negatives else 0.0
    return {
        'n_origins': int(valid.sum()), 'support': support, 'positive_outcomes': positives,
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
        'precision': precision, 'recall': recall, 'f1': f1,
        'balanced_accuracy': (tpr + tnr) / 2,
        'false_alarm_rate': fp / negatives if negatives else 0.0,
        'entity_coverage': int(df.loc[valid & trigger, 'entity_code'].nunique()),
        'year_coverage': int(df.loc[valid & trigger, 'origin_year'].nunique()),
        'lead_time_years': 1.0,
    }


def rule_id(clauses: tuple) -> str:
    return ' && '.join(f'{feature}[t-{lag}]={STATE_NAMES[state]}' for feature, lag, state in clauses)


def clauses_for_feature(feature: str) -> list[tuple]:
    states = ['low', 'high'] if feature in ZERO_STATE_FEATURES else ['low', 'mid', 'high']
    return [(feature, lag, state) for lag in LAGS for state in states]


def score_univariates(df: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    rows = []
    fit = df[df.origin_year.between(2006, 2012)]
    for feature in FEATURES:
        for clause in clauses_for_feature(feature):
            trigger = clause_mask(fit, clause, thresholds)
            m = binary_metrics(fit, trigger)
            rows.append({'rule_id': rule_id((clause,)), 'feature': feature, 'lag': clause[1], 'state': STATE_NAMES[clause[2]], **m})
    result = pd.DataFrame(rows)
    result = result[(result.support >= 20)].sort_values(['balanced_accuracy', 'f1', 'support', 'rule_id'], ascending=[False, False, False, True])
    return result.reset_index(drop=True)


def candidate_paths(shortlist: pd.DataFrame, path_lengths: tuple[int, ...]) -> list[tuple]:
    by_id = {}
    for _, row in shortlist.iterrows():
        state = {'low_or_negative': 'low', 'middle': 'mid', 'high_or_nonnegative': 'high'}[row['state']]
        clause = (row['feature'], int(row['lag']), state)
        by_id[row['rule_id']] = clause
    primitives = [by_id[k] for k in shortlist['rule_id']]
    paths = []
    for length in path_lengths:
        for combo in itertools.combinations(primitives, length):
            # Avoid duplicate feature/lag clauses and retain chronological order in the id.
            if len({(c[0], c[1]) for c in combo}) != len(combo):
                continue
            paths.append(tuple(sorted(combo, key=lambda c: (c[1], c[0], c[2]), reverse=True)))
    return paths


def path_sort_key(row: dict) -> tuple:
    return (-row['balanced_accuracy'], -row['f1'], len(row['clauses']), -row['support'], row['rule_id'])


def evaluate_paths(df: pd.DataFrame, paths: list[tuple], thresholds: dict, split_name: str) -> pd.DataFrame:
    rows = []
    subset = df[df['split'] == split_name]
    for clauses in paths:
        trigger = path_mask(subset, clauses, thresholds)
        m = binary_metrics(subset, trigger)
        if m['support'] >= 10:
            rows.append({'rule_id': rule_id(clauses), 'clauses': json.dumps(clauses), 'path_length': len(clauses), 'split': split_name, **m})
    if not rows:
        return pd.DataFrame(columns=['rule_id', 'clauses', 'path_length', 'split', 'n_origins', 'support', 'positive_outcomes', 'tp', 'tn', 'fp', 'fn', 'precision', 'recall', 'f1', 'balanced_accuracy', 'false_alarm_rate', 'entity_coverage', 'year_coverage', 'lead_time_years'])
    return pd.DataFrame(rows).sort_values(['balanced_accuracy', 'f1', 'path_length', 'support', 'rule_id'], ascending=[False, False, True, False, True]).reset_index(drop=True)


def add_split(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['split'] = np.select(
        [df.origin_year.between(2006, 2012), df.origin_year.between(2013, 2015), df.origin_year.between(2016, 2019), df.origin_year.between(2020, 2023)],
        ['discovery_fit', 'discovery_inner', 'validation', 'locked_test_deferred'],
        default='outside_contract',
    )
    # The 2024 origin cannot score t+1 in this panel, so it remains invalid/deferred.
    return df


def main() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    panel = load_panel()
    origins = add_split(make_origin_frame(panel))
    thresholds = thresholds_from_fit(origins)
    univariate = score_univariates(origins, thresholds)
    shortlist_size = int(contract['search_space']['candidate_univariate_shortlist_size'])
    path_lengths = tuple(int(x) for x in contract['search_space']['path_lengths'])
    shortlist = univariate.head(shortlist_size).copy()
    paths = candidate_paths(shortlist, path_lengths)
    inner = evaluate_paths(origins, paths, thresholds, 'discovery_inner')
    if inner.empty:
        raise RuntimeError('no candidate path met the inner support minimum')
    selected = inner.iloc[0].to_dict()
    selected_clauses = tuple(tuple(x) for x in json.loads(selected['clauses']))
    multinode_candidates = inner[inner['path_length'] >= 2]
    selected_multinode = multinode_candidates.iloc[0].to_dict() if not multinode_candidates.empty else None
    multinode_clauses = tuple(tuple(x) for x in json.loads(selected_multinode['clauses'])) if selected_multinode else None
    val = evaluate_paths(origins, [selected_clauses], thresholds, 'validation')
    fit = evaluate_paths(origins, [selected_clauses], thresholds, 'discovery_fit')
    multinode_val = evaluate_paths(origins, [multinode_clauses], thresholds, 'validation') if multinode_clauses else pd.DataFrame()
    multinode_fit = evaluate_paths(origins, [multinode_clauses], thresholds, 'discovery_fit') if multinode_clauses else pd.DataFrame()
    validation_target_baseline_metrics = None
    baseline_rows = []
    for split_name in ('discovery_fit', 'discovery_inner', 'validation'):
        subset = origins[origins['split'] == split_name]
        controls = {
            'always_negative': pd.Series(False, index=subset.index),
            'always_positive': pd.Series(True, index=subset.index),
            'target_history_negative_at_t': clause_mask(subset, (TARGET, 0, 'low'), thresholds),
        }
        for baseline_id, baseline_trigger in controls.items():
            metrics_for_baseline = binary_metrics(subset, baseline_trigger)
            baseline_rows.append({'baseline_id': baseline_id, 'split': split_name, **metrics_for_baseline})
            if split_name == 'validation' and baseline_id == 'target_history_negative_at_t':
                validation_target_baseline_metrics = metrics_for_baseline
    pd.DataFrame(baseline_rows).to_csv(OUT / 'BASELINE_CLASSIFICATION_COMPARISON.csv', index=False)
    validation_metrics_dict = val.iloc[0].to_dict() if not val.empty else None
    beats_validation_baseline = bool(
        validation_metrics_dict and validation_target_baseline_metrics
        and validation_metrics_dict['balanced_accuracy'] > validation_target_baseline_metrics['balanced_accuracy']
        and validation_metrics_dict['f1'] > validation_target_baseline_metrics['f1']
    )
    selected_status = 'reconstructed_validation_only' if beats_validation_baseline else 'rejected_or_null_like'
    selected_path = {
        'rule_id': selected['rule_id'],
        'clauses': [{'feature': c[0], 'lag': int(c[1]), 'state': STATE_NAMES[c[2]]} for c in selected_clauses],
        'path_length': len(selected_clauses),
        'trigger_definition': 'conjunction of frozen states at origin t using rows through t only; outcome is assessed at t+1 after trigger.',
        'thresholds_frozen_from': 'discovery_fit target years 2006-2012',
        'selection_split': 'discovery_inner target years 2013-2015',
        'validation_split': 'validation target years 2016-2019',
        'locked_test_run': False,
        'null_run': False,
        'causal_claim': False,
        'status': selected_status,
        'validation_baseline_metrics': validation_target_baseline_metrics,
        'beats_validation_baseline': beats_validation_baseline,
        'fit_metrics': fit.iloc[0].to_dict() if not fit.empty else None,
        'inner_metrics': selected,
        'validation_metrics': validation_metrics_dict,
    }
    if selected_multinode:
        multinode_path = {
            'rule_id': selected_multinode['rule_id'],
            'clauses': [{'feature': c[0], 'lag': int(c[1]), 'state': STATE_NAMES[c[2]]} for c in multinode_clauses],
            'path_length': len(multinode_clauses),
            'selection_split': 'discovery_inner target years 2013-2015',
            'locked_test_run': False,
            'null_run': False,
            'causal_claim': False,
            'fit_metrics': multinode_fit.iloc[0].to_dict() if not multinode_fit.empty else None,
            'inner_metrics': selected_multinode,
            'validation_metrics': multinode_val.iloc[0].to_dict() if not multinode_val.empty else None,
            'status': 'comparison_only_not_selected',
        }
        (OUT / 'FROZEN_MULTINODE_PATH.json').write_text(json.dumps(multinode_path, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
        pd.DataFrame([multinode_fit.iloc[0].to_dict(), selected_multinode, multinode_val.iloc[0].to_dict() if not multinode_val.empty else {'split': 'validation', 'status': 'no_supported_triggers'}]).to_csv(OUT / 'MULTINODE_PATH_METRICS_BY_SPLIT.csv', index=False)
    allowed_replay = origins['split'].isin(['discovery_fit', 'discovery_inner', 'validation'])
    replay = origins.loc[allowed_replay, ['entity_code', 'origin_year', TARGET, 'target_t_plus_1', 'outcome_t_plus_1', 'split']].copy()
    replay['trigger'] = path_mask(origins.loc[allowed_replay], selected_clauses, thresholds).astype(bool).to_numpy()
    replay['selected_rule_id'] = selected['rule_id']
    replay.to_csv(OUT / 'FROZEN_PATH_REPLAY_ORIGINS.csv', index=False)
    univariate.to_csv(OUT / 'DISCOVERY_UNIVARIATE_SHORTLIST.csv', index=False)
    inner.head(100).to_csv(OUT / 'DISCOVERY_INNER_TOP_PATHS.csv', index=False)
    pd.DataFrame([fit.iloc[0].to_dict(), selected, val.iloc[0].to_dict() if not val.empty else {'split': 'validation', 'status': 'no_supported_triggers'}]).to_csv(OUT / 'FROZEN_PATH_METRICS_BY_SPLIT.csv', index=False)
    (OUT / 'FROZEN_SELECTED_PATH.json').write_text(json.dumps(selected_path, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    (OUT / 'THRESHOLDS_FROM_DISCOVERY_FIT.json').write_text(json.dumps(thresholds, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    run_summary = {
        'run_id': 'reverse_extraction_v1_draft_symbolic',
        'contract': str(CONTRACT_PATH.relative_to(ROOT)),
        'panel': str(PANEL_PATH.relative_to(ROOT)),
        'status': selected_path['status'],
        'candidate_paths_generated': len(paths),
        'univariate_shortlist_rows': len(shortlist),
        'inner_supported_paths': len(inner),
        'discovery_fit_years': [2006, 2012],
        'discovery_inner_years': [2013, 2015],
        'validation_years': [2016, 2019],
        'locked_test_executed': False,
        'null_executed': False,
        'raw_data_modified': False,
        'imputation': False,
        'normalization': False,
        'selected_path': selected_path,
        'baseline_comparison': 'BASELINE_CLASSIFICATION_COMPARISON.csv',
        'multinode_comparison': 'FROZEN_MULTINODE_PATH.json' if selected_multinode else None,
        'decision': 'candidate_only; no operational promotion and no causal interpretation',
    }
    (OUT / 'RUN_SUMMARY.json').write_text(json.dumps(run_summary, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps({
        'run_id': run_summary['run_id'],
        'candidate_paths_generated': len(paths),
        'inner_supported_paths': len(inner),
        'selected_rule_id': selected['rule_id'],
        'fit_balanced_accuracy': float(fit.iloc[0]['balanced_accuracy']) if not fit.empty else None,
        'inner_balanced_accuracy': float(selected['balanced_accuracy']),
        'validation_balanced_accuracy': float(val.iloc[0]['balanced_accuracy']) if not val.empty else None,
        'locked_test_executed': False,
        'null_executed': False,
        'status': selected_path['status'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
