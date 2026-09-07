"""Shadow-only evaluation of secondary strategy signal engines."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _log(record: Dict[str, Any]) -> None:
    try:
        from core.settings import SECONDARY_SHADOW_LOG_PATH
        path = Path(SECONDARY_SHADOW_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": "secondary_strategy_shadow",
            "live_execution": False,
            **record,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except Exception:
        return


def evaluate_secondary_shadow(
    *,
    symbol: str,
    rates: Any,
    session: str,
    market_regime: str,
    confidence_pct: float = 50.0,
) -> Dict[str, Dict[str, Any]]:
    """Evaluate secondary signals without entering risk or execution paths."""
    results: Dict[str, Dict[str, Any]] = {}
    if rates is None or len(rates) < 20:
        return {name: {"signal": "NONE", "reason": "INSUFFICIENT_RATES"}
                for name in ("SCALP", "SWING", "MICRO")}

    try:
        from core.scalping_engine import get_scalping_signal
        results["SCALP"] = {"signal": str(get_scalping_signal(symbol) or "NONE")}
    except Exception as exc:
        results["SCALP"] = {"signal": "ERROR", "reason": type(exc).__name__}

    try:
        from core.swing_engine import get_swing_signal
        results["SWING"] = {"signal": str(get_swing_signal(symbol) or "NONE")}
    except Exception as exc:
        results["SWING"] = {"signal": "ERROR", "reason": type(exc).__name__}

    try:
        from core.micro_trading_engine import should_enter_micro
        rows = [
            {"open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"]}
            for r in rates
        ]
        approved, result = should_enter_micro(rows, context={"confidence": confidence_pct})
        results["MICRO"] = {
            "signal": result.get("direction", "NONE"),
            "approved": bool(approved),
            "score": result.get("score", 0),
            "reasons": result.get("reasons", []),
        }
    except Exception as exc:
        results["MICRO"] = {"signal": "ERROR", "reason": type(exc).__name__}

    for strategy, result in results.items():
        _log({
            "strategy": strategy,
            "session": session,
            "market_regime": market_regime,
            **result,
        })
    return results