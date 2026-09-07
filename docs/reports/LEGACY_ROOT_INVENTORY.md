# Legacy Root Inventory

The repository root contains historical reports and compatibility scripts from
prior FER3ON phases. They are intentionally left in place for now because
reports and external operators reference their paths.

The following root scripts are analysis/diagnostic utilities, not test suites:

- `test_sell_buy_ratio.py`
- `test_counter_trading_fix.py`
- `test_phase2_imports.py`

New analysis belongs under `scripts/` with `analyze_*.py` naming. New reports
belong under `docs/reports/`. Runtime analytics remain under `data/analytics`
and are excluded from source commits.
