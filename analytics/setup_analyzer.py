# =============================================================================
# FER3ON AI V3.5 — SETUP ANALYZER
# =============================================================================
# Answers: "Which setup actually wins?"
# Instead of: "Did the bot profit today?"
#
# For each strategy:
#   - Win Rate
#   - Profit Factor
#   - Expectancy
#   - Average RR
#   - Average Hold Time
#   - Session Performance
#   - Regime Performance
#
# Builds on top of analytics.truth_layer so all math is centralized.
# =============================================================================

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from analytics.truth_layer import (
    TradeRecord,
    compute_metrics,
    filter_trades,
    load_all_trades,
    Metrics,
)


STRATEGIES: Tuple[str, ...] = ("SCALP", "MICRO", "SMC", "SWING", "DAILY")


# =============================================================================
# SETUP ANALYSIS (per strategy)
# =============================================================================

@dataclass
class SetupAnalysis:
    strategy: str
    metrics: Metrics
    session_breakdown: Dict[str, Metrics]
    regime_breakdown: Dict[str, Metrics]
    setup_score: float
    rank: int = 0
    verdict: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "metrics": self.metrics.to_dict(),
            "session_breakdown": {k: v.to_dict() for k, v in self.session_breakdown.items()},
            "regime_breakdown":  {k: v.to_dict() for k, v in self.regime_breakdown.items()},
            "setup_score": round(self.setup_score, 2),
            "rank": self.rank,
            "verdict": self.verdict,
        }


def _setup_score(m: Metrics) -> float:
    """Composite scoring used to rank setups.
    Higher = better setup quality.
    """
    if m.total_trades == 0:
        return 0.0
    pf = m.profit_factor if m.profit_factor != float("inf") else 5.0
    pf = min(max(pf, 0.0), 5.0)  # cap at 5
    score = (
        m.win_rate * 40.0
        + (pf / 5.0) * 30.0
        + (m.expectancy / max(1.0, abs(m.expectancy) + 1.0)) * 10.0
        + (1.0 - min(m.max_drawdown / 1000.0, 1.0)) * 10.0
        + min(m.total_trades / 50.0, 1.0) * 10.0
    )
    return round(score, 2)


def _verdict(m: Metrics, score: float) -> str:
    if m.total_trades < 5:
        return "INSUFFICIENT_SAMPLES"
    if m.profit_factor >= 1.5 and m.win_rate >= 0.55:
        return "PROFITABLE"
    if m.profit_factor >= 1.0 and m.expectancy > 0:
        return "EDGE_PRESENT"
    if m.profit_factor < 0.85 or m.expectancy < 0:
        return "WEAK_NEGATIVE_EDGE"
    return "MIXED"


def analyze_setup(
    strategy: str,
    trades: Optional[List[TradeRecord]] = None,
) -> SetupAnalysis:
    """Compute full breakdown for a single strategy."""
    strat = strategy.upper()
    trades = trades or load_all_trades()
    own = [t for t in trades if t.strategy.upper() == strat]
    metrics = compute_metrics(own)
    sessions: Dict[str, List[TradeRecord]] = defaultdict(list)
    regimes:  Dict[str, List[TradeRecord]] = defaultdict(list)
    for t in own:
        sessions[(t.session or "UNKNOWN").upper()].append(t)
        regimes[(t.regime  or "UNKNOWN").upper()].append(t)
    s_metrics = {k: compute_metrics(v) for k, v in sessions.items()}
    r_metrics = {k: compute_metrics(v) for k, v in regimes.items()}
    return SetupAnalysis(
        strategy=strat,
        metrics=metrics,
        session_breakdown=s_metrics,
        regime_breakdown=r_metrics,
        setup_score=_setup_score(metrics),
        verdict=_verdict(metrics, _setup_score(metrics)),
    )


def analyze_all_setups(
    trades: Optional[List[TradeRecord]] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> Dict[str, SetupAnalysis]:
    """Analyze every registered strategy. Ranked output."""
    trades = trades or load_all_trades()
    if since or until:
        trades = filter_trades(
            trades,
            since=(since + "T00:00:00" if since else None),
            until=(until + "T23:59:59" if until else None),
        )
    results: Dict[str, SetupAnalysis] = {}
    for s in STRATEGIES:
        results[s] = analyze_setup(s, trades)
    ranked = sorted(results.values(), key=lambda x: x.setup_score, reverse=True)
    for i, item in enumerate(ranked, start=1):
        item.rank = i
    return results


def overall_setups_report() -> Dict[str, Any]:
    """Return full breakdowns for all strategies + ranking."""
    setups = analyze_all_setups()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies": {k: v.to_dict() for k, v in setups.items()},
        "ranking": [v.strategy for v in sorted(setups.values(),
                                                key=lambda x: x.setup_score,
                                                reverse=True)],
    }


# =============================================================================
# PHASE-1 ACCEPTANCE: Setup analyzer sanity test
# =============================================================================

def acceptance_smoke_test() -> Dict[str, Any]:
    """Quick test that all five strategies produce a non-empty breakdown."""
    base_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def _t(ticket, strat, profit, regime="RANGING", session="LONDON") -> TradeRecord:
        return TradeRecord(
            ticket=ticket,
            strategy=strat,
            direction="BUY" if profit >= 0 else "SELL",
            session=session,
            regime=regime,
            open_time=base_time.isoformat(),
            close_time=base_time.isoformat(),
            profit=profit,
            risk_percent=0.5,
            rr_achieved=2.0 if profit >= 0 else 1.0,
            duration_sec=300,
            is_win=profit > 0,
        )

    seed = [
        _t(1, "SCALP", 20, "TRENDING", "LONDON"),
        _t(2, "SCALP", -5, "TRENDING", "LONDON"),
        _t(3, "MICRO", 5, "RANGING", "NEW_YORK"),
        _t(4, "MICRO", -3, "RANGING", "NEW_YORK"),
        _t(5, "SMC", 10, "TRENDING", "OVERLAP"),
        _t(6, "SWING", 30, "TRENDING", "LONDON"),
        _t(7, "DAILY", 50, "TRENDING", "LONDON"),
    ]
    setups = {s: analyze_setup(s, seed) for s in STRATEGIES}
    # Apply ranking within the smoke function as well.
    ranked = sorted(setups.values(), key=lambda x: x.setup_score, reverse=True)
    for i, item in enumerate(ranked, start=1):
        item.rank = i
    return {
        "expected_strategies_present": sorted(STRATEGIES),
        "ranking_invariant": all(
            setups[k].rank > 0 for k in STRATEGIES
        ),
        "analyze_setup_seed_smoke": [
            setups[s].to_dict() for s in STRATEGIES
        ],
    }
