"""
Test: Phase 1E - Strategy Runners Unification
==============================================

Integration tests for SCALP, MICRO, SWING, DAILY runners with SignalSnapshot.
Tests that runner results can be converted to SignalSnapshot contracts.

[FER3ON-2026-08-31-PHASE1E] - Runner unification ready
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.phase1b_main_bridge import StrategyRunnerBridge, create_runner_signal_snapshot
from core.decision_contracts import SignalSnapshot


class TestStrategyRunnerBridge:
    """Test StrategyRunnerBridge for SCALP/MICRO/SWING/DAILY"""
    
    def test_bridge_converts_scalp_runner_result(self):
        """Bridge should convert SCALP runner result to SignalSnapshot"""
        runner_result = {
            'opened': True,
            'ticket': 123456,
            'lot': 0.01,
        }
        
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result=runner_result,
            strategy='SCALP',
            signal='BUY',
            quality_score=65.0,
            atr=3.5,
            session='LONDON',
            market_regime='TRENDING',
        )
        
        assert sig_snapshot is not None
        assert sig_snapshot.strategy == 'SCALP'
        assert sig_snapshot.direction == 'BUY'
        assert sig_snapshot.confidence == 65.0
        assert sig_snapshot.quality == 65.0
        print("✅ Test: Bridge converts SCALP runner result")
    
    def test_bridge_converts_micro_runner_result(self):
        """Bridge should convert MICRO runner result to SignalSnapshot"""
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result={},
            strategy='MICRO',
            signal='SELL',
            quality_score=55.0,
            atr=2.8,
            session='ASIA',
            market_regime='RANGING',
        )
        
        assert sig_snapshot is not None
        assert sig_snapshot.strategy == 'MICRO'
        assert sig_snapshot.direction == 'SELL'
        assert sig_snapshot.session == 'ASIA'
        print("✅ Test: Bridge converts MICRO runner result")
    
    def test_bridge_converts_swing_runner_result(self):
        """Bridge should convert SWING runner result to SignalSnapshot"""
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result={},
            strategy='SWING',
            signal='BUY',
            quality_score=70.0,
            atr=4.2,
            session='NEWYORK',
            market_regime='CHOPPY',
        )
        
        assert sig_snapshot is not None
        assert sig_snapshot.strategy == 'SWING'
        assert sig_snapshot.direction == 'BUY'
        print("✅ Test: Bridge converts SWING runner result")
    
    def test_convenience_function_creates_signal_snapshot(self):
        """Convenience function should create SignalSnapshot easily"""
        sig_snapshot = create_runner_signal_snapshot(
            strategy='SCALP',
            signal='BUY',
            quality_score=60.0,
            atr=3.5,
            session='LONDON',
            market_regime='TRENDING',
        )
        
        assert sig_snapshot is not None
        assert sig_snapshot.strategy == 'SCALP'
        assert sig_snapshot.signal_id  # auto-generated
        print("✅ Test: Convenience function creates signal snapshot")
    
    def test_bridge_handles_all_strategies(self):
        """Bridge should support all 4 strategies"""
        bridge = StrategyRunnerBridge()
        
        for strategy in ['SCALP', 'MICRO', 'SWING', 'DAILY']:
            sig_snapshot = bridge.from_runner_result(
                runner_result={},
                strategy=strategy,
                signal='BUY',
                quality_score=60.0,
                atr=3.5,
            )
            assert sig_snapshot is not None
            assert sig_snapshot.strategy == strategy
        
        print("✅ Test: Bridge handles all strategies (SCALP/MICRO/SWING/DAILY)")
    
    def test_bridge_preserves_signal_data(self):
        """Bridge should preserve all signal data"""
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result={},
            strategy='MICRO',
            signal='SELL',
            quality_score=75.0,
            atr=4.1,
            session='LONDON',
            market_regime='TRENDING',
        )
        
        assert sig_snapshot is not None
        assert sig_snapshot.direction == 'SELL'
        assert sig_snapshot.quality == 75.0
        assert sig_snapshot.atr == 4.1
        assert sig_snapshot.session == 'LONDON'
        assert sig_snapshot.regime == 'TRENDING'
        print("✅ Test: Bridge preserves signal data")
    
    def test_bridge_generates_signal_id(self):
        """Bridge should auto-generate signal_id if missing"""
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result={},
            strategy='SCALP',
            signal='BUY',
            quality_score=60.0,
            atr=3.5,
        )
        
        assert sig_snapshot is not None
        assert sig_snapshot.signal_id  # should be auto-generated
        assert len(sig_snapshot.signal_id) > 0
        print("✅ Test: Bridge generates signal_id")
    
    def test_bridge_includes_build_id(self):
        """Bridge should include build_id for tracing"""
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result={},
            strategy='MICRO',
            signal='SELL',
            quality_score=60.0,
            atr=3.5,
        )
        
        assert sig_snapshot is not None
        assert hasattr(sig_snapshot, 'build_id')
        assert sig_snapshot.build_id is not None
        print("✅ Test: Bridge includes build_id")


class TestMultiStrategySupport:
    """Test runner bridge for all strategies"""
    
    def test_convenience_function_all_strategies(self):
        """Convenience function should work for all strategies"""
        for strategy in ['SCALP', 'MICRO', 'SWING', 'DAILY']:
            sig_snapshot = create_runner_signal_snapshot(
                strategy=strategy,
                signal='BUY',
                quality_score=60.0,
                atr=3.5,
                session='LONDON',
                market_regime='TRENDING',
            )
            assert sig_snapshot is not None
            assert sig_snapshot.strategy == strategy
        
        print("✅ Test: Convenience function supports all strategies")


class TestErrorHandling:
    """Test error handling in runner bridge"""
    
    def test_bridge_handles_invalid_strategy(self):
        """Bridge should handle invalid strategy gracefully"""
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result={},
            strategy='INVALID',
            signal='BUY',
            quality_score=60.0,
            atr=3.5,
        )
        
        # Should fail validation
        assert sig_snapshot is None
        print("✅ Test: Bridge handles invalid strategy")
    
    def test_bridge_handles_invalid_signal(self):
        """Bridge should handle invalid signal gracefully"""
        bridge = StrategyRunnerBridge()
        sig_snapshot = bridge.from_runner_result(
            runner_result={},
            strategy='SCALP',
            signal='INVALID',
            quality_score=60.0,
            atr=3.5,
        )
        
        # Should fail validation
        assert sig_snapshot is None
        print("✅ Test: Bridge handles invalid signal")


def run_all_phase1e_tests():
    """Run all Phase 1E runner unification tests"""
    print("=" * 80)
    print("PHASE 1E: STRATEGY RUNNERS UNIFICATION TESTS")
    print("=" * 80)
    
    test_classes = [
        TestStrategyRunnerBridge(),
        TestMultiStrategySupport(),
        TestErrorHandling(),
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
    print(f"✅ ALL {total_tests} PHASE 1E RUNNER TESTS PASSED")
    print("=" * 80)
    print("\n🎯 Phase 1E Complete: Runners ready for SignalSnapshot integration")


if __name__ == "__main__":
    run_all_phase1e_tests()
