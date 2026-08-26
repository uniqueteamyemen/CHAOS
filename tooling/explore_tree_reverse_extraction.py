#!/usr/bin/env python3
"""Exploratory tree-path extraction for outcome families and longer leads.

This is a discovery/validation experiment. It uses compact decision trees as a
symbolic path extractor, keeps target-year splits disjoint, and never evaluates
locked-test outcomes. All outputs are provenance artifacts, not promotion.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, precision_score, recall_score
from sklearn.tree import DecisionTreeClassifier, _tree

ROOT = Path('/home/ubuntu/CHAOS')
PANEL = ROOT / 'catalog_first' / 'readiness_gate' / 'macro_plus_eia_energy' / 'MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
OUT = ROOT / 'experiments' / 'macro_plus_eia_energy' / 'reverse_extraction_tree_v1'
TARGET = 'wdi__NY_GDP_MKTP_KD_ZG'
ALL_FEATURES = [
    'wdi__NY_GDP_PCAP_KD', 'wdi__FP_CPI_TOTL_ZG', 'wdi__SP_POP_TOTL', 'wdi__PA_NUS_PPP',
    'imf__NGDP_RPCH', 'imf__PCPI', 'imf__PPPEX', 'imf__BCA_NGDPD',
    'eia__energy_consumption_per_capita', 'eia__energy_consumption_per_gdp',
]
HORIZONS = (1, 2, 3)
FAMILIES = ('onset_contraction', 'material_drop_2pp')
MODES = ('exogenous_only', 'with_target_history')
DEPTHS = (2, 3, 4)
SEEDS = (17, 43)
MIN_LEAF = 18


def load_panel() -> pd.DataFrame:
    df = pd.read_csv(PANEL).rename(columns=lambda c: c.replace('.', '_'))
    return df.sort_values(['entity_code', 'year']).reset_index(drop=True)


def build_origins(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    df = panel.copy()
    g = df.groupby('entity_code')[TARGET]
    df['future_target'] = g.shift(-horizon)
    df['target_year'] = df['year'] + horizon
    df['outcome_onset_contraction'] = (df['future_target'] < 0) & (df[TARGET] >= 0)
    df['outcome_material_drop_2pp'] = df['future_target'] <= (df[TARGET] - 2.0)
    for feature in ALL_FEATURES + [TARGET]:
        for lag in (0, 1, 2):
            df[f'{feature}__lag{lag}'] = df.groupby('entity_code')[feature].shift(lag)
    # Splits are assigned by outcome year, not origin year. Test outcomes are not used.
    df['split'] = np.select(
        [df['target_year'].between(2006, 2012), df['target_year'].between(2013, 2015), df['target_year'].between(2016, 2019), df['target_year'].between(2020, 2024)],
        ['discovery_fit', 'discovery_inner', 'validation', 'locked_test'], default='outside_contract')
    return df


def metrics(y: np.ndarray, pred: np.ndarray, entity: np.ndarray, year: np.ndarray, leaf: np.ndarray) -> dict[str, Any]:
    return {
        'n_origins': int(len(y)), 'support': int(pred.sum()), 'positive_outcomes': int(y.sum()),
        'precision': float(precision_score(y, pred, zero_division=0)),
        'recall': float(recall_score(y, pred, zero_division=0)),
        'f1': float(f1_score(y, pred, zero_division=0)),
        'balanced_accuracy': float(balanced_accuracy_score(y, pred)),
        'entity_coverage': int(np.unique(entity[pred]).size) if pred.any() else 0,
        'year_coverage': int(np.unique(year[pred]).size) if pred.any() else 0,
        'leaf_ids': ','.join(map(str, sorted(np.unique(leaf[pred]).tolist()))) if pred.any() else '',
        'lead_time_years': None,
    }


def feature_columns(mode: str) -> list[str]:
    base = [f'{feature}__lag{lag}' for feature in ALL_FEATURES for lag in (0, 1, 2)]
    if mode == 'with_target_history':
        base += [f'{TARGET}__lag{lag}' for lag in (0, 1, 2)]
    return base


def extract_leaf_path(tree: DecisionTreeClassifier, leaf_id: int, feature_names: list[str]) -> list[str]:
    t = tree.tree_; clauses: list[str] = []
    node = leaf_id
    while node != 0:
        parents = np.where((t.children_left == node) | (t.children_right == node))[0]
        if len(parents) == 0: break
        parent = int(parents[0]); feature_idx = int(t.feature[parent]); threshold = float(t.threshold[parent])
        name = feature_names[feature_idx]
        if t.children_left[parent] == node:
            clauses.append(f'{name} <= {threshold:.8g}')
        else:
            clauses.append(f'{name} > {threshold:.8g}')
        node = parent
    return list(reversed(clauses))


def select_leaf(tree: DecisionTreeClassifier, frame: pd.DataFrame, y: np.ndarray, feature_names: list[str], split: str) -> pd.DataFrame:
    X = frame[feature_names].to_numpy(dtype=float)
    leaves = tree.apply(X)
    rows = []
    for leaf_id in sorted(np.unique(leaves)):
        idx = leaves == leaf_id
        if int(idx.sum()) < MIN_LEAF: continue
        pred = idx
        rows.append({
            'leaf_id': int(leaf_id), 'split': split, 'support': int(pred.sum()),
            'positive_outcomes': int(y[pred].sum()),
            'precision': float(precision_score(y, pred, zero_division=0)),
            'recall': float(recall_score(y, pred, zero_division=0)),
            'f1': float(f1_score(y, pred, zero_division=0)),
            'balanced_accuracy': float(balanced_accuracy_score(y, pred)),
            'clauses': ' AND '.join(extract_leaf_path(tree, int(leaf_id), feature_names)),
            'path_length': len(extract_leaf_path(tree, int(leaf_id), feature_names)),
        })
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = load_panel(); all_rows = []; selected_rows = []; path_records = []
    for horizon in HORIZONS:
        origins = build_origins(panel, horizon)
        for family in FAMILIES:
            for mode in MODES:
                features = feature_columns(mode)
                # Fit separately per model so thresholds/splits only see discovery-fit rows.
                fit = origins[origins.split == 'discovery_fit'].dropna(subset=features + [f'outcome_{family}'])
                inner = origins[origins.split == 'discovery_inner'].dropna(subset=features + [f'outcome_{family}'])
                val = origins[origins.split == 'validation'].dropna(subset=features + [f'outcome_{family}'])
                X_fit = fit[features].to_numpy(float); y_fit = fit[f'outcome_{family}'].astype(int).to_numpy()
                for depth in DEPTHS:
                    for seed in SEEDS:
                        tree = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=MIN_LEAF, class_weight='balanced', random_state=seed)
                        tree.fit(X_fit, y_fit)
                        inner_candidates = select_leaf(tree, inner, inner[f'outcome_{family}'].astype(int).to_numpy(), features, 'discovery_inner')
                        if inner_candidates.empty: continue
                        # Select one positive leaf using inner only; ties prefer simpler/greater support.
                        selected = inner_candidates.sort_values(['balanced_accuracy', 'f1', 'support', 'path_length'], ascending=[False, False, False, True]).iloc[0]
                        leaf_id = int(selected.leaf_id)
                        for split_name, frame in (('discovery_fit', fit), ('discovery_inner', inner), ('validation', val)):
                            y = frame[f'outcome_{family}'].astype(int).to_numpy(); leaves = tree.apply(frame[features].to_numpy(float)); pred = leaves == leaf_id
                            m = metrics(y, pred, frame.entity_code.to_numpy(), frame.target_year.to_numpy(), leaves)
                            all_rows.append({'horizon': horizon, 'family': family, 'mode': mode, 'depth': depth, 'seed': seed, 'selected_leaf_id': leaf_id, 'split': split_name, **m})
                        clauses = extract_leaf_path(tree, leaf_id, features)
                        path_records.append({'horizon': horizon, 'family': family, 'mode': mode, 'depth': depth, 'seed': seed, 'leaf_id': leaf_id, 'path_length': len(clauses), 'clauses': ' AND '.join(clauses), 'inner_balanced_accuracy': float(selected.balanced_accuracy), 'inner_f1': float(selected.f1)})
                        selected_rows.append({'horizon': horizon, 'family': family, 'mode': mode, 'depth': depth, 'seed': seed, 'selected_leaf_id': leaf_id, 'inner_balanced_accuracy': float(selected.balanced_accuracy), 'inner_f1': float(selected.f1), 'path_length': len(clauses), 'clauses': ' AND '.join(clauses)})
    result = pd.DataFrame(all_rows); paths = pd.DataFrame(path_records); selected_df = pd.DataFrame(selected_rows)
    result.to_csv(OUT / 'TREE_PATH_METRICS_BY_SPLIT.csv', index=False)
    paths.to_csv(OUT / 'TREE_EXTRACTED_PATHS.csv', index=False)
    selected_df.to_csv(OUT / 'TREE_SELECTED_PATHS.csv', index=False)
    summary = {
        'run_id': 'reverse_extraction_tree_v1_exploratory', 'status': 'exploratory_validation_only',
        'candidate_models': int(len(selected_df)), 'horizons': list(HORIZONS), 'families': list(FAMILIES), 'modes': list(MODES), 'depths': list(DEPTHS), 'seeds': list(SEEDS),
        'split_definition': 'by target_year; discovery_fit=2006-2012, discovery_inner=2013-2015, validation=2016-2019, locked_test=2020-2024',
        'locked_test_executed': False, 'raw_data_modified': False, 'imputation': False, 'normalization': False,
        'decision': 'exploratory tree paths only; no promotion; null correction for model family not yet executed',
    }
    (OUT / 'TREE_RUN_SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(result[result.split == 'validation'].sort_values('balanced_accuracy', ascending=False).head(25).to_string(index=False))


if __name__ == '__main__':
    main()
