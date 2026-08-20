# Counter Trend Status

## Normalized rule set

- Counter trend is allowed only on explicit bias conflict.
- SMC score requirement: **>= 60** (implemented as >= 6.0 on the existing 0-9 runtime scale).
- Liquidity sweep requirement: **True** (runtime sweep_probability >= 60).
- Rejection candle requirement: **True** (candle trigger confirmed).
- Risk multiplier cap: **<= 0.5** by forcing the decision path to MICRO when counter-trend is active.
- No extra hidden confidence blockers remain in _counter_trend_reversal_ok().
- Hard risk protection remains active through unified hard-block checks.
