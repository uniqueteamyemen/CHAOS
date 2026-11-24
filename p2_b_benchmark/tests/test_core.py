import json
import random
import tempfile
import unittest
from pathlib import Path

import numpy as np

from p2_b_benchmark.engine import (
    BASELINE_MODES,
    audit_parallel_prefix_invariance,
    normalize_detector_key,
    register_detector,
    run_all,
    run_baseline,
    run_parallel_fusion,
    run_registered_detector,
    VARIANTS,
    _EXTENSION_RUNNERS,
)

from p2_b_benchmark.run import (
    _aggregate,
    _one_series,
    _score_all,
    _build_protocol,
    _series_manifest_sha256,
    _sorted_ids_sha256,
    aggregate_shard_files,
    combine_shard_documents,
)


class ParallelFusionCausalityTests(unittest.TestCase):
    @staticmethod
    def series(n=160, seed=44):
        rng = random.Random(seed)
        values = [rng.gauss(0.0, 1.0) for _ in range(n)]
        for i in range(95, n):
            values[i] += 3.0
        return np.asarray(values, dtype=float)

    def test_registered_arms_and_break_detector_modes(self):
        self.assertEqual(set(BASELINE_MODES), {"A_FAST", "A_MARKOV_CUSUM", "A_CONSENSUS"})
        required_arms = set(BASELINE_MODES) | {"G", "H", "J", "K", "I"}
        self.assertTrue(required_arms.issubset(VARIANTS))
        self.assertEqual(BASELINE_MODES["A_MARKOV_CUSUM"], "markov_cusum")
        self.assertEqual(VARIANTS["G"]["transition"], "reset")
        self.assertEqual(VARIANTS["H"]["h"], 12.5)
        self.assertEqual(VARIANTS["J"]["h"], 14.5)
        self.assertEqual(VARIANTS["K"]["h"], 15.5)
        self.assertEqual(VARIANTS["I"]["h"], 16.5)
        self.assertTrue(all(VARIANTS[arm]["kind"] == "parallel_fusion" for arm in ("G", "H", "J", "K", "I")))

    def test_future_suffix_mutation_preserves_prefix_hits_and_events(self):
        values = self.series()
        for arm in ("G", "H", "J", "K", "I"):
            self.assertEqual(audit_parallel_prefix_invariance(values, arm), 0, arm)

    def test_two_sided_cusum_detects_both_directions(self):
        positive = self.series()
        negative = self.series()
        positive[95:] += 5.0
        negative[95:] -= 5.0
        self.assertTrue(any(hit["sign"] > 0 for hit in run_parallel_fusion(positive, variant="H")["hits"]))
        self.assertTrue(any(hit["sign"] < 0 for hit in run_parallel_fusion(negative, variant="H")["hits"]))

    def test_invalid_series_fails_closed(self):
        with self.assertRaises(ValueError):
            run_parallel_fusion([0.0] * 20, variant="G")
        with self.assertRaises(ValueError):
            run_parallel_fusion([0.0] * 100 + [float("nan")], variant="G")

    def test_future_detector_names_fit_extension_registry_contract(self):
        expected = {
            "FOCuS": "FOCUS",
            "R-FPOP": "R_FPOP",
            "BOCPD": "BOCPD",
            "Post-Quiet Huber": "POST_QUIET_HUBER",
            "Bartlett LRV": "BARTLETT_LRV",
        }
        for display_name, key in expected.items():
            self.assertEqual(normalize_detector_key(display_name), key)

    def test_registered_extension_runs_and_prefix_replays(self):
        def stub_runner(values):
            if values.size and values[-1] >= 3.0:
                return {"hits": [{"index": int(values.size - 1), "sign": 1, "detector": "stub"}]}
            return {"hits": []}

        key = register_detector(
            "P2B_TEST_STUB", stub_runner, family="test", version="1",
            description="test-only extension adapter",
        )
        try:
            values = np.zeros(80, dtype=float)
            values[-1] = 3.0
            result = run_registered_detector(values, key, causal_audit=True)
            self.assertEqual(result["event_count"], 1)
            self.assertEqual(result["causal_audit_violations"], 0)
            self.assertEqual(VARIANTS[key]["kind"], "extension")
        finally:
            VARIANTS.pop(key, None)
            _EXTENSION_RUNNERS.pop(key, None)

    def test_registered_extension_prefix_audit_detects_lookahead(self):
        def lookahead_runner(values):
            if values.size > 60 and values[60] > 2.0:
                return {"hits": [{"index": 50, "sign": 1, "detector": "lookahead_stub"}]}
            return {"hits": []}

        key = register_detector(
            "P2B_LOOKAHEAD_STUB", lookahead_runner, family="test", version="1",
            description="must fail prefix replay because its hit depends on the future",
        )
        try:
            values = np.zeros(80, dtype=float)
            values[60] = 3.0
            result = run_registered_detector(values, key, causal_audit=True)
            self.assertEqual(result["causal_audit_violations"], 1)
        finally:
            VARIANTS.pop(key, None)
            _EXTENSION_RUNNERS.pop(key, None)

    def test_signals_never_emit_inside_the_quiet_window(self):
        values = self.series(n=160)
        result = run_parallel_fusion(values, variant="H", quiet_points=40)
        self.assertTrue(all(hit["index"] >= 40 for hit in result["hits"]))
        self.assertTrue(all(event["start_index"] >= 40 for event in result["events"]))

    def test_zero_quiet_scale_is_explicit_abstention(self):
        values = np.zeros(100, dtype=float)
        parallel = run_parallel_fusion(values, variant="H")
        self.assertEqual(parallel["status"], "ABSTAIN")
        self.assertEqual(parallel["abstain_reason"], "ZERO_QUIET_SCALE")
        self.assertEqual(parallel["hits"], [])
        all_arms = run_all(values, causal_audit=True)
        self.assertTrue(all(payload["status"] == "ABSTAIN" for payload in all_arms.values()))
        self.assertTrue(all(payload["abstain_reason"] == "ZERO_QUIET_SCALE" for payload in all_arms.values()))

    def test_zero_quiet_scale_series_and_bootstrap_replicates_are_recorded_as_abstentions(self):
        item = {
            "id": "synthetic:flat",
            "source": "gem",
            "values": np.zeros(100, dtype=float),
            "bootstrap_eligible": True,
        }
        row = _one_series(item, null_replicates=3)
        self.assertEqual(row["observed_status"], "ABSTAIN")
        self.assertEqual(row["abstain_reason"], "ZERO_QUIET_SCALE")
        for arm in VARIANTS:
            self.assertEqual(row["null"][arm]["valid_replicates"], 0)
            self.assertEqual(row["null"][arm]["abstained_replicates"], 3)
            self.assertIsNone(row["null"][arm]["conditional_alarm_probability"])
            self.assertEqual(row["injected"][arm]["positive_3sigma"]["status"], "ABSTAIN")
        summary = _aggregate([row], null_replicates=3)
        self.assertEqual(summary["null"]["H"]["all"]["replicates_abstained_zero_quiet_scale"], 3)
        self.assertEqual(summary["injected"]["H"]["positive_3sigma"]["all"]["abstained_zero_quiet_scale_series"], 1)
        self.assertEqual(summary["observed"]["H"]["all"]["abstained_zero_quiet_scale_series"], 1)

    def test_score_all_counts_quiet_to_onset_alert_and_rejects_prestarted_event(self):
        result = {
            "A_BASELINE": {"hits": [{"time": 45, "direction": 1}, {"time": 73, "direction": 1}]},
            "H": {"hits": [
                {"index": 45, "sign": 1, "detector": "cusum_positive"},
                {"index": 73, "sign": 1, "detector": "cusum_positive"}],
                "events": [{"start_index": 45, "end_index": 73, "sign": 1, "evidence": [
                    {"index": 45, "sign": 1, "detector": "cusum_positive"},
                    {"index": 73, "sign": 1, "detector": "cusum_positive"}]}]},
            "J": {"hits": [{"index": 73, "sign": 1, "detector": "cusum_positive"}],
                "events": [{"start_index": 72, "end_index": 73, "sign": 1, "evidence": [
                    {"index": 73, "sign": 1, "detector": "cusum_positive"}]}]},
        }
        scored = _score_all(result, onset=70, sign=1, quiet_points=40)
        self.assertTrue(scored["A_BASELINE"]["pre_onset_alert"])
        self.assertTrue(scored["A_BASELINE"]["detected"])
        self.assertTrue(scored["H"]["pre_onset_alert"])
        self.assertFalse(scored["H"]["detected"], "post-onset hit cannot validate an event that started pre-onset")
        self.assertFalse(scored["J"]["pre_onset_alert"])
        self.assertTrue(scored["J"]["detected"])


    @staticmethod
    def synthetic_metrics_rows():
        rows = []
        arms = list(VARIANTS)
        for index in range(458):
            rows.append({
                "id": f"gem:{index:03d}", "source": "gem", "n": 120 + (index % 17),
                "null_eligible": index < 311,
                "observed_status": "ABSTAIN" if index == 0 else "OK",
                "observed": {arm: (index + arm_index) % 4 for arm_index, arm in enumerate(arms)},
                "null": ({arm: {
                    "alarm_replicates": 1, "event_count": 2,
                    "valid_replicates": 2 if index == 0 else 3,
                    "abstained_replicates": 1 if index == 0 else 0,
                    "conditional_alarm_probability": 0.5 if index == 0 else 1.0 / 3.0,
                    "events_per_replicate": 1.0 if index == 0 else 2.0 / 3.0,
                    "replicates_attempted": 3, "status": "OK",
                } for arm in arms} if index < 311 else {}),
                "injected": {arm: {
                    "positive_3sigma": ({"status": "ABSTAIN", "detected": None, "delay": None,
                                          "pre_onset_alert": None, "wrong_direction": None, "missed": None}
                                         if index == 0 else
                                         {"status": "OK", "detected": index % 2 == 0,
                                          "delay": 3 + (index % 9), "pre_onset_alert": index % 7 == 0,
                                          "wrong_direction": index % 13 == 0, "missed": index % 2 != 0}),
                    "negative_3sigma": ({"status": "ABSTAIN", "detected": None, "delay": None,
                                          "pre_onset_alert": None, "wrong_direction": None, "missed": None}
                                         if index == 0 else
                                         {"status": "OK", "detected": index % 3 == 0,
                                          "delay": 4 + (index % 11), "pre_onset_alert": index % 8 == 0,
                                          "wrong_direction": index % 17 == 0, "missed": index % 3 != 0}),
                } for arm in arms},
                "causal": {arm: {"violations": 0, "unverifiable": 0} for arm in arms},
            })
        for index in range(51):
            rows.append({
                "id": f"pink:{index:03d}", "source": "pink_sheet", "n": 100 + (index % 13),
                "null_eligible": index < 48,
                "observed_status": "OK",
                "observed": {arm: (index + arm_index) % 3 for arm_index, arm in enumerate(arms)},
                "null": ({arm: {
                    "alarm_replicates": 0, "event_count": 1,
                    "valid_replicates": 3, "abstained_replicates": 0,
                    "conditional_alarm_probability": 0.0,
                    "events_per_replicate": 1.0 / 3.0,
                    "replicates_attempted": 3, "status": "OK",
                } for arm in arms} if index < 48 else {}),
                "injected": {arm: {
                    "positive_3sigma": {"status": "OK", "detected": index % 2 == 0,
                                         "delay": 2 + index % 5, "pre_onset_alert": False,
                                         "wrong_direction": False, "missed": index % 2 != 0},
                    "negative_3sigma": {"status": "OK", "detected": index % 3 == 0,
                                         "delay": 5 + index % 7, "pre_onset_alert": index % 9 == 0,
                                         "wrong_direction": False, "missed": index % 3 != 0},
                } for arm in arms},
                "causal": {arm: {"violations": 0, "unverifiable": 0} for arm in arms},
            })
        return sorted(rows, key=lambda row: row["id"])

    def test_four_shard_aggregation_matches_unsplit_rows_and_summary(self):
        rows = self.synthetic_metrics_rows()
        self.assertEqual(len(rows), 509)
        source_integrity = {
            "series": 509, "pink_sheet": 51, "gem": 458,
            "null_eligible": 359, "null_eligible_pink_sheet": 48,
            "null_eligible_gem": 311, "null_ineligible": 150,
            "source_commit": "fixture-source-commit",
            "prepared_artifact_sha256": "fixture-artifact-sha256",
            "pink_source_sha256": "fixture-pink-sha256",
            "pink_raw_values_persisted": False,
            "gem_values_source": "fixture",
        }
        manifest_sha = _series_manifest_sha256(rows)
        shards = []
        for shard_index in range(4):
            shard_rows = [row for index, row in enumerate(rows) if index % 4 == shard_index]
            shards.append({
                "schema": "chaos-p2-b-shard-v2",
                "shard_index": shard_index, "shard_count": 4,
                "run_id": "fixture-run-123", "run_attempt": 1,
                "expected_series_count": 509, "expected_shard_rows": len(shard_rows),
                "null_replicates": 3, "series_manifest_sha256": manifest_sha,
                "sorted_ids_sha256": _sorted_ids_sha256([row["id"] for row in rows]),
                "sorted_ids": [row["id"] for row in rows],
                "protocol": _build_protocol(3), "source_integrity": source_integrity,
                "series_results": shard_rows,
            })

        # Exercise the local --aggregate-shards path: it reads only shard JSON files.
        with tempfile.TemporaryDirectory() as tmp:
            shard_dir = Path(tmp) / "shards"
            shard_dir.mkdir()
            for shard in shards:
                path = shard_dir / f"shard_{shard['shard_index']}_of_4.json"
                path.write_text(json.dumps(shard), encoding="utf-8")
            combined = aggregate_shard_files([str(shard_dir)], output_dir=Path(tmp) / "out")
        self.assertEqual(combined["series_results"], rows)
        self.assertEqual(combined["summary"], _aggregate(rows, null_replicates=3))
        self.assertEqual(combined["execution"]["shard_rows"], {0: 128, 1: 127, 2: 127, 3: 127})
        self.assertEqual(combined["source_integrity"]["null_eligible"], 359)
        self.assertEqual(combined["series_results"][0]["observed_status"], "ABSTAIN")
        self.assertTrue(any(row["source"] == "pink_sheet" for row in combined["series_results"]))
        self.assertTrue(any(row["source"] == "gem" and row["null_eligible"] is False
                            for row in combined["series_results"]))

    def test_shard_aggregator_rejects_mixed_attempts_and_missing_shards(self):
        rows = self.synthetic_metrics_rows()
        source_integrity = {
            "series": 509, "pink_sheet": 51, "gem": 458,
            "null_eligible": 359, "null_eligible_pink_sheet": 48,
            "null_eligible_gem": 311, "null_ineligible": 150,
        }
        manifest_sha = _series_manifest_sha256(rows)
        shards = []
        for shard_index in range(4):
            shard_rows = [row for index, row in enumerate(rows) if index % 4 == shard_index]
            shards.append({
                "schema": "chaos-p2-b-shard-v2", "shard_index": shard_index, "shard_count": 4,
                "run_id": "fixture-run-123", "run_attempt": 1,
                "expected_series_count": 509, "expected_shard_rows": len(shard_rows),
                "null_replicates": 3, "series_manifest_sha256": manifest_sha,
                "sorted_ids_sha256": _sorted_ids_sha256([row["id"] for row in rows]),
                "sorted_ids": [row["id"] for row in rows],
                "protocol": _build_protocol(3), "source_integrity": source_integrity,
                "series_results": shard_rows,
            })
        with self.assertRaisesRegex(ValueError, "shard_coverage_incomplete_or_invalid") as missing:
            combine_shard_documents(shards[:3])
        self.assertEqual(missing.exception.diagnostic["missing_shard_indices"], [3])
        self.assertEqual(
            len(missing.exception.diagnostic["missing_series_ids"]), 127
        )
        self.assertTrue(missing.exception.diagnostic["missing_ids_by_shard"]["3"])
        mixed = [dict(doc) for doc in shards]
        mixed[2] = {**mixed[2], "run_attempt": 2}
        with self.assertRaisesRegex(ValueError, "mixed_run_or_attempt"):
            combine_shard_documents(mixed)

    def test_frozen_break_detector_modes_replay_from_prefix(self):
        try:
            import structural_engine.isolated_break_detector_v1  # noqa: F401
        except ModuleNotFoundError as exc:
            if exc.name not in {"structural_engine", "structural_engine.isolated_break_detector_v1"}:
                raise
            self.skipTest("P2-B package-only workspace: frozen BreakDetectorV1 source is not checked out")
        result = run_baseline(self.series(n=140), causal_audit=True)
        for arm in BASELINE_MODES:
            self.assertEqual(result[arm]["causal_audit_violations"], 0, arm)


if __name__ == "__main__":
    unittest.main()
