"""Regression tests for the HISTORY_FILE (data/history/trades.csv) close-sync fix.

Bug (found while investigating why ~half of trades.csv sat at result="OPEN"
forever, and why every closed row had rr_ratio/quality_score/brain_score==0):

`sync_mt5_history()` (core/mt5_history_sync.py) already computes the correct
`close_ticket = deal.position_id or deal.ticket` for matching a closing deal
back to its open-time record — and uses it correctly for ai_memory.csv
(`deal_exists`/`save_trade_memory`) and for `record_trade_close()`. But the
HISTORY_FILE (trades.csv) write path was never updated to match: it kept
checking/writing `deal.ticket` (the closing DEAL's own id, which is not the
same id the open-time row was logged under -- see trade_executor.py, which
logs `ticket=result.order`) and it unconditionally hardcoded
rr_ratio/quality_score/brain_score to 0.

Net effect: the open-time row (with the real quality_score/rr_ratio/
brain_score captured at entry) was never found and never updated -- it sat at
result="OPEN" forever -- while a brand-new, permanently-zeroed orphan row got
appended under the closing deal's own ticket instead. Every downstream module
that tries to learn "does quality_score/rr_ratio actually predict a win"
(adaptive_learning, outcome_learning, contribution_analysis, history_learner)
was training on broken data as a result.

Fix: key the HISTORY_FILE write on close_ticket, and merge (upsert) into the
existing open-time row -- only overwriting result/profit -- instead of always
appending a fresh, zeroed-out row.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import core.data_integrity as di
import core.mt5_history_sync as sync_mod


def _make_fake_deal(ticket, position_id, profit=45.0, comment="[tp 2415.00]"):
    return SimpleNamespace(
        entry=1,
        ticket=ticket,
        position_id=position_id,
        type=0,  # BUY
        magic=123,
        symbol="XAUUSD",
        volume=0.01,
        profit=profit,
        price=2415.0,
        time=1753300000,  # arbitrary fixed unix timestamp
        comment=comment,
    )


def _patched_sync(monkeypatch, tmp_path, deal, *, has_open_record):
    """Run sync_mt5_history() with every side-effect dependency neutralised
    except the exact HISTORY_FILE read/write path being tested."""
    history_file = str(tmp_path / "trades.csv")
    mt5_file = str(tmp_path / "mt5_trade_history.csv")

    monkeypatch.setattr(sync_mod, "HISTORY_FILE", history_file)
    monkeypatch.setattr(sync_mod, "FILE_NAME", mt5_file)
    monkeypatch.setattr(sync_mod, "MT5_AVAILABLE", True)
    monkeypatch.setattr(sync_mod, "mt5", MagicMock(history_deals_get=lambda *a, **k: [deal]))

    monkeypatch.setattr(
        sync_mod, "resolve_trade_identity",
        lambda magic=0: {"strategy": "SMC", "magic": 123, "raw_magic": 123, "magic_mismatch": False},
    )
    monkeypatch.setattr(sync_mod, "deal_exists", lambda ticket: has_open_record)
    monkeypatch.setattr(sync_mod, "save_trade_memory", MagicMock())
    monkeypatch.setattr(sync_mod, "record_trade_outcome", MagicMock())
    monkeypatch.setattr(sync_mod, "append_trade", MagicMock())
    monkeypatch.setattr(sync_mod, "register_win", MagicMock())
    monkeypatch.setattr(sync_mod, "register_loss", MagicMock())
    monkeypatch.setattr(sync_mod, "record_trade_close", MagicMock())
    monkeypatch.setattr(sync_mod, "update_certification_progress", lambda: {"closed_trade_count": 1})

    return history_file, mt5_file


def test_unknown_magic_recovered_via_parent_position_strategy(monkeypatch, tmp_path):
    """Regression test for the recovery fix: a deal with magic=0/unresolved
    (e.g. a partial TP-ladder close, or a manual SL/TP tweak on a
    bot-opened position) must be recovered via its parent position's
    already-recorded strategy, not silently discarded."""
    open_ticket = 77700
    orphan_deal = _make_fake_deal(ticket=99500, position_id=open_ticket, profit=12.34)
    orphan_deal.magic = 0

    history_file, _ = _patched_sync(monkeypatch, tmp_path, orphan_deal, has_open_record=True)
    # This test needs UNKNOWN specifically (unlike the shared SMC-always mock).
    monkeypatch.setattr(
        sync_mod, "resolve_trade_identity",
        lambda magic=0: {"strategy": "UNKNOWN", "magic": 0, "raw_magic": 0, "magic_mismatch": False},
    )

    di.append_csv_row(history_file, di.HISTORY_COLUMNS, {
        "date": "2026-07-23T05:00:00+00:00",
        "ticket": open_ticket,
        "signal": "BUY",
        "lot": 0.01,
        "profit": 0,
        "result": "OPEN",
        "strategy": "MICRO",
        "session": "LONDON",
        "market_regime": "TRENDING",
        "exec_grade": "A",
        "rr_ratio": 1.5,
        "quality_score": 60,
        "brain_score": 70,
    })

    sync_mod.sync_mt5_history()

    rows = di.read_csv_records(history_file, di.HISTORY_COLUMNS)
    matching = [r for r in rows if str(r["ticket"]) == str(open_ticket)]
    assert len(matching) == 1
    assert matching[0]["strategy"] == "MICRO"
    assert matching[0]["result"] == "WIN"
    assert float(matching[0]["profit"]) == 12.34


def test_unknown_magic_with_no_parent_recorded_as_manual(monkeypatch, tmp_path):
    """A deal with no resolvable magic AND no matching parent position (a
    fully manual trade opened and closed outside the bot) must still be
    recorded -- as strategy=MANUAL -- not discarded."""
    orphan_deal = _make_fake_deal(ticket=99600, position_id=88800, profit=-7.5)
    orphan_deal.magic = 0

    history_file, _ = _patched_sync(monkeypatch, tmp_path, orphan_deal, has_open_record=False)
    monkeypatch.setattr(
        sync_mod, "resolve_trade_identity",
        lambda magic=0: {"strategy": "UNKNOWN", "magic": 0, "raw_magic": 0, "magic_mismatch": False},
    )

    sync_mod.sync_mt5_history()

    rows = di.read_csv_records(history_file, di.HISTORY_COLUMNS)
    assert len(rows) == 1
    assert rows[0]["strategy"] == "MANUAL"
    assert rows[0]["result"] == "LOSS"
    assert float(rows[0]["profit"]) == -7.5


def test_close_merges_into_existing_open_row_preserving_scores(monkeypatch, tmp_path):
    open_ticket = 55000  # this is what result.order was at open time
    closing_deal = _make_fake_deal(ticket=99001, position_id=open_ticket)

    history_file, _ = _patched_sync(monkeypatch, tmp_path, closing_deal, has_open_record=True)

    # Seed the open-time row exactly as trade_executor.py's persist_trade_log
    # would have written it -- real quality/RR data, still "OPEN".
    di.append_csv_row(history_file, di.HISTORY_COLUMNS, {
        "date": "2026-07-23T05:00:00+00:00",
        "ticket": open_ticket,
        "signal": "BUY",
        "lot": 0.01,
        "profit": 0,
        "result": "OPEN",
        "strategy": "SMC",
        "session": "LONDON",
        "market_regime": "TRENDING",
        "exec_grade": "A",
        "rr_ratio": 2.1,
        "quality_score": 77,
        "brain_score": 88,
    })

    sync_mod.sync_mt5_history()

    rows = di.read_csv_records(history_file, di.HISTORY_COLUMNS)
    matching = [r for r in rows if str(r["ticket"]) == str(open_ticket)]

    assert len(rows) == 1, (
        f"Expected the open row to be updated in place, got {len(rows)} rows -- "
        "a duplicate/orphan row was created instead (bug regressed)."
    )
    assert len(matching) == 1
    row = matching[0]
    assert row["result"] == "WIN"
    assert float(row["profit"]) == 45.0
    # The whole point of the fix: these must survive the close untouched.
    assert float(row["quality_score"]) == 77, "quality_score was zeroed on close -- bug regressed."
    assert float(row["rr_ratio"]) == 2.1, "rr_ratio was zeroed on close -- bug regressed."
    assert float(row["brain_score"]) == 88, "brain_score was zeroed on close -- bug regressed."
    assert row["session"] == "LONDON"
    assert row["strategy"] == "SMC"


def test_close_falls_back_to_placeholders_when_no_open_row_exists(monkeypatch, tmp_path):
    """A trade with no matching open-time record (opened manually, or before
    this bot instance ran) has nothing to merge into -- it should still get
    logged (with the documented SYNC/0 placeholders), not silently dropped."""
    open_ticket = 66000
    closing_deal = _make_fake_deal(ticket=99002, position_id=open_ticket, profit=-12.0, comment="[sl 2400.00]")

    history_file, _ = _patched_sync(monkeypatch, tmp_path, closing_deal, has_open_record=False)

    sync_mod.sync_mt5_history()

    rows = di.read_csv_records(history_file, di.HISTORY_COLUMNS)
    assert len(rows) == 1
    row = rows[0]
    assert str(row["ticket"]) == str(open_ticket)
    assert row["result"] == "LOSS"
    assert float(row["profit"]) == -12.0
    assert row["exec_grade"] == "SYNC"


def test_truth_layer_record_keyed_by_position_ticket_not_deal_ticket(monkeypatch, tmp_path):
    """Regression test for a data-integrity bug found while investigating why
    analytics/csv_truth_bridge.py::sync_csv_to_truth_layer() kept re-"syncing"
    trades that mt5_history_sync() had already recorded: the truth_layer
    TradeRecord was keyed by deal.ticket (the closing DEAL's own id), while
    trades.csv (and everything the bridge dedupes against) is keyed by
    close_ticket (= position_id, the POSITION ticket). Confirmed empirically
    against real data: zero ticket overlap between the two files for the
    same 20 real trades -- every trade was silently duplicated into
    truth_layer with a blank build_id the first time both sync paths ran in
    the same session.

    Fix: TradeRecord.ticket must equal close_ticket (same value written to
    trades.csv), not deal.ticket.
    """
    open_ticket = 77000  # position ticket -- what trade_executor.py logged at open
    deal_ticket = 88123  # the CLOSING deal's own id -- must NOT end up as TradeRecord.ticket
    closing_deal = _make_fake_deal(ticket=deal_ticket, position_id=open_ticket, profit=30.0)

    history_file, _ = _patched_sync(monkeypatch, tmp_path, closing_deal, has_open_record=True)

    di.append_csv_row(history_file, di.HISTORY_COLUMNS, {
        "date": "2026-07-23T05:00:00+00:00",
        "ticket": open_ticket,
        "signal": "BUY",
        "lot": 0.01,
        "profit": 0,
        "result": "OPEN",
        "strategy": "SMC",
        "session": "LONDON",
        "market_regime": "TRENDING",
        "exec_grade": "A",
        "rr_ratio": 2.1,
        "quality_score": 77,
        "brain_score": 88,
    })

    sync_mod.sync_mt5_history()

    # append_trade is mocked in _patched_sync -- inspect what it was called with.
    assert sync_mod.append_trade.call_count == 1
    record = sync_mod.append_trade.call_args[0][0]
    assert record.ticket == open_ticket, (
        f"TradeRecord.ticket={record.ticket} -- expected close_ticket={open_ticket} "
        f"(must match trades.csv's key), not deal_ticket={deal_ticket}. Bug regressed."
    )
