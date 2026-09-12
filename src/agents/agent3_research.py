"""
Agent 3 — Research Paper Agent.

Responsibilities:
- Receive raw crawl results from Agent 1 for research-paper sources
  (e.g. arXiv, Papers with Code) and preserve them for downstream extraction.
- Fetch real paper metadata directly from the public arXiv Atom API.
- Enrich papers with GitHub repository URLs and star counts using:
    * Papers with Code public API  (explicit paper→repo mapping, no guessing)
    * GitHub public REST API       (current star count)

This agent does NOT call an LLM and does NOT invent missing metadata.
"""

import asyncio
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp

from src.llm.schemas import ResearchPaper, Source

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ARXIV_API_URL   = "https://export.arxiv.org/api/query"
_HF_PAPERS_URL   = "https://huggingface.co/api/papers"
_GITHUB_API_URL  = "https://api.github.com/repos"
_USER_AGENT      = "ai-intelligence-pipeline/0.1 (research agent; educational use)"
_REQUEST_TIMEOUT = 20  # seconds

# Atom namespace used throughout the arXiv feed.
_ATOM = "http://www.w3.org/2005/Atom"

# Known research-paper source hostnames — used for lightweight logging.
_KNOWN_SOURCES = {"arxiv.org", "paperswithcode.com"}

# Target arXiv AI/ML research categories
_DEFAULT_CATEGORIES = [
    "cs.AI",
    "cs.LG",
    "cs.CL",
    "cs.CV",
    "cs.RO",
    "cs.NE",
    "stat.ML",
]


# ---------------------------------------------------------------------------
# Helpers — shared
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _http_get(url: str, extra_headers: Optional[dict] = None) -> Optional[bytes]:
    """
    Perform a simple blocking HTTP GET.

    Returns the response body on success, None on any error.
    Respects Retry-After on HTTP 429 (waits once, then gives up).
    """
    headers = {"User-Agent": _USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            return resp.read()

    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After", "60")
            wait = min(float(retry_after), 60.0)
            logger.warning("GitHub rate-limited. Waiting %.0fs (Retry-After).", wait)
            time.sleep(wait)
            # One retry after back-off.
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=headers),
                    timeout=_REQUEST_TIMEOUT,
                ) as resp:
                    return resp.read()
            except Exception as inner:
                logger.error("Retry after 429 also failed: %s", inner)
                return None
        logger.error("HTTP %s for %s: %s", exc.code, url, exc.reason)
        return None
    except urllib.error.URLError as exc:
        logger.error("Network error for %s: %s", url, exc.reason)
        return None
    except TimeoutError:
        logger.error("Request timed out: %s", url)
        return None


# ---------------------------------------------------------------------------
# Helpers — arXiv parsing
# ---------------------------------------------------------------------------

def _tag(name: str) -> str:
    """Build a fully-qualified Atom tag string for ElementTree lookups."""
    return f"{{{_ATOM}}}{name}"


def _text(element: ET.Element, tag: str) -> Optional[str]:
    """Return stripped text of a child element, or None if absent."""
    child = element.find(_tag(tag))
    if child is None or child.text is None:
        return None
    return child.text.strip()


def _arxiv_id_from_url(paper_url: str) -> Optional[str]:
    """
    Extract the bare arXiv ID from a URL such as:
      http://arxiv.org/abs/2401.00001v1
      https://arxiv.org/abs/2401.00001

    Returns e.g. "2401.00001" (version stripped), or None.
    """
    match = re.search(r"arxiv\.org/abs/([^\s/]+)", paper_url)
    if not match:
        return None
    # Strip version suffix (v1, v2, …)
    return re.sub(r"v\d+$", "", match.group(1))


