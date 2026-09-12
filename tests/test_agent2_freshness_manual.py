"""
Manual verification script for Agent 2 Freshness Integration (Step 17).

Tests 24-hour freshness filtering on NEWS and JOB records using a fixed
reference timestamp: 2026-09-12T12:00:00Z.

Verifies:
- NEWS freshness: <=24h retained, >24h/future/missing excluded
- JOB freshness: <=24h retained, >24h/future/missing excluded
- STARTUP and PRODUCT unaffected
- Source URLs strictly preserved on all retained records

Run from project root:
    python tests/test_agent2_freshness_manual.py
"""

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.agent2_general_data import GeneralDataAgent

REFERENCE_NOW = "2026-09-12T12:00:00Z"


def test_news_freshness(agent: GeneralDataAgent) -> tuple[int, int]:
    """Test 24-hour freshness filtering for NEWS records."""
    news_inputs = [
        {
            "url": "https://news.example.com/item1-1h-old",
            "status_code": 200,
            "html": "<p>1 hour old news</p>",
            "success": True,
            "published_date": "2026-09-12T11:00:00Z",
        },
        {
            "url": "https://news.example.com/item2-24h-exact",
            "status_code": 200,
            "html": "<p>Exactly 24 hours old news</p>",
            "success": True,
            "published_date": "2026-09-11T12:00:00Z",
        },
        {
            "url": "https://news.example.com/item3-24h1s-old",
            "status_code": 200,
            "html": "<p>24h + 1s old news</p>",
            "success": True,
            "published_date": "2026-09-11T11:59:59Z",
        },
        {
            "url": "https://news.example.com/item4-future",
            "status_code": 200,
            "html": "<p>Future news</p>",
            "success": True,
            "published_date": "2026-09-12T13:00:00Z",
        },
        {
            "url": "https://news.example.com/item5-missing-date",
            "status_code": 200,
            "html": "<p>News without date</p>",
            "success": True,
            "published_date": None,
        },
    ]

    retained = agent.process(news_inputs, record_type="NEWS", now=REFERENCE_NOW)
    total_in = len(news_inputs)
    retained_count = len(retained)
    excluded_count = total_in - retained_count

    # Assertions
    assert retained_count == 2, f"Expected 2 retained NEWS records, got {retained_count}"
    assert excluded_count == 3, f"Expected 3 excluded NEWS records, got {excluded_count}"

    retained_urls = {r["source_url"] for r in retained}
    assert "https://news.example.com/item1-1h-old" in retained_urls, "1h old news was not retained"
    assert "https://news.example.com/item2-24h-exact" in retained_urls, "24h exact news was not retained"
    assert "https://news.example.com/item3-24h1s-old" not in retained_urls, "24h+1s old news was not excluded"
    assert "https://news.example.com/item4-future" not in retained_urls, "Future news was not excluded"
    assert "https://news.example.com/item5-missing-date" not in retained_urls, "Missing date news was not excluded"

    # Verify source URLs and record_type preserved
    for r in retained:
        assert r["record_type"] == "NEWS"
        assert r["source_url"] in retained_urls

    print(f"[PASS] NEWS Freshness: {retained_count} retained, {excluded_count} excluded (from {total_in} inputs)")
    return retained_count, excluded_count


