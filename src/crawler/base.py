"""
Async HTTP crawler — Agent 1 foundation.

Responsibilities:
- Fetch raw HTML over HTTP using aiohttp.
- Retry transient failures with exponential backoff + jitter.
- Detect pages that likely require JavaScript rendering.
- Record 429 / 403 results honestly rather than attempting to bypass them.
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class CrawlResult:
    url: str
    status_code: Optional[int] = None
    html: Optional[str] = None
    success: bool = False
    used_browser: bool = False          # set to True by the agent after Playwright fallback
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# JS-detection heuristics
# ---------------------------------------------------------------------------

# Patterns found in the raw HTML that strongly suggest the real content is
# rendered client-side and the static response is just a shell.
_JS_INDICATORS = [
    "You need to enable JavaScript",
    "Please enable JavaScript",
    "This page requires JavaScript",
    "__NEXT_DATA__",            # Next.js
    "window.__NUXT__",          # Nuxt.js
    'id="__vue-root"',          # Vue SSR minimal shell
    "ng-version=",              # Angular
    "<app-root></app-root>",    # Angular empty root
]

def looks_like_js_required(html: str) -> bool:
    """Return True if the page body appears to need client-side JS to render."""
    # Very short bodies are usually JS shells too
    if len(html.strip()) < 512:
        return True
    for indicator in _JS_INDICATORS:
        if indicator in html:
            return True
    return False


# ---------------------------------------------------------------------------
# HTTP crawler
# ---------------------------------------------------------------------------

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=20)
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.5   # seconds


async def _backoff(attempt: int) -> None:
    """Exponential backoff with ±25 % random jitter."""
    delay = _BACKOFF_BASE ** attempt + random.uniform(0, 0.5)
    await asyncio.sleep(delay)


async def fetch(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    *,
    retries: int = _MAX_RETRIES,
) -> CrawlResult:
    """
    Fetch a single URL.

    - Respects the shared semaphore for concurrency control.
    - Retries up to `retries` times on network errors or 5xx responses.
    - Does NOT retry 403 or 429 — records those results as-is.
    """
    async with semaphore:
        last_error: Optional[str] = None

        for attempt in range(retries + 1):
            try:
                async with session.get(
                    url,
                    timeout=_DEFAULT_TIMEOUT,
                    allow_redirects=True,     # avoid certificate issues on lesser-known hosts
                ) as response:
                    status = response.status

                    # Do not retry access-control or rate-limit responses.
                    if status == 403:
                        return CrawlResult(
                            url=url,
                            status_code=403,
                            success=False,
                            error="HTTP 403 Forbidden — site blocked automated access",
                        )

                    if status == 429:
                        # Honor Retry-After if present, otherwise back off and stop.
                        retry_after = response.headers.get("Retry-After")
                        wait = float(retry_after) if retry_after else 60.0
                        await asyncio.sleep(min(wait, 60.0))
                        return CrawlResult(
                            url=url,
                            status_code=429,
                            success=False,
                            error=f"HTTP 429 Too Many Requests — backed off {wait:.0f}s",
                        )

                    # Retry server-side errors.
                    if status >= 500:
                        last_error = f"HTTP {status}"
                        if attempt < retries:
                            await _backoff(attempt)
                            continue
                        return CrawlResult(
                            url=url,
                            status_code=status,
                            success=False,
                            error=last_error,
                        )

                    # 2xx / 3xx — read body.
                    html = await response.text(errors="replace")
                    return CrawlResult(
                        url=url,
                        status_code=status,
                        html=html,
                        success=(status < 400),
                    )

            except asyncio.TimeoutError:
                last_error = "Request timed out"
            except aiohttp.ClientConnectionError as exc:
                last_error = f"Connection error: {exc}"
            except aiohttp.ClientError as exc:
                last_error = f"Client error: {exc}"

            if attempt < retries:
                await _backoff(attempt)

        return CrawlResult(url=url, success=False, error=last_error)


async def fetch_many_batched(
    urls: list[str],
    *,
    concurrency: int = 5,
    batch_size: int = 100,
    session: Optional[aiohttp.ClientSession] = None,
    retries: int = _MAX_RETRIES,
) -> list[CrawlResult]:
    """
    Fetch a large list of URLs in bounded batches of `batch_size`.
    Within each batch, at most `concurrency` HTTP requests execute simultaneously.
    This bounds memory and active coroutine count to O(min(batch_size, len(urls)))
    instead of allocating 500,000 tasks at once.
    """
    if not urls:
        return []

    semaphore = asyncio.Semaphore(concurrency)

    async def _process_batches(s: aiohttp.ClientSession) -> list[CrawlResult]:
        accumulated: list[CrawlResult] = []
        for i in range(0, len(urls), batch_size):
            chunk = urls[i:i + batch_size]
            tasks = [fetch(s, url, semaphore, retries=retries) for url in chunk]
            batch_results = await asyncio.gather(*tasks)
            accumulated.extend(batch_results)
        return accumulated

    if session is not None:
        return await _process_batches(session)

    headers = {"User-Agent": _USER_AGENT}
    async with aiohttp.ClientSession(headers=headers) as new_session:
        return await _process_batches(new_session)


async def fetch_many(
    urls: list[str],
    *,
    concurrency: int = 5,
    batch_size: Optional[int] = None,
) -> list[CrawlResult]:
    """
    Fetch multiple URLs concurrently.
    Returns one CrawlResult per URL in the same order.
    If batch_size is provided or len(urls) > 100, processes in bounded batches.
    """
    if batch_size is not None or len(urls) > 100:
        eff_batch = batch_size if batch_size is not None else 100
        return await fetch_many_batched(urls, concurrency=concurrency, batch_size=eff_batch)

    semaphore = asyncio.Semaphore(concurrency)
    headers = {"User-Agent": _USER_AGENT}

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [fetch(session, url, semaphore) for url in urls]
        return await asyncio.gather(*tasks)

