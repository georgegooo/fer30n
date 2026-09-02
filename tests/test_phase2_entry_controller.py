# =============================================================================
# FER3ON — PHASE 2 tests: entry controller + structural SL
# =============================================================================
import json
import os
import tempfile
import unittest

from core.entry_controller import (
    compute_structural_sl_dist,
    plan_entry,
    scan_opportunity_zones,
    log_entry_plan,
    resolve_entry_plans,
    summary,
)

T0 = "2026-08-20T10:00:00+00:00"


def _candles(spec):
    return [{"time": f"2026-08-20T10:{i:02d}:00+00:00", "high": h, "low": l}
            for i, (h, l) in enumerate(spec, start=1)]


class TestStructuralSL(unittest.TestCase):
    def test_buy_sl_below_swing_low_with_buffer_capped(self):
        sa = {"swing_lows": [{"price": 95.0}]}
        r = compute_structural_sl_dist("BUY", 100.0, 10.0, sa, "SMC")
        # dist = 100 - (95 - 0.3*10) = 8 → under $15 swing cap
        self.assertEqual(r["source"], "structure")
        self.assertEqual(r["sl_dist"], 8.0)
        self.assertFalse(r["capped"])

    def test_cap_applies(self):
        sa = {"swing_lows": [{"price": 80.0}]}
        r = compute_structural_sl_dist("BUY", 100.0, 10.0, sa, "SCALP")
        # dist = 100 - (80-3) = 23 → capped to $10 scalp cap
        self.assertEqual(r["sl_dist"], 10.0)
        self.assertTrue(r["capped"])
        self.assertEqual(r["cap"], 10.0)

    def test_sell_above_swing_high(self):
        sa = {"swing_highs": [104.0]}
        r = compute_structural_sl_dist("SELL", 100.0, 10.0, sa, "SWING")
        # dist = (104+3) - 100 = 7
        self.assertEqual(r["sl_dist"], 7.0)

    def test_wrong_side_level_rejected(self):
        sa = {"swing_lows": [{"price": 120.0}]}  # low ABOVE entry — invalid
        r = compute_structural_sl_dist("BUY", 100.0, 10.0, sa, "SMC")
        self.assertIsNone(r["sl_dist"])
        self.assertEqual(r["source"], "structure_invalid")

    def test_atr_fallback_and_garbage_safety(self):
        r = compute_structural_sl_dist("BUY", 100.0, 10.0, None, "SMC")
        self.assertEqual(r["source"], "atr_fallback")
        self.assertEqual(r["sl_dist"], 15.0)  # 1.5*10, capped at 15
        self.assertIsNone(compute_structural_sl_dist("BUY", 0, 10.0, None))
        self.assertIsNone(compute_structural_sl_dist("WAT", 100.0, 10.0, None))
        self.assertIsNone(compute_structural_sl_dist(None, None, None, "garbage"))


class TestPlanEntry(unittest.TestCase):
    def test_limit_pullback_plan(self):
        sa = {"swing_lows": [{"price": 97.0}]}
        p = plan_entry(signal_id="s1", symbol="XAUUSD", direction="BUY",
                       signal_price=100.0, atr=10.0,
                       structure_analysis=sa, strategy="SMC")
        self.assertEqual(p["entry_mode"], "LIMIT_PULLBACK")
        self.assertEqual(p["limit_price"], 95.0)  # 100 - 0.5*10
        self.assertEqual(p["status"], "PENDING")
        self.assertEqual(p["structural_sl"]["source"], "structure")
        self.assertEqual(p["expected_sl"], 94.0)
        self.assertEqual(p["expected_tp"], 104.0)
        self.assertEqual(p["cancel_level"], 94.0)
        self.assertEqual(p["opportunity_mode"], "PREPARE_THEN_CONFIRM")
        self.assertTrue(p["confirmation_conditions"]["structure_valid"])

    def test_market_when_no_atr(self):
        p = plan_entry(direction="SELL", signal_price=100.0, atr=0.0)
        self.assertEqual(p["entry_mode"], "MARKET")
        self.assertEqual(p["status"], "READY")

    def test_invalid_never_raises(self):
        self.assertEqual(plan_entry(direction="BUY", signal_price=0)["entry_mode"], "SKIP")
        self.assertEqual(plan_entry(direction=None, signal_price=None)["entry_mode"], "SKIP")

    def test_proactive_scan_prepares_shadow_zone(self):
        plans = scan_opportunity_zones(
            symbol="XAUUSD", rates=[{"close": 100.0}], atr=10.0,
            structure_analysis={"structure_bias": "BUY", "swing_lows": [{"price": 97.0}]},
            strategy="SMC",
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["record_type"], "OPPORTUNITY_ZONE")
        self.assertFalse(plans[0]["live"])
        self.assertEqual(plans[0]["opportunity_source"], "PROACTIVE_STRUCTURE_SCAN")


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "plans.jsonl")

    def _plan(self, **kw):
        base = {"record_type": "ENTRY_PLAN", "signal_id": "s1",
                "direction": "BUY", "signal_time": T0,
                "entry_mode": "LIMIT_PULLBACK", "limit_price": 95.0,
                "ttl_bars": 3, "status": "PENDING"}
        base.update(kw)
        return base

    def test_fill_and_expire(self):
        log_entry_plan(self._plan(signal_id="fill"), log_path=self.path)
        log_entry_plan(self._plan(signal_id="expire", limit_price=50.0), log_path=self.path)
        res = resolve_entry_plans(_candles([(100, 96), (100, 94), (100, 99), (100, 99)]),
                                  log_path=self.path)
        self.assertTrue(res["ok"])
        with open(self.path, encoding="utf-8") as fh:
            recs = [json.loads(l) for l in fh]
        by_id = {r["signal_id"]: r for r in recs}
        self.assertEqual(by_id["fill"]["status"], "FILLED")      # low 94 <= 95 @ bar2
        self.assertEqual(by_id["fill"]["filled_bar"], 2)
        self.assertEqual(by_id["expire"]["status"], "EXPIRED")   # never reaches 50
        s = summary(log_path=self.path)
        self.assertEqual(s["fill_rate"], 0.5)

    def test_pending_when_not_enough_bars(self):
        log_entry_plan(self._plan(limit_price=50.0), log_path=self.path)
        resolve_entry_plans(_candles([(100, 99)]), log_path=self.path)
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(json.loads(fh.readline())["status"], "PENDING")

    def test_never_raises(self):
        self.assertFalse(resolve_entry_plans(None, log_path=self.path)["ok"])
        self.assertTrue(summary(log_path="/nonexistent/x.jsonl")["ok"])


class TestNoExecutionCapability(unittest.TestCase):
    def test_no_execution_imports(self):
        import core.entry_controller as mod
        with open(mod.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for banned in ("MetaTrader5", "order_send"):
            self.assertNotIn(banned, src)


if __name__ == "__main__":
    unittest.main()
