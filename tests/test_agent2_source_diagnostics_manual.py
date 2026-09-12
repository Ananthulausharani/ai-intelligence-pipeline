"""
Diagnostic Script for Step 20A — Diagnose Source Link Extraction and Job Freshness.

Investigates:
1. Four zero-link sources:
   - MIT Technology Review
   - RemoteOK
   - WorkingNomads
   - Jobspresso
2. Job sources with 0 fresh items:
   - Y Combinator
   - Built In
3. News sources with 0 or few fresh items:
   - VentureBeat
   - Engadget
   - WIRED

DOES NOT modify extraction logic or production code.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import re
import sys
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.agents.agent1_scraper import IntelligentScrapingAgent
from src.agents.agent2_general_data import (
    GeneralDataAgent,
    normalize_item_url,
    extract_publication_date,
)
from src.agents.freshness import is_within_24_hours, normalize_datetime

# Mute noisy crawl logs for clean diagnostics output
logging.basicConfig(level=logging.WARNING)

ZERO_LINK_SOURCES = [
    ("MIT Technology Review", "NEWS", "https://www.technologyreview.com/topic/artificial-intelligence/"),
    ("RemoteOK", "JOB", "https://remoteok.com/remote-ai-jobs"),
    ("WorkingNomads", "JOB", "https://www.workingnomads.com/remote-ai-jobs"),
    ("Jobspresso", "JOB", "https://www.jobspresso.co/remote-work/"),
]

TEN_LINK_SOURCES = [
    ("Y Combinator", "JOB", "https://www.ycombinator.com/jobs/role/ai"),
    ("Built In", "JOB", "https://builtin.com/jobs/artificial-intelligence"),
    ("VentureBeat", "NEWS", "https://venturebeat.com/ai"),
    ("Engadget", "NEWS", "https://www.engadget.com/ai/"),
    ("WIRED", "NEWS", "https://www.wired.com/tag/artificial-intelligence/"),
]


async def diagnose_zero_link_sources(scraper: IntelligentScrapingAgent) -> None:
    print("\n" + "=" * 70)
    print("SECTION 1 — DIAGNOSTICS FOR ZERO-LINK SOURCES")
    print("=" * 70)

    for name, stype, url in ZERO_LINK_SOURCES:
        print(f"\n------------------------------------------------------------")
        print(f"SOURCE: {name} ({stype})")
        print(f"URL: {url}")
        print(f"------------------------------------------------------------")

        res_list = await scraper.scrape([url])
        res = res_list[0] if res_list else {}

        status_code = res.get("status_code")
        used_browser = res.get("used_browser", False)
        success = res.get("success", False)
        error = res.get("error")
        html = res.get("html") or ""
        html_len = len(html)

        print(f"HTTP Status      : {status_code}")
        print(f"Used Browser     : {used_browser}")
        print(f"Crawl Success    : {success}")
        print(f"Crawl Error      : {error}")
        print(f"HTML Length      : {html_len} chars")

        if not html:
            print("No HTML returned (crawl failed or timed out).")
            continue

        soup = BeautifulSoup(html, "html.parser")
        parsed_source = urlparse(url)
        source_domain = parsed_source.netloc.lower()

        # All <a> tags
        anchors = soup.find_all("a", href=True)
        print(f"Total <a> tags   : {len(anchors)}")

        # Anchor analysis
        useful_anchors = []
        same_domain_count = 0
        candidate_path_count = 0
        candidate_href_examples = []

        likely_path_keywords = [
            "/story/", "/job/", "/jobs/", "/remote-jobs/", "/article/",
            "/202", "/2026/", "/ai/", "/news/"
        ]

        for a in anchors:
            raw_href = a.get("href", "").strip()
            norm_href = normalize_item_url(raw_href, base_url=url)
            text = " ".join(a.get_text().split())

            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            parsed_href = urlparse(norm_href if norm_href else raw_href)
            href_domain = parsed_href.netloc.lower()

            is_same_domain = (
                source_domain in href_domain
                or href_domain.endswith("." + source_domain.replace("www.", ""))
                or not href_domain
            )
            if is_same_domain:
                same_domain_count += 1

            p_lower = parsed_href.path.lower()
            is_likely_candidate = is_same_domain and any(kw in p_lower for kw in likely_path_keywords)
            if is_likely_candidate:
                candidate_path_count += 1
                if len(candidate_href_examples) < 6 and (norm_href or raw_href) not in candidate_href_examples:
                    candidate_href_examples.append(norm_href or raw_href)

            if len(useful_anchors) < 15:
                useful_anchors.append((text[:50] if text else "[No text]", raw_href))

        print(f"Same-domain <a>  : {same_domain_count}")
        print(f"Likely path <a>  : {candidate_path_count}")
        print(f"Sample candidate hrefs:")
        if candidate_href_examples:
            for ch in candidate_href_examples:
                print(f"    * {ch}")
        else:
            print("    * (None found)")

        print("\nFirst 15 useful anchor elements (Text -> Href):")
        for idx, (txt, h) in enumerate(useful_anchors, start=1):
            print(f"  {idx:2d}. {txt:<50} -> {h}")

        # JSON-LD inspection
        json_ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
        # Also check with regex in case malformed
        regex_json_ld = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)

        has_json_ld = bool(json_ld_scripts or regex_json_ld)
        print(f"\nJSON-LD Present  : {has_json_ld}")

        all_types = set()
        script_contents = [s.get_text() for s in json_ld_scripts if s.get_text()] or regex_json_ld
        for raw in script_contents:
            try:
                data = json.loads(raw.strip())
                items = []
                if isinstance(data, dict):
                    items.append(data)
                    if "@graph" in data and isinstance(data["@graph"], list):
                        items.extend([x for x in data["@graph"] if isinstance(x, dict)])
                elif isinstance(data, list):
                    items.extend([x for x in data if isinstance(x, dict)])
                for item in items:
                    t = item.get("@type")
                    if t:
                        if isinstance(t, list):
                            all_types.update(t)
                        else:
                            all_types.add(str(t))
            except Exception:
                pass

        print(f"JSON-LD Types    : {sorted(list(all_types)) if all_types else 'None found'}")


async def diagnose_ten_link_sources(scraper: IntelligentScrapingAgent, agent2: GeneralDataAgent) -> None:
    print("\n" + "=" * 70)
    print("SECTION 2 & 3 — DATE & FRESHNESS DIAGNOSTICS FOR EXTRACTED SOURCES")
    print("=" * 70)

    now_utc = datetime.now(timezone.utc)
    print(f"\nCurrent Reference UTC Time: {now_utc.isoformat()}\n")

    for name, stype, url in TEN_LINK_SOURCES:
        print(f"\n============================================================")
        print(f"SOURCE: {name} ({stype})")
        print(f"URL: {url}")
        print(f"============================================================")

        res_list = await scraper.scrape([url])
        listing_res = res_list[0] if res_list else {}
        html = listing_res.get("html") or ""

        candidate_links = agent2.extract_links(html, url, stype, max_items=10)
        print(f"Extracted Candidate Links: {len(candidate_links)}")

        if not candidate_links:
            print("No candidate links found.")
            continue

        item_results = await scraper.scrape(candidate_links)

        print(f"\nInspecting up to {len(item_results)} fetched items:")
        for idx, item in enumerate(item_results, start=1):
            item_url = item.get("url")
            item_html = item.get("html") or ""
            item_success = item.get("success", False)

            if not item_success or not item_html:
                print(f"\n  [{idx}] {item_url}")
                print(f"      Fetch status: FAILED (success={item_success})")
                continue

            meta = agent2.extract_metadata(item_html, item_url, url, stype, now=now_utc)
            soup = BeautifulSoup(item_html, "html.parser")

            # Look up raw date sources for debugging
            raw_meta_pub = None
            for p in ["article:published_time", "og:article:published_time", "parsely-pub-date"]:
                tag = soup.find("meta", attrs={"property": p}) or soup.find("meta", attrs={"name": p})
                if tag and tag.get("content"):
                    raw_meta_pub = (p, tag.get("content"))
                    break

            raw_time_tag = soup.find("time")
            time_dt_val = (raw_time_tag.get("datetime"), raw_time_tag.get_text(strip=True)) if raw_time_tag else None

            # Extracted publication/posting date
            if stype == "NEWS":
                extracted_date = meta["content"].get("published_date")
            else:
                extracted_date = meta["content"].get("date")

            norm_dt = normalize_datetime(extracted_date)
            is_fresh = is_within_24_hours(extracted_date, now=now_utc)

            age_str = "N/A"
            if norm_dt:
                age_hours = (now_utc - norm_dt).total_seconds() / 3600.0
                age_str = f"{age_hours:.1f} hours"

            title = meta["content"].get("title") or "[No title]"
            company = meta["content"].get("company")

            print(f"\n  [{idx}] {title[:60]}")
            print(f"      URL                 : {item_url}")
            if stype == "JOB" and company:
                print(f"      Company             : {company}")
            print(f"      Raw Meta Date       : {raw_meta_pub}")
            print(f"      Raw Time Tag        : {time_dt_val}")
            print(f"      Extracted Date      : {extracted_date}")
            print(f"      Normalized UTC Date : {norm_dt.isoformat() if norm_dt else 'None'}")
            print(f"      Age vs Current UTC  : {age_str}")
            print(f"      is_within_24_hours  : {is_fresh}")


async def main() -> None:
    scraper = IntelligentScrapingAgent()
    agent2 = GeneralDataAgent()

    await diagnose_zero_link_sources(scraper)
    await diagnose_ten_link_sources(scraper, agent2)


if __name__ == "__main__":
    asyncio.run(main())
