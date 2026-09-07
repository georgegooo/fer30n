# Current Status

Updated: 2026-09-07

## Safety

- `ALLOW_LIVE_TRADING=False`
- Phase 2, Phase 3, Phase 5 live authorities remain disabled.
- Exit manager remains advisory-only.

## Resolver

- Resolver telemetry is enabled.
- Resolver history window is 5000 M5 bars.
- Clean Shadow records are resolved before analysis.
- Legacy ledgers are outside runtime paths and retained externally as a
  compressed archive with a manifest.

## Validation

- Resolver integration tests cover WIN, LOSS, TIMEOUT, and invalid records.
- SL/TP finalizer contract includes a behavioral pre-sizing assertion.
- Test analytics writes use an isolated temporary root.

## Open Gates

- Fresh post-recovery configuration cohort is still required before changing
  thresholds or enabling live authorities.
- Secondary strategy runners need a dedicated shadow-evaluation path before
  being wired into the main loop.
