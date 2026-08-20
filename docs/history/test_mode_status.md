# Test Mode Status

- Daily max trades: **8**
- Micro trades: **4 × 0.01 lot**
- Normal trades: **4 × 0.02 lot**
- Auto reset basis: **UTC day key in data/analytics/test_mode_state.json**

## Current counters

- used_micro: **0**
- used_normal: **0**
- used_total: **0**
- remaining_micro: **4**
- remaining_normal: **4**
- remaining_total: **8**

## Direct integrations

- Decision Authority: unified_decision blocks when quota is exhausted.
- Risk Engine: calculate_smart_lot() snaps lots to 0.01 / 0.02 and rejects exhausted buckets.
- Position Sizing: final lot is produced only after quota validation.
