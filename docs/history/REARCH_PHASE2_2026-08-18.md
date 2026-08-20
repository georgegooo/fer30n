# Re-architecture — Phase 2 (2026-08-18)

## Scope
Continuation of Phase 1, same method (audit + de-duplicate, no folder
restructuring, no logic changes), extended to the rest of `core/` plus
`analytics/`, `risk/`, `config/` — everything Phase 1 didn't already cover.

## Method
Baseline before this pass: **541 passed, 1 skipped** (same as Phase 1's
post-change state — nothing regressed between passes). Every check below was
either (a) a targeted read of a specific file, or (b) a repo-wide search for
the same *classes* of problem Phase 1 actually found (literal duplication,
false "single source of truth" claims, hardcoded values that should read
settings.py). Final test run after all Phase 2 changes: **541 passed, 1
skipped** — identical.

## What this pass found

### Confirmed healthy (verified, not assumed)
- **`core/sl_tp_finalizer.py`**'s "single source of truth" claim is
  **true**: `main.py`, `core/strategy_runners.py`, and
  `core/trade_executor.py` all three genuinely call
  `finalize_sl_tp()` — this is the real architecture Phase 1's
  [REARCH-1] fix pushes the codebase toward, already done correctly here.
- **`analytics/truth_layer.py`**'s "single source of truth for performance
  analytics" claim mostly holds up on inspection: modules that looked at
  first glance like independent `win_rate`/`profit_factor` recomputations
  (`analytics/session_edge_analysis.py`, `analytics/regime_edge_analysis.py`,
  `analytics/portfolio_statistics.py`) actually import and reuse
  `truth_layer.Metrics` rather than reimplementing the math.
- No further copies of the [SLTP-1]-style bug (a formula duplicated as a
  literal in multiple files) were found anywhere else in the codebase — a
  repo-wide search for the specific pattern Phase 1 fixed (point-conversion
  arithmetic, magic-number literals for SCALP/DAILY/SWING/SMC/MICRO/
  RECOVERY/SURVIVAL) turned up nothing outside what Phase 1 already fixed.

### [REARCH-4] Fixed a real bug in the project's own audit tooling
`scripts/architecture_runtime_audit.py` (referenced by
`docs/history/architecture_audit_report.md`) builds an import graph to find
orphaned modules. Its `resolve_relative()` had a bug: for a plain absolute
import — `from core.settings import X`, by far the most common import style
in this codebase — it returned `"<importing-module>.core.settings"` instead
of `"core.settings"`. That silently broke the whole incoming-edge graph:
before the fix, it reported **160 core-business-logic modules as
"zero-inbound / dead"**, including modules directly verified as live in
Phase 1 (`core.strategy_runners`, `core.sl_tp_finalizer`). After the
one-line fix, that number is **32**, and spot-checks against known-live
modules (`core.settings`: 101 inbound edges; `core.sl_tp_finalizer`: exactly
its 3 documented callers) now line up with reality. This doesn't change any
trading behavior — it's a dev-tool script, not imported by anything — but it
matters for the same reason [REARCH-3] mattered: a governance/audit tool
that silently reports the wrong thing is worse than no tool, because it
looks authoritative.

### Confirmed, not fixed — legacy compatibility wrappers (by design)
`core/risk_protection.py` and `core/adaptive_lot_engine.py` both define
their own session/loss-limit constants that look, at a glance, like they
could drift from `core/settings.py`'s equivalents. Checked both: neither is
called from the live trading path (`main.py` /
`core/strategy_runners.py` / `core/trade_executor.py`) — this matches
`core/settings.py`'s own stated philosophy ("No Engine Deletion — every
V6/V7 module stays as an Evidence Producer") and is confirmed by the
corrected audit tool (`risk_protection` shows zero inbound edges from
runtime code). Not a live risk today. If either is ever wired back into the
live path, its constants should be re-pointed at `core/settings.py` first —
noted here so that's not forgotten rather than fixed now, since fixing
code with zero live callers has no verifiable behavior to test against.

### Flagged for a separate, dedicated pass (not risk/execution, lower priority)
Several `analytics/` modules (`analytics/quant_engine.py`,
`analytics/institutional_dashboard_phase3.py`,
`core/institutional_dashboard.py`) compute their own health/scoring metrics
independently rather than through `truth_layer.py`. Unlike the
false-positive cases above, these look like genuinely separate
calculations, not reuse-in-disguise. This is real, but it's an analytics/
reporting concern, not a live-trading-risk one (nothing here sizes a
position or places an order), and safely consolidating it means
understanding what each one is actually measuring first — worth its own
pass rather than folding into a risk/execution-focused audit.

## Net result
Phase 1 found and fixed the concentrated, live-trading-risk instances of
"same rule, multiple copies" — that's where the real exposure was. Phase 2
covered the remaining ~120+ files in `core/` (plus `analytics/`, `risk/`,
`config/`) looking for the same pattern and found the risk surface there is
much smaller: one real tooling bug (fixed), a couple of confirmed-inert
legacy wrappers (documented, correctly left alone), and one lower-priority
analytics-consolidation candidate (flagged for later, not fixed here).

## Still outstanding (unchanged from Phase 1's roadmap)
1. Decide `risk_policy.py` / `data_source_registry.py`'s fate: wire in as
   the real read path, or retire.
2. Split `core/` into domain sub-packages — mechanical move + import fix,
   one sub-package at a time, full test suite green before moving to the
   next. Still the single biggest remaining structural item; not attempted
   in Phase 1 or 2.
3. The `analytics/` scoring-consolidation item flagged above.
4. `main.py`'s pre-existing authority-layer overlap
   (`architecture_audit_report.md` recommendations #1-#3) — unchanged.
