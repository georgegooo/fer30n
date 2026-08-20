# =============================================================================
# FER3ON V3.5 — Performance Validation Test (Phase-1 Acceptance)
# =============================================================================
# Validates that analytics/setup_analyzer.py correctly answers:
#   "Which setup actually wins?"
# =============================================================================

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analytics.truth_layer import TradeRecord, __test_reset__
from analytics.setup_analyzer import (
    analyze_setup,
    analyze_all_setups,
    acceptance_smoke_test,
    overall_setups_report,
)


class PerformanceValidationTests(unittest.TestCase):

    def setUp(self):
        __test_reset__()

    def test_01_analyze_all_strategies_returns_metrics(self):
        out = acceptance_smoke_test()
        # All five core strategies present in the analyzer
        self.assertEqual(out["expected_strategies_present"],
                         sorted(["SCALP", "MICRO", "SMC", "SWING", "DAILY"]))

    def test_02_ranking_invariant(self):
        out = acceptance_smoke_test()
        # ranks are 1..N
        items = out["analyze_setup_seed_smoke"]
        ranks = [i["rank"] for i in items]
        self.assertEqual(sorted(ranks), list(range(1, len(items) + 1)))

    def test_03_overall_report_shape(self):
        rep = overall_setups_report()
        self.assertIn("strategies", rep)
        self.assertIn("ranking", rep)
        for s in ("SCALP", "MICRO", "SMC", "SWING", "DAILY"):
            self.assertIn(s, rep["strategies"])

    def test_04_verdict_key_words(self):
        out = analyze_setup("SCALP", trades=[])
        self.assertIn(out.verdict, ("INSUFFICIENT_SAMPLES", "PROFITABLE",
                                    "EDGE_PRESENT", "WEAK_NEGATIVE_EDGE", "MIXED"))


def run_all():
    suite = unittest.TestLoader().loadTestsFromTestCase(PerformanceValidationTests)
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    return {
        "tests_run": res.testsRun,
        "failures": len(res.failures),
        "errors": len(res.errors),
        "ok": res.wasSuccessful(),
    }


if __name__ == "__main__":
    import json
    summary = run_all()
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["ok"] else 1)
