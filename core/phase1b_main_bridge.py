"""
Phase 1B: Main.py Integration Adapter
======================================

Role: Bridge between old dict-based signals and new SignalSnapshot contracts.
This is the FIRST file to touch live code paths, but in a non-breaking way.

[FER3ON-2026-08-31-PHASE1B]
- Integration starts here
- main.py snapshot → SignalSnapshot conversion
- Zero behavior change (backward compatible)
- Safe rollback possible at any step
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import Any, Dict, Optional
from core.signal_snapshot_converter import (
    dict_to_signal_snapshot,
    validate_signal_snapshot,
)
from core.decision_contracts import SignalSnapshot


class UnifiedStrategyBridge:
    """
    Unified bridge for ALL strategies (SMC, SCALP, MICRO, DAILY).
    Converts any strategy's dict format to SignalSnapshot.
    
    Usage in main.py (Phase 1E):
    ┌──────────────────────────────────────────────────────────┐
    │ bridge = UnifiedStrategyBridge()                        │
    │                                                          │
    │ # For SMC:                                               │
    │ smc_snapshot = bridge.from_dict_snapshot(               │
    │     dict_snapshot=smc_dict, strategy='SMC')            │
    │                                                          │
    │ # For SCALP:                                            │
    │ scalp_snapshot = bridge.from_dict_snapshot(            │
    │     dict_snapshot=scalp_result, strategy='SCALP')      │
    │                                                          │
    │ # For MICRO:                                            │
    │ micro_snapshot = bridge.from_dict_snapshot(            │
    │     dict_snapshot=micro_result, strategy='MICRO')      │
    │                                                          │
    │ # For DAILY (SWING):                                   │
    │ daily_snapshot = bridge.from_dict_snapshot(            │
    │     dict_snapshot=swing_result, strategy='DAILY')      │
    └──────────────────────────────────────────────────────────┘
    """
    
    def __init__(self):
        self.last_snapshot = None
        self.last_error = None
    
    def from_dict_snapshot(
        self,
        dict_snapshot: Dict[str, Any],
        strategy: str = "SMC",
    ) -> Optional[SignalSnapshot]:
        """
        Convert dict snapshot from ANY strategy to SignalSnapshot.
        
        Supports: SMC, SCALP, MICRO, DAILY
        
        Args:
            dict_snapshot: Full dict from strategy (check_live_opportunity, run_scalp_cycle, etc)
            strategy: Strategy name (SMC/MICRO/SCALP/DAILY)
        
        Returns:
            SignalSnapshot or None if conversion failed
        """
        
        try:
            # Extract signal direction from various possible locations
            direction = None
            if 'signal' in dict_snapshot:
                direction = dict_snapshot.get('signal')
            elif 'direction' in dict_snapshot:
                direction = dict_snapshot.get('direction')
            elif 'mode' in dict_snapshot:
                direction = dict_snapshot.get('mode')
            
            if not direction:
                self.last_error = "No direction/signal found in snapshot"
                return None
            
            # Extract essential fields with fallbacks for each strategy
            signal_dict = {
                "signal_id": dict_snapshot.get("signal_id"),
                "direction": direction,
                "entry_price": dict_snapshot.get("entry_price") or dict_snapshot.get("current_price", 0),
                "signal_time": dict_snapshot.get("signal_time") or dict_snapshot.get("timestamp"),
                "regime": dict_snapshot.get("market_regime", "") or dict_snapshot.get("regime", ""),
                "session": dict_snapshot.get("session", ""),
                "confidence": dict_snapshot.get("confidence", {}).get("pct") or dict_snapshot.get("confidence_pct", 0),
                "quality": dict_snapshot.get("quality_score", 0) or dict_snapshot.get("score", 0),
                "atr": dict_snapshot.get("atr", 0),
                "execution_grade": dict_snapshot.get("execution", {}).get("grade") or dict_snapshot.get("grade", ""),
                "structure": dict_snapshot.get("structure", {}),
                "liquidity": dict_snapshot.get("liquidity", {}),
                "raw_signal_reason": dict_snapshot.get("phase", "") or dict_snapshot.get("reason", ""),
                "mtf_alignment": dict_snapshot.get("mtf_strength", 0),
            }
            
            # Convert to SignalSnapshot
            snapshot = dict_to_signal_snapshot(signal_dict, strategy)
            
            # Validate
            is_valid, reason = validate_signal_snapshot(snapshot)
            if not is_valid:
                self.last_error = reason
                return None
            
            # Store for debugging
            self.last_snapshot = snapshot
            return snapshot
            
        except Exception as e:
            self.last_error = str(e)
            return None
    
    def get_last_error(self) -> Optional[str]:
        """Get last conversion error"""
        return self.last_error


# Backward compatibility: SMCSignalBridge is now just an alias
SMCSignalBridge = UnifiedStrategyBridge


def _integrate_snapshot_bridge_into_check_live_opportunity(
    original_snapshot: Dict[str, Any],
    strategy: str = "SMC",
) -> tuple[Dict[str, Any], Optional[SignalSnapshot]]:
    """
    Helper function for Phase 1B integration.
    
    Returns BOTH the original dict (for backward compat) AND the new SignalSnapshot.
    This allows gradual migration without breaking existing code.
    
    Example usage (future):
    ┌────────────────────────────────────────────────────────┐
    │ dict_snapshot = check_live_opportunity(...)           │
    │ dict_snap, sig_snapshot = _integrate_snapshot_...(...) │
    │                                                        │
    │ # Old code still works:                               │
    │ if dict_snap.get('ready'):                            │
    │     execute_trade(dict_snap)  # Still works!          │
    │                                                        │
    │ # New code uses SignalSnapshot:                       │
    │ if sig_snapshot:                                      │
    │     decision = authority.decide(sig_snapshot)        │
    └────────────────────────────────────────────────────────┘
    """
    
    bridge = SMCSignalBridge()
    sig_snapshot = bridge.from_dict_snapshot(original_snapshot, strategy)
    
    # Original dict is unchanged
    return original_snapshot, sig_snapshot


class StrategyRunnerBridge:
    """
    Phase 1E: Bridge for SCALP/MICRO/SWING runners
    
    Converts runner results (minimal dicts) to SignalSnapshot for unification.
    Used when runners execute trades (already decided and executed).
    This is for logging/tracing only - doesn't affect execution.
    """
    
    def from_runner_result(
        self,
        runner_result: Dict[str, Any],
        strategy: str,
        signal: str,
        quality_score: float = 50.0,
        atr: float = 0.0,
        session: str = "UNKNOWN",
        market_regime: str = "UNKNOWN",
    ) -> Optional[SignalSnapshot]:
        """
        Convert runner result to SignalSnapshot (Phase 1E).
        
        Args:
            runner_result: Dict from run_scalp_cycle(), etc.
            strategy: SCALP, MICRO, SWING, DAILY
            signal: BUY or SELL
            quality_score: Quality metric (0-100)
            atr: ATR value
            session: Session name
            market_regime: Market regime
        
        Returns:
            SignalSnapshot or None if conversion failed
        """
        
        try:
            # Build minimal signal dict from runner results
            signal_dict = {
                "signal_id": None,  # Will auto-generate
                "direction": signal,
                "entry_price": None,  # Runner doesn't have this yet
                "signal_time": None,  # Will auto-generate
                "regime": market_regime,
                "session": session,
                "confidence": quality_score,
                "quality": quality_score,
                "atr": atr,
                "execution_grade": "B",  # Default for SCALP/MICRO runners
                "structure": {},
                "liquidity": {},
                "raw_signal_reason": "RUNNER",
                "mtf_alignment": 0,
            }
            
            # Convert to SignalSnapshot
            snapshot = dict_to_signal_snapshot(signal_dict, strategy)
            
            # Validate
            is_valid, reason = validate_signal_snapshot(snapshot)
            if not is_valid:
                return None
            
            return snapshot
            
        except Exception:
            return None


def create_runner_signal_snapshot(
    strategy: str,
    signal: str,
    quality_score: float,
    atr: float,
    session: str = "UNKNOWN",
    market_regime: str = "UNKNOWN",
) -> Optional[SignalSnapshot]:
    """
    Convenience function for Phase 1E: Convert runner signal data to SignalSnapshot.
    
    Usage in main.py after run_scalp_cycle(), run_micro_cycle(), etc.:
    ┌──────────────────────────────────────────────────────────┐
    │ result = run_scalp_cycle(...)                           │
    │                                                          │
    │ if result.get('opened'):                               │
    │     sig_snapshot = create_runner_signal_snapshot(      │
    │         strategy='SCALP',                              │
    │         signal=<signal from runner>,                    │
    │         quality_score=<quality>,                        │
    │         atr=<atr>,                                      │
    │         session=snapshot.get('session'),               │
    │         market_regime=snapshot.get('market_regime')    │
    │     )                                                   │
    │     if sig_snapshot:                                   │
    │         print(f"Signal ID: {sig_snapshot.signal_id}")  │
    └──────────────────────────────────────────────────────────┘
    """
    
    bridge = StrategyRunnerBridge()
    return bridge.from_runner_result(
        runner_result={},
        strategy=strategy,
        signal=signal,
        quality_score=quality_score,
        atr=atr,
        session=session,
        market_regime=market_regime,
    )


if __name__ == "__main__":
    # Example: test the bridge with mock data
    print("=" * 80)
    print("PHASE 1B: Main.py Integration Bridge Test")
    print("=" * 80)
    
    from datetime import datetime, timezone
    
    # Mock a snapshot from check_live_opportunity()
    mock_snapshot = {
        "ready": True,
        "signal": "BUY",
        "entry_price": 4400.0,
        "signal_time": datetime.now(timezone.utc).isoformat(),
        "market_regime": "TRENDING",
        "session": "LONDON",
        "confidence": {"pct": 75.0},
        "quality_score": 80.0,
        "atr": 4.5,
        "execution": {"grade": "A", "rr_ratio": 1.5},
        "structure": {"structure": "CHOCH", "mtf_aligned": True},
        "liquidity": {"bias": "BUY", "score": 80},
        "mtf_strength": 3,
        "phase": "SETUP",
    }
    
    bridge = SMCSignalBridge()
    sig_snapshot = bridge.from_dict_snapshot(mock_snapshot, "SMC")
    
    if sig_snapshot:
        print("✅ Bridge conversion successful!")
        print(f"   Signal ID: {sig_snapshot.signal_id}")
        print(f"   Strategy: {sig_snapshot.strategy}")
        print(f"   Direction: {sig_snapshot.direction}")
        print(f"   Confidence: {sig_snapshot.confidence}%")
        print(f"   Quality: {sig_snapshot.quality}%")
        print(f"   Build ID: {sig_snapshot.build_id}")
        print(f"   Decision Snapshot ID: {sig_snapshot.decision_snapshot_id}")
    else:
        print(f"❌ Bridge conversion failed: {bridge.get_last_error()}")
    
    print("\n" + "=" * 80)
    print("✅ Phase 1B Bridge ready for integration into main.py")
    print("=" * 80)
