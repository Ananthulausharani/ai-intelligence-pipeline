"""
Manual Test Suite for Agent 2 Item Extraction & Freshness Filtering (Step 20).

Tests:
1. Relative article URL becomes absolute URL.
2. Duplicate URLs are removed.
3. JSON-LD datePublished is extracted.
4. JSON-LD JobPosting datePosted is extracted.
5. <time datetime> date extraction works.
6. 'today' / relative date handling works.
7. Missing date returns None rather than collected_at.
8. Fresh item is retained.
9. Stale item is excluded.
10. Future item is excluded.
11. Source URL is preserved separately from item URL.
12. Existing freshness tests still pass (verified via imports).
"""

from datetime import datetime, timezone, timedelta
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.agent2_general_data import (
    GeneralDataAgent,
    normalize_item_url,
    extract_candidate_links,
    extract_publication_date,
    extract_item_metadata,
)
from src.agents.freshness import is_within_24_hours


def run_tests() -> None:
    agent = GeneralDataAgent()
    ref_now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    passes = 0
    total = 12

    print("=" * 60)
    print("STEP 20 — AGENT 2 ITEM EXTRACTION & FRESHNESS TESTS")
    print("=" * 60)

    # -----------------------------------------------------------------
    # Test 1: Relative article URL becomes absolute URL
    # -----------------------------------------------------------------
    rel_url = "/2026/09/11/ai-model-released/"
    base_url = "https://techcrunch.com/category/artificial-intelligence/"
    abs_url = normalize_item_url(rel_url, base_url=base_url)
    assert abs_url == "https://techcrunch.com/2026/09/11/ai-model-released/", f"Expected absolute URL, got {abs_url}"
    print("[PASS] Test 1: Relative article URL correctly becomes absolute URL.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 2: Duplicate URLs are removed
    # -----------------------------------------------------------------
    sample_html = """
    <html><body>
        <a href="/2026/09/11/story-one/">Story 1</a>
        <a href="https://techcrunch.com/2026/09/11/story-one/?utm_source=feed">Story 1 Dup</a>
        <a href="/2026/09/11/story-two/">Story 2</a>
        <a href="/2026/09/11/story-one/#comments">Story 1 Dup Frag</a>
    </body></html>
    """
    links = agent.extract_links(sample_html, base_url, record_type="NEWS", max_items=10)
    assert len(links) == 2, f"Expected 2 unique links, got {len(links)}: {links}"
    assert links[0] == "https://techcrunch.com/2026/09/11/story-one/"
    assert links[1] == "https://techcrunch.com/2026/09/11/story-two/"
    print(f"[PASS] Test 2: Duplicate and tracked URLs deduplicated cleanly ({len(links)} unique URLs).")
    passes += 1

    # -----------------------------------------------------------------
    # Test 3: JSON-LD datePublished is extracted
    # -----------------------------------------------------------------
    html_jsonld_news = """
    <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": "AI Frontier Labs",
            "datePublished": "2026-09-12T08:30:00+00:00"
        }
        </script>
    </head></html>
    """
    date3 = extract_publication_date(html_jsonld_news, record_type="NEWS", now=ref_now)
    assert date3 == "2026-09-12T08:30:00+00:00", f"Expected '2026-09-12T08:30:00+00:00', got {date3}"
    print(f"[PASS] Test 3: JSON-LD NewsArticle datePublished extracted ({date3}).")
    passes += 1

    # -----------------------------------------------------------------
    # Test 4: JSON-LD JobPosting datePosted is extracted
    # -----------------------------------------------------------------
    html_jsonld_job = """
    <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Machine Learning Engineer",
            "datePosted": "2026-09-11T18:00:00Z"
        }
        </script>
    </head></html>
    """
    date4 = extract_publication_date(html_jsonld_job, record_type="JOB", now=ref_now)
    assert date4 == "2026-09-11T18:00:00+00:00", f"Expected '2026-09-11T18:00:00+00:00', got {date4}"
    print(f"[PASS] Test 4: JSON-LD JobPosting datePosted extracted ({date4}).")
    passes += 1

    # -----------------------------------------------------------------
    # Test 5: <time datetime> date extraction works
    # -----------------------------------------------------------------
    html_time = '<html><body><time datetime="2026-09-12T04:15:00-04:00">Sep 12, 2026</time></body></html>'
    date5 = extract_publication_date(html_time, record_type="NEWS", now=ref_now)
    # 04:15-04:00 is 08:15 UTC
    assert date5 == "2026-09-12T08:15:00+00:00", f"Expected '2026-09-12T08:15:00+00:00', got {date5}"
    print(f"[PASS] Test 5: <time datetime> extracted and normalized to UTC ({date5}).")
    passes += 1

    # -----------------------------------------------------------------
    # Test 6: 'today' / relative date handling works
    # -----------------------------------------------------------------
    html_rel = '<html><body><span class="post-date">today</span></body></html>'
    date6 = extract_publication_date(html_rel, record_type="NEWS", now=ref_now)
    assert date6 == "2026-09-12T12:00:00+00:00", f"Expected ref_now for 'today', got {date6}"

    html_rel2 = '<html><body><div class="job-date">5 hours ago</div></body></html>'
    date6b = extract_publication_date(html_rel2, record_type="JOB", now=ref_now)
    expected6b = (ref_now - timedelta(hours=5)).isoformat()
    assert date6b == expected6b, f"Expected {expected6b}, got {date6b}"
    print(f"[PASS] Test 6: Relative dates ('today', '5 hours ago') correctly parsed.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 7: Missing date returns None rather than collected_at
    # -----------------------------------------------------------------
    html_nodate = '<html><body><h1>Breaking AI Discovery</h1><p>No date metadata anywhere.</p></body></html>'
    meta7 = agent.extract_metadata(html_nodate, "https://example.com/article", base_url, "NEWS", now=ref_now)
    assert meta7["content"]["published_date"] is None, f"Expected None, got {meta7['content']['published_date']}"
    assert meta7["collected_at"] is not None, "collected_at must be populated"
    assert meta7["content"]["published_date"] != meta7["collected_at"], "Must NOT use collected_at as published_date"
    print("[PASS] Test 7: Missing date returns None and does not invent or substitute collected_at.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 8: Fresh item is retained (<= 24h)
    # -----------------------------------------------------------------
    html_fresh = """
    <html><head>
        <meta property="article:published_time" content="2026-09-12T02:00:00Z">
        <meta property="og:title" content="Fresh AI News">
    </head></html>
    """
    meta8 = agent.extract_metadata(html_fresh, "https://example.com/fresh", base_url, "NEWS", now=ref_now)
    is_fresh8, reason8 = agent.evaluate_freshness(meta8, now=ref_now)
    assert is_fresh8 is True and reason8 == "fresh", f"Expected fresh, got {is_fresh8}, {reason8}"
    print("[PASS] Test 8: Item published 10 hours ago is correctly retained as fresh.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 9: Stale item is excluded (> 24h)
    # -----------------------------------------------------------------
    html_stale = """
    <html><head>
        <meta property="article:published_time" content="2026-09-10T12:00:00Z">
        <meta property="og:title" content="Stale AI News">
    </head></html>
    """
    meta9 = agent.extract_metadata(html_stale, "https://example.com/stale", base_url, "NEWS", now=ref_now)
    is_fresh9, reason9 = agent.evaluate_freshness(meta9, now=ref_now)
    assert is_fresh9 is False and reason9 == "stale", f"Expected stale, got {is_fresh9}, {reason9}"
    print("[PASS] Test 9: Item published 48 hours ago is correctly excluded as stale.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 10: Future item is excluded
    # -----------------------------------------------------------------
    html_future = """
    <html><head>
        <meta property="article:published_time" content="2026-09-13T12:00:00Z">
        <meta property="og:title" content="Future AI News">
    </head></html>
    """
    meta10 = agent.extract_metadata(html_future, "https://example.com/future", base_url, "NEWS", now=ref_now)
    is_fresh10, reason10 = agent.evaluate_freshness(meta10, now=ref_now)
    assert is_fresh10 is False and reason10 == "future", f"Expected future, got {is_fresh10}, {reason10}"
    print("[PASS] Test 10: Item with future timestamp is correctly excluded.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 11: Source URL is preserved separately from item URL
    # -----------------------------------------------------------------
    item_url = "https://techcrunch.com/2026/09/11/new-startup-round/"
    rec11 = agent.extract_metadata(html_fresh, item_url, base_url, "NEWS", now=ref_now)
    assert rec11["source"]["url"] == base_url, f"Expected source.url == {base_url}, got {rec11['source']['url']}"
    assert rec11["content"]["url"] == item_url, f"Expected content.url == {item_url}, got {rec11['content']['url']}"
    assert rec11["source"]["url"] != rec11["content"]["url"], "source.url must differ from content.url"
    print(f"[PASS] Test 11: Source URL ({rec11['source']['url']}) preserved separately from Item URL ({rec11['content']['url']}).")
    passes += 1

    # -----------------------------------------------------------------
    # Test 12: Existing freshness tests still pass
    # -----------------------------------------------------------------
    assert is_within_24_hours("2026-09-12T11:00:00Z", now=ref_now) is True
    assert is_within_24_hours("2026-09-11T11:00:00Z", now=ref_now) is False
    assert is_within_24_hours(None, now=ref_now) is False
    assert is_within_24_hours("invalid", now=ref_now) is False
    print("[PASS] Test 12: Core freshness utility behavior fully verified.")
    passes += 1

    print("=" * 60)
    print(f"RESULTS: {passes}/{total} tests passed. Status: ALL PASS")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