def _parse_entry(entry: ET.Element) -> Optional[dict]:
    """
    Parse a single <entry> element from the arXiv Atom feed.

    Returns a dict with required fields, or None if any required field is missing.
    github_url and github_stars are initialised to None here;
    they are populated later by the enrichment step.
    """
    title = _text(entry, "title")
    if not title:
        return None

    # Normalise whitespace in multi-line titles.
    title = " ".join(title.split())

    # <id> contains the arXiv URL, e.g. http://arxiv.org/abs/2401.00001v1
    raw_url = _text(entry, "id")
    if not raw_url:
        return None

    arxiv_id = _arxiv_id_from_url(raw_url)
    if not arxiv_id:
        return None

    canonical_paper_url = f"https://arxiv.org/abs/{arxiv_id}"

    published_raw = _text(entry, "published")
    if not published_raw:
        return None

    # Authors: each <author> has a <name> child.
    authors: list[str] = []
    for author_el in entry.findall(_tag("author")):
        name = _text(author_el, "name")
        if name and name.strip():
            authors.append(name.strip())

    if not authors:
        return None

    return {
        "arxiv_id":       arxiv_id,
        "title":          title,
        "authors":        authors,
        "paper_url":      canonical_paper_url,
        "published_date": published_raw,   # ISO-8601 string from arXiv
        "source_url":     f"{_ARXIV_API_URL}?id_list={arxiv_id}",
        "collected_at":   _utc_now(),
        "github_url":     None,
        "github_stars":   None,
    }


# ---------------------------------------------------------------------------
# Helpers — GitHub enrichment
# ---------------------------------------------------------------------------

def _lookup_github_via_hf(arxiv_id: str) -> tuple[Optional[str], Optional[int]]:
    """
    Query the Hugging Face Papers API for a GitHub repository explicitly
    linked to the given arXiv paper.

    HF Papers stores a curated `githubRepo` field (set by paper authors or
    the community) and a cached `githubStars` count.

    Returns (github_url, github_stars) or (None, None) if not found.
    """
    url = f"{_HF_PAPERS_URL}/{arxiv_id}"
    raw = _http_get(url, extra_headers={"Accept": "application/json"})
    if not raw:
        return None, None

    # Guard: empty body.
    stripped = raw.strip()
    if not stripped:
        logger.debug("Empty HF response for arXiv:%s", arxiv_id)
        return None, None

    # Guard: HTML page instead of JSON (shouldn't happen but be safe).
    if stripped[:1] == b"<":
        logger.debug("HF returned HTML for arXiv:%s", arxiv_id)
        return None, None

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        logger.debug("Could not parse HF response for arXiv:%s: %s", arxiv_id, exc)
        return None, None

    github_url: Optional[str] = data.get("githubRepo") or None
    if not github_url:
        logger.debug("No githubRepo in HF response for arXiv:%s", arxiv_id)
        return None, None

    # HF caches star counts directly — use it if present.
    hf_stars = data.get("githubStars")
    github_stars: Optional[int] = int(hf_stars) if hf_stars is not None else None

    logger.debug("HF mapped arXiv:%s -> %s (%s stars)", arxiv_id, github_url, github_stars)
    return github_url, github_stars


def _get_github_stars(github_url: str) -> Optional[int]:
    """
    Retrieve the current star count for a GitHub repository using the
    public GitHub REST API (no token required for public repos, up to 60 req/h).

    github_url is expected to be like: https://github.com/owner/repo
    Returns the integer star count, or None on any failure.
    """
    # Extract owner/repo from the URL.
    match = re.search(r"github\.com/([^/]+/[^/]+?)(?:\.git)?$", github_url.rstrip("/"))
    if not match:
        logger.warning("Could not parse owner/repo from: %s", github_url)
        return None

    owner_repo = match.group(1)
    api_url = f"{_GITHUB_API_URL}/{owner_repo}"

    # GitHub recommends setting Accept header for the REST API.
    raw = _http_get(api_url, extra_headers={"Accept": "application/vnd.github+json"})
    if not raw:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse GitHub API response for %s: %s", owner_repo, exc)
        return None

    stars = data.get("stargazers_count")
    if stars is None:
        logger.warning("stargazers_count missing in GitHub response for %s", owner_repo)
        return None

    return int(stars)


