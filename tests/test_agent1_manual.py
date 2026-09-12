"""
Manual verification script for Agent 1 (IntelligentScrapingAgent).

Run from the project root:
    python -m tests.test_agent1_manual
or:
    python tests/test_agent1_manual.py
"""

import asyncio
import sys
import os

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.agent1_scraper import IntelligentScrapingAgent

URLS = [
    "https://example.com",
    "https://httpbin.org/html",
    "https://httpbin.org/status/404",
]


async def main() -> None:
    agent = IntelligentScrapingAgent()

    print("=" * 60)
    print("Agent 1 — Manual Verification")
    print("=" * 60)
    print(f"Testing {len(URLS)} URL(s)...\n")

    results = await agent.scrape(URLS)

    for r in results:
        html_len = len(r["html"]) if r["html"] else 0
        print(f"URL          : {r['url']}")
        print(f"  status_code: {r['status_code']}")
        print(f"  success    : {r['success']}")
        print(f"  used_browser: {r['used_browser']}")
        print(f"  html length: {html_len} chars")
        print(f"  error      : {r['error']}")
        print()

    # Summary
    total = len(results)
    succeeded = sum(1 for r in results if r["success"])
    failed = total - succeeded
    browser_used = sum(1 for r in results if r["used_browser"])

    print("-" * 60)
    print("Summary")
    print("-" * 60)
    print(f"  Total URLs      : {total}")
    print(f"  Successful      : {succeeded}")
    print(f"  Failed          : {failed}")
    print(f"  Browser fallback: {browser_used}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
