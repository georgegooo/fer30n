"""Compatibility-preserving dispatcher for secondary strategy runners."""

from __future__ import annotations

from typing import Callable, Dict


def dispatch_secondary_strategies(
    snapshot: dict,
    *,
    allow_execution: bool,
    runners: Dict[str, Callable],
    enabled_strategies: Dict[str, bool] | None = None,
) -> dict:
    session = str(snapshot.get("session", "UNKNOWN") or "UNKNOWN")
    regime = str(snapshot.get("market_regime", "UNKNOWN") or "UNKNOWN")
    confidence = snapshot.get("confidence") or {}
    confidence_pct = float(confidence.get("pct", 50) or 50) if isinstance(confidence, dict) else float(confidence or 50)

    enabled = {
        name: bool((enabled_strategies or {}).get(name, allow_execution))
        for name in ("SCALP", "SWING", "MICRO")
    }

    results = {}
    for strategy_name in ("SCALP", "SWING", "MICRO"):
        if not enabled[strategy_name]:
            results[strategy_name] = {
                "opened": False,
                "reason": "STRATEGY_LIVE_DISABLED" if allow_execution else "CANONICAL_AUTHORITY_BLOCK",
            }
            continue
        runner = runners[strategy_name]
        try:
            results[strategy_name] = runner(
                session=session,
                market_regime=regime,
                confidence_pct=confidence_pct,
            )
        except TypeError:
            results[strategy_name] = runner(session=session, market_regime=regime)
        except Exception as exc:
            results[strategy_name] = {"opened": False, "reason": f"RUNNER_ERROR:{exc}"}
    return results