from __future__ import annotations
import json
import os
from pathlib import Path

OUT = Path('artifacts/p1_4/c3/v2_3_causal_slope_shift')
REPORT = OUT / 'C3_V2_3_SLOPE_SHIFT_EVALUATION.json'


def main() -> int:
    lines = [
        '# C3 v2.3 — Causal Local Slope-Shift', '',
        f'- Evaluation commit: {os.environ.get("GITHUB_SHA", "UNKNOWN")}',
        f'- Evaluation run: {os.environ.get("GITHUB_RUN_ID", "UNKNOWN")}',
        '- Frozen source-intake run: 45757611871',
        '- Frozen source artifact ID: 15088960800',
        '- Seed namespace: CHAOS:C3_V2_3_LOCAL_SLOPE_SHIFT_2000X2_V1_PREREG_20261127',
        '- Replicates: 2,000 Development + 2,000 independent Holdout per target series', '',
    ]
    if not REPORT.is_file():
        lines.append('Report unavailable; inspect the failed workflow step.')
    else:
        report = json.loads(REPORT.read_text(encoding='utf-8'))
        lines.extend([f'Status: {report["status"]}', '', '## Detector summary'])
        for name, item in report['detector_summary'].items():
            lines.append(f'- {name}: {json.dumps(item, sort_keys=True)}')
        for sid, series in report['series'].items():
            lines.extend(['', f'## {sid} — {series["status"]}'])
            for name, arm in series.get('calibration', {}).items():
                dev, hold = arm.get('development', {}), arm.get('holdout', {})
                lines.append(
                    f'- {name}: threshold={arm.get("frozen_threshold")}; '
                    f'Dev U95={dev.get("wilson_upper_95_one_sided")}; '
                    f'Holdout U95={hold.get("wilson_upper_95_one_sided")}; '
                    f'risk={arm.get("risk_validation_status")}'
                )
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a', encoding='utf-8') as handle:
            handle.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
