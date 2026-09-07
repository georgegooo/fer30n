"""Regression coverage for the FER3ON-FINAL-build1 certification-fix audit.

Each test here locks in one specific gap from the audit report so it can't
silently reopen:
  1. RECOVERY/SURVIVAL magic-number landmine (core/trade_identity.py)
  2. SWING's missing entry in the position-limits table (core/risk_manager.py)
     and the copy-paste 'DAILY' bug that exposed it (core/strategy_runners.py)
  3. risk_policy.py <-> settings.py numeric drift (covered in
     tests/test_governance_p0.py's test_risk_policy_matches_settings_numeric_fields,
     not duplicated here)
  4. [CERT-6] core.trade_executor's STEP 3 hardcoding `>= 1` instead of
     reading settings.MAX_OPEN_PER_STRATEGY (docs/history/FER3ON_FINAL_CHANGELOG.md).
     Re-applied on top of the rearch-phase1-2 branch, which forked from a
     pre-CERT-6 snapshot and had lost this coverage.
"""

import unittest
from unittest.mock import MagicMock

from core.settings import RECOVERY_MAGIC, SURVIVAL_MAGIC, MAX_OPEN_PER_STRATEGY
from core.trade_identity import (
    STRATEGY_TO_MAGIC,
    MAGIC_TO_STRATEGY,
    magic_from_strategy,
    strategy_from_magic,
    resolve_trade_identity,
)
from core.risk_manager import evaluate_position_limits
from core.trade_executor import _check_per_strategy_limit, _check_hedge_policy


class RecoverySurvivalMagicTests(unittest.TestCase):
    def test_recovery_and_survival_have_registered_magic_numbers(self):
        self.assertIn("RECOVERY", STRATEGY_TO_MAGIC)
        self.assertIn("SURVIVAL", STRATEGY_TO_MAGIC)
        self.assertEqual(STRATEGY_TO_MAGIC["RECOVERY"], int(RECOVERY_MAGIC))
        self.assertEqual(STRATEGY_TO_MAGIC["SURVIVAL"], int(SURVIVAL_MAGIC))

    def test_all_magic_numbers_are_unique(self):
        magics = list(STRATEGY_TO_MAGIC.values())
        self.assertEqual(len(magics), len(set(magics)), "duplicate magic numbers in STRATEGY_TO_MAGIC")

    def test_magic_from_strategy_ignores_fallback_for_known_strategies(self):
        # This is the exact landmine from the audit: previously, an unknown
        # strategy fell through to whatever `fallback` the caller passed
        # (possibly 0, possibly another strategy's magic). Now RECOVERY and
        # SURVIVAL are known strategies, so a caller-supplied fallback must
        # never override their registered magic.
        self.assertEqual(magic_from_strategy("RECOVERY", fallback=0), int(RECOVERY_MAGIC))
        self.assertEqual(magic_from_strategy("RECOVERY", fallback=9999), int(RECOVERY_MAGIC))
        self.assertEqual(magic_from_strategy("SURVIVAL", fallback=0), int(SURVIVAL_MAGIC))

    def test_strategy_from_magic_resolves_recovery_and_survival(self):
        self.assertEqual(strategy_from_magic(int(RECOVERY_MAGIC)), "RECOVERY")
        self.assertEqual(strategy_from_magic(int(SURVIVAL_MAGIC)), "SURVIVAL")
        self.assertEqual(MAGIC_TO_STRATEGY[int(RECOVERY_MAGIC)], "RECOVERY")
        self.assertEqual(MAGIC_TO_STRATEGY[int(SURVIVAL_MAGIC)], "SURVIVAL")

    def test_resolve_trade_identity_no_longer_defaults_recovery_to_manual(self):
        # This is what certification/framework.py's _is_bot_row relies on:
        # a deal closing with RECOVERY_MAGIC must resolve to RECOVERY, not
        # fall through mt5_history_sync's UNKNOWN -> MANUAL default.
        identity = resolve_trade_identity(magic=int(RECOVERY_MAGIC))
        self.assertEqual(identity["strategy"], "RECOVERY")
        self.assertFalse(identity["magic_mismatch"])


class SwingPositionLimitTests(unittest.TestCase):
    def test_swing_has_its_own_position_limit_entry(self):
        result = evaluate_position_limits(strategy="SWING", current_positions=0, total_positions=0)
        self.assertIn("SWING", result["hard_limits"])

    def test_swing_limit_is_enforced_independently_of_daily(self):
        # Before the fix, run_swing_cycle checked its count against the
        # 'DAILY' key (cap=10). Confirm SWING now has its own cap and it
        # isn't silently aliased to DAILY's.
        swing_result = evaluate_position_limits(strategy="SWING", current_positions=10, total_positions=10)
        self.assertIn(swing_result["hard_limits"]["SWING"], (10,))
        # At exactly the cap, SWING must be blocked on its own key, not fall
        # through as if unrecognized.
        self.assertFalse(swing_result["allowed"])
        self.assertEqual(swing_result["reason"], "SWING_POSITION_LIMIT_REACHED")


