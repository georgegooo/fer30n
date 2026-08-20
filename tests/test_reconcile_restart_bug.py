"""
Regression test for a critical restart bug found while reviewing real
production data: 20 positions (10 SMC + 10 MICRO) had accumulated open
simultaneously over 4 days across multiple bot restarts, even though
MAX_OPEN_PER_STRATEGY is supposed to cap each strategy at 1 concurrent
position.

Root cause: core.portfolio_risk_authority's _STATE.open_trades is in-memory
only. reconcile_with_live_positions() used to be prune-only -- it removed
stale entries but never re-imported a live MT5 position that was already
open when the process started. So every restart reset the per-strategy
open count to 0 regardless of what was actually still open on the broker,
letting a brand new position open on top of one still live from a previous
session.

Fix: reconcile_with_live_positions() now also imports any live position
missing from open_trades, inferring strategy from its magic number.
"""
from unittest.mock import MagicMock

import core.portfolio_risk_authority as pra


def _fake_position(ticket, magic, volume=0.02, price_open=4090.0, sl=4080.0, tp=4110.0, type_=0):
    p = MagicMock()
    p.ticket = ticket
    p.magic = magic
    p.volume = volume
    p.price_open = price_open
    p.sl = sl
    p.tp = tp
    p.type = type_  # 0 = BUY, 1 = SELL
    return p


def test_reconcile_imports_live_position_missing_after_restart():
    """The actual bug: simulate a fresh process start (empty open_trades)
    where a real SMC position is already open on the broker from a
    previous session. Without the fix, the cap check sees 0 open and lets
    a second SMC position through -- reproducing the 20-position pileup."""
    pra.__test_reset__()
    pra.reset_portfolio_state(balance=1000.0)

    assert len(pra._STATE.open_trades) == 0  # simulating a fresh restart

    live_position = _fake_position(ticket=57779739545, magic=4001)  # SMC magic
    result = pra.reconcile_with_live_positions([live_position])

    assert result["imported"] == 1
    assert result["removed"] == 0
    assert len(pra._STATE.open_trades) == 1
    assert pra._STATE.open_trades[0]["strategy"] == "SMC"
    assert pra._STATE.open_trades[0]["ticket"] == 57779739545

    # This is the actual failure mode this fix prevents: a second SMC
    # trade must now be correctly blocked, not silently allowed.
    decision = pra.evaluate_risk(strategy="SMC", direction="BUY", requested_risk_percent=1.0)
    assert not decision.approved
    assert decision.rejection_reason == "PER_STRATEGY_MAX_OPEN_HIT"

    pra.__test_reset__()


def test_reconcile_still_prunes_stale_entries():
    """Existing behavior must be preserved: an open_trades entry for a
    position that's no longer open on the broker gets removed."""
    pra.__test_reset__()
    pra.reset_portfolio_state(balance=1000.0)

    pra.record_trade_open(
        ticket=111, strategy="MICRO", direction="BUY", lot=0.01,
        risk_percent=1.0, entry_price=4000.0, sl=3990.0, tp=4010.0,
    )
    assert len(pra._STATE.open_trades) == 1

    result = pra.reconcile_with_live_positions([])  # nothing open on broker now
    assert result["removed"] == 1
    assert result["imported"] == 0
    assert len(pra._STATE.open_trades) == 0

    pra.__test_reset__()


def test_reconcile_does_not_duplicate_already_tracked_position():
    pra.__test_reset__()
    pra.reset_portfolio_state(balance=1000.0)

    pra.record_trade_open(
        ticket=222, strategy="SMC", direction="SELL", lot=0.02,
        risk_percent=1.5, entry_price=4090.0, sl=4100.0, tp=4070.0,
    )

    live_position = _fake_position(ticket=222, magic=4001)
    result = pra.reconcile_with_live_positions([live_position])

    assert result["imported"] == 0
    assert len(pra._STATE.open_trades) == 1

    pra.__test_reset__()
