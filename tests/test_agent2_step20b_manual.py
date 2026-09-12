"""
Step 20B Verification Test Suite — Fix Phase II Source Extraction, CSR Jobs, MIT Tech Review, and Date Handling.

Tests:
1. RemoteOK rendered HTML → individual job links extracted
2. WorkingNomads rendered HTML → individual job links extracted
3. Jobspresso rendered HTML → individual job links extracted
4. Navigation/category links are rejected
5. Duplicate job URLs are removed
6. MIT Technology Review rendered HTML → article links extracted
7. MIT Technology Review rendering failure does not crash the pipeline
8. Built In date-only value remains date-only / does not receive a fabricated time
9. Existing strict freshness behavior remains unchanged
10. Source URL and item URL remain separate and traceable
"""

import asyncio
from datetime import datetime, timezone, timedelta
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.agent1_scraper import IntelligentScrapingAgent, _needs_csr_job_fallback
from src.agents.agent2_general_data import (
    GeneralDataAgent,
    extract_candidate_links,
    extract_date_info,
    extract_publication_date,
    extract_item_metadata,
    normalize_item_url,
)
from src.agents.freshness import is_within_24_hours


def run_step_20b_tests() -> None:
    agent = GeneralDataAgent()
    ref_now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=timezone.utc)
    passes = 0
    total = 10

    print("=" * 65)
    print("STEP 20B — SOURCE EXTRACTION, CSR JOBS & DATE TESTS")
    print("=" * 65)

    # -----------------------------------------------------------------
    # Test 1: RemoteOK rendered HTML → individual job links extracted
    # -----------------------------------------------------------------
    remoteok_html = """
    <html><body>
        <table>
            <tr class="job" id="job-1137309">
                <a href="/remote-jobs/remote-ai-response-analyst-imerit-technology-1137309">AI Response Analyst</a>
            </tr>
            <tr class="job" id="job-1132152">
                <a href="/remote-jobs/remote-data-annotator-curasenseai-1132152">Data Annotator</a>
            </tr>
            <!-- Category and nav links to reject -->
            <a href="/remote-jobs-in-france">Remote Jobs in France</a>
            <a href="/remote-ai+content-writing-jobs">AI Content Jobs</a>
            <a href="/login">Login</a>
        </table>
    </body></html>
    """
    links1 = agent.extract_links(remoteok_html, "https://remoteok.com/remote-ai-jobs", "JOB", max_items=10)
    assert len(links1) == 2, f"Expected 2 job links, got {len(links1)}: {links1}"
    assert "https://remoteok.com/remote-jobs/remote-ai-response-analyst-imerit-technology-1137309" in links1
    assert "https://remoteok.com/remote-jobs/remote-data-annotator-curasenseai-1132152" in links1
    print("[PASS] Test 1: RemoteOK rendered HTML correctly extracts individual job links.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 2: WorkingNomads rendered HTML → individual job links extracted
    # -----------------------------------------------------------------
    workingnomads_html = """
    <html><body>
        <div class="job-list">
            <a href="/jobs/senior-ai-engineer-lemonio-1797731">Senior AI Engineer</a>
            <a href="/jobs/ai-image-evaluation-analyst-imerit-technology">AI Image Analyst</a>
            <!-- Nav & filter links to reject -->
            <a href="/jobs">Browse All Jobs</a>
            <a href="/remote-uk-jobs">UK Jobs</a>
            <a href="/companies-hiring-remote-workers">Companies</a>
            <a href="/jobs/css/main.css">CSS file</a>
        </div>
    </body></html>
    """
    links2 = agent.extract_links(workingnomads_html, "https://www.workingnomads.com/remote-ai-jobs", "JOB", max_items=10)
    assert len(links2) == 2, f"Expected 2 job links, got {len(links2)}: {links2}"
    assert "https://www.workingnomads.com/jobs/senior-ai-engineer-lemonio-1797731" in links2
    assert "https://www.workingnomads.com/jobs/ai-image-evaluation-analyst-imerit-technology" in links2
    print("[PASS] Test 2: WorkingNomads rendered HTML correctly extracts individual job links.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 3: Jobspresso rendered HTML → individual job links extracted
    # -----------------------------------------------------------------
    jobspresso_html = """
    <html><body>
        <ul class="job_listings">
            <a href="/job/principal-product-manager-conversational-ai/">Principal PM</a>
            <a href="/job/senior-full-stack-engineer-realtime-voice/">Senior Full Stack</a>
            <!-- Category and nav links to reject -->
            <a href="/remote-work/">All Remote Work</a>
            <a href="/remote-ai-data-jobs/">AI & Data Jobs</a>
            <a href="/my-account">My Account</a>
        </ul>
    </body></html>
    """
    links3 = agent.extract_links(jobspresso_html, "https://jobspresso.co/remote-work/", "JOB", max_items=10)
    assert len(links3) == 2, f"Expected 2 job links, got {len(links3)}: {links3}"
    assert "https://jobspresso.co/job/principal-product-manager-conversational-ai/" in links3
    assert "https://jobspresso.co/job/senior-full-stack-engineer-realtime-voice/" in links3
    print("[PASS] Test 3: Jobspresso rendered HTML correctly extracts individual job links.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 4: Navigation/category links are rejected
    # -----------------------------------------------------------------
    nav_html = """
    <html><body>
        <a href="/login">Login</a>
        <a href="/sign-up">Sign Up</a>
        <a href="/privacy-policy">Privacy</a>
        <a href="/terms-of-service">Terms</a>
        <a href="/remote-jobs-in-france">Category France</a>
        <a href="/remote-ai-data-jobs/">Category AI</a>
        <a href="/remote-work/">Remote Work Tag</a>
        <a href="/jobs/senior-ai-engineer-lemonio-1797731">Valid Job</a>
    </body></html>
    """
    links4 = agent.extract_links(nav_html, "https://www.workingnomads.com/remote-ai-jobs", "JOB", max_items=10)
    assert len(links4) == 1, f"Expected exactly 1 valid link, got {len(links4)}: {links4}"
    assert links4[0] == "https://www.workingnomads.com/jobs/senior-ai-engineer-lemonio-1797731"
    print("[PASS] Test 4: Navigational, legal, filter, and category links are rejected.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 5: Duplicate job URLs are removed
    # -----------------------------------------------------------------
    dup_html = """
    <html><body>
        <a href="/remote-jobs/remote-ai-analyst-12345">Job 1</a>
        <a href="/remote-jobs/remote-ai-analyst-12345?utm_source=rss">Job 1 with UTM</a>
        <a href="/remote-jobs/remote-ai-analyst-12345#apply">Job 1 with Hash</a>
        <a href="/remote-jobs/remote-backend-dev-67890">Job 2</a>
    </body></html>
    """
    links5 = agent.extract_links(dup_html, "https://remoteok.com/remote-ai-jobs", "JOB", max_items=10)
    assert len(links5) == 2, f"Expected 2 deduplicated links, got {len(links5)}: {links5}"
    print("[PASS] Test 5: Duplicate URLs with query/fragment variations are deduplicated cleanly.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 6: MIT Technology Review rendered HTML → article links extracted
    # -----------------------------------------------------------------
    mit_html = """
    <html><body>
        <a href="/2026/09/11/1143936/roundtables-will-ai-really-kill-us-all/">Roundtables: AI</a>
        <a href="/2026/09/08/1143747/what-openais-latest-controversy-tells-us-about-the-future-of-math/">Math Controversy</a>
        <a href="/topic/artificial-intelligence/">Category Link</a>
        <a href="/subscribe?itm_source=nav">Subscribe</a>
    </body></html>
    """
    links6 = agent.extract_links(mit_html, "https://www.technologyreview.com/topic/artificial-intelligence/", "NEWS", max_items=10)
    assert len(links6) == 2, f"Expected 2 article links, got {len(links6)}: {links6}"
    assert "https://www.technologyreview.com/2026/09/11/1143936/roundtables-will-ai-really-kill-us-all/" in links6
    assert "https://www.technologyreview.com/2026/09/08/1143747/what-openais-latest-controversy-tells-us-about-the-future-of-math/" in links6
    print("[PASS] Test 6: MIT Technology Review article links correctly identified and normalized.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 7: MIT Technology Review rendering failure does not crash pipeline
    # -----------------------------------------------------------------
    empty_html = ""
    links7 = agent.extract_links(empty_html, "https://www.technologyreview.com/topic/artificial-intelligence/", "NEWS", max_items=10)
    assert links7 == [], f"Expected empty list on failed crawl, got {links7}"
    print("[PASS] Test 7: Empty or failed crawl returns clean empty result without crashing.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 8: Built In date-only value remains date-only / does not receive fabricated time
    # -----------------------------------------------------------------
    builtin_html = """
    <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "AI Strategist",
            "datePosted": "2026-09-11"
        }
        </script>
    </head></html>
    """
    date8, is_date_only8 = extract_date_info(builtin_html, record_type="JOB", now=ref_now)
    assert is_date_only8 is True, f"Expected is_date_only=True, got {is_date_only8}"
    assert date8 == "2026-09-11T00:00:00+00:00", f"Expected standard UTC midnight ISO string, got {date8}"

    meta8 = agent.extract_metadata(builtin_html, "https://builtin.com/job/ai/123", "https://builtin.com/jobs", "JOB", now=ref_now)
    assert meta8["content"]["is_date_only"] is True, "Expected is_date_only=True in record content"
    print("[PASS] Test 8: Built In date-only value is preserved without fabricated time-of-day.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 9: Existing strict freshness behavior remains unchanged
    # -----------------------------------------------------------------
    # Exact timestamp <= 24h -> True
    assert is_within_24_hours("2026-09-12T00:00:00Z", now=ref_now) is True
    # Date-only 2026-09-11 evaluated at 2026-09-12 12:00 UTC is 36 hours old -> False
    assert is_within_24_hours("2026-09-11", now=ref_now) is False
    # Missing / None -> False
    assert is_within_24_hours(None, now=ref_now) is False
    # Future timestamp -> False
    assert is_within_24_hours("2026-09-13T12:00:00Z", now=ref_now) is False
    print("[PASS] Test 9: Strict 24-hour freshness behavior is strictly verified.")
    passes += 1

    # -----------------------------------------------------------------
    # Test 10: Source URL and item URL remain separate and traceable
    # -----------------------------------------------------------------
    source_url = "https://remoteok.com/remote-ai-jobs"
    item_url = "https://remoteok.com/remote-jobs/remote-ai-analyst-1137309"
    meta10 = agent.extract_metadata(remoteok_html, item_url, source_url, "JOB", now=ref_now)
    assert meta10["source"]["url"] == source_url, f"Expected source.url == {source_url}"
    assert meta10["content"]["url"] == item_url, f"Expected content.url == {item_url}"
    assert meta10["source"]["url"] != meta10["content"]["url"]
    print(f"[PASS] Test 10: Source URL ({meta10['source']['url']}) and item URL ({meta10['content']['url']}) separate and traceable.")
    passes += 1

    print("=" * 65)
    print(f"RESULTS: {passes}/{total} tests passed. Status: ALL PASS")
    print("=" * 65)


if __name__ == "__main__":
    run_step_20b_tests()
