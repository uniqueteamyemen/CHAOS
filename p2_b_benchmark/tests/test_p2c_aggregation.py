from __future__ import annotations

import unittest

from p2_b_benchmark.p2c_engine import P2C_VARIANTS
from p2_b_benchmark.p2c_run import (
    EXPECTED_COUNTS,
    SHARD_COUNT,
    _combine_shards,
    _protocol,
)
from p2_b_benchmark.run import _series_manifest_sha256, _sorted_ids_sha256


def make_rows():
    rows = []
    for i in range(509):
        source = "pink_sheet" if i < 51 else "gem"
        eligible = i < 48 if source == "pink_sheet" else i - 51 < 311
        row = {
            "id": f"{'pink' if source == 'pink_sheet' else 'gem'}:{i:04d}",
            "source": source, "n": 120 + i % 11,
            "null_eligible": eligible, "observed_status": "OK",
            "abstain_reason": None,
            "observed": {arm: 1 for arm in P2C_VARIANTS},
            "null": {}, "injected": {}, "causal": {},
            "r_fpop_segmentation": {
                "status": "OK", "abstain_reason": None, "breakpoints": [],
                "metadata": {"loss": "Huber", "track": "retrospective"},
            },
        }
        for arm in P2C_VARIANTS:
            row["causal"][arm] = {"violations": 0, "unverifiable": 0, "details": []}
            for scenario in ("positive_3sigma", "negative_3sigma"):
                row["injected"].setdefault(arm, {})[scenario] = {
                    "status": "OK", "detected": i % 2 == 0, "delay": 3,
                    "pre_onset_alert": False, "wrong_direction": False,
                    "missed": i % 2 != 0,
                }
            if eligible:
                row["null"][arm] = {
                    "alarm_replicates": 1, "event_count": 2,
                    "valid_replicates": 3, "abstained_replicates": 0,
                    "conditional_alarm_probability": 1.0 / 3.0,
                    "events_per_replicate": 2.0 / 3.0,
                    "replicates_attempted": 3, "status": "OK",
                }
        rows.append(row)
    return sorted(rows, key=lambda row: row["id"])


def make_shards(rows):
    ids = [row["id"] for row in rows]
    source_integrity = dict(EXPECTED_COUNTS)
    return [{
        "schema": "chaos-p2-c-shard-v1",
        "shard_index": shard_index, "shard_count": SHARD_COUNT,
        "run_id": "p2c-fixture-run", "run_attempt": 1,
        "expected_series_count": 509,
        "expected_shard_rows": len([i for i in range(509) if i % 4 == shard_index]),
        "null_replicates": 3,
        "series_manifest_sha256": _series_manifest_sha256(rows),
        "sorted_ids_sha256": _sorted_ids_sha256(ids), "sorted_ids": ids,
        "protocol": _protocol(3), "source_integrity": source_integrity,
        "series_results": [row for i, row in enumerate(rows) if i % 4 == shard_index],
    } for shard_index in range(4)]


class P2CAggregationTests(unittest.TestCase):
    def test_p2c_four_shards_cover_all_509_and_preserve_cohorts(self):
        rows = make_rows()
        combined = _combine_shards(make_shards(rows))
        self.assertEqual(len(combined["series_results"]), 509)
        self.assertEqual(combined["source_integrity"], EXPECTED_COUNTS)
        self.assertEqual(combined["execution"]["shard_rows"], {
            0: 128, 1: 127, 2: 127, 3: 127,
        })
        self.assertEqual(
            combined["summary"]["observed"]["A_FAST"]["all"]["series"], 509
        )
        self.assertEqual(
            combined["summary"]["null"]["A_FAST"]["all"]["series"], 359
        )
        self.assertEqual(
            combined["summary"]["r_fpop_segmentation"]["all"]["series"], 509
        )

    def test_p2c_aggregator_rejects_missing_duplicate_or_misassigned_shards(self):
        rows = make_rows()
        shards = make_shards(rows)
        with self.assertRaisesRegex(ValueError, "p2c_shard_count_mismatch"):
            _combine_shards(shards[:3])
        duplicate = [dict(x) for x in shards]
        duplicate[3] = {**duplicate[3], "shard_index": 2}
        with self.assertRaisesRegex(ValueError, "p2c_shard_indices_missing_or_duplicate"):
            _combine_shards(duplicate)
        wrong_owner = [dict(x) for x in shards]
        wrong_owner[1] = {**wrong_owner[1], "series_results": list(wrong_owner[1]["series_results"])}
        wrong_owner[1]["series_results"][0] = dict(wrong_owner[1]["series_results"][0])
        wrong_owner[1]["series_results"][0]["id"] = "wrong-owner"
        with self.assertRaisesRegex(ValueError, "p2c_shard_assignment_mismatch"):
            _combine_shards(wrong_owner)

    def test_bartlett_is_not_registered_as_a_detector_and_rfpop_is_separate(self):
        self.assertEqual(set(P2C_VARIANTS), {
            "A_FAST", "A_CONSENSUS", "FOCUS", "BOCPD",
            "POST_QUIET_HUBER_MAD", "POST_QUIET_HUBER_BARTLETT",
        })
        self.assertNotIn("BARTLETT_LRV", P2C_VARIANTS)
        self.assertNotIn("R_FPOP", P2C_VARIANTS)
        self.assertEqual(P2C_VARIANTS["POST_QUIET_HUBER_BARTLETT"]["parameters"]["scale_estimator"],
                         "Bartlett-LRV")


if __name__ == "__main__":
    unittest.main(verbosity=2)
