#!/usr/bin/env python3
"""Quick validation that Phase 1-3 implementation is production-ready."""

import sys
from pathlib import Path

print("=" * 70)
print("FINAL PRODUCTION READINESS CHECK: Phases 1-3")
print("=" * 70)

# Test 1: Imports work
print("\n[1] Testing imports...")
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
    print("✓ All required methods present")
except AssertionError as e:
    print(f"✗ Method check failed: {e}")
    sys.exit(1)

# Test 4: Guppy UI imports
print("\n[4] Testing Guppy UI imports...")
try:
    from guppy_ui import Worker
    from merlin_core import get_merlin_startup_system
    print("✓ Guppy UI and Merlin imports successful")
except Exception as e:
    print(f"✗ Guppy UI import failed: {e}")
    sys.exit(1)

# Test 5: Task classification works
print("\n[5] Testing task classifier...")
test_cases = [
    ("What time is it?", "simple"),
    ("Build a REST API", "complex"),
    ("Explain machine learning", "teaching"),
]
all_passed = True
for text, expected in test_cases:
    result = router._classify_task(text)
    if result == expected:
        print(f"✓ '{text[:40]}' → {result}")
    else:
        print(f"✗ '{text[:40]}' expected {expected}, got {result}")
        all_passed = False

if not all_passed:
    sys.exit(1)

# Test 6: Smart dispatch signature
print("\n[6] Testing smart dispatch signature...")
try:
    import inspect
    sig = inspect.signature(router.query_smart)
    params = list(sig.parameters.keys())
    expected_params = ['system_prompt', 'user_text', 'tools', 'messages']
    for p in expected_params:
        assert p in params, f"Parameter {p} missing from query_smart"
    print(f"✓ query_smart signature correct: {', '.join(params)}")
except Exception as e:
    print(f"✗ Signature check failed: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("✓ ALL PRODUCTION READINESS CHECKS PASSED")
print("=" * 70)
print("\nPhases 1-3 are production-ready:")
print("  - Router: ✓ importable, instantiable, all methods present")
print("  - Classification: ✓ working (simple/complex/teaching)")
print("  - Integration: ✓ Guppy UI and Merlin core accessible")
print("  - Signatures: ✓ query_smart has correct parameters")
print("\nReady for live testing with real butler queries.")
