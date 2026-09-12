"""
Manual verification script for Agent 2 (GeneralDataAgent).

Run from the project root:
    python tests/test_agent2_manual.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.agent2_general_data import GeneralDataAgent

# ---------------------------------------------------------------------------
# Mock Agent 1 output
# ---------------------------------------------------------------------------

MOCK_CRAWL_RESULTS = [
    {
        "url": "https://example.com/startup",
        "status_code": 200,
        "html": "<html><body>Example AI Startup</body></html>",
        "success": True,
        "used_browser": False,
        "error": None,
    },
    {
        "url": "https://example.com/product",
        "status_code": 200,
        "html": "<html><body>Example AI Product</body></html>",
        "success": True,
        "used_browser": False,
        "error": None,
    },
    {
        "url": "https://example.com/failed",
        "status_code": 404,
        "html": "",
        "success": False,
        "used_browser": False,
        "error": None,
    },
]


def main() -> None:
    agent = GeneralDataAgent()

    print("=" * 60)
    print("Agent 2 — Manual Verification")
    print("=" * 60)
    print(f"Input records : {len(MOCK_CRAWL_RESULTS)}\n")

    # Pass all mock results as STARTUP for this test.
    # (In production, the caller decides the record type per source.)
    records = agent.process(MOCK_CRAWL_RESULTS, record_type="STARTUP")

    # --- Print each returned record ----------------------------------------
    for i, rec in enumerate(records, start=1):
        print(f"Record {i}:")
        print(f"  record_type  : {rec['record_type']}")
        print(f"  source_url   : {rec['source_url']}")
        print(f"  html length  : {len(rec['html'])} chars")
        print(f"  collected_at : {rec['collected_at']}")
        print()

    # --- Summary ------------------------------------------------------------
    total_in = len(MOCK_CRAWL_RESULTS)
    total_out = len(records)
    ignored = total_in - total_out

    print("-" * 60)
    print("Summary")
    print("-" * 60)
    print(f"  Input records   : {total_in}")
    print(f"  Output records  : {total_out}")
    print(f"  Ignored/failed  : {ignored}")
    print()

    # --- Assertions ---------------------------------------------------------
    assert total_out == 2,          f"Expected 2 output records, got {total_out}"
    assert ignored == 1,            f"Expected 1 ignored record, got {ignored}"

    assert records[0]["source_url"] == "https://example.com/startup", "source_url mismatch"
    assert records[1]["source_url"] == "https://example.com/product", "source_url mismatch"

    assert "Example AI Startup" in records[0]["html"], "HTML not preserved for startup"
    assert "Example AI Product" in records[1]["html"], "HTML not preserved for product"

    assert records[0]["collected_at"], "collected_at missing on record 0"
    assert records[1]["collected_at"], "collected_at missing on record 1"

    print("All assertions passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
