from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from check_experiments_immutable import changed_paths


class FrozenPathGuardTests(unittest.TestCase):
    @patch("check_experiments_immutable.subprocess.run")
    def test_diff_covers_both_frozen_roots(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout=(
                "M\\texperiments/identity_lab/result.json\\n"
                "A\\tstructural_engine/isolated_break_detector_v1/new.py\\n"
            ),
            stderr="",
        )

        changed = changed_paths("base-sha", "head-sha", triple_dot=False)

        self.assertEqual(
            changed,
            [
                ("M", ["experiments/identity_lab/result.json"]),
                ("A", ["structural_engine/isolated_break_detector_v1/new.py"]),
            ],
        )
        command = run.call_args.args[0]
        self.assertEqual(
            command[-2:],
            ["experiments/", "structural_engine/isolated_break_detector_v1/"],
        )

    @patch("check_experiments_immutable.subprocess.run")
    def test_pull_request_uses_merge_base_diff(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=0,
            stdout="",
            stderr="",
        )

        self.assertEqual(changed_paths("base", "head", triple_dot=True), [])
        command = run.call_args.args[0]
        self.assertIn("base...head", command)
        self.assertEqual(
            command[-2:],
            ["experiments/", "structural_engine/isolated_break_detector_v1/"],
        )

    @patch("check_experiments_immutable.subprocess.run")
    def test_git_diff_failure_is_not_treated_as_clean(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=["git", "diff"],
            returncode=128,
            stdout="",
            stderr="bad revision",
        )

        with self.assertRaisesRegex(RuntimeError, "refusing to treat an unverifiable diff as clean"):
            changed_paths("missing-base", "head", triple_dot=False)


if __name__ == "__main__":
    unittest.main()
