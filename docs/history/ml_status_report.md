# ML Status Report

## Phase 1 — ML Audit

- Unified status: **PARTIAL**
- Exact required artifacts: **4**
- Usable runtime artifacts: **2**

## ML file scan

### Xgb Models
- `data/models/xgb_scaler_sklearn.pkl`
- `ml/xgboost_model.py`

### Neural Models
- `data/models/nn_model.pkl`
- `ml/neural_network.py`

### Rl Models
- `ml/reinforcement.py`

### Scalers
- `data/models/xgb_scaler_sklearn.pkl`

### Feature Generators
- `ml/feature_engine.py`
- `tests/test_production_spec_features.py`

## Exact supported model files

- **XGBoost Model** → `data/models/xgb_model.pkl` → **MISSING**
  - runtime source: none
- **XGBoost Scaler** → `data/models/xgb_scaler.pkl` → **MISSING**
  - legacy alias: `data/models/xgb_scaler_sklearn.pkl` → **VALID**
  - runtime source: `data/models/xgb_scaler_sklearn.pkl` (legacy_alias)
- **Neural Model** → `data/models/nn_model.pkl` → **VALID**
  - runtime source: `data/models/nn_model.pkl` (required)
- **RL Model** → `data/models/rl_model.pkl` → **MISSING**
  - runtime source: none

## Missing exact files

- `data/models/xgb_model.pkl`
- `data/models/xgb_scaler.pkl`
- `data/models/rl_model.pkl`

## Status policy

- Allowed output states: `REAL`, `PARTIAL`, `DISABLED`.
- `REAL` requires the exact supported file set, not only legacy aliases.
- Current runtime may fall back to legacy aliases, but aliases do not promote status to `REAL`.
