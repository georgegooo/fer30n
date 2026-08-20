# Integration Status Report

- Integration status: **PASS**
- History rows: **25**
- Memory rows: **50**
- Analytics total trades: **25**
- Statistics total trades: **25**

## Flow validation

- Trade → History: enforced through `core/mt5_history_sync.py` into `data/history/trades.csv`.
- History → Analytics: `core/analytics.py` reads `data/history/trades.csv`.
- History → AI Memory: MT5 closed trades are upserted into `data/memory/ai_memory.csv`.
- AI Memory → Adaptive AI: MT5 closed trades are forwarded to `core/adaptive_learning.record_trade_outcome()`.

## Coverage checks

- History tickets missing in memory: **0**
- Memory tickets missing in history: **25**
- Pending open memory tickets: **25**
- Orphan closed memory tickets: **0**
- Duplicate history tickets: **0**
- Duplicate memory tickets: **0**
- Magic mismatches in memory: **0**

## Missing history tickets in memory

- None

## Memory tickets without history counterpart

- `57064454950`
- `57064455077`
- `57064462074`
- `57064462107`
- `57064788066`
- `57064788114`
- `57065066321`
- `57065148702`
- `57065487342`
- `57065611832`
- `57065613297`
- `57065639596`
- `57065639634`
- `57066130712`
- `57066207076`
- `57066336591`
- `57066846196`
- `57067061885`
- `57067471235`
- `57067590462`
- `57067891475`
- `57068292142`
- `57068400159`
- `57069193047`
- `57069602645`

## Open-memory-only tickets

- `57064454950`
- `57064455077`
- `57064462074`
- `57064462107`
- `57064788066`
- `57064788114`
- `57065066321`
- `57065148702`
- `57065487342`
- `57065611832`
- `57065613297`
- `57065639596`
- `57065639634`
- `57066130712`
- `57066207076`
- `57066336591`
- `57066846196`
- `57067061885`
- `57067471235`
- `57067590462`
- `57067891475`
- `57068292142`
- `57068400159`
- `57069193047`
- `57069602645`

## Orphan closed-memory tickets

- None

## Duplicate tickets

- History duplicates: `{}`
- Memory duplicates: `{}`

## Magic mismatch details

- None

## Analytics summary

- `📈 ANALYTICS | 25T WR:36.0% P:-863.95$ PF:0.07 DD:874.75$ AvgW:7.39$ AvgL:-58.16$ Best:21.16$ Worst:-794.88$ Streak:1W`
- Statistics grade: **LOSING ❌**