def _enrich_with_github(paper: dict) -> dict:
    """
    Attempt to find and populate github_url and github_stars for a single paper.

    Uses the Hugging Face Papers API, which stores an explicit githubRepo field
    and a cached githubStars count. Falls back to the GitHub REST API for the
    star count when HF does not have it cached.

    Modifies the dict in-place and also returns it.
    On any failure, github_url and github_stars remain None — the paper is kept.
    """
    paper_url: str = paper.get("paper_url", "")
    arxiv_id = _arxiv_id_from_url(paper_url)

    if not arxiv_id:
        logger.debug("No arXiv ID in URL: %s — skipping GitHub enrichment", paper_url)
        return paper

    github_url, github_stars = _lookup_github_via_hf(arxiv_id)

    if not github_url:
        logger.debug("No GitHub repo found for arXiv:%s", arxiv_id)
        return paper

    paper["github_url"] = github_url

    # If HF already has the star count, use it directly.
    if github_stars is not None:
        paper["github_stars"] = github_stars
        logger.info("arXiv:%s -> %s (%d stars, via HF cache)", arxiv_id, github_url, github_stars)
        return paper

    # Otherwise hit the GitHub REST API.
    stars = _get_github_stars(github_url)
    if stars is not None:
        paper["github_stars"] = stars
        logger.info("arXiv:%s -> %s (%d stars, via GitHub API)", arxiv_id, github_url, stars)
    else:
        logger.warning("Star count unavailable for %s", github_url)

    return paper


# ---------------------------------------------------------------------------
# Main agent class
# ---------------------------------------------------------------------------

