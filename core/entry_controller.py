# =============================================================================
# FER3ON — PHASE 2 | ENTRY CONTROLLER + STRUCTURAL SL (Demo)
# =============================================================================
# Replaces "enter at market the instant a signal fires" with:
#   1. A pullback LIMIT entry plan (retracement of PULLBACK_DEPTH_ATR × ATR),
#      valid for ENTRY_TTL_BARS bars, then expired.
#   2. A STRUCTURE-anchored SL: beyond the opposing swing ± ATR buffer,
#      hard-capped at STRUCTURAL_SL_CAP_SCALP ($10) for SCALP/MICRO and
#      STRUCTURAL_SL_CAP_SWING ($15) for SMC/SWING.
#
# MODE: advisory by default (PHASE2_ENTRY_CONTROLLER_LIVE_ENABLED = False):
# plans are computed + logged, live orders untouched. Flipping the live flag
# on Demo makes these the values handed to the finalizer.
#
# SAFETY CONTRACT (same as analytics/shadow_counterfactual.py):
#   - Never raises. Never imports execution code (no MT5 / trade_executor).
#   - Nothing here is read back into a live decision unless the LIVE flag
#     is on AND the caller explicitly consumes the returned plan.
# =============================================================================
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Config access (defensive)
# ---------------------------------------------------------------------------

def _cfg(name: str, default: Any) -> Any:
    try:
        import core.settings as _s
        return getattr(_s, name, default)
    except Exception:
        return default


def _enabled() -> bool:
    return bool(_cfg("PHASE2_ENTRY_CONTROLLER_ENABLED", True))


def _live() -> bool:
    return bool(_cfg("PHASE2_ENTRY_CONTROLLER_LIVE_ENABLED", False))


def _log_path() -> str:
    return str(_cfg("PHASE2_ENTRY_CONTROLLER_LOG_PATH",
                    "data/analytics/entry_controller/entry_plans.jsonl"))


