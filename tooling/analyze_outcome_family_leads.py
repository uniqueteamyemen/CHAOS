#!/usr/bin/env python3
"""Profile prespecified outcome families and lead horizons on the current annual panel."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('/home/ubuntu/CHAOS')
PANEL = ROOT / 'catalog_first' / 'readiness_gate' / 'macro_plus_eia_energy' / 'MACRO_PLUS_EIA_ENERGY_COMPLETE_139_NUMERIC_RAW_2000_2024_WIDE.csv'
OUT = ROOT / 'experiments' / 'macro_plus_eia_energy' / 'reverse_extraction_v1_draft'
TARGET = 'wdi__NY_GDP_MKTP_KD_ZG'


def load() -> pd.DataFrame:
    df = pd.read_csv(PANEL)
    df = df.rename(columns={c: c.replace('.', '_') for c in df.columns})
    return df.sort_values(['entity_code', 'year']).reset_index(drop=True)


def profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon in (1, 2, 3):
        work = df[['entity_code', 'year', TARGET]].copy()
        g = work.groupby('entity_code')[TARGET]
        work['current'] = work[TARGET]
        work['future'] = g.shift(-horizon)
        work['future_1'] = g.shift(-1)
        work['future_2'] = g.shift(-2)
        work['future_3'] = g.shift(-3)
        work['split'] = np.select(
            [work.year.between(2006, 2012), work.year.between(2013, 2015), work.year.between(2016, 2019)],
            ['discovery_fit', 'discovery_inner', 'validation'], default='other_or_deferred')
        valid = work['future'].notna()
        # Every family is defined before any model is trained; this is profiling, not selection.
        outcomes = {
            'contraction_at_h': work['future'] < 0,
            'nonpositive_at_all_steps_to_h': (work['future_1'] < 0) if horizon == 1 else ((work['future_1'] < 0) & (work['future_2'] < 0)) if horizon == 2 else ((work['future_1'] < 0) & (work['future_2'] < 0) & (work['future_3'] < 0)),
            'deterioration_vs_origin_at_h': work['future'] < work['current'],
            'drop_2pp_vs_origin_at_h': work['future'] <= work['current'] - 2.0,
            'drop_5pp_vs_origin_at_h': work['future'] <= work['current'] - 5.0,
            'adverse_tail_q10_fit_threshold_at_h': work['future'] <= work.loc[work.year.between(2006, 2012), 'future'].quantile(0.10),
            'min_future_below_zero_by_h': ((work['future_1'] < 0) if horizon == 1 else (work[['future_1', 'future_2']].min(axis=1) < 0) if horizon == 2 else (work[['future_1', 'future_2', 'future_3']].min(axis=1) < 0)),
        }
        for family, series in outcomes.items():
            for split in ('discovery_fit', 'discovery_inner', 'validation'):
                s = work[work.split == split]
                eligible = valid.loc[s.index]
                y = series.loc[s.index].where(eligible)
                rows.append({
                    'family': family, 'horizon_years': horizon, 'split': split,
                    'eligible_origins': int(eligible.sum()), 'positive_events': int(y.fillna(False).sum()),
                    'event_rate': float(y.mean()) if int(eligible.sum()) else np.nan,
                    'entity_coverage': int(s.loc[y.fillna(False), 'entity_code'].nunique()),
                    'year_coverage': int(s.loc[y.fillna(False), 'year'].nunique()),
                })
    return pd.DataFrame(rows)


def main() -> None:
    df = load()
    result = profile(df)
    result.to_csv(OUT / 'OUTCOME_FAMILY_LEAD_PROFILE.csv', index=False)
    print(result[result.split == 'validation'].to_string(index=False))


if __name__ == '__main__':
    main()