class PerStrategyLimitTests(unittest.TestCase):
    """Covers CERT-6: core.trade_executor's STEP 3 used to hardcode `>= 1`
    inline instead of reading settings.MAX_OPEN_PER_STRATEGY. Pulled out
    into _check_per_strategy_limit() specifically so this is directly
    testable without driving the rest of execute_trade()."""

    @staticmethod
    def _fake_position(magic):
        pos = MagicMock()
        pos.magic = magic
        return pos

    def test_does_not_block_below_the_configured_threshold(self):
        # The exact regression this guards against: hardcoding `>= 1` would
        # incorrectly block here even though max_open_per_strategy=3 permits
        # 2 concurrent positions for this strategy.
        fake_mt5 = MagicMock()
        fake_mt5.positions_get.return_value = [
            self._fake_position(4001), self._fake_position(4001),
        ]
        blocked, count = _check_per_strategy_limit(
            fake_mt5, "XAUUSD", magic=4001, max_open_per_strategy=3
        )
        self.assertFalse(blocked, "must not block below the configured threshold")
        self.assertEqual(count, 2)

    def test_blocks_once_the_configured_threshold_is_reached(self):
        fake_mt5 = MagicMock()
        fake_mt5.positions_get.return_value = [
            self._fake_position(4001), self._fake_position(4001), self._fake_position(4001),
        ]
        blocked, count = _check_per_strategy_limit(
            fake_mt5, "XAUUSD", magic=4001, max_open_per_strategy=3
        )
        self.assertTrue(blocked)

    def test_only_counts_positions_sharing_this_strategys_magic(self):
        fake_mt5 = MagicMock()
        fake_mt5.positions_get.return_value = [
            self._fake_position(5001),
        ]
        blocked, count = _check_per_strategy_limit(
            fake_mt5, "XAUUSD", magic=4001, max_open_per_strategy=1
        )
        self.assertFalse(blocked)
        self.assertEqual(count, 0)

    def test_current_live_setting_still_blocks_at_one(self):
        self.assertEqual(MAX_OPEN_PER_STRATEGY, 1)
        fake_mt5 = MagicMock()
        fake_mt5.positions_get.return_value = [self._fake_position(4001)]
        blocked, _ = _check_per_strategy_limit(
            fake_mt5, "XAUUSD", magic=4001, max_open_per_strategy=MAX_OPEN_PER_STRATEGY
        )
        self.assertTrue(blocked)


class HedgePolicyTests(unittest.TestCase):
    @staticmethod
    def _position(position_type, magic):
        pos = MagicMock()
        pos.type = position_type
        pos.magic = magic
        return pos

    @staticmethod
    def _mt5(positions, margin_mode=2):
        fake_mt5 = MagicMock()
        fake_mt5.ORDER_TYPE_BUY = 0
        fake_mt5.ORDER_TYPE_SELL = 1
        fake_mt5.POSITION_TYPE_BUY = 0
        fake_mt5.POSITION_TYPE_SELL = 1
        fake_mt5.ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 2
        fake_mt5.positions_get.return_value = positions
        fake_mt5.account_info.return_value.margin_mode = margin_mode
        return fake_mt5

    def test_cross_strategy_hedge_is_allowed_on_hedging_account(self):
        fake_mt5 = self._mt5([self._position(1, 3001)])
        blocked, count = _check_hedge_policy(fake_mt5, "XAUUSD", 0, "SCALP")
        self.assertFalse(blocked)
        self.assertEqual(count, 1)

    def test_second_cross_strategy_hedge_is_allowed_for_two_buy_two_sell_plan(self):
        fake_mt5 = self._mt5([
            self._position(0, 1001),
            self._position(0, 3001),
        ])
        blocked, count = _check_hedge_policy(fake_mt5, "XAUUSD", 1, "MICRO")
        self.assertFalse(blocked)
        self.assertEqual(count, 2)

    def test_same_strategy_hedge_is_blocked(self):
        fake_mt5 = self._mt5([self._position(1, 1001)])
        blocked, _ = _check_hedge_policy(fake_mt5, "XAUUSD", 0, "SCALP")
        self.assertTrue(blocked)

    def test_netting_account_blocks_hedge(self):
        fake_mt5 = self._mt5([self._position(1, 3001)], margin_mode=0)
        blocked, _ = _check_hedge_policy(fake_mt5, "XAUUSD", 0, "SCALP")
        self.assertTrue(blocked)


if __name__ == "__main__":
    unittest.main()
