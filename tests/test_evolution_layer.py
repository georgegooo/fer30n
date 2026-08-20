import unittest

from core.micro_probe_entries import build_execution_decision
from core.recovery_cooldown import RecoveryCooldownTracker
from core.dynamic_aggression import evaluate_aggression_state


class EvolutionLayerTests(unittest.TestCase):
    def test_probe_decision_uses_micro_entry_under_mixed_conditions(self):
        decision = build_execution_decision(
            spread=1.4,
            volatility=1.1,
            confidence=0.72,
            orderflow_pressure=0.64,
            smc_score=82,
            ai_override_strength=0.72,
            recovery_state="NONE",
            session="LONDON",
            market_dna="LIQUIDITY_SWEEP",
            drawdown=0.04,
            session_quality=0.8,
            liquidity_quality=0.7,
            counter_trend=False,
        )
        self.assertEqual(decision["decision"], "MICRO_PROBE")
        self.assertGreaterEqual(decision["probe_lot"], 0.01)

    def test_cooldown_reduces_reentry_after_loss(self):
        tracker = RecoveryCooldownTracker()
        state = tracker.record_outcome(
            outcome="LOSS",
            loss_amount=25.0,
            volatility=2.4,
            drawdown=0.08,
            session="NEW_YORK",
        )
        self.assertTrue(state["cooldown_active"])
        self.assertGreater(state["cooldown_seconds"], 0)

    def test_session_multiplier_reduces_aggression_in_news(self):
        state = evaluate_aggression_state(
            volatility=0.9,
            drawdown=0.02,
            winrate=0.55,
            spread=1.2,
            session_quality=0.8,
            liquidity_quality=0.8,
            ai_confidence=0.72,
            recovery_state="NONE",
            market_dna="TRENDING",
            session="NEWS_VOLATILITY",
        )
        self.assertLess(state["aggression_level"], 0.6)
        self.assertEqual(state["session_multiplier"], 0.55)


if __name__ == "__main__":
    unittest.main()
