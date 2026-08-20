import unittest

from core.adaptive_sl_tp_engine import calculate_adaptive_sl_tp


class AdaptiveSLTPEngineTests(unittest.TestCase):
    def test_sl_and_tp_change_with_atr_and_lot(self):
        base = calculate_adaptive_sl_tp(
            atr=12.0,
            strategy="SCALP",
            lot=0.01,
            confidence=0.55,
            quality_score=60.0,
            market_regime="RANGING",
            session="LONDON",
            structure_strength=0.6,
            liquidity=0.55,
            volatility=0.4,
            spread=1.0,
            execution_grade="B",
        )
        larger = calculate_adaptive_sl_tp(
            atr=24.0,
            strategy="SCALP",
            lot=0.10,
            confidence=0.55,
            quality_score=60.0,
            market_regime="RANGING",
            session="LONDON",
            structure_strength=0.6,
            liquidity=0.55,
            volatility=0.4,
            spread=1.0,
            execution_grade="B",
        )

        self.assertGreater(larger["sl_distance"], base["sl_distance"])
        self.assertGreater(larger["tp_distance"], base["tp_distance"])
        self.assertGreater(larger["risk_reward"], base["risk_reward"])

    def test_quality_and_regime_change_sl_and_rr(self):
        conservative = calculate_adaptive_sl_tp(
            atr=15.0,
            strategy="SMC",
            lot=0.02,
            confidence=0.45,
            quality_score=45.0,
            market_regime="CRISIS",
            session="ASIA",
            structure_strength=0.35,
            liquidity=0.25,
            volatility=0.7,
            spread=3.0,
            execution_grade="C",
        )
        premium = calculate_adaptive_sl_tp(
            atr=15.0,
            strategy="SMC",
            lot=0.02,
            confidence=0.85,
            quality_score=90.0,
            market_regime="TRENDING",
            session="LONDON",
            structure_strength=0.9,
            liquidity=0.85,
            volatility=0.25,
            spread=0.5,
            execution_grade="A",
        )

        self.assertNotEqual(conservative["sl_distance"], premium["sl_distance"])
        self.assertNotEqual(conservative["risk_reward"], premium["risk_reward"])

    def test_structure_context_can_override_atr_distance(self):
        result = calculate_adaptive_sl_tp(
            atr=8.0,
            strategy="SMC",
            lot=0.02,
            confidence=0.8,
            quality_score=85.0,
            market_regime="TRENDING",
            session="LONDON",
            structure_strength=0.85,
            liquidity=0.8,
            volatility=0.25,
            spread=0.5,
            execution_grade="A",
            entry_price=2000.0,
            signal="BUY",
            structure_context={
                "swing_high": 1950.0,
                "swing_low": 1880.0,
                "order_block": 1940.0,
                "fair_value_gap": 1930.0,
                "liquidity_zone": 1910.0,
                "broker_minimum": 120.0,
            },
        )
        self.assertGreaterEqual(result["sl_distance"], 120.0)
        self.assertEqual(result["selected_stop_source"], "structure")

    def test_adaptive_sl_tp_returns_tp_tiers(self):
        result = calculate_adaptive_sl_tp(
            atr=10.0,
            strategy="SMC",
            lot=0.02,
            confidence=0.7,
            quality_score=75.0,
            market_regime="RANGING",
            session="LONDON",
            structure_strength=0.5,
            liquidity=0.6,
            volatility=0.4,
            spread=1.5,
            execution_grade="B",
            entry_price=2000.0,
            signal="BUY",
        )
        self.assertIn("tp_tiers", result)
        self.assertEqual(len(result["tp_tiers"]), 3)
        first_tier = result["tp_tiers"][0]
        self.assertEqual(first_tier["label"], "TP1")
        self.assertEqual(first_tier["close_pct"], 0.5)
        self.assertGreater(first_tier["price"], 2000.0)

    def test_broker_stop_level_is_guard_not_primary_basis(self):
        computed = calculate_adaptive_sl_tp(
            atr=5.0,
            strategy="MICRO",
            lot=0.01,
            confidence=0.6,
            quality_score=70.0,
            market_regime="RANGING",
            session="LONDON",
            structure_strength=0.6,
            liquidity=0.6,
            volatility=0.3,
            spread=1.0,
            execution_grade="B",
            broker_stop_level=0,
            broker_stop_fallback=200,
            min_sl=0,
        )
        guarded = calculate_adaptive_sl_tp(
            atr=5.0,
            strategy="MICRO",
            lot=0.01,
            confidence=0.6,
            quality_score=70.0,
            market_regime="RANGING",
            session="LONDON",
            structure_strength=0.6,
            liquidity=0.6,
            volatility=0.3,
            spread=1.0,
            execution_grade="B",
            broker_stop_level=120,
            broker_stop_fallback=200,
            min_sl=0,
        )

        self.assertLess(computed["sl_distance"], 200)
        self.assertGreaterEqual(guarded["sl_distance"], 120)


if __name__ == "__main__":
    unittest.main()