def _quarantine_path() -> str:
    return str(_cfg("PHASE2_ENTRY_CONTROLLER_QUARANTINE_PATH",
                    "data/analytics/quarantine/entry_plans_invalid.jsonl"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Structural SL
# ---------------------------------------------------------------------------

def _swing_level(structure_analysis: Optional[Dict[str, Any]], direction: str) -> Optional[float]:
    """Protective level: most recent swing LOW for BUY, swing HIGH for SELL.
    Tolerates the multiple key spellings used across the codebase."""
    try:
        sa = structure_analysis or {}
        seq_key = "swing_lows" if direction == "BUY" else "swing_highs"
        alt_key = "lows" if direction == "BUY" else "highs"
        seq = sa.get(seq_key) or sa.get(alt_key) or []
        if seq:
            lvl = seq[-1]
            v = lvl.get("price") if isinstance(lvl, dict) else lvl
            return float(v) if v is not None else None
        single_key = "last_swing_low" if direction == "BUY" else "last_swing_high"
        v = sa.get(single_key)
        return float(v) if v is not None else None
    except Exception:
        return None


def compute_structural_sl_dist(
    direction: Optional[str],
    entry_price: Optional[float],
    atr: Optional[float],
    structure_analysis: Optional[Dict[str, Any]] = None,
    strategy: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """SL distance anchored beyond the opposing swing, hard-capped.
    Returns a dict or None. NEVER raises."""
    try:
        d = str(direction or "").upper()
        entry = float(entry_price or 0)
        atr_v = max(0.0, float(atr or 0))
        if entry <= 0 or d not in ("BUY", "SELL"):
            return None

        strat = str(strategy or "").upper()
        cap = float(_cfg("STRUCTURAL_SL_CAP_SCALP", 10.0)) if strat in ("SCALP", "MICRO") \
            else float(_cfg("STRUCTURAL_SL_CAP_SWING", 15.0))
        buf = float(_cfg("STRUCTURAL_SL_ATR_BUFFER", 0.3)) * atr_v

        lvl = _swing_level(structure_analysis, d)
        if lvl is None:
            if atr_v <= 0:
                return None
            dist = 1.5 * atr_v
            return {"sl_dist": round(min(dist, cap), 2), "source": "atr_fallback",
                    "cap": cap, "capped": dist > cap}

        sl_price = (lvl - buf) if d == "BUY" else (lvl + buf)
        dist = (entry - sl_price) if d == "BUY" else (sl_price - entry)
        if dist <= 0:
            return {"sl_dist": None, "source": "structure_invalid", "cap": cap,
                    "reason": "swing_level_on_wrong_side_of_entry"}

        return {"sl_dist": round(min(dist, cap), 2), "source": "structure",
                "cap": cap, "uncapped_dist": round(dist, 2), "capped": dist > cap,
                "swing_level": round(lvl, 5), "buffer": round(buf, 5)}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Entry plan
# ---------------------------------------------------------------------------

def plan_entry(
    *,
    signal_id: Optional[str] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    signal_price: Optional[float] = None,
    atr: Optional[float] = None,
    structure_analysis: Optional[Dict[str, Any]] = None,
    strategy: Optional[str] = None,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the entry plan. Advisory unless LIVE flag is on. NEVER raises."""
    plan: Dict[str, Any] = {
        "record_type": "ENTRY_PLAN",
        "signal_id": signal_id,
        "symbol": symbol,
        "direction": str(direction or "").upper() or None,
        "signal_time": _utc_now_iso(),
        "live": _live(),
        "entry_mode": "SKIP",
        "status": "INVALID",
    }
    try:
        d = plan["direction"]
        price = float(signal_price or 0)
        atr_v = max(0.0, float(atr or 0))
        if d not in ("BUY", "SELL") or price <= 0:
            return plan

        depth = float(_cfg("PULLBACK_DEPTH_ATR", 0.5)) * atr_v
        if atr_v > 0 and depth > 0:
            limit_price = (price - depth) if d == "BUY" else (price + depth)
            plan.update(entry_mode="LIMIT_PULLBACK",
                        limit_price=round(limit_price, 5),
                        pullback_depth=round(depth, 5),
                        ttl_bars=int(_cfg("ENTRY_TTL_BARS", 6)))
        else:
            plan.update(entry_mode="MARKET", limit_price=round(price, 5),
                        pullback_depth=0.0, ttl_bars=0)

        planned_entry = float(plan["limit_price"])
        sl = compute_structural_sl_dist(
            d, price, atr_v, structure_analysis, strategy
        )
        if sl and sl.get("sl_dist"):
            plan["structural_sl"] = sl
            sl_distance = float(sl["sl_dist"])
            if d == "BUY":
                plan["cancel_level"] = round(price - sl_distance, 5)
            else:
                plan["cancel_level"] = round(price + sl_distance, 5)
            rr = float(_cfg("TP_LADDER_RR", (1.5,))[0])
            tp_distance = sl_distance * rr
            plan["expected_sl"] = round(plan["cancel_level"], 5)
            plan["expected_tp"] = round(
                planned_entry + tp_distance if d == "BUY"
                else planned_entry - tp_distance,
                5,
            )
        else:
            plan["structural_sl"] = sl or {"sl_dist": None, "source": "unavailable"}
            plan["cancel_level"] = None
            plan["expected_sl"] = None
            plan["expected_tp"] = None

        plan["confidence"] = confidence
        plan["strategy"] = strategy
        plan["opportunity_mode"] = "PREPARE_THEN_CONFIRM"
        plan["confirmation_conditions"] = {
            "direction": d,
            "minimum_confidence": 0.60,
            "structure_valid": bool(
                plan["structural_sl"].get("source") == "structure"
            ),
            "entry_touched": plan["entry_mode"] == "MARKET",
            "cancel_if_price_crosses": plan["cancel_level"],
            "cancel_after_bars": int(plan.get("ttl_bars") or 0),
        }
        plan["status"] = "PENDING" if plan["entry_mode"] == "LIMIT_PULLBACK" else "READY"
        return plan
    except Exception:
        plan["status"] = "ERROR"
        return plan


def scan_opportunity_zones(
    *,
    symbol: Optional[str] = None,
    rates: Optional[List[Dict[str, Any]]] = None,
    atr: Optional[float] = None,
    structure_analysis: Optional[Dict[str, Any]] = None,
    strategy: Optional[str] = None,
    max_candidates: int = 2,
) -> List[Dict[str, Any]]:
    """Prepare candidate zones before a final entry signal is consumed.

    This is advisory only: it creates plans and never places or modifies an
    order. Candidates require a recent structural level and valid OHLC data.
    """
    try:
        candles = list(rates or [])
        if not candles or not structure_analysis:
            return []
        current_price = float(candles[-1].get("close") or 0)
        if current_price <= 0 or float(atr or 0) <= 0:
            return []
        analysis = structure_analysis
        directions = []
        bias = str(analysis.get("structure_bias") or "").upper()
        if bias in {"BUY", "SELL"}:
            directions.append(bias)
        else:
            directions.extend(("BUY", "SELL"))
        plans: List[Dict[str, Any]] = []
        for direction in directions[:max(1, int(max_candidates))]:
            level_key = "swing_lows" if direction == "BUY" else "swing_highs"
            if not (analysis.get(level_key) or analysis.get(
                "lows" if direction == "BUY" else "highs"
            )):
                continue
            plan = plan_entry(
                signal_id=f"zone-{_utc_now_iso()}",
                symbol=symbol,
                direction=direction,
                signal_price=current_price,
                atr=atr,
                structure_analysis=analysis,
                strategy=strategy,
            )
            plan["record_type"] = "OPPORTUNITY_ZONE"
            plan["opportunity_source"] = "PROACTIVE_STRUCTURE_SCAN"
            plans.append(plan)
        return plans
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Ledger: log plans, resolve LIMIT fill/expiry against real candles
# ---------------------------------------------------------------------------

def log_entry_plan(plan: Optional[Dict[str, Any]], *, log_path: Optional[str] = None) -> bool:
    try:
        if not _enabled():
            return False
        rec = dict(plan or {})
        from core.data_quality import quarantine, stamp
        if str(rec.get("direction") or "").upper() not in {"BUY", "SELL"} or float(rec.get("limit_price") or 0) <= 0:
            quarantine(rec, "INVALID_ENTRY_PLAN", _quarantine_path())
            return False
        stamp(rec)
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


def _candle_time(c: Dict[str, Any]) -> str:
    return str(c.get("time") or c.get("timestamp") or "")


def resolve_entry_plans(candles: Optional[List[Dict[str, Any]]], *,
                        log_path: Optional[str] = None) -> Dict[str, Any]:
    """Resolve PENDING LIMIT_PULLBACK plans: FILLED if price touched the
    limit level within ttl_bars of signal_time, else EXPIRED. NEVER raises."""
    try:
        path = log_path or _log_path()
        if not candles or not os.path.exists(path):
            return {"ok": False, "resolved": 0, "reason": "no candles or no ledger"}

        with open(path, "r", encoding="utf-8") as fh:
            records = [json.loads(l) for l in fh if l.strip()]

        resolved = 0
        for rec in records:
            if rec.get("status") != "PENDING" or rec.get("entry_mode") != "LIMIT_PULLBACK":
                continue
            try:
                d = str(rec.get("direction") or "").upper()
                limit = float(rec.get("limit_price") or 0)
                ttl = max(1, int(rec.get("ttl_bars") or 1))
                sig_t = str(rec.get("signal_time") or "")
                if limit <= 0 or not sig_t:
                    continue
                start = None
                for i, c in enumerate(candles):
                    if _candle_time(c) and _candle_time(c) > sig_t:
                        start = i
                        break
                if start is None:
                    continue  # still waiting for post-signal candles
                touched = False
                for j in range(start, min(start + ttl, len(candles))):
                    c = candles[j]
                    if d == "BUY" and float(c.get("low")) <= limit:
                        touched = True
                        break
                    if d == "SELL" and float(c.get("high")) >= limit:
                        touched = True
                        break
                if touched:
                    rec["status"] = "FILLED"
                    rec["filled_bar"] = j - start + 1
                    resolved += 1
                elif len(candles) - start >= ttl:
                    rec["status"] = "EXPIRED"
                    resolved += 1
            except Exception:
                continue

        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        return {"ok": True, "resolved": resolved, "total": len(records)}
    except Exception:
        return {"ok": False, "resolved": 0, "reason": "exception"}


def summary(*, log_path: Optional[str] = None) -> Dict[str, Any]:
    """Fill-rate stats: how often pullback entries actually fill. NEVER raises."""
    try:
        path = log_path or _log_path()
        out: Dict[str, Any] = {"ok": True, "total": 0, "PENDING": 0, "FILLED": 0,
                               "EXPIRED": 0, "READY": 0, "fill_rate": None}
        if not os.path.exists(path):
            return out
        with open(path, "r", encoding="utf-8") as fh:
            records = [json.loads(l) for l in fh if l.strip()]
        out["total"] = len(records)
        for rec in records:
            st = rec.get("status")
            if st in out:
                out[st] += 1
        decided = out["FILLED"] + out["EXPIRED"]
        if decided > 0:
            out["fill_rate"] = round(out["FILLED"] / decided, 4)
        return out
    except Exception:
        return {"ok": False}


def get_entry_plans_summary(*, log_path: Optional[str] = None) -> Dict[str, Any]:
    """Backward-compatible name used by the main heartbeat resolver."""
    return summary(log_path=log_path)
