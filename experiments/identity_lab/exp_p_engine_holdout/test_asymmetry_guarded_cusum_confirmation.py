import unittest
from experiments.identity_lab.exp_p_engine_holdout.asymmetry_guarded_cusum_confirmation import run_confirmation
class AsymmetryGuardedConfirmationTests(unittest.TestCase):
    def test_requires_large_disjoint_seed_confirmation(self):
        with self.assertRaisesRegex(ValueError,"trials_must_be_at_least_500"):
            run_confirmation(100)
if __name__=="__main__":unittest.main()
