from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from discovery_engine.calendar_coincidence_null_v1 import write_calendar_null_artifacts

if __name__ == "__main__":
    result = write_calendar_null_artifacts(
        candidates_path=ROOT / "discovery/behavioral_v1/BEHAVIORAL_CANDIDATES_V1.jsonl",
        contract_path=ROOT / "experimental_contracts/CONDITIONAL_CALENDAR_COINCIDENCE_NULL_V1.json",
        output_dir=ROOT / "discovery/behavioral_v1",
        repository_root=ROOT,
    )
    print({
        "candidate_count": result["candidate_count_conditioned_on"],
        "groups": result["groups_meeting_minimum_support"],
        "observed_max_support": result["observed_global_max_support"],
        "null_mean_max": result["null_global_max_mean"],
        "null_q95_max": result["null_global_max_q95"],
        "familywise_p": result["global_max_conditional_p"],
        "null_fpr": result["null_is_detector_fpr"],
    })
