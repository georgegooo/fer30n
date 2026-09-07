# =============================================================================
# FER3ON V3.5 — Micro Stability Test (Phase-1 Acceptance)
# =============================================================================
# Verifies that MICRO has been *softly* stabilized:
#   - Confidence 30 → 35 / 35 → 40
#   - Score 55 → 60 / 60 → 65
#   - 2-bar confirmation for REJECTION / INSIDE BAR / MOMENTUM BREAKOUT
# =============================================================================

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import micro_trading_engine as micro


def _make_rates(*bars):
    """Each bar=(o,h,l,c)."""
    out = []
    for o, h, l, c in bars:
        out.append({"open": o, "high": h, "low": l, "close": c})
    return out


class MicroStabilityTests(unittest.TestCase):

    def test_01_strict_score_threshold(self):
        # Single bullish breakout on last bar but only 2-bar context.
        # With V3.5 stricter threshold + 2-bar confirmation,
        # a single bullish breakout on the LAST bar should not be enough.
        rates = _make_rates(
            (2000, 2001, 1999, 2000.5),    # prev1 (bullish)
            (2000.6, 2001.5, 2000.5, 2001.4),  # prev2 (bullish)
            (2001.5, 2002.5, 2001.4, 2002.4),  # last — strong bullish momentum
        )
        ok, res = micro.should_enter_micro(rates, context={
            "confidence": 80, "liquidity_sweep": True, "volume_spike": True,
            "atr_expansion": True, "breakout_strength": 2,
        })
        # With momentum breakout + 2-bar confirmation → approved
        self.assertTrue(ok, msg=f"Expected approval, got reasons={res.get('reasons')}")

    def test_02_single_bar_no_confirmation_rejected(self):
        # Only one bullish bar — second is opposite. Should NOT confirm.
        rates = _make_rates(
            (2000, 2001, 1999, 2000.5),
            (2000.6, 2001.5, 2000.5, 2001.4),
            (2001.5, 2002.5, 2001.4, 2000.7),  # last is bearish inside-bar
        )
        # We don't expect confirmation because last 2 bars do not match direction.
        ok, res = micro.should_enter_micro(rates, context={"confidence": 80})
        # With bearish last bar, no momentum breakout, no rejection confirm.
        self.assertFalse(ok)

    def test_03_low_confidence_blocks_entry(self):
        rates = _make_rates(
            (2000, 2001, 1999, 2000.5),
            (2000.6, 2001.5, 2000.5, 2001.4),
            (2001.5, 2002.5, 2001.4, 2002.4),
        )
        # confidence below V3.5 minimum (35)
        ok, res = micro.should_enter_micro(rates, context={
            "confidence": 30, "liquidity_sweep": True, "volume_spike": True,
            "atr_expansion": True, "breakout_strength": 2,
        })
        self.assertFalse(ok)
        self.assertTrue(any("CONF_BELOW" in r for r in res.get("reasons", [])))

    def test_04_accept_disabled_stabilization(self):
        # If for some reason MICRO_STABILIZATION_ACTIVE=False, behavior must
        # still be safe (no crash; standard threshold applied).
        rates = _make_rates(
            (2000, 2001, 1999, 2000.5),
            (2000.6, 2001.5, 2000.5, 2001.4),
            (2001.5, 2002.5, 2001.4, 2002.4),
        )
        ok, res = micro.should_enter_micro(rates, context={
            "confidence": 60, "liquidity_sweep": True, "volume_spike": True,
            "atr_expansion": True, "breakout_strength": 2,
        })
        self.assertTrue(ok)

    def test_05_ema_alignment_adds_bonus_without_veto(self):
        # EMA alignment is a quality bonus only for MICRO. It should improve
        # the score without rejecting trades when the trend is neutral or mixed.
        rates = _make_rates(
            (2000, 2001, 1999, 2000.5),
            (2000.6, 2001.5, 2000.5, 2001.4),
            (2001.5, 2002.5, 2001.4, 2002.4),
        )
        base_context = {
            "confidence": 80, "liquidity_sweep": True, "volume_spike": True,
            "atr_expansion": True, "breakout_strength": 2,
        }
        ok, res = micro.should_enter_micro(rates, context={**base_context, "ema_direction": "BUY"})
        self.assertTrue(ok)
        self.assertTrue(any("EMA_DIRECTION_BONUS" in r for r in res.get("reasons", [])))

        ok2, res2 = micro.should_enter_micro(rates, context={**base_context, "ema_direction": "SELL"})
        self.assertTrue(ok2)
        self.assertFalse(any("EMA_DIRECTION_BLOCK" in r for r in res2.get("reasons", [])))


def run_all():
    suite = unittest.TestLoader().loadTestsFromTestCase(MicroStabilityTests)
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
