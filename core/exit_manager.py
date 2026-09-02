# =============================================================================
# FER3ON — PHASE 3 | EXIT MANAGER (Demo)
# =============================================================================
# Four independent exit mechanisms, computed from position state + candles:
#   1. INDEPENDENT TP LADDER — TP levels from their own RR ladder
#      (TP_LADDER_RR × SL distance), NOT re-derived from how SL was built.
#   2. PARTIAL EXITS — close TP_LADDER_FRACTIONS of the position per level.
#   3. TRAILING — after TP1: SL → breakeven + BREAKEVEN_BUFFER_ATR × ATR.
#      After TP2: trail at TRAILING_ATR_MULT × ATR behind price.
#   4. TIME EXIT — if neither TP1 nor SL within TIME_EXIT_BARS bars → close.
#
# Advisory by default (PHASE3_EXIT_MANAGER_LIVE_ENABLED = False): actions are
# computed + logged, real positions untouched.
#
# SAFETY CONTRACT: never raises; imports no execution code (no MT5 /
# trade_executor); callers pass plain dicts, get plain dicts back.
# =============================================================================
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _cfg(name: str, default: Any) -> Any:
    try:
        import core.settings as _s
        return getattr(_s, name, default)
    except Exception:
        return default


def _enabled() -> bool:
    return bool(_cfg("PHASE3_EXIT_MANAGER_ENABLED", True))


def _live() -> bool:
    return bool(_cfg("PHASE3_EXIT_MANAGER_LIVE_ENABLED", False))


def _log_path() -> str:
    return str(_cfg("PHASE3_EXIT_MANAGER_LOG_PATH",
                    "data/analytics/exit_manager/exit_actions.jsonl"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 1+2. Independent TP ladder with partial-close fractions
# ---------------------------------------------------------------------------

def compute_tp_ladder(
    direction: Optional[str],
    entry_price: Optional[float],
    sl_dist: Optional[float],
    strategy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Independent TP levels: entry ± rr × sl_dist, each with its partial
    close fraction. NEVER raises; returns [] on bad input."""
    try:
        from execution.multi_tp import compute_tp_prices

        result = compute_tp_prices(
            entry_price=float(entry_price or 0),
            sl_distance=float(sl_dist or 0),
            direction=str(direction or "").upper(),
            strategy=str(strategy or "SMC").upper(),
        )
        if not result.get("enabled"):
            return []
        return [
            {
                "tier": index + 1,
                "rr": float(level.get("rr", 0) or 0),
                "fraction": float(level.get("close_pct", 0) or 0),
                "price": float(level.get("price", 0) or 0),
                "dist": round(abs(float(level["price"]) - float(entry_price)), 2),
            }
            for index, level in enumerate(result.get("levels", []))
        ]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 3+4. Position-state evaluation: breakeven / trailing / time exit
# ---------------------------------------------------------------------------

def _candle_time(c: Dict[str, Any]) -> str:
    return str(c.get("time") or c.get("timestamp") or "")


def evaluate_exit(
    position: Optional[Dict[str, Any]],
    candles: Optional[List[Dict[str, Any]]],
    atr: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate one open position against candles (ascending, with
    time/high/low). `position` keys: direction, entry_price, sl_dist,
    open_time (ISO). Returns an action dict:

        action: NONE | PARTIAL_CLOSE | MOVE_SL_BREAKEVEN | TRAIL |
                TIME_EXIT | CLOSE_ALL | SL_HIT
        plus context fields (tier, new_sl_dist, trail_dist, bars_open...)

    NEVER raises; imports nothing executable.
    """
    out: Dict[str, Any] = {"action": "NONE", "live": _live()}
    try:
        pos = position or {}
        d = str(pos.get("direction") or "").upper()
        entry = float(pos.get("entry_price") or 0)
        sl = float(pos.get("sl_dist") or 0)
        open_t = str(pos.get("open_time") or "")
        if d not in ("BUY", "SELL") or entry <= 0 or sl <= 0:
            out["action"] = "INVALID"
            return out

        ladder = compute_tp_ladder(d, entry, sl, pos.get("strategy"))
        if not ladder:
            out["action"] = "INVALID"
            return out
        tp1, tp2, tp_last = ladder[0], (ladder[1] if len(ladder) > 1 else None), ladder[-1]
        loss_level = (entry - sl) if d == "BUY" else (entry + sl)
        atr_v = max(0.0, float(atr or 0))
        time_exit_bars = int(_cfg("TIME_EXIT_BARS", 24))

        bars = candles or []
        start = 0
        if open_t:
            start = next((i for i, c in enumerate(bars) if _candle_time(c) and _candle_time(c) > open_t),
                         len(bars))
        post = bars[start:]
        out["bars_open"] = len(post)

        highest = entry
        lowest = entry
        for c in post:
            high = float(c.get("high"))
            low = float(c.get("low"))
            highest, lowest = max(highest, high), min(lowest, low)

            # SL first — conservative ordering
            sl_hit = (low <= loss_level) if d == "BUY" else (high >= loss_level)
            if sl_hit:
                out.update(action="SL_HIT", level=round(loss_level, 5))
                return out

            def _touched(level_price: float) -> bool:
                return (high >= level_price) if d == "BUY" else (low <= level_price)

            if _touched(tp_last["price"]):
                out.update(action="CLOSE_ALL", tier=tp_last["tier"], price=tp_last["price"])
                return out
            if tp2 and _touched(tp2["price"]):
                trail = round(float(_cfg("TRAILING_ATR_MULT", 1.0)) * atr_v, 2) if atr_v > 0 else None
                out.update(action="TRAIL", tier=tp2["tier"], fraction=tp2["fraction"],
                           trail_dist=trail, price=tp2["price"])
                return out
            if _touched(tp1["price"]):
                buf = round(float(_cfg("BREAKEVEN_BUFFER_ATR", 0.1)) * atr_v, 2) if atr_v > 0 else 0.0
                out.update(action="MOVE_SL_BREAKEVEN", tier=tp1["tier"],
                           fraction=tp1["fraction"], breakeven_buffer=buf,
                           price=tp1["price"])
                return out

        # Time exit: stale trade, no TP1 and no SL within the window
        if len(post) >= time_exit_bars:
            out.update(action="TIME_EXIT", bars_open=len(post),
                       limit=time_exit_bars)
            return out

        return out
    except Exception:
        return {"action": "ERROR", "live": _live()}


# ---------------------------------------------------------------------------
# Ledger (advisory logging)
# ---------------------------------------------------------------------------

def log_exit_action(record: Optional[Dict[str, Any]], *, log_path: Optional[str] = None) -> bool:
    try:
        if not _enabled():
            return False
        rec = dict(record or {})
        rec.setdefault("record_type", "EXIT_ACTION")
        rec.setdefault("logged_at", _utc_now_iso())
        path = log_path or _log_path()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        return True
    except Exception:
        return False
