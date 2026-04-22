#!/usr/bin/env python3
"""Offline validation tests for smart dispatch classification and routing setup."""

import os

from src.guppy.inference.router import InferenceRouter


def _make_router() -> InferenceRouter:
    previous = os.environ.get("GUPPY_SEMANTIC_CLASSIFIER")
    os.environ["GUPPY_SEMANTIC_CLASSIFIER"] = "0"
    try:
        return InferenceRouter()
    finally:
        if previous is None:
            os.environ.pop("GUPPY_SEMANTIC_CLASSIFIER", None)
        else:
            os.environ["GUPPY_SEMANTIC_CLASSIFIER"] = previous

def test_task_classification():
    """Test task classifier with various butler-style queries."""
    router = _make_router()

    test_cases = [
        # (text, expected_classification)
        ("What time is it?", "simple"),
        ("Remind me to call John at 3pm", "simple"),
        ("Format this text in markdown", "simple"),
        ("Summarize this article", "simple"),
        ("What's on my calendar tomorrow?", "simple"),

        ("Build a Python async function for database pooling", "complex"),
        ("Debug this memory leak in the C++ code", "complex"),
        ("Design a microservices architecture for e-commerce", "complex"),
        ("Research the latest AI alignment papers", "complex"),
        ("Review this code for security vulnerabilities", "complex"),

        ("Explain how diffusion models work", "teaching"),
        ("Teach me about Transformer attention mechanisms", "teaching"),
        ("How does quantum computing differ from classical computing?", "teaching"),
        ("Help me understand OAuth 2.0 flow", "teaching"),
        ("What is zero-knowledge proof?", "teaching"),
    ]

    print("=" * 70)
    print("TASK CLASSIFICATION TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    for text, expected in test_cases:
        result = router._classify_task(text)
        status = "✓" if result == expected else "✗"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status} {text[:50]:50} | Expected: {expected:10} | Got: {result}")

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 70)

    assert failed == 0, f"{failed} classification(s) did not match expected"

def test_task_classification_edge_cases():
    """Test edge cases for task classifier."""
    router = _make_router()

    edge_cases = [
        # Empty/short queries
        ("hi", "simple"),
        ("", "simple"),  # Very short defaults to simple

        # Ambiguous queries (should route safely)
        ("What is a REST API?", "simple"),  # "What is" → simple
        ("Research REST API best practices", "complex"),  # "Research" → complex

        # Mixed keywords
        ("Explain machine learning and build a classifier", "complex"),  # "build" > "explain"
    ]

    print("\n" + "=" * 70)
    print("EDGE CASE TESTS")
    print("=" * 70)

    for text, expected in edge_cases:
        result = router._classify_task(text)
        print(f"  '{text:50}' → {result} (expected {expected})")
        assert result == expected

    print("=" * 70)

def test_router_initialization():
    """Test that router initializes correctly."""
    print("\n" + "=" * 70)
    print("ROUTER INITIALIZATION TEST")
    print("=" * 70)

    try:
        router = _make_router()
        print(f"✓ Router initialized")
        print(f"  - Current primary: {router.current_primary}")
        print(f"  - Anthropic available: {router.anthropic_available}")
        print(f"  - OLLAMA_TIMEOUT: {router.OLLAMA_TIMEOUT}s")
        print(f"  - HAIKU_TIMEOUT_SMART: {router.HAIKU_TIMEOUT_SMART}s")
        print("✓ Router successfully initialized")
    except Exception as e:
        raise AssertionError(f"Router initialization failed: {e}") from e


def test_semantic_classifier_mode_is_instance_stable():
    """Router should keep the classifier mode it was created with."""
    previous = os.environ.get("GUPPY_SEMANTIC_CLASSIFIER")
    os.environ["GUPPY_SEMANTIC_CLASSIFIER"] = "0"
    try:
        router = InferenceRouter()
        os.environ["GUPPY_SEMANTIC_CLASSIFIER"] = "1"
        assert router.semantic_classifier_enabled is False
        assert router._classify_task("Research REST API best practices") == "complex"
    finally:
        if previous is None:
            os.environ.pop("GUPPY_SEMANTIC_CLASSIFIER", None)
        else:
            os.environ["GUPPY_SEMANTIC_CLASSIFIER"] = previous

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PHASE 1 SMART DISPATCH VALIDATION TEST SUITE")
    print("=" * 70)

    # Run tests
    init_ok = test_router_initialization()
    classification_ok = test_task_classification()
    test_task_classification_edge_cases()

    # Summary
    print("\n" + "=" * 70)
    if init_ok and classification_ok:
        print("✓ ALL TESTS PASSED - Phase 1 implementation validated")
    else:
        print("✗ SOME TESTS FAILED - Review implementation")
    print("=" * 70)

    sys.exit(0 if (init_ok and classification_ok) else 1)
