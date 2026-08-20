# Risk Status Report

- Consolidation status: **PASS**
- Primary engine: `core/risk_manager.py`
- Compatibility wrapper: `core/risk_protection.py`
- Hard cap module: `risk/hard_risk_cap.py`

## Verification

- Unified Engine: **OK**
- Lot Size: **OK**
- Drawdown Control: **OK**
- Max Open Trades: **OK**
- Session Risk: **OK**
- Ai Confidence Modifiers: **OK**
- Hard Risk Bridge: **OK**
- Duplicate Wrapper Removed: **OK**
- Legacy Duplicate State Removed: **OK**
- Hard Risk Module Present: **OK**

## Consolidated responsibilities

- Lot size → `calculate_smart_lot()`
- Drawdown control → `check_drawdown_limits()`
- Max open trades → `evaluate_position_limits()`
- Session risk → `get_session_risk_multiplier()`
- AI confidence modifiers → `compute_ai_risk_modifier()`
- Hard risk cap → `check_hard_risk_cap()` bridge inside unified engine
