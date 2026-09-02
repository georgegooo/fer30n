#!/usr/bin/env python3
"""Quick test to identify import issues"""

import sys
import traceback

try:
    print("Testing import sequence...")
    print("1. Testing phase1b_main_bridge...")
    from core.phase1b_main_bridge import UnifiedStrategyBridge
    print("   ✅ phase1b_main_bridge OK")
    
    print("2. Testing phase2_unified_authority...")
    from core.phase2_unified_authority import get_unified_authority
    print("   ✅ phase2_unified_authority OK")
    
    print("3. Testing fer3on_decision_authority...")
    from core.fer3on_decision_authority import decide_trade
    print("   ✅ fer3on_decision_authority OK")
    
    print("\n4. Attempting main.py import...")
    import main
    print("   ✅ main.py OK")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All imports successful - Phase 2 integration OK")
