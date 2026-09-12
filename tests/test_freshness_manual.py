"""
Manual verification script for 24-hour freshness utility (Step 16).

Tests boundary conditions, timezone normalization, and format parsing
against a fixed reference timestamp: 2026-09-12T12:00:00Z.

Run from project root:
    python tests/test_freshness_manual.py
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.freshness import is_within_24_hours, normalize_datetime

REFERENCE_NOW = "2026-09-12T12:00:00Z"


def run_tests() -> bool:
    test_cases = [
        # (name, published_at, expected_result, note)
        (
            "Test 1: Exactly 1 hour old",
            "2026-09-12T11:00:00Z",
            True,
            "1 hour before reference (within 24h)",
        ),
        (
            "Test 2: Exactly 23 hours old",
            "2026-09-11T13:00:00Z",
            True,
            "23 hours before reference (within 24h)",
        ),
        (
            "Test 3: Exactly 24 hours old",
            "2026-09-11T12:00:00Z",
            True,
            "Exact 24-hour boundary (inclusive)",
        ),
        (
            "Test 4: 24 hours + 1 second old",
            "2026-09-11T11:59:59Z",
            False,
            "1 second beyond 24-hour boundary (excluded)",
        ),
        (
            "Test 5: Future timestamp",
            "2026-09-12T13:00:00Z",
            False,
            "1 hour in the future (excluded)",
        ),
        (
            "Test 6a: Missing timestamp (None)",
            None,
            False,
            "Missing/None value returns False",
        ),
        (
            "Test 6b: Empty timestamp string",
            "",
            False,
            "Empty string returns False",
        ),
        (
            "Test 7: Invalid timestamp",
            "not-a-valid-date",
            False,
            "Unparseable string returns False",
        ),
        (
            "Test 8: ISO timestamp with +05:30 timezone",
            "2026-09-12T16:30:00+05:30",
            True,
            "16:30+05:30 converts to 11:00Z (1h old -> True)",
        ),
        (
            "Test 9: ISO timestamp ending in Z",
            "2026-09-12T10:00:00Z",
            True,
            "Standard ISO ending in Z (2h old -> True)",
        ),
        (
            "Test 10a: Date-only value (today)",
            "2026-09-12",
            True,
            "Date 2026-09-12 normalized to 00:00:00Z (12h old -> True)",
        ),
        (
            "Test 10b: Date-only value (stale)",
            "2026-09-10",
            False,
            "Date 2026-09-10 normalized to 00:00:00Z (60h old -> False)",
        ),
    ]

    total_tests = len(test_cases)
    passed_count = 0
    failed_count = 0

    for name, pub_at, expected, note in test_cases:
        actual = is_within_24_hours(pub_at, now=REFERENCE_NOW)
        if actual == expected:
            passed_count += 1
            print(f"[PASS] {name} -> returned {actual} ({note})")
        else:
            failed_count += 1
            print(f"[FAIL] {name} -> expected {expected}, got {actual} ({note})")

    all_passed = failed_count == 0

    print("\n=== FRESHNESS TEST ===")
    print(f"Tests: {total_tests}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Status: {'PASS' if all_passed else 'FAIL'}")

    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
