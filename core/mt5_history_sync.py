from core.mt5_compat import mt5, MT5_AVAILABLE
import csv
import json
import os

from datetime import datetime, timezone, timedelta

from certification.framework import update_certification_progress
from core.adaptive_learning import record_trade_outcome
from core.ai_memory import deal_exists, save_trade_memory
from core.data_integrity import (
    HISTORY_COLUMNS,
    HISTORY_FILE,
    ensure_csv_schema,
    read_csv_records,
    upsert_csv_row,
)
from core.risk_manager import register_loss, register_win
from core.portfolio_risk_authority import record_trade_close, record_trade_partial_close
from analytics.truth_layer import TradeRecord, append_trade
from core.trade_identity import resolve_trade_identity
from core.settings import BUILD_ID
from core.account_scope import get_cached_account_id

# =========================================
# FILE
# =========================================

FILE_NAME = "data/history/mt5_trade_history.csv"
OPEN_RECONCILIATION_LOG = "data/analytics/reconciliation/open_records_shadow.jsonl"
DEAL_EVENTS_FILE = "data/history/mt5_deal_events.jsonl"


# =========================================
# INIT CSV
# =========================================


def initialize_mt5_history():
    os.makedirs("data/history", exist_ok=True)
    ensure_csv_schema(HISTORY_FILE, HISTORY_COLUMNS)

    if not os.path.exists(FILE_NAME):
        with open(
            FILE_NAME,
            mode="w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.writer(file)
            writer.writerow([
                "ticket",
                "strategy",
                "symbol",
                "type",
                "volume",
                "profit",
                "open_price",
                "close_price",
                "open_time",
                "close_time",
                "comment",
                "raw_magic",
                "canonical_magic",
                "build_id",
            ])

    print("✅ MT5 HISTORY READY")


# =========================================
# SYNC MT5 HISTORY
# =========================================


def shadow_reconcile_open_records(*, history_file: str = HISTORY_FILE,
                                  log_file: str = OPEN_RECONCILIATION_LOG) -> dict:
    """Report local OPEN rows absent from current MT5 positions.

    Shadow-only: this function never changes a trade ledger or an MT5
    position. A row becomes CLOSED_UNCONFIRMED only as a recommendation;
    WIN/LOSS still requires a confirmed closing deal in sync_mt5_history().
    """
    result = {"ok": False, "checked": 0, "candidates": 0, "logged": 0}
    try:
        if not MT5_AVAILABLE or mt5 is None:
            result["reason"] = "MT5_UNAVAILABLE"
            return result
        positions = mt5.positions_get()
        if positions is None:
            result["reason"] = "POSITION_STATE_UNAVAILABLE"
            return result
        active_tickets = {
            str(getattr(position, "ticket", ""))
            for position in positions
            if getattr(position, "ticket", None) is not None
        }
        if not os.path.exists(history_file):
            result.update(ok=True, reason="NO_HISTORY_FILE")
            return result

        with open(history_file, "r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        candidates = []
        for row in rows:
            if str(row.get("result", "")).upper() != "OPEN":
                continue
            result["checked"] += 1
            ticket = str(row.get("ticket", "") or "")
            if ticket and ticket not in active_tickets:
                candidates.append({
                    "record_type": "OPEN_RECONCILIATION",
                    "ticket": ticket,
                    "symbol": row.get("symbol", "XAUUSD"),
                    "strategy": row.get("strategy", "UNKNOWN"),
                    "previous_status": "OPEN",
                    "proposed_status": "CLOSED_UNCONFIRMED",
                    "reason": "ABSENT_FROM_CURRENT_MT5_POSITIONS",
                    "confirmed_close_required": True,
                    "shadow_only": True,
                })
        result["candidates"] = len(candidates)
        existing = set()
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                        existing.add(str(record.get("ticket", "")))
                    except json.JSONDecodeError:
                        continue
        if candidates:
            parent = os.path.dirname(log_file)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as handle:
                for candidate in candidates:
                    if candidate["ticket"] in existing:
                        continue
                    candidate["timestamp"] = datetime.now(timezone.utc).isoformat()
                    handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                    result["logged"] += 1
        result["ok"] = True
        return result
    except Exception as exc:
        result["reason"] = type(exc).__name__
        return result


def sync_mt5_history():
    if not MT5_AVAILABLE or mt5 is None:
        print("⚠️ MT5 unavailable — history sync skipped")
        return {"synced": 0, "history_rows": 0, "memory_rows": 0,
                "adaptive_rows": 0, "close_events": []}

    initialize_mt5_history()

    reconciliation = shadow_reconcile_open_records()
    if reconciliation.get("candidates"):
        print(
            f"🔎 OPEN_RECONCILIATION_SHADOW | candidates="
            f"{reconciliation['candidates']} | logged={reconciliation['logged']}"
        )

    try:
        deals = mt5.history_deals_get(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime.now(timezone.utc) + timedelta(hours=1),
        )
        if deals is None:
            print("❌ NO MT5 HISTORY")
            return {"synced": 0, "history_rows": 0, "memory_rows": 0,
                    "adaptive_rows": 0, "close_events": []}

        # Deal events are immutable evidence. Their composite key prevents
        # duplicate close notifications across restarts and accounts.
        account_id = str(get_cached_account_id() or "UNKNOWN")
        known_deal_events = set()
        if os.path.exists(DEAL_EVENTS_FILE):
            try:
                with open(DEAL_EVENTS_FILE, "r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            event = json.loads(line)
                            known_deal_events.add((
                                str(event.get("account_id", "")),
                                str(event.get("deal_ticket", "")),
                            ))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        open_volumes = {}
        close_volumes = {}
        for deal in deals:
            position_id = int(getattr(deal, "position_id", 0) or 0)
            volume = float(getattr(deal, "volume", 0.0) or 0.0)
            if getattr(deal, "entry", None) == 0:
                open_volumes[position_id] = open_volumes.get(position_id, 0.0) + volume
            elif getattr(deal, "entry", None) == 1:
                close_volumes[position_id] = close_volumes.get(position_id, 0.0) + volume

        close_events = []
        event_by_deal_ticket = {}
        new_event_records = []
        for deal in deals:
            if getattr(deal, "entry", None) != 1:
                continue
            event_key = (account_id, str(getattr(deal, "ticket", "")))
            if event_key in known_deal_events:
                continue
            profit_value = float(getattr(deal, "profit", 0.0) or 0.0)
            position_id = int(getattr(deal, "position_id", 0) or 0)
            outcome = "WIN" if profit_value > 0 else "LOSS" if profit_value < 0 else "BREAKEVEN"
            event = {
                "record_type": "MT5_CLOSE_DEAL",
                "account_id": account_id,
                "deal_ticket": int(getattr(deal, "ticket", 0) or 0),
                "position_id": position_id,
                "symbol": str(getattr(deal, "symbol", "") or ""),
                "profit": round(profit_value, 4),
                "outcome": outcome,
                "is_final_close": close_volumes.get(position_id, 0.0)
                >= open_volumes.get(position_id, 0.0) - 1e-9,
                "timestamp": datetime.fromtimestamp(
                    float(getattr(deal, "time", 0) or 0), tz=timezone.utc
                ).isoformat(),
                "shadow_only": False,
            }
            new_event_records.append(event)
            event_by_deal_ticket[event["deal_ticket"]] = event
            if event["is_final_close"]:
                close_events.append({
                    "ticket": event["position_id"],
                    "deal_ticket": event["deal_ticket"],
                    "profit": event["profit"],
                    "result": outcome,
                })
        if new_event_records:
            os.makedirs(os.path.dirname(DEAL_EVENTS_FILE), exist_ok=True)
            with open(DEAL_EVENTS_FILE, "a", encoding="utf-8") as handle:
                for event in new_event_records:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")

        mt5_existing_tickets = set()
        if os.path.exists(FILE_NAME):
            with open(FILE_NAME, mode="r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    try:
                        mt5_existing_tickets.add(int(row["ticket"]))
                    except Exception:
                        continue

        _history_rows_snapshot = read_csv_records(HISTORY_FILE, HISTORY_COLUMNS)
        history_existing_tickets = {
            str(row.get("ticket", "") or "") for row in _history_rows_snapshot
        }
        # RECOVERY FIX: maps a position's opening ticket to the strategy it
        # was actually opened with. Used below to recover a deal whose own
        # magic is missing/unresolvable (0 or unmapped) — e.g. a partial
        # TP-ladder close (see execution/tp_monitor.py fix) or a manual
        # SL/TP adjustment from the terminal that closes part of a
        # bot-opened position — by looking up the ORIGINAL position's
        # recorded strategy instead of discarding a real, valid trade.
        history_ticket_to_strategy = {}
        for row in _history_rows_snapshot:
            strat = str(row.get("strategy") or "").upper()
            if not strat or strat in ("UNKNOWN",):
                continue
            try:
                history_ticket_to_strategy[int(row.get("ticket") or 0)] = strat
            except (TypeError, ValueError):
                continue

        # DATA-INTEGRITY FIX (open_price bug): this loop only ever iterates
        # closing deals (entry == 1, filtered below), and every row written
        # to mt5_trade_history.csv used to put that SAME closing deal.price
        # into BOTH the open_price and close_price columns — so open_price
        # was never the real entry price, it was just close_price duplicated.
        # That silently broke every downstream use of open_price (slippage
        # analysis, R:R verification against actual fills, adaptive-SL
        # calibration) without ever raising an error, since both columns
        # always had *a* number in them.
        #
        # Fix: index every OPENING deal (entry == 0) by position_id up front
        # — position_id is what links an opening deal to the closing deal(s)
        # of the same position — so the real entry price can be looked up
        # when writing each closing row. Falls back to deal.price only if no
        # opening deal exists in the fetched window (e.g. a position opened
        # before 2024-01-01, or opened by a different terminal/history not
        # covered by this history_deals_get() call).
        open_price_by_position = {}
        open_volume_by_position = {}
        closed_volume_by_position = {}
        for _d in deals:
            if getattr(_d, "entry", None) == 0:
                open_price_by_position[_d.position_id] = _d.price
                open_volume_by_position[_d.position_id] = (
                    open_volume_by_position.get(_d.position_id, 0.0)
                    + float(getattr(_d, "volume", 0.0) or 0.0)
                )

        new_rows = []
        cumulative_profit_by_ticket = {}
        for row in _history_rows_snapshot:
            try:
                cumulative_profit_by_ticket[str(row.get("ticket", ""))] = float(row.get("profit", 0) or 0)
            except (TypeError, ValueError):
                pass
        synced_history = 0
        synced_memory = 0
        synced_adaptive = 0

        for deal in deals:
            try:
                if deal.entry != 1:
                    continue
                if deal.ticket in mt5_existing_tickets:
                    continue

                trade_type = "BUY"
                if deal.type == 1:
                    trade_type = "SELL"

                identity = resolve_trade_identity(magic=getattr(deal, "magic", 0))
                strategy = identity["strategy"]
                if strategy == "UNKNOWN":
                    # RECOVERY FIX (see history_ticket_to_strategy above):
                    # this used to skip silently -- zero log output -- making
                    # a real closed deal with an unrecognized/zero magic
                    # vanish from mt5_trade_history.csv and trades.csv with
                    # no trace at all. Confirmed in production: 8 real trades
                    # (net +$154.36) were partial TP-ladder closes that lost
                    # their magic to the tp_monitor.py bug (now fixed) and
                    # were completely invisible to every stat until this fix.
                    #
                    # First try recovering the REAL strategy via the parent
                    # position -- this covers both that bug's historical
                    # backlog (re-synced fresh on the next run, since these
                    # deals were never persisted anywhere) and any future
                    # deal that loses its magic for a different reason, e.g.
                    # جو manually adjusting SL/TP on a bot-opened position
                    # from the terminal for support/risk-management.
                    _recovered_strategy = history_ticket_to_strategy.get(
                        int(getattr(deal, "position_id", None) or 0)
                    )
                    if _recovered_strategy:
                        strategy = _recovered_strategy
                        print(
                            f"✅ SYNC_RECOVERED_VIA_POSITION | ticket={deal.ticket} "
                            f"position_id={getattr(deal, 'position_id', None)} "
                            f"magic={getattr(deal, 'magic', 0)} -> strategy={strategy}"
                        )
                    else:
                        # Genuinely can't attribute this to any known
                        # strategy or parent position -- most likely a fully
                        # manual trade (opened AND closed outside the bot).
                        # Still record it as MANUAL rather than discarding
                        # it, so overall account P&L stays complete and
                        # auditable. It's excluded from SMC/MICRO-specific
                        # performance stats (which filter by exact strategy
                        # name) the same way a human trader's manual
                        # override shouldn't be scored as the algorithm's
                        # own decision -- but it still counts toward overall
                        # certification/account totals, same as any other
                        # closed trade.
                        strategy = "MANUAL"
                        print(
                            f"⚠️ SYNC_UNRESOLVED_RECORDED_AS_MANUAL | ticket={deal.ticket} "
                            f"magic={getattr(deal, 'magic', 0)} profit={deal.profit} "
                            f"time={datetime.fromtimestamp(deal.time, tz=timezone.utc).isoformat()}"
                        )

                close_dt = datetime.fromtimestamp(deal.time, tz=timezone.utc)
                profit_value = float(deal.profit or 0)
                result = "WIN" if profit_value > 0 else "LOSS" if profit_value < 0 else "BREAKEVEN"
                session = _session_from_hour(close_dt.hour)
                market_regime = "UNKNOWN"

                # ENRICHMENT FIX (root cause): open-time save_trade_memory()
                # (core/trade_executor.py) stores ticket=result.order — the
                # MT5 ORDER/POSITION ticket. deal.ticket here is a SEPARATE
                # identifier for the closing deal record and essentially
                # never equals it (same distinction already documented and
                # fixed below for record_trade_close(), but that fix was
                # never applied to this save_trade_memory() call). Using
                # deal.ticket meant _upsert_memory_row() could never find
                # the existing open-time row, so every close silently
                # appended a brand-new orphan row instead of merging into
                # it — the open-time row stayed result="OPEN" forever, and
                # the new row had all the SYNC placeholders (atr=0,
                # exec_grade="SYNC", choch/liquidity/mtf never populated at
                # all). deal.position_id is the correct field for mapping a
                # closing deal back to the position/order it closes.
                close_ticket = int(getattr(deal, "position_id", None) or deal.ticket)
                has_open_record = deal_exists(close_ticket)
                event = event_by_deal_ticket.get(int(deal.ticket), {
                    "is_final_close": True,
                })
                cumulative_profit = cumulative_profit_by_ticket.get(str(close_ticket), 0.0) + profit_value
                cumulative_profit_by_ticket[str(close_ticket)] = cumulative_profit

                # See open_price_by_position note above: falls back to
                # deal.price (old behavior) only when the true opening deal
                # isn't in the fetched history window.
                real_open_price = open_price_by_position.get(
                    getattr(deal, "position_id", None), deal.price
                )

                row = [
                    deal.ticket,
                    strategy,
                    deal.symbol,
                    trade_type,
                    deal.volume,
                    round(deal.profit, 2),
                    real_open_price,
                    deal.price,
                    close_dt.isoformat(),
                    close_dt.isoformat(),
                    deal.comment,
                    getattr(deal, "magic", 0),
                    identity["magic"],
                    BUILD_ID,
                ]
                new_rows.append(row)

                # DATA-INTEGRITY FIX: this used to always append a brand-new
                # HISTORY_FILE row keyed by deal.ticket (the closing deal's own
                # id, which never matches the open-time row — see the
                # close_ticket/position_id note above) and hardcoded
                # rr_ratio/quality_score/brain_score to 0 no matter what. That
                # meant (a) the open-time row was left at result="OPEN" forever
                # instead of ever being closed out, and (b) even the new close
                # row that did get written silently discarded the real
                # quality/score/RR captured at entry (in trade_executor.py's
                # persist_trade_log), breaking every downstream module that
                # tries to learn "which quality_score/rr_ratio actually
                # predicts a win" (adaptive_learning, outcome_learning,
                # contribution_analysis, history_learner, ...).
                #
                # Fix: key on close_ticket (== the original open-time ticket,
                # result.order) like the rest of this function already does,
                # and only overwrite result/profit on the existing open-time
                # row — every other field it already captured (quality_score,
                # rr_ratio, brain_score, session, market_regime, exec_grade,
                # strategy, lot) is left untouched. Only fall back to the SYNC
                # placeholders when there truly is no open-time row to update
                # (has_open_record is False — a manually-opened trade, or one
                # opened before this bot instance ran).
                ticket_str = str(close_ticket)
                if has_open_record:
                    upsert_csv_row(
                        HISTORY_FILE,
                        HISTORY_COLUMNS,
                        "ticket",
                        close_ticket,
                        {
                            "result": result if event["is_final_close"] else "PARTIAL",
                            "profit": round(cumulative_profit, 2),
                        },
                    )
                else:
                    upsert_csv_row(
                        HISTORY_FILE,
                        HISTORY_COLUMNS,
                        "ticket",
                        close_ticket,
                        {
                            "date": close_dt.isoformat(),
                            "ticket": close_ticket,
                            "signal": trade_type,
                            "lot": round(float(deal.volume or 0), 2),
                            "profit": round(cumulative_profit, 2),
                            "result": result if event["is_final_close"] else "PARTIAL",
                            "strategy": strategy,
                            "session": session,
                            "market_regime": market_regime,
                            "exec_grade": "SYNC",
                            "rr_ratio": 0,
                            "quality_score": 0,
                            "brain_score": 0,
                            "build_id": BUILD_ID,
                            "account_id": get_cached_account_id(),
                        },
                    )
                if ticket_str not in history_existing_tickets:
                    history_existing_tickets.add(ticket_str)
                    synced_history += 1

                _memory_kwargs = dict(
                    ticket=close_ticket,
                    strategy=strategy,
                    signal=trade_type,
                    result=result,
                    profit=round(float(deal.profit or 0), 2),
                    session=session,
                    magic=identity["magic"],
                    volume=round(float(deal.volume or 0), 2),
                    decision_reason="MT5_HISTORY_SYNC",
                    conflict_report=(
                        f"RAW_MAGIC={identity['raw_magic']}"
                        if identity["magic_mismatch"] else ""
                    ),
                )
                if not has_open_record:
                    # No open-time snapshot exists for this position (opened
                    # before this bot instance ran, or opened manually) —
                    # nothing to merge into, so fall back to the previous
                    # SYNC placeholders rather than leaving the row bare.
                    _memory_kwargs.update(
                        atr=0,
                        market_regime=market_regime,
                        hour=close_dt.hour,
                        spread=0,
                        quality_score=0,
                        confidence_score=0,
                        confidence_pct=0,
                        exec_grade="SYNC",
                        rr_ratio=0,
                    )
                save_trade_memory(**_memory_kwargs)
                synced_memory += 1

                record_trade_outcome(
                    strategy=strategy,
                    session=session,
                    regime=market_regime,
                    signal=trade_type,
                    composite_score=0,
                    size_mode="SYNC",
                    pnl=round(float(deal.profit or 0), 4),
                    win=result == "WIN",
                )
                # V3.5 PHASE-3.1 FIX: Truth Layer existed in analytics/truth_layer.py
                # but nothing ever called append_trade() with real data — its
                # trade_history.jsonl stayed empty. This feeds it the same
                # closed-deal data already used for register_win/loss above,
                # using the actual TradeRecord schema (the original plan's
                # `record_trade_outcome` import does not exist in this module).
                try:
                    append_trade(TradeRecord(
                        # DATA-INTEGRITY FIX: was `ticket=int(deal.ticket)` --
                        # deal.ticket is the closing DEAL's own id, not the
                        # POSITION ticket used everywhere else this trade is
                        # keyed (trades.csv via close_ticket above, ai_memory,
                        # portfolio_risk_authority). Because
                        # analytics/csv_truth_bridge.py::sync_csv_to_truth_layer()
                        # dedupes against truth_layer by comparing trades.csv's
                        # ticket column (= close_ticket) to this file's ticket
                        # values, the two numbering schemes never matched --
                        # confirmed empirically (zero ticket overlap between
                        # the two files for the same 20 real trades) -- so
                        # every real trade was getting silently duplicated
                        # into truth_layer the first time both sync paths ran
                        # in the same session.
                        ticket=close_ticket,
                        strategy=strategy,
                        direction=trade_type,
                        session=session,
                        regime=market_regime,
                        close_time=close_dt.isoformat(),
                        entry_price=float(real_open_price or 0),
                        exit_price=float(deal.price or 0),
                        lot=round(float(deal.volume or 0), 2),
                        profit=round(float(deal.profit or 0), 2),
                        is_win=(result == "WIN"),
                        build_id=BUILD_ID,
                        extra={"source": "mt5_history_sync", "deal_ticket": int(deal.ticket)},
                    ))
                except Exception as error:
                    print(f"⚠️ truth_layer.append_trade failed for ticket={deal.ticket}: {error}")

                if result == "WIN":
                    register_win(round(float(deal.profit or 0), 4))
                elif result == "LOSS":
                    register_loss(round(float(deal.profit or 0), 4))
                synced_adaptive += 1

                # V3.5 PHASE-1 FIX (CORRECTED): record_trade_close() existed
                # in portfolio_risk_authority.py but was never called
                # anywhere, so its in-memory open_trades list never shrank
                # even on a close.
                #
                # BUG FOUND AND FIXED: the first version of this wiring used
                # deal.ticket here, but record_trade_open() in main.py stores
                # the ticket as int(result.order) — the ORDER ticket from
                # mt5.order_send(). deal.ticket is a SEPARATE identifier for
                # the deal record itself and does not equal the order ticket.
                # The field that actually maps a closing deal back to the
                # position/order it closes is deal.position_id. Using
                # deal.ticket meant record_trade_close() could never find a
                # match in open_trades, so closed trades were never removed
                # — open_trades grew without bound and falsely blocked every
                # subsequent trade with PER_STRATEGY_MAX_OPEN_HIT forever,
                # even with zero real open positions on the account.
                try:
                    position_id = getattr(deal, "position_id", None)
                    close_volume = float(getattr(deal, "volume", 0.0) or 0.0)
                    closed_volume_by_position[position_id] = (
                        closed_volume_by_position.get(position_id, 0.0)
                        + close_volume
                    )
                    opened_volume = open_volume_by_position.get(position_id, 0.0)
                    is_partial = (
                        opened_volume > 0.0
                        and closed_volume_by_position[position_id] < opened_volume - 1e-9
                    )
                    if is_partial:
                        record_trade_partial_close(
                            ticket=close_ticket,
                            volume_closed=close_volume,
                            profit=round(float(deal.profit or 0), 4),
                        )
                    else:
                        record_trade_close(ticket=close_ticket, profit=round(float(deal.profit or 0), 4))
                except Exception as error:
                    print(f"⚠️ record_trade_close failed for ticket={deal.ticket}: {error}")

            except Exception as error:
                print(f"❌ DEAL ERROR: {error}")

        if len(new_rows) > 0:
            with open(
                FILE_NAME,
                mode="a",
                newline="",
                encoding="utf-8",
            ) as file:
                writer = csv.writer(file)
                writer.writerows(new_rows)

            print(f"✅ MT5 SYNCED {len(new_rows)} NEW DEALS")
        else:
            print("ℹ️ NO NEW MT5 DEALS")

        certification = update_certification_progress()
        return {
            "synced": len(new_rows),
            "history_rows": synced_history,
            "memory_rows": synced_memory,
            "adaptive_rows": synced_adaptive,
            "close_events": close_events,
            "certification_closed_trades": certification.get("closed_trade_count", 0),
        }

    except Exception as error:
        print(f"❌ MT5 SYNC ERROR: {error}")
        return {"synced": 0, "history_rows": 0, "memory_rows": 0,
            "adaptive_rows": 0, "close_events": [], "error": str(error)}


def _session_from_hour(hour):
    try:
        hour = int(hour)
    except Exception:
        return "UNKNOWN"
    if 0 <= hour < 8:
        return "ASIA"
    if 8 <= hour < 13:
        return "LONDON"
    if 13 <= hour < 18:
        return "NEWYORK"
    return "OFF_HOURS"
