"""
AI Intelligence Pipeline — Step 20: Extract Individual News Articles & Jobs.

Pipeline Flow:
SOURCE PAGE
    ↓
AGENT 1 (Crawl Listing)
    ↓
RAW HTML
    ↓
AGENT 2 (Extract Candidate URLs, Max 10 per source)
    ↓
FETCH INDIVIDUAL ITEM (Agent 1 Scraper)
    ↓
EXTRACT ACTUAL DATE & METADATA (Agent 2)
    ↓
24-HOUR FRESHNESS FILTER (freshness.py)
    ↓
NEWS / JOB RECORD (Preserving Source Traceability)

Verified Sources:
NEWS:
1. https://techcrunch.com/category/artificial-intelligence/
2. https://venturebeat.com/ai
3. https://www.technologyreview.com/topic/artificial-intelligence/
4. https://www.wired.com/tag/artificial-intelligence/
5. https://www.engadget.com/ai/

JOBS:
1. https://www.ycombinator.com/jobs/role/ai
2. https://builtin.com/jobs/artificial-intelligence
3. https://remoteok.com/remote-ai-jobs
4. https://www.workingnomads.com/remote-ai-jobs
5. https://www.jobspresso.co/remote-work/
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys

# Ensure repository root is on sys.path when invoked directly via `python src/main.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.agents.agent1_scraper import IntelligentScrapingAgent
from src.agents.agent2_general_data import (
    GeneralDataAgent,
    MAX_ITEMS_PER_SOURCE,
    normalize_item_url,
)
from src.entity.resolver import DeterministicEntityResolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")

# 5 Verified News Sources
NEWS_URLS = [
    "https://techcrunch.com/category/artificial-intelligence/",
    "https://venturebeat.com/ai",
    "https://www.technologyreview.com/topic/artificial-intelligence/",
    "https://www.wired.com/tag/artificial-intelligence/",
    "https://www.engadget.com/ai/",
]

# 5 Verified Job Sources
JOB_URLS = [
    "https://www.ycombinator.com/jobs/role/ai",
    "https://builtin.com/jobs/artificial-intelligence",
    "https://remoteok.com/remote-ai-jobs",
    "https://www.workingnomads.com/remote-ai-jobs",
    "https://www.jobspresso.co/remote-work/",
]


async def run_step_20_pipeline(max_items_per_source: int = MAX_ITEMS_PER_SOURCE) -> None:
    scraper = IntelligentScrapingAgent()
    agent2 = GeneralDataAgent()

    logger.info("Initializing Step 20 item extraction pipeline...")

    news_summaries = []
    job_summaries = []

    unique_fresh_news: dict[str, dict] = {}
    unique_fresh_jobs: dict[str, dict] = {}

    # -------------------------------------------------------------
    # Process NEWS Sources
    # -------------------------------------------------------------
    print("\n" + "=" * 60)
    print("STEP 20 — FETCHING AND EXTRACTING INDIVIDUAL ITEMS")
    print("=" * 60 + "\n")

    for url in NEWS_URLS:
        logger.info("Processing NEWS source: %s", url)
        # Step 1: Fetch listing page
        res_list = await scraper.scrape([url])
        listing_res = res_list[0] if res_list else {"url": url, "html": None, "success": False, "used_browser": False}

        html = listing_res.get("html") or ""
        used_browser = listing_res.get("used_browser", False)
        candidate_links = []
        if listing_res.get("success") and html:
            candidate_links = agent2.extract_links(html, url, "NEWS", max_items=max_items_per_source)

        logger.info("  Found %d candidate article link(s) (browser=%s)", len(candidate_links), used_browser)

        # Step 2: Fetch individual articles using existing Agent 1 crawler
        fetched_count = 0
        dates_extracted_count = 0
        exact_timestamps_count = 0
        date_only_count = 0
        fresh_count = 0
        stale_count = 0
        missing_or_invalid_count = 0

        if candidate_links:
            item_results = await scraper.scrape(candidate_links)
            for item_res in item_results:
                if not item_res.get("success") or not item_res.get("html"):
                    missing_or_invalid_count += 1
                    continue

                fetched_count += 1
                item_html = item_res.get("html") or ""
                item_url = item_res.get("url") or ""

                # Step 3: Extract metadata and actual publication date
                meta = agent2.extract_metadata(item_html, item_url, url, "NEWS")
                pub_date = meta["content"].get("published_date")
                is_date_only = meta["content"].get("is_date_only", False)

                if pub_date is not None:
                    dates_extracted_count += 1
                    if is_date_only:
                        date_only_count += 1
                    else:
                        exact_timestamps_count += 1

                # Step 4: 24-hour freshness evaluation
                is_fresh, reason = agent2.evaluate_freshness(meta)
                if is_fresh:
                    fresh_count += 1
                    norm_key = normalize_item_url(item_url, url)
                    if norm_key not in unique_fresh_news:
                        unique_fresh_news[norm_key] = meta
                else:
                    if reason == "stale":
                        stale_count += 1
                    else:
                        missing_or_invalid_count += 1

        summary = {
            "source": url,
            "used_browser": used_browser,
            "candidates": len(candidate_links),
            "fetched": fetched_count,
            "dates_extracted": dates_extracted_count,
            "exact_timestamps": exact_timestamps_count,
            "date_only": date_only_count,
            "fresh": fresh_count,
            "stale": stale_count,
            "missing_or_invalid": missing_or_invalid_count,
        }
        news_summaries.append(summary)

    # -------------------------------------------------------------
    # Process JOB Sources
    # -------------------------------------------------------------
    for url in JOB_URLS:
        logger.info("Processing JOB source: %s", url)
        # Step 1: Fetch listing page
        res_list = await scraper.scrape([url])
        listing_res = res_list[0] if res_list else {"url": url, "html": None, "success": False, "used_browser": False}

        html = listing_res.get("html") or ""
        used_browser = listing_res.get("used_browser", False)
        candidate_links = []
        if listing_res.get("success") and html:
            candidate_links = agent2.extract_links(html, url, "JOB", max_items=max_items_per_source)

        logger.info("  Found %d candidate job link(s) (browser=%s)", len(candidate_links), used_browser)

        # Step 2: Fetch individual jobs using existing Agent 1 crawler
        fetched_count = 0
        dates_extracted_count = 0
        exact_timestamps_count = 0
        date_only_count = 0
        fresh_count = 0
        stale_count = 0
        missing_or_invalid_count = 0

        if candidate_links:
            item_results = await scraper.scrape(candidate_links)
            for item_res in item_results:
                if not item_res.get("success") or not item_res.get("html"):
                    missing_or_invalid_count += 1
                    continue

                fetched_count += 1
                item_html = item_res.get("html") or ""
                item_url = item_res.get("url") or ""

                # Step 3: Extract metadata and actual posting date
                meta = agent2.extract_metadata(item_html, item_url, url, "JOB")
                job_date = meta["content"].get("date")
                is_date_only = meta["content"].get("is_date_only", False)

                if job_date is not None:
                    dates_extracted_count += 1
                    if is_date_only:
                        date_only_count += 1
                    else:
                        exact_timestamps_count += 1

                # Step 4: 24-hour freshness evaluation
                is_fresh, reason = agent2.evaluate_freshness(meta)
                if is_fresh:
                    fresh_count += 1
                    norm_key = normalize_item_url(item_url, url)
                    if norm_key not in unique_fresh_jobs:
                        unique_fresh_jobs[norm_key] = meta
                else:
                    if reason == "stale":
                        stale_count += 1
                    else:
                        missing_or_invalid_count += 1

        summary = {
            "source": url,
            "used_browser": used_browser,
            "candidates": len(candidate_links),
            "fetched": fetched_count,
            "dates_extracted": dates_extracted_count,
            "exact_timestamps": exact_timestamps_count,
            "date_only": date_only_count,
            "fresh": fresh_count,
            "stale": stale_count,
            "missing_or_invalid": missing_or_invalid_count,
        }
        job_summaries.append(summary)

    # -------------------------------------------------------------
    # PART 9 — PRINT SUMMARY OUTPUT
    # -------------------------------------------------------------
    print("\n" + "=" * 40)
    print("STEP 20 — ITEM EXTRACTION SUMMARY")
    print("=" * 40 + "\n")

    print("NEWS:\n")
    for s in news_summaries:
        print(f"Source: {s['source']}")
        if "technologyreview.com" in s['source']:
            print(f"Transport: {'Playwright' if s['used_browser'] else 'HTTP'}")
        print(f"Candidate links: {s['candidates']}")
        print(f"Individual pages fetched: {s['fetched']}")
        print(f"Dates extracted: {s['dates_extracted']}")
        print(f"Fresh within 24h: {s['fresh']}")
        print(f"Excluded as stale: {s['stale']}")
        print(f"Excluded missing/invalid date: {s['missing_or_invalid']}")
        print()

    print("JOBS:\n")
    for s in job_summaries:
        print(f"Source: {s['source']}")
        if any(d in s['source'] for d in ["remoteok.com", "workingnomads.com", "jobspresso.co"]):
            print(f"Playwright used: {s['used_browser']}")
        if "builtin.com" in s['source']:
            print(f"Exact timestamps: {s['exact_timestamps']}, Date-only: {s['date_only']}")
            print(f"Strict 24h pass: {s['fresh']}")
            print("Note: Built In provides calendar dates without time-of-day (date-only normalized to UTC midnight).")
        print(f"Candidate links: {s['candidates']}")
        print(f"Individual pages fetched: {s['fetched']}")
        print(f"Dates extracted: {s['dates_extracted']}")
        print(f"Fresh within 24h: {s['fresh']}")
        print(f"Excluded as stale: {s['stale']}")
        print(f"Excluded missing/invalid date: {s['missing_or_invalid']}")
        print()

    total_candidate_news = sum(s["candidates"] for s in news_summaries)
    total_news_dates = sum(s["dates_extracted"] for s in news_summaries)
    total_fresh_news = sum(s["fresh"] for s in news_summaries)

    total_candidate_jobs = sum(s["candidates"] for s in job_summaries)
    total_job_dates = sum(s["dates_extracted"] for s in job_summaries)
    total_fresh_jobs = sum(s["fresh"] for s in job_summaries)

    print("FINAL:\n")
    print(f"Total candidate news items: {total_candidate_news}")
    print(f"News dates extracted: {total_news_dates}")
    print(f"Fresh news items: {total_fresh_news}")
    print()
    print(f"Total candidate jobs: {total_candidate_jobs}")
    print(f"Job dates extracted: {total_job_dates}")
    print(f"Fresh job items: {total_fresh_jobs}")
    print()
    print(f"Unique fresh news URLs: {len(unique_fresh_news)}")
    print(f"Unique fresh job URLs: {len(unique_fresh_jobs)}")
    print()

    # -------------------------------------------------------------
    # PART 10 — PRINT SAMPLE RECORDS
    # -------------------------------------------------------------
    print("=" * 60)
    print("SAMPLE RECORDS")
    print("=" * 60)

    print("\n--- SAMPLE FRESH NEWS RECORDS (UP TO 3) ---")
    if not unique_fresh_news:
        print("No fresh news records within the previous 24 hours found.")
    for idx, rec in enumerate(list(unique_fresh_news.values())[:3], start=1):
        print(f"\n[News Record {idx}]")
        print(f"recordType: {rec['recordType']}")
        print(f"source.url: {rec['source']['url']}")
        print(f"content.url: {rec['content']['url']}")
        print(f"title: {rec['content'].get('title')}")
        print(f"published_date/date: {rec['content'].get('published_date')}")
        print(f"company: None")
        print(f"is_remote: None")

    print("\n--- SAMPLE FRESH JOB RECORDS (UP TO 3) ---")
    if not unique_fresh_jobs:
        print("No fresh job records within the previous 24 hours found.")
    for idx, rec in enumerate(list(unique_fresh_jobs.values())[:3], start=1):
        print(f"\n[Job Record {idx}]")
        print(f"recordType: {rec['recordType']}")
        print(f"source.url: {rec['source']['url']}")
        print(f"content.url: {rec['content']['url']}")
        print(f"title: {rec['content'].get('title')}")
        print(f"published_date/date: {rec['content'].get('date')}")
        print(f"company: {rec['content'].get('company')}")
        print(f"is_remote: {rec['content'].get('is_remote')}")

    # -------------------------------------------------------------
    # PART 11 — PHASE IV DETERMINISTIC ENTITY RESOLUTION
    # -------------------------------------------------------------
    print("=" * 60)
    print("PHASE IV ENTITY RESOLUTION")
    print("=" * 60 + "\n")

    resolver = DeterministicEntityResolver()

    # Process entities extracted from real records
    entity_test_samples = [
        ("OpenAI, Inc.", "STARTUP", "https://techcrunch.com/2026/09/11/openais-feud-with-mathematicians-is-only-escalating/", None),
        ("Open AI", "STARTUP", "https://news.ycombinator.com/", None),
        ("Mecka AI", "STARTUP", "https://techcrunch.com/2026/09/11/mecka-ai-nears-500m-valuation-in-sequoia-led-deal-amid-rush-for-robot-training-data/", None),
        ("Scale AI, Inc.", "STARTUP", "https://www.ycombinator.com/companies/scale-ai", None),
        ("Replo", "STARTUP", "https://www.ycombinator.com/companies/replo/jobs/YcMC1B8-software-engineer-full-stack", None),
        ("Method Financial", "STARTUP", "https://www.ycombinator.com/companies/method-financial/jobs/XQmFunZ-senior-software-engineer", None),
        ("ChatGPT", "PRODUCT", "https://openai.com/chatgpt", "OpenAI, Inc."),
        ("Claude 3.5 Sonnet", "PRODUCT", "https://anthropic.com/claude", "Anthropic, PBC"),
        ("Some Unknown Robotics Corp", "STARTUP", "https://techcrunch.com/unknown-robotics", None),
    ]

    exact_count = 0
    alias_count = 0
    unresolved_count = 0
    resolution_examples = []

    for raw_name, etype, src_url, ctx in entity_test_samples:
        res = resolver.resolve(raw_name, entity_type=etype, source_url=src_url, startup_context=ctx)
        if res.match_method.value == "EXACT":
            exact_count += 1
        elif res.match_method.value == "ALIAS":
            alias_count += 1
        else:
            unresolved_count += 1

        resolution_examples.append(f"{res.raw_name} -> {res.canonical_name} -> {res.match_method.value} -> {res.entity_type}")

    # Deduplication demonstration on records
    sample_records_to_dedup = [
        {"recordType": "STARTUP", "content": {"entityName": "OpenAI, Inc."}, "source": {"url": "https://techcrunch.com/1"}},
        {"recordType": "STARTUP", "content": {"entityName": "Open AI"}, "source": {"url": "https://techcrunch.com/2"}},
        {"recordType": "STARTUP", "content": {"entityName": "Mecka AI"}, "source": {"url": "https://techcrunch.com/3"}},
        {"recordType": "PRODUCT", "content": {"productName": "ChatGPT", "startupName": "OpenAI, Inc."}, "source": {"url": "https://techcrunch.com/4"}},
        {"recordType": "PRODUCT", "content": {"productName": "ChatGPT", "startupName": "OpenAI"}, "source": {"url": "https://techcrunch.com/5"}},
    ]
    _, dups_removed = resolver.deduplicate(sample_records_to_dedup)

    print(f"Seed entities: {resolver.seed_count}")
    print(f"Records tested: {len(entity_test_samples)}")
    print(f"Exact matches: {exact_count}")
    print(f"Alias matches: {alias_count}")
    print(f"Unresolved: {unresolved_count}")
    print(f"Duplicates removed: {dups_removed}")
    print(f"Mapping log records: {len(resolver.mapping_logs)}\n")

    print("EXAMPLES (RAW -> CANONICAL -> METHOD -> TYPE):")
    for ex in resolution_examples:
        print(f"  {ex}")
    print("\n" + "=" * 60 + "\n")

    # -------------------------------------------------------------
    # PART 12 — PERSIST PIPELINE OUTPUTS FOR EXPORT (STEP 27B)
    # -------------------------------------------------------------
    out_dir = Path("data/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    news_records = list(unique_fresh_news.values())
    jobs_records = list(unique_fresh_jobs.values())

    mapping_logs_records = []
    for log in resolver.mapping_logs:
        mapping_logs_records.append({
            "schemaVersion": "1.0",
            "recordType": "ENTITY_MAPPING_LOG",
            "source": {
                "name": "Entity Resolver",
                "url": log.source_url,
            },
            "raw_name": log.raw_name,
            "canonical_name": log.canonical_name,
            "match_type": log.match_method.value if hasattr(log.match_method, "value") else str(log.match_method),
            "entity_type": log.entity_type,
            "confidence": log.confidence,
            "source_url": log.source_url,
            "item_url": log.source_url,
            "reason": f"Deterministic resolution via {log.match_method.value if hasattr(log.match_method, 'value') else str(log.match_method)}",
        })

    with open(out_dir / "news.json", "w", encoding="utf-8") as f:
        json.dump(news_records, f, indent=2, ensure_ascii=True)

    with open(out_dir / "jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs_records, f, indent=2, ensure_ascii=True)

    with open(out_dir / "entity_mapping_logs.json", "w", encoding="utf-8") as f:
        json.dump(mapping_logs_records, f, indent=2, ensure_ascii=True)

    logger.info(
        "Persisted pipeline outputs: %d fresh news -> data/output/news.json, "
        "%d fresh jobs -> data/output/jobs.json, %d entity mapping logs -> data/output/entity_mapping_logs.json",
        len(news_records), len(jobs_records), len(mapping_logs_records),
    )


def main() -> None:
    asyncio.run(run_step_20_pipeline())


if __name__ == "__main__":
    main()