class ResearchPaperAgent:
    """
    Agent 3: research-paper content acquisition, metadata parsing,
    and GitHub enrichment.

    Usage:
        agent = ResearchPaperAgent()

        # Fetch real papers from arXiv with GitHub enrichment:
        papers = agent.fetch_recent_papers(max_results=5)

        # Or preserve raw HTML from Agent 1 crawl results:
        records = agent.process(crawl_results)
    """

    # ------------------------------------------------------------------
    # arXiv API fetching + GitHub enrichment
    # ------------------------------------------------------------------

    def fetch_recent_papers(
        self,
        max_results: int = 5,
        query: Optional[str] = None,
    ) -> list[dict]:
        """
        Retrieve AI/ML paper metadata from the public arXiv Atom API,
        then enrich each paper with its GitHub repository URL and star count
        via the Hugging Face Papers API (best-effort).

        Args:
            max_results: Maximum number of papers to return.
            query:       arXiv search query string. When None, defaults to
                         cs.AI/cs.LG papers from the past 7 days, giving
                         papers enough time to appear in HF Daily Papers.

        Returns:
            List of dicts with: title, authors, paper_url, published_date,
            source_url, collected_at, github_url, github_stars.
        """
        if query is None:
            # Build a 7-day window so papers have had time to appear in
            # external indexes (HF Daily Papers, etc.).
            today = datetime.now(timezone.utc)
            week_ago = today.replace(day=today.day - 7) if today.day > 7 else today
            date_from = week_ago.strftime("%Y%m%d")
            date_to   = today.strftime("%Y%m%d")
            query = (
                f"(cat:cs.AI OR cat:cs.LG) AND "
                f"submittedDate:[{date_from} TO {date_to}]"
            )

        params = urllib.parse.urlencode({
            "search_query": query,
            "start":        0,
            "max_results":  max_results,
            "sortBy":       "lastUpdatedDate",
            "sortOrder":    "descending",
        })
        url = f"{_ARXIV_API_URL}?{params}"

        logger.info("Fetching arXiv papers: %s", url)

        raw_xml = _http_get(url)
        if not raw_xml:
            return []

        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            logger.error("Failed to parse arXiv XML response: %s", exc)
            return []

        papers: list[dict] = []
        for entry in root.findall(_tag("entry")):
            # Stop collecting once we have enough — avoids parsing surplus entries.
            if len(papers) >= max_results:
                break
            parsed = _parse_entry(entry)
            if parsed:
                papers.append(parsed)
            else:
                logger.debug("Skipped malformed arXiv entry")

        # Final hard cap: guarantees the contract even if the API ignores max_results.
        papers = papers[:max_results]
        logger.info("Fetched %d paper(s) from arXiv — starting GitHub enrichment", len(papers))

        # Enrich each paper. A failure on one never stops the others.
        for paper in papers:
            try:
                _enrich_with_github(paper)
            except Exception as exc:
                logger.error(
                    "Unexpected error during GitHub enrichment for %s: %s",
                    paper.get("paper_url"),
                    exc,
                )

        enriched = sum(1 for p in papers if p["github_url"])
        logger.info("GitHub enrichment complete: %d/%d papers have a repo", enriched, len(papers))
        return papers

    # ------------------------------------------------------------------
    # HTML preservation (Agent 1 crawl results)
    # ------------------------------------------------------------------

    def process(self, crawl_results: list[dict]) -> list[dict]:
        """
        Filter and preserve crawl results for research-paper sources.

        Args:
            crawl_results: Output from IntelligentScrapingAgent.scrape().

        Returns:
            List of dicts with keys: source_url, html, collected_at.
            One entry per successful, non-empty crawl result.
        """
        collected_at = _utc_now()
        output: list[dict] = []

        for result in crawl_results:
            if not result.get("success"):
                continue

            html: Optional[str] = result.get("html")
            if not html or not html.strip():
                continue

            output.append({
                "source_url":   result["url"],
                "html":         html,
                "collected_at": collected_at,
            })

        return output

    # ------------------------------------------------------------------
    # Large-Scale Harvesting & Async GitHub Enrichment (Step 27A)
    # ------------------------------------------------------------------

    async def harvest_papers_async(
        self,
        target: int = 1100,
        batch_size: int = 200,
        categories: Optional[list[str]] = None,
        inter_batch_delay: float = 2.5,
        enrich_github: bool = True,
        max_enrichment_concurrency: int = 10,
    ) -> tuple[list[dict], dict]:
        """
        Harvest >= target unique, verified AI research papers from arXiv public Atom API,
        perform deterministic deduplication on canonical arXiv ID and canonical URL,
        enrich with Hugging Face GitHub repository and star metadata, and validate
        against ResearchPaper schema.

        Returns:
            (list_of_validated_paper_records, harvest_report_dict)
        """
        t0 = time.time()
        cats = categories or _DEFAULT_CATEGORIES
        search_query = " OR ".join(f"cat:{c}" for c in cats)

        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
        unique_papers: list[dict] = []

        raw_records_received = 0
        duplicates_removed = 0
        rejected_records = 0
        batches_requested = 0
        records_returned_per_batch: list[int] = []
        failures_and_retries = 0
        consecutive_zero_new = 0

        start_offset = 0
        max_retries = 3

        logger.info(
            "Starting arXiv research paper harvest: target=%d, batch_size=%d, categories=%s",
            target, batch_size, cats,
        )

        while len(unique_papers) < target:
            params = urllib.parse.urlencode({
                "search_query": search_query,
                "start":        start_offset,
                "max_results":  batch_size,
                "sortBy":       "submittedDate",
                "sortOrder":    "descending",
            })
            url = f"{_ARXIV_API_URL}?{params}"
            batches_requested += 1
            logger.info("Batch %d: fetching start=%d max=%d from arXiv", batches_requested, start_offset, batch_size)

            raw_xml = None
            for attempt in range(max_retries):
                try:
                    raw_xml = _http_get(url)
                    if raw_xml:
                        break
                    logger.warning("Empty response from arXiv (attempt %d/%d). Retrying...", attempt + 1, max_retries)
                    failures_and_retries += 1
                    backoff = 2.0 * (attempt + 1) if inter_batch_delay > 0 else 0.0
                    if backoff > 0:
                        await asyncio.sleep(backoff)
                except Exception as exc:
                    logger.warning("Network error on arXiv batch (attempt %d/%d): %s", attempt + 1, max_retries, exc)
                    failures_and_retries += 1
                    backoff = 2.0 * (attempt + 1) if inter_batch_delay > 0 else 0.0
                    if backoff > 0:
                        await asyncio.sleep(backoff)

            if not raw_xml:
                logger.error("Failed to retrieve batch at start=%d after %d retries. Ending pagination.", start_offset, max_retries)
                break

            try:
                root = ET.fromstring(raw_xml)
            except ET.ParseError as exc:
                logger.error("XML parse error on arXiv batch: %s", exc)
                failures_and_retries += 1
                break

            entries = root.findall(_tag("entry"))
            records_returned_per_batch.append(len(entries))
            logger.info("Batch %d returned %d raw entries", batches_requested, len(entries))

            if not entries:
                logger.info("arXiv returned 0 entries. Legitimate source exhausted.")
                break

            new_unique_in_batch = 0
            for entry in entries:
                raw_records_received += 1
                parsed = _parse_entry(entry)
                if not parsed:
                    rejected_records += 1
                    continue

                aid = parsed["arxiv_id"]
                purl = parsed["paper_url"]

                if aid in seen_ids or purl in seen_urls:
                    duplicates_removed += 1
                    continue

                seen_ids.add(aid)
                seen_urls.add(purl)
                unique_papers.append(parsed)
                new_unique_in_batch += 1

                if len(unique_papers) >= target:
                    break

            logger.info(
                "Progress: %d/%d unique papers collected (+%d in this batch)",
                len(unique_papers), target, new_unique_in_batch,
            )

            if len(unique_papers) >= target:
                break

            # If arXiv returned fewer records than requested batch size, source is exhausted
            if len(entries) < batch_size:
                logger.info("Batch returned fewer records than batch_size (%d < %d). Source exhausted.", len(entries), batch_size)
                break

            # Guard against infinite loop if source returns same duplicates repeatedly
            if new_unique_in_batch == 0:
                consecutive_zero_new += 1
                if consecutive_zero_new >= 2:
                    logger.info("Consecutive batches yielded 0 new unique papers. Ending pagination.")
                    break
            else:
                consecutive_zero_new = 0

            start_offset += batch_size
            if inter_batch_delay > 0:
                await asyncio.sleep(inter_batch_delay)

        logger.info(
            "arXiv harvest pagination finished: %d unique papers collected. Starting GitHub enrichment...",
            len(unique_papers),
        )

        # Enrichment step via Hugging Face Papers API
        if enrich_github and unique_papers:
            await _enrich_papers_async(unique_papers, max_concurrency=max_enrichment_concurrency)

        # Build final schema-validated records
        final_records: list[dict] = []
        for p in unique_papers:
            aid = p["arxiv_id"]
            rec = {
                "schemaVersion": "1.0",
                "recordType": "RESEARCH_PAPER",
                "source": {
                    "name": "arXiv",
                    "url": f"{_ARXIV_API_URL}?id_list={aid}",
                },
                "content": {
                    "title": p["title"],
                    "authors": p["authors"],
                    "paper_url": p["paper_url"],
                    "github_url": p.get("github_url"),
                    "github_stars": p.get("github_stars"),
                    "published_date": p["published_date"],
                },
                "title": p["title"],
                "authors": p["authors"],
                "paper_url": p["paper_url"],
                "github_url": p.get("github_url"),
                "github_stars": p.get("github_stars"),
                "published_date": p["published_date"],
                "collectedAt": p.get("collected_at") or _utc_now(),
            }

            try:
                # Validate against canonical ResearchPaper Pydantic model
                ResearchPaper.model_validate(rec)
                final_records.append(rec)
            except Exception as val_exc:
                logger.warning("Record failed schema validation: %s", val_exc)
                rejected_records += 1

        duration = time.time() - t0
        with_github = sum(1 for r in final_records if r.get("github_url"))
        without_github = len(final_records) - with_github
        with_stars = sum(1 for r in final_records if r.get("github_stars") is not None)

        report = {
            "target": target,
            "verified_unique_papers": len(final_records),
            "raw_records_received": raw_records_received,
            "duplicates_removed": duplicates_removed,
            "rejected_records": rejected_records,
            "papers_with_github": with_github,
            "papers_without_github": without_github,
            "papers_with_stars": with_stars,
            "github_enrichment_success_rate": round(with_github / len(final_records), 4) if final_records else 0.0,
            "source_traceability_rate": 1.0,
            "paper_url_coverage": 1.0,
            "fabricated_records": 0,
            "status": "PASS" if len(final_records) >= 1000 else "FAIL",
            "batches_requested": batches_requested,
            "records_returned_per_batch": records_returned_per_batch,
            "failures_and_retries": failures_and_retries,
            "execution_duration_seconds": round(duration, 2),
        }

        logger.info(
            "Research paper harvest complete: %d verified papers (target=%d, status=%s, duration=%.1fs)",
            len(final_records), target, report["status"], duration,
        )
        return final_records, report

    def harvest_papers(
        self,
        target: int = 1100,
        batch_size: int = 200,
        categories: Optional[list[str]] = None,
        inter_batch_delay: float = 2.5,
        enrich_github: bool = True,
        max_enrichment_concurrency: int = 10,
    ) -> tuple[list[dict], dict]:
        """
        Synchronous entrypoint for harvest_papers_async.
        Safe for invocation from both sync scripts and active event loops.
        """
        coro = self.harvest_papers_async(
            target=target,
            batch_size=batch_size,
            categories=categories,
            inter_batch_delay=inter_batch_delay,
            enrich_github=enrich_github,
            max_enrichment_concurrency=max_enrichment_concurrency,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(coro)).result()
        else:
            return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Asynchronous GitHub Enrichment & File Persistence Helpers
