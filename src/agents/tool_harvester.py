"""
AI Tool Discovery & Candidate Extraction Agent — Step 3.

Extracts candidate AI tools from approved discovery directories:
1. There's An AI For That (TAAFT)
2. Creati.ai

Engineering Rules:
- Zero fabricated records.
- Zero premature claims of verified official websites.
- Deterministic deduplication across multi-directory appearances, preserving all discovery references.
- Honest and graceful handling of HTTP 403, 404, 429, timeouts, and network connection errors.
- Extensible adapter architecture allowing new directories to be plugged in seamlessly.
"""

import asyncio
import json
import logging
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional

from bs4 import BeautifulSoup

from src.entity.resolver import normalize_entity_name

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# URL Normalization Utility
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """
    Clean and normalize URL for candidate deduplication and reference tracking.
    Strips tracking queries (utm_*, ref, fid, etc.), fragments, and trailing slashes.
    """
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        # Strip common advertising/tracking query parameters
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        tracking_prefixes = ("utm_", "ref", "fid", "aff", "fbclid", "gclid")
        cleaned_query = [
            (k, v) for k, v in query_pairs
            if not any(k.lower().startswith(p) for p in tracking_prefixes)
        ]
        new_query = urllib.parse.urlencode(cleaned_query)
        path = parsed.path.rstrip("/")
        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            new_query,
            "",
        ))
        return normalized
    except Exception:
        return url.split("?")[0].rstrip("/")


# ---------------------------------------------------------------------------
# Base Discovery Adapter
# ---------------------------------------------------------------------------

