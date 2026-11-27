from __future__ import annotations

import numpy as np

from p1_4_validation.c3.causal_multiscale_adaptive import (
    CausalMultiScaleExcursionDetector,
    CausalMultiScaleFlowDetector,
)


def test_registered_series_parameter_shapes():
    unrate = CausalMultiScaleExcursionDetector(
        windows=(3, 6), baseline_points=24, guard_points=2, confirm_points=2,
    )
    icsa = CausalMultiScaleExcursionDetector(
        windows=(4, 12), baseline_points=24, guard_points=3, confirm_points=2,
    )
    payems = CausalMultiScaleFlowDetector(
        windows=(3, 12), baseline_points=24, guard_points=2,
        confirm_points=2, rearm_quiet_points=6,
    )
    assert unrate.windows == (3, 6)
    assert icsa.windows == (4, 12)
    assert payems.windows == (3, 12)
    assert payems.rearm_quiet_points == 6


def test_level_detector_catches_both_directions_without_cross_lock():
    rng = np.random.default_rng(41024)
    increments = rng.normal(0.0, 0.015, 240)
    values = np.cumsum(increments)
    values[85:] += 2.0
    values[155:] -= 4.0

    detector = CausalMultiScaleExcursionDetector(
        windows=(3, 6), baseline_points=24, guard_points=2,
        initial_quiet_points=40, confirm_points=2,
    )
    result = detector.detect(values, threshold=3.0)
    signs = [int(hit["sign"]) for hit in result["hits"]]
    assert result["status"] == "OK"
    assert 1 in signs
    assert -1 in signs


def test_flow_uses_delta_x_directly_and_catches_flow_shift():
    rng = np.random.default_rng(42024)
    delta_x = rng.normal(0.0, 0.10, 220)
    delta_x[90:102] += 3.0

    detector = CausalMultiScaleFlowDetector(
        windows=(3, 12), baseline_points=24, guard_points=2,
        initial_quiet_points=40, confirm_points=2, rearm_quiet_points=6,
    )
    result = detector.detect(delta_x, threshold=3.0)
    assert result["status"] == "OK"
    assert any(int(hit["sign"]) == 1 for hit in result["hits"])


def test_prefix_replay_invariance_for_every_emitted_hit():
    rng = np.random.default_rng(43024)
    values = np.cumsum(rng.normal(0.0, 0.02, 180))
    values[75:] += 1.5
    values[130:] -= 3.0
    detector = CausalMultiScaleExcursionDetector(
        windows=(3, 6), baseline_points=24, guard_points=2,
        initial_quiet_points=40, confirm_points=2,
    )
    full = detector.detect(values, threshold=3.0)
    for hit in full["hits"]:
        index = int(hit["index"])
        prefix = detector.detect(values[:index + 1], threshold=3.0)
        assert any(
            int(item["index"]) == index and int(item["sign"]) == int(hit["sign"])
            for item in prefix["hits"]
        )


def test_zero_dispersion_abstains_without_inventing_a_scale():
    detector = CausalMultiScaleExcursionDetector(
        windows=(3, 6), baseline_points=24, guard_points=2,
    )
    result = detector.detect(np.zeros(180), threshold=3.0)
    assert result["status"] == "NOT_ELIGIBLE"
    assert result["hits"] == []
    assert result["zero_scale_points"] > 0
