"""
Agent 1 — Intelligent Scraping Agent.

Responsibilities:
- Accept a list of URLs.
- Crawl each URL using the aiohttp-based crawler first (fast, no browser).
- Detect pages that need JavaScript rendering.
- Fall back to Playwright (headless Chromium) for JS-heavy pages.
- Return raw HTML for every URL — no parsing, no LLM, no extraction.

Each result dict matches the shape expected by downstream agents:
{
    "url": str,
    "status_code": int | None,
    "html": str | None,
    "success": bool,
    "used_browser": bool,
    "error": str | None,
}
"""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from src.crawler.base import CrawlResult, fetch_many, looks_like_js_required

logger = logging.getLogger(__name__)

# Concurrency limits — keep polite and within assignment scope.
_HTTP_CONCURRENCY = 5
_BROWSER_CONCURRENCY = 2          # Playwright is heavier; fewer parallel tabs
_PLAYWRIGHT_TIMEOUT_MS = 25_000   # 25 s page load timeout

# Known client-side rendered (CSR) job board domains (Fix 1)
_KNOWN_CSR_JOB_DOMAINS = {"remoteok.com", "workingnomads.com", "jobspresso.co"}


def _needs_csr_job_fallback(url: str, html: str) -> bool:
    """
    Check if a known CSR job listing source needs browser rendering
    because its static HTTP HTML lacks individual job detail links.
    """
    if not url or not html:
        return False
    domain = urlparse(url).netloc.lower()
    if not any(d in domain for d in _KNOWN_CSR_JOB_DOMAINS):
        return False

    # If the static HTML already contains actual job links, no browser needed
    if "remoteok.com" in domain and re.search(r'/remote-jobs/[a-zA-Z0-9_\-]+-\d+', html):
        return False
    if "workingnomads.com" in domain:
        wn_matches = [
            m for m in re.findall(r'/jobs/([a-zA-Z0-9_\-]+)', html)
            if '-' in m and not any(m.startswith(pfx) for pfx in ('bg-', 'remote-', 'static-'))
        ]
        if wn_matches:
            return False
    if "jobspresso.co" in domain and re.search(r'/job/[a-zA-Z0-9_\-]+/', html):
        return False

    return True


# ---------------------------------------------------------------------------
# Browser fallback (Playwright)
# ---------------------------------------------------------------------------

async def _fetch_with_browser(
    url: str,
    semaphore: asyncio.Semaphore,
) -> CrawlResult:
    """
    Render a single URL with headless Chromium and return the final HTML.
    Only called when the HTTP crawler signals that JS rendering may be required.
    Prefers DOM readiness and content hydration over indefinite networkidle (Fix 3).
    """
    async with semaphore:
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page()

                # Fast initial document load
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=_PLAYWRIGHT_TIMEOUT_MS,
                )

                # Wait for content hydration based on source pattern
                u_lower = url.lower()
                try:
                    if "technologyreview.com" in u_lower:
                        # Wait for article links to hydrate in Next.js React DOM
                        await page.wait_for_selector('a[href*="/20"]', timeout=8000)
                        await page.wait_for_timeout(2500)
                    elif "remoteok.com" in u_lower:
                        # Wait for job rows to populate via AJAX
                        await page.wait_for_selector('tr.job, a[href*="/remote-jobs/"]', timeout=8000)
                        await page.wait_for_timeout(2500)
                    elif "workingnomads.com" in u_lower:
                        # Wait for client-side job list hydration
                        await page.wait_for_selector('a[href*="/jobs/"]', timeout=8000)
                        await page.wait_for_timeout(2500)
                    elif "jobspresso.co" in u_lower:
                        # Wait for client-side job listings to render
                        await page.wait_for_selector('a[href*="/job/"]', timeout=8000)
                        await page.wait_for_timeout(1500)
                    else:
                        await page.wait_for_timeout(2000)
                except Exception:
                    # Proceed with whatever DOM is rendered
                    pass

                status = response.status if response else None
                html = await page.content()
                await browser.close()

            return CrawlResult(
                url=url,
                status_code=status,
                html=html,
                success=True,
                used_browser=True,
            )

        except PlaywrightTimeout:
            return CrawlResult(
                url=url,
                success=False,
                used_browser=True,
                error="Playwright timed out waiting for page load",
            )
        except Exception as exc:
            return CrawlResult(
                url=url,
                success=False,
                used_browser=True,
                error=f"Playwright error: {exc}",
            )


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class IntelligentScrapingAgent:
    """
    Agent 1: raw web content acquisition.

    Usage:
        agent = IntelligentScrapingAgent()
        results = await agent.scrape(["https://example.com", ...])
    """

    async def scrape(self, urls: list[str]) -> list[dict]:
        """
        Scrape a list of URLs and return raw results.

        Steps:
        1. Fetch all URLs over HTTP concurrently.
        2. For any result that looks JS-rendered or is a known CSR listing lacking links, fall back to Playwright.
        3. Merge results and return. If Playwright fails, preserve original HTTP result.
        """
        if not urls:
            return []

        logger.info("Agent 1: starting HTTP crawl for %d URL(s)", len(urls))

        # --- Step 1: HTTP crawl -------------------------------------------------
        http_results: list[CrawlResult] = await fetch_many(
            urls, concurrency=_HTTP_CONCURRENCY
        )

        # Store original HTTP results for safe fallback
        http_map: dict[str, CrawlResult] = {r.url: r for r in http_results}
        final: dict[str, CrawlResult] = {}
        needs_browser: list[str] = []

        for result in http_results:
            if result.success and result.html:
                if looks_like_js_required(result.html) or _needs_csr_job_fallback(result.url, result.html):
                    logger.info("Scheduling browser fallback for %s", result.url)
                    needs_browser.append(result.url)
                else:
                    final[result.url] = result
            else:
                # HTTP hard failure (403, 429, timeout)
                final[result.url] = result

        # --- Step 2: Browser fallback -------------------------------------------
        if needs_browser:
            logger.info(
                "Agent 1: %d URL(s) need browser rendering", len(needs_browser)
            )
            browser_semaphore = asyncio.Semaphore(_BROWSER_CONCURRENCY)
            browser_tasks = [
                _fetch_with_browser(url, browser_semaphore) for url in needs_browser
            ]
            browser_results = await asyncio.gather(*browser_tasks)
            for result in browser_results:
                if result.success and result.html:
                    final[result.url] = result
                else:
                    # If Playwright fails, preserve original HTTP result if available
                    orig = http_map.get(result.url)
                    if orig and orig.success and orig.html:
                        logger.warning(
                            "Playwright failed for %s (%s); preserving original HTTP result",
                            result.url,
                            result.error,
                        )
                        final[result.url] = orig
                    else:
                        final[result.url] = result

        # --- Step 3: Serialise in original order --------------------------------
        output: list[dict] = []
        for url in urls:
            r = final.get(url)
            if r is None:
                # Shouldn't happen, but guard anyway.
                output.append({
                    "url": url,
                    "status_code": None,
                    "html": None,
                    "success": False,
                    "used_browser": False,
                    "error": "Result missing — unknown crawl error",
                })
            else:
                output.append({
                    "url": r.url,
                    "status_code": r.status_code,
                    "html": r.html,
                    "success": r.success,
                    "used_browser": r.used_browser,
                    "error": r.error,
                })

        succeeded = sum(1 for r in output if r["success"])
        logger.info(
            "Agent 1: done — %d/%d URLs succeeded (%d via browser)",
            succeeded,
            len(urls),
            sum(1 for r in output if r["used_browser"]),
        )
        return output