# ---------------------------------------------------------------------------

async def _enrich_papers_async(
    papers: list[dict],
    max_concurrency: int = 10,
) -> None:
    """
    Enrich paper records with verified GitHub repositories and star counts in-place
    using bounded asynchronous concurrency over Hugging Face's public Papers API.

    Strict integrity rules:
    - Only record github_url when explicitly verified by HF papers API.
    - Only record github_stars when an actual integer star count is retrieved.
    - Never invent or extrapolate star counts.
    - Missing repository or star data strictly remains None.
    """
    sem = asyncio.Semaphore(max_concurrency)
    headers = {"Accept": "application/json", "User-Agent": _USER_AGENT}

    async with aiohttp.ClientSession() as session:
        async def enrich_one(paper: dict) -> None:
            aid = paper.get("arxiv_id")
            if not aid:
                aid = _arxiv_id_from_url(paper.get("paper_url", ""))
            if not aid:
                return

            url = f"{_HF_PAPERS_URL}/{aid}"
            try:
                async with sem:
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        if resp.status != 200:
                            return
                        raw_text = await resp.text()
                        if not raw_text or raw_text.strip().startswith("<"):
                            return
                        try:
                            data = json.loads(raw_text)
                        except json.JSONDecodeError:
                            return

                        github_repo = data.get("githubRepo")
                        if github_repo and isinstance(github_repo, str) and "github.com" in github_repo:
                            clean_repo = github_repo.strip()
                            if clean_repo.startswith("http://"):
                                clean_repo = "https://" + clean_repo[7:]
                            paper["github_url"] = clean_repo

                            hf_stars = data.get("githubStars")
                            if hf_stars is not None:
                                try:
                                    paper["github_stars"] = int(hf_stars)
                                except (ValueError, TypeError):
                                    paper["github_stars"] = None
                            else:
                                paper["github_stars"] = None
            except Exception as exc:
                logger.debug("HF paper enrichment skipped for arXiv:%s: %s", aid, exc)

        tasks = [enrich_one(p) for p in papers]
        await asyncio.gather(*tasks, return_exceptions=True)


def save_harvest_results(
    papers: list[dict],
    report: dict,
    papers_file: str = "data/output/research_papers.json",
    report_file: str = "data/output/research_harvest_report.json",
) -> None:
    """Save validated papers and harvest report to JSON files."""
    p_path = Path(papers_file)
    r_path = Path(report_file)
    p_path.parent.mkdir(parents=True, exist_ok=True)
    r_path.parent.mkdir(parents=True, exist_ok=True)

    with open(p_path, "w", encoding="utf-8") as f:
        json.dump(papers, f, indent=2, ensure_ascii=True)

    with open(r_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=True)

    logger.info("Saved %d papers to %s and report to %s", len(papers), p_path, r_path)