def test_job_freshness(agent: GeneralDataAgent) -> tuple[int, int]:
    """Test 24-hour freshness filtering for JOB records."""
    job_inputs = [
        {
            "url": "https://jobs.example.com/job1-1h-old",
            "status_code": 200,
            "html": "<p>1 hour old job</p>",
            "success": True,
            "date": "2026-09-12T11:00:00Z",
        },
        {
            "url": "https://jobs.example.com/job2-24h-exact",
            "status_code": 200,
            "html": "<p>Exactly 24 hours old job</p>",
            "success": True,
            "date": "2026-09-11T12:00:00Z",
        },
        {
            "url": "https://jobs.example.com/job3-24h1s-old",
            "status_code": 200,
            "html": "<p>24h + 1s old job</p>",
            "success": True,
            "date": "2026-09-11T11:59:59Z",
        },
        {
            "url": "https://jobs.example.com/job4-future",
            "status_code": 200,
            "html": "<p>Future job</p>",
            "success": True,
            "date": "2026-09-12T13:00:00Z",
        },
        {
            "url": "https://jobs.example.com/job5-missing-date",
            "status_code": 200,
            "html": "<p>Job without date</p>",
            "success": True,
            "date": None,
        },
    ]

    retained = agent.process(job_inputs, record_type="JOB", now=REFERENCE_NOW)
    total_in = len(job_inputs)
    retained_count = len(retained)
    excluded_count = total_in - retained_count

    # Assertions
    assert retained_count == 2, f"Expected 2 retained JOB records, got {retained_count}"
    assert excluded_count == 3, f"Expected 3 excluded JOB records, got {excluded_count}"

    retained_urls = {r["source_url"] for r in retained}
    assert "https://jobs.example.com/job1-1h-old" in retained_urls, "1h old job was not retained"
    assert "https://jobs.example.com/job2-24h-exact" in retained_urls, "24h exact job was not retained"
    assert "https://jobs.example.com/job3-24h1s-old" not in retained_urls, "24h+1s old job was not excluded"
    assert "https://jobs.example.com/job4-future" not in retained_urls, "Future job was not excluded"
    assert "https://jobs.example.com/job5-missing-date" not in retained_urls, "Missing date job was not excluded"

    # Verify source URLs and record_type preserved
    for r in retained:
        assert r["record_type"] == "JOB"
        assert r["source_url"] in retained_urls

    print(f"[PASS] JOB Freshness: {retained_count} retained, {excluded_count} excluded (from {total_in} inputs)")
    return retained_count, excluded_count


def test_startup_and_product_unaffected(agent: GeneralDataAgent) -> bool:
    """Verify STARTUP and PRODUCT filtering remain unaffected by publication dates."""
    startup_inputs = [
        {
            "url": "https://example.com/startup-no-date",
            "status_code": 200,
            "html": "<p>Startup with no date</p>",
            "success": True,
        },
        {
            "url": "https://example.com/startup-old-date",
            "status_code": 200,
            "html": "<p>Startup with old date</p>",
            "success": True,
            "published_date": "2020-01-01T00:00:00Z",
        },
    ]

    product_inputs = [
        {
            "url": "https://example.com/product-no-date",
            "status_code": 200,
            "html": "<p>Product with no date</p>",
            "success": True,
        },
        {
            "url": "https://example.com/product-old-date",
            "status_code": 200,
            "html": "<p>Product with old date</p>",
            "success": True,
            "date": "2020-01-01T00:00:00Z",
        },
    ]

    retained_startups = agent.process(startup_inputs, record_type="STARTUP", now=REFERENCE_NOW)
    assert len(retained_startups) == 2, f"Expected 2 STARTUP records, got {len(retained_startups)}"
    assert retained_startups[0]["source_url"] == "https://example.com/startup-no-date"
    assert retained_startups[1]["source_url"] == "https://example.com/startup-old-date"

    retained_products = agent.process(product_inputs, record_type="PRODUCT", now=REFERENCE_NOW)
    assert len(retained_products) == 2, f"Expected 2 PRODUCT records, got {len(retained_products)}"
    assert retained_products[0]["source_url"] == "https://example.com/product-no-date"
    assert retained_products[1]["source_url"] == "https://example.com/product-old-date"

    print("[PASS] STARTUP & PRODUCT behavior: Unaffected by freshness filtering (all valid HTML preserved)")
    return True


def main() -> None:
    print("=" * 60)
    print("Agent 2 — 24-Hour Freshness Manual Verification")
    print("=" * 60)

    agent = GeneralDataAgent()

    news_retained, news_excluded = test_news_freshness(agent)
    job_retained, job_excluded = test_job_freshness(agent)
    test_startup_and_product_unaffected(agent)

    print("\n" + "=" * 60)
    print("=== SUMMARY ===")
    print(f"NEWS records: {news_retained} retained, {news_excluded} excluded")
    print(f"JOB records:  {job_retained} retained, {job_excluded} excluded")
    print("STARTUP / PRODUCT: Fully preserved (unaffected)")
    print("Source URLs: 100% preserved")
    print("Status: ALL PASS")
    print("=" * 60)


if __name__ == "__main__":
    main()
