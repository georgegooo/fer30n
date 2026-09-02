# FER3ON V3+++ — Phase 2 Performance Intelligence
Generated: 2026-09-02 06:57 UTC  |  Trades analysed: 149

> advisory_only=True  not_applied_live=True

## Overall Portfolio
| Metric | Value |
|--------|-------|
| Total Trades | 149 |
| Win Rate | 49.0% |
| Profit Factor | 0.83 |
| Expectancy | -2.50 |
| Net PnL | -372.52 |
| Max Drawdown | 665.09 |
| Best Trade | +301.10 |
| Worst Trade | -94.80 |
| Max Consec. Losses | 7 |

## Session Edge Ranking
| Rank | Session | Trades | WR | PF | Expectancy | Status |
|------|---------|--------|----|----|-----------|--------|
| #1 | OFF_HOURS | 18 | 61.1% | 2.09 | +6.84 | EDGE_CONFIRMED |
| #2 | NEWYORK | 42 | 40.5% | 1.16 | +2.88 | EDGE_CONFIRMED |
| #3 | ASIA | 37 | 45.9% | 0.50 | -6.37 | EDGE_CONFIRMED |
| #4 | LONDON | 51 | 52.9% | 0.58 | -7.53 | EDGE_CONFIRMED |
| - | NEW_YORK | 1 | 100.0% | ∞ | +3.00 | INSUFFICIENT_SAMPLE |
| - | OVERLAP | 0 | 0.0% | ∞ | +0.00 | NO_TRADES |

## Regime Edge Ranking
| Rank | Regime | Trades | WR | PF | Expectancy | Type | Status |
|------|--------|--------|----|----|-----------|------|--------|
| #1 | UNKNOWN | 59 | 59.3% | 1.61 | +8.05 | live | EDGE_CONFIRMED |
| #2 | TRENDING | 51 | 41.2% | 0.46 | -8.24 | live | EDGE_CONFIRMED |
| #3 | RANGING | 39 | 43.6% | 0.38 | -10.95 | live | EDGE_CONFIRMED |
| #4 | LOW_VOLATILITY_ANALYTIC | 39 | 43.6% | 0.38 | -10.95 | analytic | EDGE_CONFIRMED |
| - | VOLATILE | 0 | 0.0% | ∞ | +0.00 | live | NO_TRADES |
| - | CRISIS | 0 | 0.0% | ∞ | +0.00 | live | NO_TRADES |

## Module Contribution Analysis
Coverage: Only 0% of Truth Layer trades matched to decision snapshots. Contribution analysis may be limited. To improve coverage, ensure decision snapshots are enriched with module signals at trade open (see core/decision_snapshot.py).

| Module | N(with) | WR(with) | WR(delta) | Exp(delta) | Verdict |
|--------|---------|----------|-----------|------------|---------|
| SMC | 0 | 0.0% | +0.0% | +0.00 | INSUFFICIENT [INSUFFICIENT_SAMPLE] |
| Liquidity | 0 | 0.0% | +0.0% | +0.00 | INSUFFICIENT [INSUFFICIENT_SAMPLE] |
| Structure | 0 | 0.0% | +0.0% | +0.00 | INSUFFICIENT [INSUFFICIENT_SAMPLE] |
| News | 0 | 0.0% | +0.0% | +0.00 | INSUFFICIENT [INSUFFICIENT_SAMPLE] |
| MTF | 0 | 0.0% | +0.0% | +0.00 | INSUFFICIENT [INSUFFICIENT_SAMPLE] |

## Exposure Diagnostics

✅ No concentration issues detected.

## Adaptive Shadow Calibration Readiness
shadow_only=True  activated=False

| Bucket | Key | Suggestion | Confidence |
|--------|-----|------------|------------|
| strategy | MANUAL | HOLD | ? LOW |
| strategy | MICRO | TIGHTEN | ? LOW |
| strategy | SCALP | TIGHTEN | ? LOW |
| strategy | SMC | TIGHTEN | ? LOW |
| session | ASIA | TIGHTEN | ? LOW |
| session | LONDON | TIGHTEN | ? LOW |
| session | NEWYORK | HOLD | ? LOW |
| session | NEW_YORK | HOLD | ? LOW |
| session | OFF_HOURS | MONITOR | ? LOW |
| regime | RANGING | TIGHTEN | ? LOW |
| regime | TRENDING | TIGHTEN | ? LOW |
| regime | UNKNOWN | RELAX | ? LOW |