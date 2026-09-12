"""
Manual verification script for Agent 3 (ResearchPaperAgent).

Run from the project root:
    python tests/test_agent3_manual.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.agent3_research import ResearchPaperAgent

# ---------------------------------------------------------------------------
# Mock Agent 1 output
# ---------------------------------------------------------------------------

MOCK_CRAWL_RESULTS = [
    {
        "url": "https://arxiv.org/abs/2401.00001",
        "status_code": 200,
        "html": "<html><body>Research paper content</body></html>",
        "success": True,
        "used_browser": False,
        "error": None,
    },
    {
        "url": "https://paperswithcode.com/paper/example-paper",
        "status_code": 200,
        "html": "<html><body>Paper with code content</body></html>",
        "success": True,
        "used_browser": False,
        "error": None,
    },
    {
        "url": "https://arxiv.org/invalid",
        "status_code": 404,
        "html": "",
        "success": False,
        "used_browser": False,
        "error": None,
    },
]


def main() -> None:
    agent = ResearchPaperAgent()

    print("=" * 60)
    print("Agent 3 — Manual Verification")
    print("=" * 60)
    print(f"Input records : {len(MOCK_CRAWL_RESULTS)}\n")

    records = agent.process(MOCK_CRAWL_RESULTS)

    for i, rec in enumerate(records, start=1):
        print(f"Record {i}:")
        print(f"  source_url   : {rec['source_url']}")
        print(f"  html length  : {len(rec['html'])} chars")
        print(f"  collected_at : {rec['collected_at']}")
        print()

    # --- Summary ------------------------------------------------------------
    total_in  = len(MOCK_CRAWL_RESULTS)
    total_out = len(records)
    ignored   = total_in - total_out

    print("-" * 60)
    print("Summary")
    print("-" * 60)
    print(f"  Input records   : {total_in}")
    print(f"  Output records  : {total_out}")
    print(f"  Ignored/failed  : {ignored}")
    print()

    # --- Assertions ---------------------------------------------------------
    assert total_out == 2, \
        f"Expected 2 output records, got {total_out}"
    assert ignored == 1, \
        f"Expected 1 ignored record, got {ignored}"

    assert records[0]["source_url"] == "https://arxiv.org/abs/2401.00001", \
        "source_url mismatch on record 0"
    assert records[1]["source_url"] == "https://paperswithcode.com/paper/example-paper", \
        "source_url mismatch on record 1"

    assert "Research paper content" in records[0]["html"], \
        "HTML not preserved for arXiv record"
    assert "Paper with code content" in records[1]["html"], \
        "HTML not preserved for Papers with Code record"

    assert records[0]["collected_at"], "collected_at missing on record 0"
    assert records[1]["collected_at"], "collected_at missing on record 1"

    print("All assertions passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
