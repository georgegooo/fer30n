# Runtime Execution Map

## Scope
This map describes the **actual active runtime path** after architecture cleanup and runtime stabilization work.

## Active Entrypoint
`main.py`

## Actual Runtime Flow

```text
main.py
  -> core.startup_check.run_startup_check()
      -> config/env validation
      -> module registry validation
      -> critical function validation
      -> core.runtime_validation.run_runtime_validation()
          -> core.fer3on_decision_authority
          -> core.quality_score
          -> core.risk_manager
          -> core.risk_protection
          -> core.trade_executor
          -> core.ai_memory
          -> core.trailing_stop
          -> core.daily.signal

  -> heartbeat loop
      -> MT5 tick fetch via core.mt5_compat
      -> quality pre-check via core.quality_score.evaluate_quality_gate()
      -> decision context build via core.fer3on_decision_authority.build_decision_context()
      -> final decision via core.fer3on_decision_authority.decide_trade()
          -> core.unified_bridge.build_decision_context()
          -> core.unified_decision.unified_decide()
      -> runtime formatting via core.fer3on_decision_authority.decision_to_runtime_format()
      -> if approved and MT5 available:
          -> core.trade_executor.execute_trade()
              -> MT5 order_check
              -> MT5 order_send
              -> local trade log
              -> core.ai_memory.save_trade_memory()
              -> core.trailing_stop.update_trailing_stop()
```

## Authority Ownership
Only the final authority layer should decide:
- approve trade
- reject trade
- assign execution size mode
- assign risk multiplier

### Current active authority
- `core/fer3on_decision_authority.py`
  - wraps the final authority path
  - presents FER3ON AI V2 runtime identity

### Final decision engine under the facade
- `core/unified_decision.py`

## Module Role Classification

### Market Data
- `core.mt5_compat.py`
- MT5 tick/rates access

### Signal Engines / Evidence Producers
Present in repository but **not yet fully wired into the active `main.py` loop**:
- `core/scalping_engine.py`
- `core/micro_trading_engine.py`
- `core/smc_entry_engine.py`
- `core/daily/signal.py`
- `brain/master_brain.py`
- `core/confidence_engine.py`
- `core/candle_trigger.py`
- `core/market_structure.py`
- `core/liquidity_map.py`

### FER3ON Decision Authority
- `core/fer3on_decision_authority.py`
- `core/unified_decision.py`
- `core/unified_bridge.py`

### Risk Engine
- `core/risk_manager.py`
- `core/risk_protection.py`

### Execution Engine
- `core.trade_executor.py`
- `core.trailing_stop.py`

### Logging / Memory
- `core.ai_memory.py`
- local console logging in runtime modules

## Skipped / Inactive / Bypassed Systems

### 1) Signal engines currently bypassed by active runtime loop
The active `main.py` loop still builds a synthetic decision context rather than collecting live evidence from all signal engines.

Bypassed in active runtime path:
- `core/scalping_engine.py`
- `core/micro_trading_engine.py`
- `core/smc_entry_engine.py`
- `brain/master_brain.py`
- `core/confidence_engine.py`
- `core/candle_trigger.py`
- `core/market_structure.py`
- `core/liquidity_map.py`

### 2) Legacy authority layer bypassed
- `core/ai_v1_authority.py`
- not used by active `main.py`
- not used by startup validation anymore

### 3) Legacy validation path bypassed
- `core/v7_audit.py`
- replaced in startup path by `core/runtime_validation.py`

### 4) V7 integration bundle not on active runtime path
- `core/v7_integration.py`
- contains useful auxiliary modules but is not part of the active `main.py` execution chain

## Fake / Partial Integrations Identified

### Previous state
The runtime used:
- static quality score
- static confidence
- static strategy
- static signal
- hardcoded order payload

### Current state
Authority routing is cleaner, but **full live evidence collection is still not wired**.

That means:
- runtime authority is real
- startup validation is real
- execution pipeline is real
- upstream market-to-signal integration is still partial

## Runtime Validation Result
Validated successfully after cleanup:
- decision authority: PASS
- quality gate: PASS
- risk engine: PASS
- risk protection: PASS
- execution engine: PASS
- memory: PASS
- trailing: PASS
- daily signal: PASS

Health score: **100/100**

## Conclusion
The project now has a cleaner active runtime path with a single V2 authority facade and a validated startup chain. However, the runtime is still using a simplified decision-context build instead of the full market-data -> signal-engine -> authority pipeline. That deeper signal wiring should be the next architecture phase, without changing trade logic semantics.
