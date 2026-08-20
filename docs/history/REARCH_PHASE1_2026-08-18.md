# Re-architecture — Phase 1 (2026-08-18)

## Why this pass exists
Follow-up to audit point 7 ("too many AUDIT FIX comments = patch-driven, not
architecture-driven"). This is not a new finding — it overlaps with
`docs/history/architecture_audit_report.md`'s own finding #7, "Duplicate
risk / safety logic layers: layered protection exists, but ownership
boundaries are not sharply defined." Phase 1 below fixes the specific,
verifiable instances of that inside the risk/execution core named in the
audit. It does not touch the broader `core/` package layout — see
"What Phase 1 deliberately did not do" below.

## Method
1. Full baseline test run before any change: `pytest tests/` →
   **541 passed, 1 skipped, 17 subtests** (0 failures).
2. Every change below is a *move*, not a *rewrite*: the formula, threshold,
   or table being consolidated keeps its original value. No trading
   parameter changed.
3. Full test run again after every change: still **541 passed, 1 skipped,
   17 subtests** — identical to baseline.

## What changed

### [REARCH-1] `min_sl` floor formula — 7 independent copies → 1 function
`max(5.00, float(MIN_SL_DISTANCE) * 0.01)` existed as a literal, copy-pasted
7 times: 6 in `core/strategy_runners.py` (one per strategy-cycle / TP-ladder
branch) and 1 in `main.py`'s SMC path (as a local `from core.settings import
MIN_SL_DISTANCE` + inline computation). `core/trade_executor.py` had a
*structurally different* implementation of the same formula
(`_enforce_min_stop_distance`, using the live broker `point` value instead
of a hardcoded `0.01`).

This is the exact failure mode [SLTP-1] came from: the same domain rule
written more than once, able to drift apart silently. All 7 sites now call
`core.settings.get_min_sl_dollars(point=0.01)`; `trade_executor.py` calls it
with the real broker point, exactly reproducing its prior behavior.

### [REARCH-2] Per-strategy position-limit table — moved into settings.py
`core/risk_manager.py::evaluate_position_limits` had its own hardcoded dict
(`{'SCALP': 20, 'MICRO': 40, 'DAILY': 10, 'SWING': 10}`) with no visibility
from `core/settings.py`, even though `settings.py` already owns
`MAX_OPEN_TRADES` and `MAX_OPEN_PER_STRATEGY` — the same domain. Moved to
`settings.PER_STRATEGY_SOFT_POSITION_LIMITS`; `risk_manager.py` now reads
it instead of keeping a second copy. Values unchanged (and, per the
existing comment this preserves, currently non-binding in practice because
`MAX_OPEN_TRADES=4` is always the tighter constraint).

### [REARCH-3] `core/risk_policy.py` — stopped being a second copy of settings
This module documented itself as "the single source of truth for risk
limits" while actually holding a hand-maintained static dict that had
already drifted once (`max_daily_trades: 80` vs. the live `50` — caught only
by `tests/test_governance_p0.py`, not by anything structural). `
get_risk_policy()` now reads `core.settings` directly, field by field, so
this class of drift is no longer possible by construction — there is
nothing left to remember to keep in sync. `DEFAULT_RISK_POLICY` is kept as
a documented, explicitly-non-live reference snapshot for
`validate_risk_policy()`'s own testing.

**Still true after this fix, and worth being direct about:**
`core/risk_manager.py` (what actually runs on every live trade) still reads
`core.settings` directly, not `core.risk_policy`. This module documents and
validates policy; it does not execute it. Making it the actual enforcement
path is a bigger, separate decision — it would mean every risk read in the
live path changes its import, which is worth its own review and sign-off
rather than folding into a "no behavior change" pass.

## What Phase 1 deliberately did not do
- **`core/data_source_registry.py`** has the identical "declared canonical,
  not actually consumed by live code" shape as `risk_policy.py` did (its own
  docstring says so). Not touched this pass — flagged for the same
  live/documented decision above.
- **The `core/` package itself** is a flat, 130+-file directory mixing risk,
  execution, strategy signal engines, AI/ML, session intelligence, the
  Telegram bot, and logging with no sub-package boundaries. This is a much
  larger finding than audit point 7's comment volume, and it's not new —
  it's the same shape `architecture_audit_report.md` already flagged
  (findings #1, #2, #4, #7). Restructuring it into `core/risk/`,
  `core/execution/`, `core/strategy/`, `core/intelligence/`, `core/ai/`,
  `core/infra/`-style sub-packages is a real, worthwhile Phase 2 — but it
  means updating imports across all ~368 `.py` files in the project, and
  doing that safely on a live-money trading system needs to happen
  file-by-file against the test suite, not in one pass.
- **`main.py`'s own architecture issues** (multiple overlapping authority /
  validation layers, static test inputs in places — see
  `architecture_audit_report.md` findings #1, #2, #5) are pre-existing,
  already documented, and out of scope for this risk/execution-focused pass.

## Roadmap (proposed order for Phase 2+)
1. Decide `risk_policy.py` / `data_source_registry.py`'s fate: wire them in
   as the real read path, or retire them. Either is fine; "declared
   canonical but unread" is the state that isn't.
2. Continue the same audit-and-deduplicate pass through the rest of
   `core/`'s ~130 files (this pass only covered the 4 files named in the
   audit plus the 5 most tightly-coupled to them).
3. Split `core/` into domain sub-packages — mechanical move + import fix,
   one sub-package at a time, full test suite green before moving to the
   next.
4. Revisit `main.py`'s pre-existing authority-layer overlap per
   `architecture_audit_report.md`'s own recommendations #1-#3.
