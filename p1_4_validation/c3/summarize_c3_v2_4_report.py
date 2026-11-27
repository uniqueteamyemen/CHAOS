from __future__ import annotations

import json
import os
from pathlib import Path

OUT = Path("artifacts/p1_4/c3/v2_4_multiscale_adaptive")
REPORT = OUT / "C3_V2_4_MULTISCALE_EVALUATION.json"


def main() -> int:
    lines = [
        "# C3 v2.4 — MultiScale Adaptive Evaluation",
        "",
        f"- Evaluation commit: {os.environ.get('GITHUB_SHA', 'UNKNOWN')}",
        f"- Evaluation run: {os.environ.get('GITHUB_RUN_ID', 'UNKNOWN')}",
        "- Frozen source-intake run: 45757611871",
        "- Frozen source artifact ID: 15088960800",
        "- Replicates: 2,000 Development + 2,000 independent Holdout per target series",
        "- Historical matching: one-to-one +/-12 calendar months",
        "",
    ]
    if not REPORT.is_file():
        lines.append("Evaluation JSON unavailable; inspect the failed workflow step.")
    else:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        lines.extend([
            f"Status: {report.get('status')}",
            "",
            "## Historical diagnostics",
        ])
        for name, item in report.get("historical_diagnostic_summary", {}).items():
            post = item.get("post_break_recall", {})
            early = item.get("early_warning_matches", {})
            lines.append(
                f"- {name}: post-break={post.get('matched_pairs')}/{post.get('total_pairs')}; "
                f"early-warning={early.get('matched_pairs')}; "
                f"unmatched/year={item.get('unmatched_alarms_per_year')}; "
                f"post-break episode coverage={post.get('episode_coverage')}/8"
            )
        for sid, series in report.get("series", {}).items():
            lines.extend(["", f"## {sid} — {series.get('status')}"])
            for name, arm in series.get("calibration", {}).items():
                dev = arm.get("development", {})
                hold = arm.get("holdout", {})
                lines.append(
                    f"- {name}: threshold={arm.get('frozen_threshold')}; "
                    f"Dev U95={dev.get('wilson_upper_95_one_sided')}; "
                    f"Holdout U95={hold.get('wilson_upper_95_one_sided')}; "
                    f"risk={arm.get('risk_validation_status')}"
                )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
