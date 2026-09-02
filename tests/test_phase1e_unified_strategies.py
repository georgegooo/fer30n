"""
Test: Phase 1E - All Strategies Unified
========================================

Integration tests to verify the bridge works for all 4 strategies.
Tests SMC, SCALP, MICRO, DAILY (SWING) with unified bridge.

[FER3ON-2026-08-31-PHASE1E] - All strategies support
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.phase1b_main_bridge import UnifiedStrategyBridge
from core.decision_contracts import SignalSnapshot


class TestUnifiedStrategyBridge:
    """Test bridge supports all strategies"""
    
    def test_bridge_converts_smc_snapshot(self):
        """Bridge should convert SMC snapshot"""
        smc_snapshot = {
            "signal": "BUY",
            "market_regime": "TRENDING",
            "session": "LONDON",
            "confidence": {"pct": 75.0},
            "quality_score": 80.0,
            "atr": 4.2,
            "execution": {"grade": "A"},
        }
        
        bridge = UnifiedStrategyBridge()
        sig_snapshot = bridge.from_dict_snapshot(smc_snapshot, "SMC")
        
        assert sig_snapshot is not None
        assert sig_snapshot.direction == "BUY"
        assert sig_snapshot.strategy == "SMC"
        print("✅ Test: Bridge converts SMC snapshot")
    
    def test_bridge_converts_scalp_snapshot(self):
        """Bridge should convert SCALP snapshot (different dict format)"""
        scalp_result = {
            "mode": "BUY",  # SCALP uses 'mode' instead of 'signal'
            "regime": "RANGING",  # 'regime' key instead of 'market_regime'
            "session": "ASIA",
            "confidence_pct": 65.0,  # Direct pct instead of nested
            "score": 70.0,  # 'score' instead of 'quality_score'
            "atr": 3.5,
            "grade": "B",  # Direct grade instead of nested
            "current_price": 4395.0,  # 'current_price' instead of 'entry_price'
        }
        
        bridge = UnifiedStrategyBridge()
        sig_snapshot = bridge.from_dict_snapshot(scalp_result, "SCALP")
        
        assert sig_snapshot is not None
        assert sig_snapshot.direction == "BUY"
        assert sig_snapshot.strategy == "SCALP"
        assert sig_snapshot.confidence == 65.0
        assert sig_snapshot.quality == 70.0
        print("✅ Test: Bridge converts SCALP snapshot")
    
    def test_bridge_converts_micro_snapshot(self):
        """Bridge should convert MICRO snapshot"""
        micro_result = {
            "direction": "SELL",  # MICRO might use 'direction'
            "market_regime": "CHOPPY",
            "session": "NEWYORK",
            "confidence": {"pct": 55.0},
            "quality_score": 60.0,
            "atr": 2.8,
            "execution": {"grade": "C"},
        }
        
        bridge = UnifiedStrategyBridge()
        sig_snapshot = bridge.from_dict_snapshot(micro_result, "MICRO")
        
        assert sig_snapshot is not None
        assert sig_snapshot.direction == "SELL"
        assert sig_snapshot.strategy == "MICRO"
        print("✅ Test: Bridge converts MICRO snapshot")
    
    def test_bridge_converts_daily_snapshot(self):
        """Bridge should convert DAILY (SWING) snapshot"""
        daily_result = {
            "signal": "BUY",
            "market_regime": "TRENDING",
            "session": "LONDON",
            "confidence": {"pct": 85.0},
            "quality_score": 90.0,
            "atr": 5.0,
            "execution": {"grade": "A+"},
        }
        
        bridge = UnifiedStrategyBridge()
        sig_snapshot = bridge.from_dict_snapshot(daily_result, "DAILY")
        
        assert sig_snapshot is not None
        assert sig_snapshot.direction == "BUY"
        assert sig_snapshot.strategy == "DAILY"
        assert sig_snapshot.confidence == 85.0
        print("✅ Test: Bridge converts DAILY (SWING) snapshot")
    
    def test_bridge_handles_all_strategies_in_sequence(self):
        """Bridge should handle all 4 strategies in quick sequence (main loop simulation)"""
        strategies_and_data = [
            ("SMC", {
                "signal": "BUY",
                "market_regime": "TRENDING",
                "confidence": {"pct": 75.0},
            }),
            ("SCALP", {
                "mode": "SELL",
                "regime": "RANGING",
                "confidence_pct": 60.0,
            }),
            ("MICRO", {
                "direction": "BUY",
                "market_regime": "CHOPPY",
                "confidence": {"pct": 50.0},
            }),
            ("DAILY", {
                "signal": "SELL",
                "market_regime": "TRENDING",
                "confidence": {"pct": 80.0},
            }),
        ]
        
        bridge = UnifiedStrategyBridge()
        converted = []
        
        for strategy, data in strategies_and_data:
            snapshot = bridge.from_dict_snapshot(data, strategy)
            assert snapshot is not None
            assert snapshot.strategy == strategy.upper()
            converted.append(snapshot)
        
        assert len(converted) == 4
        print("✅ Test: Bridge handles all strategies in sequence")


class TestStrategyFieldVariations:
    """Test bridge handles field name variations across strategies"""
    
    def test_direction_field_variations(self):
        """Bridge should handle 'signal', 'direction', 'mode' variations"""
        bridge = UnifiedStrategyBridge()
        
        # Test 'signal'
        snap1 = bridge.from_dict_snapshot({"signal": "BUY"}, "SMC")
        assert snap1.direction == "BUY"
        
        # Test 'direction'
        snap2 = bridge.from_dict_snapshot({"direction": "SELL"}, "MICRO")
        assert snap2.direction == "SELL"
        
        # Test 'mode'
        snap3 = bridge.from_dict_snapshot({"mode": "BUY"}, "SCALP")
        assert snap3.direction == "BUY"
        
        print("✅ Test: Bridge handles direction field variations")
    
    def test_confidence_field_variations(self):
        """Bridge should handle nested and flat confidence"""
        bridge = UnifiedStrategyBridge()
        
        # Nested confidence
        snap1 = bridge.from_dict_snapshot({
            "signal": "BUY",
            "confidence": {"pct": 75.0}
        }, "SMC")
        assert snap1.confidence == 75.0
        
        # Flat confidence
        snap2 = bridge.from_dict_snapshot({
            "signal": "BUY",
            "confidence_pct": 80.0
        }, "SCALP")
        assert snap2.confidence == 80.0
        
        print("✅ Test: Bridge handles confidence field variations")
    
    def test_regime_field_variations(self):
        """Bridge should handle 'market_regime' and 'regime'"""
        bridge = UnifiedStrategyBridge()
        
        snap1 = bridge.from_dict_snapshot({
            "signal": "BUY",
            "market_regime": "TRENDING"
        }, "SMC")
        assert snap1.regime == "TRENDING"
        
        snap2 = bridge.from_dict_snapshot({
            "signal": "BUY",
            "regime": "RANGING"
        }, "SCALP")
        assert snap2.regime == "RANGING"
        
        print("✅ Test: Bridge handles regime field variations")
    
    def test_grade_field_variations(self):
        """Bridge should handle nested and flat execution grade"""
        bridge = UnifiedStrategyBridge()
        
        # Nested grade
        snap1 = bridge.from_dict_snapshot({
            "signal": "BUY",
            "execution": {"grade": "A"}
        }, "SMC")
        assert snap1.execution_grade == "A"
        
        # Flat grade
        snap2 = bridge.from_dict_snapshot({
            "signal": "BUY",
            "grade": "B"
        }, "SCALP")
        assert snap2.execution_grade == "B"
        
        print("✅ Test: Bridge handles grade field variations")


class TestBackwardCompatibilityAll:
    """Test backward compatibility for all strategies"""
    
    def test_original_dicts_unchanged_all_strategies(self):
        """Original dicts should remain unchanged for all strategies"""
        
        strategy_dicts = {
            "SMC": {"signal": "BUY", "market_regime": "TRENDING"},
            "SCALP": {"mode": "SELL", "regime": "RANGING"},
            "MICRO": {"direction": "BUY", "market_regime": "CHOPPY"},
            "DAILY": {"signal": "SELL", "market_regime": "TRENDING"},
        }
        
        bridge = UnifiedStrategyBridge()
        
        for strategy, original_dict in strategy_dicts.items():
            # Keep original values
            original_copy = dict(original_dict)
            
            # Convert through bridge
            snapshot = bridge.from_dict_snapshot(original_dict, strategy)
            
            # Verify dict unchanged
            assert original_dict == original_copy
            assert snapshot is not None
        
        print("✅ Test: Original dicts unchanged for all strategies")


class TestErrorHandlingAll:
    """Test error handling works for all strategies"""
    
    def test_bridge_rejects_missing_direction_all_strategies(self):
        """Bridge should reject snapshots with no direction for any strategy"""
        bridge = UnifiedStrategyBridge()
        
        for strategy in ["SMC", "SCALP", "MICRO", "DAILY"]:
            invalid_dict = {"market_regime": "TRENDING"}  # No direction
            snapshot = bridge.from_dict_snapshot(invalid_dict, strategy)
            
            assert snapshot is None
            assert bridge.get_last_error() is not None
        
        print("✅ Test: Bridge rejects missing direction for all strategies")


def run_all_phase1e_tests():
    """Run all Phase 1E tests"""
    print("=" * 80)
    print("PHASE 1E: UNIFIED STRATEGY BRIDGE TESTS (ALL STRATEGIES)")
    print("=" * 80)
    
    test_classes = [
        TestUnifiedStrategyBridge(),
        TestStrategyFieldVariations(),
        TestBackwardCompatibilityAll(),
        TestErrorHandlingAll(),
    ]
    
    total_tests = 0
    for test_class in test_classes:
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                try:
                    method = getattr(test_class, method_name)
                    method()
                    total_tests += 1
                except AssertionError as e:
                    print(f"❌ {method_name} failed: {e}")
                    raise
                except Exception as e:
                    print(f"❌ {method_name} error: {e}")
                    raise
    
    print("\n" + "=" * 80)
    print(f"✅ ALL {total_tests} PHASE 1E TESTS PASSED")
    print("=" * 80)
    print("\n🎯 Phase 1E Complete: Unified bridge ready for ALL strategies")
    print("   SMC, SCALP, MICRO, DAILY all supported")


if __name__ == "__main__":
    run_all_phase1e_tests()
