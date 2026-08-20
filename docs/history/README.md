# docs/history/

Archived point-in-time status/implementation reports, moved out of the
project root to reduce clutter (see the cleanup recommendation this
repo's own review process flagged: 13+ `*_status_report.md` files plus
several one-off phase/implementation reports sitting in the root made the
project harder to navigate without adding runtime value).

Nothing here is deleted, and nothing here is load-bearing at runtime —
these are historical snapshots of a particular development phase, kept
for reference. If you're looking for the **current, canonical** project
docs, see the root instead:

- `README.md`, `README_MASR.md` — current project overview
- `CHANGELOG.md` — current, single changelog (this directory's
  `FER3ON_FINAL_CHANGELOG.md` is the detailed historical version it
  summarizes)
- `PHASE_2_SAFETY_BOUNDARY.md` — **active** safety contract, still
  enforced and referenced by code (not archived — this one matters at
  runtime)
- `BACKTEST_VALIDITY_NOTICE.md` — **active** caveat about backtest data
  realism, still relevant (not archived)
- `certification_framework.md`, `certification_status.md` — **live,
  code-generated** files written by `certification/framework.py`, not
  static reports (not archived; moving them would just have them
  regenerate at root anyway)

## What's here

| File | What it was |
|---|---|
| `FER3ON_FINAL_CHANGELOG.md` | Full historical changelog with item IDs (`[SLTP-1]`, `[EXPOSURE-1]`, etc.) still cited throughout inline code comments — grep for the ID, not the file location, if a comment points you here |
| `PHASE_1_ACCEPTANCE.md` | Phase 1 acceptance sign-off |
| `TP_CAPPING_IMPLEMENTATION_REPORT.md` | TP capping feature implementation report (feature is live — see `analytics/tp_cap_monitor.py` for current validation telemetry) |
| `FOUR_FIXES_REPORT.md` | Report on four specific bug fixes |
| `IMPLEMENTATION_STATUS_MASR.md` | MASR subsystem implementation status snapshot |
| `architecture_audit_report.md` | Point-in-time architecture audit |
| `counter_trend_status.md` | Counter-trend module status snapshot |
| `execution_pipeline_status.md` | Execution pipeline status snapshot |
| `fer3on_v2_readiness_report.md` | v2 readiness assessment |
| `final_cleanup_report.md` | Prior cleanup pass report |
| `integration_status_report.md` | Integration status snapshot |
| `live_integration_report.md` | Live integration status snapshot |
| `ml_status_report.md` | ML subsystem status snapshot |
| `risk_status_report.md` | Risk subsystem status snapshot |
| `runtime_execution_map.md` | Runtime execution flow map (point-in-time) |
| `test_mode_status.md` | Test mode status snapshot |
| `watchdog_status_report.md` | Watchdog module status snapshot |
