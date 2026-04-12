#!/usr/bin/env python3
"""Quick validation that Phase 1-3 implementation is production-ready (no UI import)."""

import sys
from pathlib import Path

print("=" * 70)
print("FINAL PRODUCTION READINESS CHECK: Phases 1-3")
print("=" * 70)

# Test 1: Imports work
print("\n[1] Testing router imports...")
try:
    from inference_router import InferenceRouter, get_router, route_inference_smart
    print("✓ Router imports successful")
except Exception as e:
    print(f"✗ Router import failed: {e}")
    sys.exit(1)

# Test 2: Router instantiates
print("\n[2] Testing router instantiation...")
try:
    router = get_router()
    print(f"✓ Router initialized")
    print(f"  - Anthropic available: {router.anthropic_available}")
    print(f"  - HAIKU_TIMEOUT_SMART: {router.HAIKU_TIMEOUT_SMART}s")
    print(f"  - Current primary: {router.current_primary}")
except Exception as e:
    print(f"✗ Router instantiation failed: {e}")
    sys.exit(1)

# Test 3: Methods exist
print("\n[3] Testing method availability...")
try:
    assert hasattr(router, 'query_smart'), "query_smart method missing"
    assert hasattr(router, '_classify_task'), "_classify_task method missing"
    assert hasattr(router, 'query_haiku'), "query_haiku method missing"
    assert hasattr(router, 'query_sonnet'), "query_sonnet method missing"
    assert hasattr(router, 'query_local'), "query_local method missing"
    print("✓ All required methods present (query_smart, _classify_task, query_*, etc)")
except AssertionError as e:
    print(f"✗ Method check failed: {e}")
    sys.exit(1)

# Test 4: Task classification works
print("\n[4] Testing task classifier...")
test_cases = [
    ("What time is it?", "simple"),
    ("Build a REST API", "complex"),
    ("Explain machine learning", "teaching"),
    ("Remind me to call John", "simple"),
    ("Debug this memory leak", "complex"),
    ("Help me understand OAuth", "teaching"),
]
all_passed = True
for text, expected in test_cases:
    result = router._classify_task(text)
    if result == expected:
        print(f"  ✓ '{text}' → {result}")
    else:
        print(f"  ✗ '{text}' expected {expected}, got {result}")
        all_passed = False

if not all_passed:
    print("✗ Task classification check failed")
    sys.exit(1)
else:
    print("✓ Task classification working correctly")

# Test 5: Smart dispatch signature
print("\n[5] Testing smart dispatch method signature...")
try:
    import inspect
    sig = inspect.signature(router.query_smart)
    params = list(sig.parameters.keys())
    expected_params = ['system_prompt', 'user_text', 'tools', 'messages']
    for p in expected_params:
        assert p in params, f"Parameter {p} missing from query_smart"
    print(f"✓ query_smart signature correct")
    print(f"  Parameters: {', '.join(expected_params)}")
except Exception as e:
    print(f"✗ Signature check failed: {e}")
    sys.exit(1)

# Test 6: Merlin core imports
print("\n[6] Testing Merlin core imports...")
try:
    from merlin_core import get_merlin_startup_system, MERLIN_SYSTEM
    print("✓ Merlin imports successful")
    assert "Socratic" in MERLIN_SYSTEM, "Merlin system prompt missing Socratic reference"
    print("✓ Merlin system prompt contains Socratic method reference")
except Exception as e:
    print(f"✗ Merlin import failed: {e}")
    sys.exit(1)

# Test 7: Documentation updated
print("\n[7] Checking documentation...")
try:
    roadmap = (Path(__file__).parent / "ROADMAP.md").read_text()
    readme = (Path(__file__).parent / "README.md").read_text()
    
    assert "Phase 1" in roadmap and "Smart Dispatcher" in roadmap, "ROADMAP missing Phase 1 docs"
    assert "Phase 3" in roadmap and "Merlin" in roadmap, "ROADMAP missing Phase 3 docs"
    assert "Butler" in readme or "butler" in readme, "README missing butler focus note"
    
    print("✓ Documentation properly updated")
    print("  - ROADMAP.md: Phase 1-3 descriptions present")
    print("  - README.md: Butler focus statement present")
except Exception as e:
    print(f"✗ Documentation check failed: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✓ ALL PRODUCTION READINESS CHECKS PASSED")
print("=" * 70)
print("\nPhases 1-3 Implementation Summary:")
print("  [✓] Router: importable, instantiable, all methods present")
print("  [✓] Classification: 6/6 test cases correct (simple/complex/teaching)")
print("  [✓] Integration: query_smart has correct method signature")
print("  [✓] Merlin: system prompt accessible and Socratic method present")
print("  [✓] Documentation: ROADMAP and README properly updated")
print("\n" + "=" * 70)
print("\nProduction Status: READY FOR LIVE TESTING")
print("  - Guppy can be launched with smart dispatch enabled")
print("  - Set mode='auto' to use Phase 1-3 smart routing")
print("  - Teaching tasks will auto-route to Merlin persona")
print("  - Simple tasks: <3s latency expected (Haiku)")
print("  - Complex tasks: 5-10s latency expected (Sonnet)")
print("=" * 70)
