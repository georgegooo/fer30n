# Architecture Audit Report

## Scope
Phase 1 audit completed on the full extracted project with focus on runtime architecture, authority flow, duplication, legacy coupling, and inactive systems.

## Executive Summary
The repository is feature-rich but architecturally fragmented. The main runtime was not using the documented single-authority model consistently. Legacy V5/V6/V7 modules still exist across the codebase, but most of them are not on the current `main.py` runtime path. The highest-risk issue found was **runtime bypass of true signal generation and decision authority**, where `main.py` was using static gate inputs and a hardcoded execution request instead of a full live pipeline.

## Key Findings

### 1) Multiple authority layers detected
Decision-related modules found:
- `core/decision_engine.py`
- `core/unified_decision.py`
- `core/unified_bridge.py`
- `core/ai_v1_authority.py`
- `core/fer3on_decision_authority.py` (new facade added in cleanup)
- `core/decision_snapshot.py`

**Assessment:** authority was historically split across legacy decision layers, unified bridge, and AI V1 wrapper. Runtime now points to a single V2 facade, but legacy authority modules remain in repo for archive/compatibility purposes.

### 2) Multiple execution / validation layers detected
Runtime/validation stack overlap found in:
- `core/startup_check.py`
- `core/runtime_validation.py` (new)
- `core/v7_audit.py`
- `core/spec_runtime.py`
- `core/module_registry.py`
- `tools/system_health_check.py`
- `tools/end_to_end_smoke.py`
- related tests in `tests/` and `testing/`

**Assessment:** several parallel health-check systems exist. Only one should own runtime startup validation.

### 3) Legacy version footprint remains widespread
Automated scan summary from `data/analytics/architecture_runtime_audit.json`:
- modules scanned: **185**
- modules containing `V5`: **31**
- modules containing `V6`: **29**
- modules containing `V7`: **38**
- modules containing `ai_v1_authority` references: **3**

**Assessment:** the repository still contains heavy legacy branding and legacy naming even when logic may still be useful as evidence producers.

### 4) Inactive / skipped / not-on-runtime-path modules
The audit flagged a large set of zero-inbound, non-test/non-tool candidates. Important examples:
- `core/decision_engine.py`
- `core/ai_v1_authority.py`
- `core/v7_integration.py`
- `analytics/recovery_dashboard.py`
- `core/spec_runtime.py`
- `core/module_registry.py`
- `core/scalping_engine.py`
- `core/micro_trading_engine.py`
- `core/smc_entry_engine.py`
- `core/daily/signal.py`

**Important note:** zero inbound here means “not referenced by the internal import graph used by the audit script after excluding docs/archive/test-only paths.” It is a strong cleanup signal, not an automatic delete instruction.

### 5) Fake / partial integrations detected
The most important runtime integrity problem was in `main.py`:
- static `quality_score=50`, `confidence_pct=60`, `strategy="SMC"`
- static `signal="BUY"`
- hardcoded request object
- no real upstream signal-engine call chain before authority decision

**Assessment:** runtime loop existed, but actual signal-generation integration was incomplete and partially simulated.

### 6) Dead or weakly used code candidates
Examples of dead / weak runtime code:
- `build_market_snapshot_hash()` in `main.py`
- `maybe_skip_analysis()` in `main.py`
- imported `connect_mt5` in `main.py` was not used in runtime flow
- `AIV1Evidence` import in `main.py` was unused before cleanup

### 7) Duplicate risk / safety logic layers
Risk-related layers identified:
- `core/risk_manager.py`
- `core/risk_protection.py`
- `risk/hard_risk_cap.py`
- `core/recovery_cooldown.py`
- `core/account_protection.py`

**Assessment:** layered protection exists, but ownership boundaries are not sharply defined. Runtime should consume one clear risk engine plus catastrophic safety guards.

## Current Architectural Judgment
### Healthy
- `core/unified_decision.py` provides a clear 4-outcome authority model.
- `core/unified_bridge.py` cleanly builds a normalized decision context.
- `core/trade_executor.py` correctly chains execution → logging → memory → trailing update.
- `core/mt5_compat.py` provides safe non-MT5 fallback.

### Unhealthy
- runtime entrypoint was not aligned with the intended architecture.
- legacy version identity leaks heavily into runtime-visible logs and module naming.
- startup validation previously depended on a V7-branded audit path.
- actual live signal-generation flow is not yet wired end-to-end.

## Recommendations
1. Keep only one runtime authority entrypoint: `core/fer3on_decision_authority.py`
2. Keep legacy modules archived / compatibility-only, not runtime-owned
3. Keep one startup validator: `core/runtime_validation.py`
4. Later phase: wire true market-data → signal-engine → authority inputs into `main.py`
5. Later phase: move non-runtime V5/V6/V7 modules to explicit `archive/legacy_runtime/`

## Files Generated / Updated During Cleanup
- `core/fer3on_decision_authority.py`
- `core/runtime_validation.py`
- `scripts/architecture_runtime_audit.py`
- `main.py` (runtime authority cleanup)
- `core/startup_check.py` (runtime validation cleanup)

## Conclusion
Architecture cleanup for runtime ownership has started successfully, but the project still contains a large legacy surface. The runtime is now more coherent, while deeper signal-engine integration remains intentionally deferred to avoid changing trading logic in this phase.