class ToolDiscoveryAdapter:
    """Base class for approved AI tool discovery directory adapters."""

    source_name: str = "Unknown"
    source_url: str = "https://example.com"

    def __init__(self, timeout_sec: float = 15.0):
        self.timeout_sec = timeout_sec
        self.stats: dict[str, Any] = {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "pages_attempted": 0,
            "candidates_discovered": 0,
            "candidates_extracted": 0,
            "failed_requests": 0,
            "status": "NOT_STARTED",
            "errors": [],
        }

    async def discover_candidates(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch candidates from this source up to limit."""
        raise NotImplementedError

    def _fetch_html(self, url: str) -> Optional[str]:
        """
        Safely fetch raw HTML from a URL with polite User-Agent and honest error handling.
        Gracefully handles HTTP 403, 404, 429, timeouts, and network connection errors.
        """
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        self.stats["pages_attempted"] += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                status = getattr(resp, "status", 200)
                if status == 200:
                    return resp.read().decode("utf-8", errors="replace")
                else:
                    msg = f"HTTP {status}"
                    self.stats["failed_requests"] += 1
                    self.stats["errors"].append(f"{url}: {msg}")
                    return None
        except urllib.error.HTTPError as exc:
            self.stats["failed_requests"] += 1
            if exc.code == 403:
                msg = "HTTP 403 Forbidden — site blocked automated access"
            elif exc.code == 404:
                msg = "HTTP 404 Not Found"
            elif exc.code == 429:
                retry_after = exc.headers.get("Retry-After", "unknown") if hasattr(exc, "headers") else "unknown"
                msg = f"HTTP 429 Too Many Requests (Retry-After: {retry_after})"
            else:
                msg = f"HTTP Error {exc.code}: {exc.reason}"
            logger.warning("%s fetch error for %s: %s", self.source_name, url, msg)
            self.stats["errors"].append(f"{url}: {msg}")
            return None
        except urllib.error.URLError as exc:
            self.stats["failed_requests"] += 1
            msg = f"Connection error: {exc.reason}"
            logger.warning("%s connection error for %s: %s", self.source_name, url, msg)
            self.stats["errors"].append(f"{url}: {msg}")
            return None
        except (TimeoutError, socket.timeout) as exc:
            self.stats["failed_requests"] += 1
            msg = f"Request timed out: {exc}"
            logger.warning("%s timeout for %s: %s", self.source_name, url, msg)
            self.stats["errors"].append(f"{url}: {msg}")
            return None
        except Exception as exc:
            self.stats["failed_requests"] += 1
            msg = f"Unexpected fetch error: {exc}"
            logger.warning("%s unexpected error for %s: %s", self.source_name, url, msg)
            self.stats["errors"].append(f"{url}: {msg}")
            return None


# ---------------------------------------------------------------------------
# 1. There's An AI For That (TAAFT) Adapter
# ---------------------------------------------------------------------------

class TAAFTDiscoveryAdapter(ToolDiscoveryAdapter):
    """
    Adapter for There's An AI For That (TAAFT) directory.
    Extracts real AI tool candidates, task categories, developer attribution,
    and directory permalinks.
    """

    source_name = "There's An AI For That"
    source_url = "https://theresanaiforthat.com/"

    def __init__(self, timeout_sec: float = 15.0):
        super().__init__(timeout_sec=timeout_sec)

    async def discover_candidates(self, limit: int = 50) -> list[dict[str, Any]]:
        self.stats["status"] = "RUNNING"
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, self._fetch_html, self.source_url)

        if not html:
            self.stats["status"] = "FAIL" if self.stats["failed_requests"] > 0 else "EMPTY"
            return []

        candidates = self.parse_html(html, limit=limit)
        self.stats["candidates_discovered"] = len(candidates)
        self.stats["candidates_extracted"] = len(candidates)
        self.stats["status"] = "PASS" if candidates else "EMPTY"
        return candidates

    def parse_html(self, html: str, limit: int = 50) -> list[dict[str, Any]]:
        """Parse TAAFT HTML content into candidate records."""
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        now_iso = datetime.now(timezone.utc).isoformat()

        # Target structured rows first
        rows = soup.select(".listing-table-row, .home-listing-row, .home-today-row")
        if not rows:
            # Fallback to general cards or links if markup differs
            rows = soup.select(".ai, .tool, [class*='listing']")

        for row in rows:
            name_cell = row.find(class_=lambda c: c and "name-cell" in c)
            tool_name = ""
            desc = ""
            perm_url = ""

            if name_cell:
                links = name_cell.find_all("a")
                if links:
                    tool_name = links[0].get_text(strip=True)
                    perm_url = links[0].get("href", "")
                    if len(links) > 1:
                        desc = links[1].get_text(strip=True)
            else:
                # Direct link search inside row
                ai_link = row.find("a", href=lambda h: h and "/ai/" in h)
                if ai_link:
                    perm_url = ai_link.get("href", "")
                    tool_name = ai_link.get_text(strip=True)
                    # Try finding sibling or paragraph description
                    p = row.find("p")
                    if p:
                        desc = p.get_text(strip=True)

            full_url = perm_url if perm_url.startswith("http") else urllib.parse.urljoin(self.source_url, perm_url)
            parsed_perm = urllib.parse.urlparse(full_url)
            if "theresanaiforthat.com" not in parsed_perm.netloc or not parsed_perm.path.startswith("/ai/"):
                continue

            norm_url = normalize_url(full_url)
            if norm_url in seen_urls:
                continue
            seen_urls.add(norm_url)

            # Category / task
            categories: list[str] = []
            topic_cell = row.find(class_=lambda c: c and "topic-cell" in c)
            if topic_cell:
                topic_link = topic_cell.find("a")
                if topic_link:
                    cat_name = topic_link.get_text(strip=True)
                    if cat_name:
                        categories.append(cat_name)

            # Company / Developer
            developer: Optional[str] = None
            author_cell = row.find(class_=lambda c: c and "author-cell" in c)
            if author_cell:
                author_link = author_cell.find("a")
                if author_link:
                    dev_raw = author_link.get_text(strip=True)
                    if dev_raw and len(dev_raw) > 1:
                        # Clean emoji flags and social handles
                        dev_clean = re.sub(r"[\U00010000-\U0010ffff]", "", dev_raw).strip()
                        dev_clean = dev_clean.split("@")[0].strip()
                        developer = dev_clean if len(dev_clean) > 1 else None

            # If developer not in cell, check "by <Company>" pattern in name
            if not developer and " by " in tool_name:
                parts = tool_name.split(" by ", 1)
                tool_name = parts[0].strip()
                developer = parts[1].strip()
            elif developer and " by " in tool_name:
                parts = tool_name.split(" by ", 1)
                tool_name = parts[0].strip()

            # Pricing detection from row text
            pricing_hint: Optional[str] = None
            row_text = row.get_text(separator=" ").lower()
            if "freemium" in row_text:
                pricing_hint = "Freemium"
            elif "free" in row_text and "trial" not in row_text:
                pricing_hint = "Free"
            elif "paid" in row_text or "/mo" in row_text or "$" in row_text:
                pricing_hint = "Paid"

            slug = norm_url.rstrip("/").split("/")[-1]
            candidate_id = f"candidate-{slug}"

            candidate = {
                "candidate_id": candidate_id,
                "tool_name": tool_name,
                "company_developer": developer,
                "discovered_url": norm_url,
                "discovery_source": self.source_name,
                "discovery_source_url": self.source_url,
                "short_description": desc or None,
                "categories": categories,
                "tags": [c.lower() for c in categories],
                "raw_metadata": {
                    "source_slug": slug,
                    "pricing_hint": pricing_hint,
                },
                "discovery_timestamp": now_iso,
                "discovery_references": [
                    {
                        "source": self.source_name,
                        "source_url": self.source_url,
                        "discovered_url": norm_url,
                        "discovered_at": now_iso,
                    }
                ],
            }
            candidates.append(candidate)
            if len(candidates) >= limit:
                break

        return candidates


# ---------------------------------------------------------------------------
# 2. Creati.ai Adapter
# ---------------------------------------------------------------------------

class CreatiAIDiscoveryAdapter(ToolDiscoveryAdapter):
    """
    Adapter for Creati.ai AI tools directory.
    Extracts real AI tool candidates, categories/tags, descriptions,
    and external product website links.
    """

    source_name = "Creati.ai"
    source_url = "https://creati.ai/ai-tools/"

    NAV_PREFIXES = (
        "/ai-tools/month",
        "/ai-tools/new",
        "/ai-tools/ranking",
        "/ai-tools/most-",
        "/ai-tools/platform",
        "/ai-tools/pricing",
        "/ai-tools/tag",
        "/ai-tools/categories",
    )

    def __init__(self, timeout_sec: float = 15.0):
        super().__init__(timeout_sec=timeout_sec)

    async def discover_candidates(self, limit: int = 50) -> list[dict[str, Any]]:
        self.stats["status"] = "RUNNING"
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, self._fetch_html, self.source_url)

        if not html:
            self.stats["status"] = "FAIL" if self.stats["failed_requests"] > 0 else "EMPTY"
            return []

        candidates = self.parse_html(html, limit=limit)
        self.stats["candidates_discovered"] = len(candidates)
        self.stats["candidates_extracted"] = len(candidates)
        self.stats["status"] = "PASS" if candidates else "EMPTY"
        return candidates

    def parse_html(self, html: str, limit: int = 50) -> list[dict[str, Any]]:
        """Parse Creati.ai HTML content into candidate records."""
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        now_iso = datetime.now(timezone.utc).isoformat()

        # Target card containers (prefer .cardContainer, otherwise li)
        cards = soup.select(".cardContainer")
        if not cards:
            cards = soup.select("li[style*='display:grid'], [class*='card']")
        if not cards:
            cards = soup.find_all("li")

        for card in cards:
            # Find primary tool link
            tool_a = card.find("a", href=lambda h: h and h.startswith("/ai-tools/") and not any(h.startswith(p) for p in self.NAV_PREFIXES))
            if not tool_a:
                continue

            href = tool_a.get("href", "")
            clean_path = href.split("?")[0].strip("/")
            parts = clean_path.split("/")
            if len(parts) != 2:  # Expected: ['ai-tools', 'slug']
                continue

            full_url = urllib.parse.urljoin("https://creati.ai", href)
            norm_url = normalize_url(full_url)
            if norm_url in seen_urls:
                continue

            # Extract tool name from heading, title, or alt
            tool_name = ""
            h3 = card.find("h3")
            if h3:
                tool_name = h3.get_text(strip=True)
            if not tool_name:
                img = card.find("img")
                if img and img.get("alt"):
                    tool_name = img.get("alt").strip()
            if not tool_name:
                tool_name = tool_a.get_text(strip=True)

            if not tool_name or len(tool_name) < 2:
                continue

            seen_urls.add(norm_url)

            # Description
            desc: Optional[str] = None
            desc_div = card.find(class_=lambda c: c and "description" in c)
            if desc_div:
                desc_text = desc_div.get_text(strip=True)
                if desc_text:
                    desc = desc_text

            # Categories and tags
            categories: list[str] = []
            for tag_el in card.select(".category-tag, .categoriedTag"):
                tag_text = tag_el.get_text(strip=True)
                if tag_text and tag_text not in categories:
                    categories.append(tag_text)

            # External product URL if provided in card
            external_product_url: Optional[str] = None
            for ext_a in card.find_all("a"):
                ext_href = ext_a.get("href") or ""
                if ext_href.startswith("http"):
                    host = urllib.parse.urlparse(ext_href).netloc.lower()
                    if "creati.ai" not in host:
                        external_product_url = normalize_url(ext_href)
                        break

            slug = parts[1]
            candidate_id = f"candidate-{slug}"

            candidate = {
                "candidate_id": candidate_id,
                "tool_name": tool_name,
                "company_developer": None,
                "discovered_url": norm_url,
                "discovery_source": self.source_name,
                "discovery_source_url": self.source_url,
                "short_description": desc,
                "categories": categories,
                "tags": [c.lower() for c in categories],
                "raw_metadata": {
                    "source_slug": slug,
                    "external_product_url": external_product_url,
                },
                "discovery_timestamp": now_iso,
                "discovery_references": [
                    {
                        "source": self.source_name,
                        "source_url": self.source_url,
                        "discovered_url": norm_url,
                        "discovered_at": now_iso,
                    }
                ],
            }
            candidates.append(candidate)
            if len(candidates) >= limit:
                break

        return candidates


# ---------------------------------------------------------------------------
# Master Tool Harvester
# ---------------------------------------------------------------------------

class ToolHarvester:
    """
    Orchestrates AI Tool discovery extraction across configured directory adapters.
    Deduplicates candidates across multi-directory appearances and preserves
    source traceability in discovery references.
    """

    def __init__(self, adapters: Optional[list[ToolDiscoveryAdapter]] = None):
        self.adapters: list[ToolDiscoveryAdapter] = adapters or [
            TAAFTDiscoveryAdapter(),
            CreatiAIDiscoveryAdapter(),
        ]
        self.report: dict[str, Any] = {}

    async def discover(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Execute candidate discovery across all active adapters.
        Deduplicates records across sources while merging discovery references.
        """
        all_raw_candidates: list[dict[str, Any]] = []
        sources_report: list[dict[str, Any]] = []
        total_failures = 0
        total_pages_attempted = 0

        # Calculate per-adapter allocation
        adapter_budget = max(limit, 25)

        for adapter in self.adapters:
            logger.info("Discovering candidates from %s...", adapter.source_name)
            try:
                raw_records = await adapter.discover_candidates(limit=adapter_budget)
                all_raw_candidates.extend(raw_records)
            except Exception as exc:
                logger.error("Adapter %s raised unexpected error: %s", adapter.source_name, exc)
                adapter.stats["failed_requests"] += 1
                adapter.stats["errors"].append(str(exc))

            sources_report.append(adapter.stats)
            total_failures += adapter.stats.get("failed_requests", 0)
            total_pages_attempted += adapter.stats.get("pages_attempted", 0)

        # -------------------------------------------------------------------
        # Deduplication Strategy
        # -------------------------------------------------------------------
        unique_candidates: list[dict[str, Any]] = []
        seen_by_name: dict[str, dict[str, Any]] = {}
        seen_by_domain: dict[str, dict[str, Any]] = {}
        duplicates_removed = 0

        for cand in all_raw_candidates:
            tool_name = cand.get("tool_name", "")
            norm_name = normalize_entity_name(tool_name)
            if not norm_name or len(norm_name) < 2:
                continue

            # Extract external product domain if present
            ext_url = cand.get("raw_metadata", {}).get("external_product_url") or ""
            domain = ""
            if ext_url:
                try:
                    parsed_domain = urllib.parse.urlparse(ext_url).netloc.lower()
                    domain = parsed_domain.replace("www.", "")
                except Exception:
                    domain = ""

            # Check for existing match
            matched_candidate: Optional[dict[str, Any]] = None
            if domain and domain in seen_by_domain:
                matched_candidate = seen_by_domain[domain]
            elif norm_name in seen_by_name:
                matched_candidate = seen_by_name[norm_name]

            if matched_candidate is not None:
                duplicates_removed += 1
                # Merge discovery reference
                existing_sources = {
                    ref.get("source") for ref in matched_candidate.get("discovery_references", [])
                }
                for new_ref in cand.get("discovery_references", []):
                    if new_ref.get("source") not in existing_sources:
                        matched_candidate["discovery_references"].append(new_ref)
                        existing_sources.add(new_ref.get("source"))

                # Enrich missing company developer
                if not matched_candidate.get("company_developer") and cand.get("company_developer"):
                    matched_candidate["company_developer"] = cand["company_developer"]

                # Enrich missing description
                if not matched_candidate.get("short_description") and cand.get("short_description"):
                    matched_candidate["short_description"] = cand["short_description"]

                # Merge categories
                for cat in cand.get("categories", []):
                    if cat not in matched_candidate["categories"]:
                        matched_candidate["categories"].append(cat)

                # Merge tags
                for tag in cand.get("tags", []):
                    if tag not in matched_candidate["tags"]:
                        matched_candidate["tags"].append(tag)

                # Update raw metadata with any extra hints
                matched_candidate["raw_metadata"].update(cand.get("raw_metadata", {}))
                continue

            # New unique candidate
            seen_by_name[norm_name] = cand
            if domain:
                seen_by_domain[domain] = cand
            unique_candidates.append(cand)

            if len(unique_candidates) >= limit:
                break

        # Compile harvest summary report
        self.report = {
            "target_limit": limit,
            "final_candidate_count": len(unique_candidates),
            "total_discovered": len(all_raw_candidates),
            "duplicates_removed": duplicates_removed,
            "total_pages_attempted": total_pages_attempted,
            "total_failures": total_failures,
            "sources": sources_report,
            "status": "PASS" if unique_candidates else "FAIL",
        }

        logger.info(
            "Tool Discovery Summary: attempted %d pages across %d sources, "
            "discovered %d raw candidates, removed %d duplicates, "
            "failures: %d, final candidates: %d",
            total_pages_attempted,
            len(self.adapters),
            len(all_raw_candidates),
            duplicates_removed,
            total_failures,
            len(unique_candidates),
        )

        return unique_candidates

    async def discover_and_save(
        self,
        limit: int = 50,
        output_file: str = "data/output/raw_ai_tools.json",
    ) -> list[dict[str, Any]]:
        """Discover candidates and save directly to raw JSON output file."""
        candidates = await self.discover(limit=limit)
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(candidates, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d raw AI tool candidates to %s", len(candidates), output_file)
        return candidates
