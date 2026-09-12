"""
Agent 2 — General Data Agent.

Responsibilities:
- Receive raw crawl results from Agent 1 (for whole-page or individual items).
- Extract individual candidate URLs from category/board pages (source-aware extraction).
- Extract actual publication/posting dates using hierarchical metadata inspection:
  1. <meta property="article:published_time"> / <meta property="datePublished">
  2. JSON-LD (NewsArticle, JobPosting datePosted, etc.)
  3. <time datetime="...">
  4. Visible publication dates and relative dates ("today", "yesterday", "X hours ago", "X days ago").
- Normalize valid dates to UTC ISO-8601 timestamps.
- Apply 24-hour freshness filtering via src.agents.freshness.is_within_24_hours.
- Discard failed, empty, stale, future, or date-missing records.
- Preserve source traceability: source.url (listing) and content.url (individual item).
- Tag each item with a record type (STARTUP, PRODUCT, JOB, NEWS).
- Return clean records ready for downstream processing.
"""

from datetime import datetime, timezone, timedelta
import json
import logging
import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

from bs4 import BeautifulSoup

from src.agents.freshness import is_within_24_hours, normalize_datetime

logger = logging.getLogger(__name__)

# Configurable limit for initial crawl size per source (Part 2)
MAX_ITEMS_PER_SOURCE = 10

# Assets and media file extensions to exclude from article/job links
EXCLUDED_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js', '.pdf',
    '.ico', '.woff', '.woff2', '.eot', '.ttf', '.mp4', '.mp3', '.xml', '.rss',
    '.zip', '.gz', '.tar', '.exe', '.dmg', '.pkg'
}

# External non-article / non-job domains to exclude
EXCLUDED_DOMAINS = {
    'twitter.com', 'x.com', 'facebook.com', 'linkedin.com', 'instagram.com',
    'youtube.com', 'bsky.app', 'tiktok.com', 'pinterest.com', 'reddit.com',
    'threads.net', 'google.com', 'apple.com', 'amazon.com'
}

# Common navigational, legal, and transactional path keywords to ignore
EXCLUDED_PATH_KEYWORDS = {
    '/login', '/signin', '/sign-in', '/sign_in', '/signup', '/sign-up', '/sign_up',
    '/register', '/subscribe', '/privacy', '/terms', '/contact', '/about',
    '/cookie', '/advertise', '/sponsor', '/cart', '/account', '/feed', '/rss',
    '/faq', '/help', '/support', '/pricing', '/disrupt', '/newsletter'
}


def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def normalize_item_url(url: str, base_url: str = "") -> str:
    """
    Normalize relative or tracking URLs into a clean, canonical absolute URL.
    - Strips fragments (#...).
    - Removes common marketing tracking query parameters (utm_*, ref, promo).
    - Normalizes schemes and hostnames to lowercase.
    """
    if not url or url.strip().startswith(('javascript:', 'mailto:', 'tel:', '#')):
        return ""

    full = urljoin(base_url, url.strip())
    parsed = urlparse(full)
    if parsed.scheme not in ('http', 'https'):
        return ""

    netloc = parsed.netloc.lower()
    if any(d in netloc for d in EXCLUDED_DOMAINS):
        return ""

    path = parsed.path.strip()
    if any(path.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
        return ""

    # Filter tracking query parameters
    tracking_keys = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'ref', 'promo'}
    q_params = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=True):
        if k.lower() not in tracking_keys:
            q_params.append((k, v))
    clean_query = urlencode(q_params)

    # Normalize trailing slash consistently for paths
    norm_path = path.rstrip('/') + ('/' if path.endswith('/') and len(path) > 1 else '')
    return urlunparse((parsed.scheme.lower(), netloc, norm_path, parsed.params, clean_query, ''))


def parse_relative_date_text(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parse relative date strings into timezone-aware UTC datetime.
    Supports:
    - 'today', 'just now'
    - 'yesterday'
    - 'X hours ago', 'X hr ago', 'X hrs ago'
    - 'X days ago', 'X day ago'
    - 'X weeks ago', 'X week ago'
    - 'X months ago', 'X month ago'
    - 'X minutes ago', 'X min ago'
    """
    if not text:
        return None
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Normalize non-breaking spaces \xa0 and html entities
    s = text.replace('\xa0', ' ').replace('&nbsp;', ' ').strip().lower()

    if s in {"today", "just now"}:
        return now
    if s == "yesterday":
        return now - timedelta(days=1)

    m_hours = re.search(r'(\d+)\s*(?:hour|hr|hours|hrs)\s*ago', s)
    if m_hours:
        return now - timedelta(hours=int(m_hours.group(1)))

    m_days = re.search(r'(\d+)\s*(?:day|days)\s*ago', s)
    if m_days:
        return now - timedelta(days=int(m_days.group(1)))

    m_weeks = re.search(r'(\d+)\s*(?:week|weeks)\s*ago', s)
    if m_weeks:
        return now - timedelta(days=int(m_weeks.group(1)) * 7)

    m_months = re.search(r'(\d+)\s*(?:month|months)\s*ago', s)
    if m_months:
        return now - timedelta(days=int(m_months.group(1)) * 30)

    m_mins = re.search(r'(\d+)\s*(?:min|minute|mins|minutes)\s*ago', s)
    if m_mins:
        return now - timedelta(minutes=int(m_mins.group(1)))

    return None


def extract_date_info(
    html: str,
    record_type: str = "NEWS",
    now: Optional[Any] = None,
) -> tuple[Optional[str], bool]:
    """
    Extract the actual publication/posting date from HTML without fabricating.
    Returns (iso_date_str, is_date_only).

    Order for NEWS:
      1. <meta property="article:published_time">
      2. <meta property="datePublished">
      3. JSON-LD: NewsArticle / Article / etc. datePublished
      4. <time datetime="...">
      5. visible publication-date elements / relative dates

    Order for JOBS:
      1. JSON-LD JobPosting datePosted
      2. <meta property="datePosted">
      3. <meta property="article:published_time"> / datePublished
      4. <time datetime="...">
      5. visible posted date / relative dates
    """
    if not html or not html.strip():
        return None, False

    now_utc = normalize_datetime(now) if now is not None else datetime.now(timezone.utc)
    soup = BeautifulSoup(html, "html.parser")
    record_type = record_type.upper()

    def _clean_and_norm(val: Any) -> tuple[Optional[str], bool]:
        if not val:
            return None, False
        is_date_only = bool(isinstance(val, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', val.strip()))
        dt = normalize_datetime(val)
        if dt is not None:
            return dt.isoformat(), is_date_only
        if isinstance(val, str):
            rel_dt = parse_relative_date_text(val, now=now_utc)
            if rel_dt is not None:
                return rel_dt.isoformat(), False
        return None, False

    # Helper: extract all JSON-LD blocks
    def _extract_json_ld() -> list[dict]:
        results: list[dict] = []
        script_texts = [s.get_text() for s in soup.find_all("script", attrs={"type": "application/ld+json"}) if s.get_text()]
        if not script_texts:
            script_texts = re.findall(
                r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>',
                html,
                re.DOTALL | re.IGNORECASE,
            )

        for raw in script_texts:
            try:
                data = json.loads(raw.strip())
                if isinstance(data, dict):
                    results.append(data)
                    if "@graph" in data and isinstance(data["@graph"], list):
                        results.extend([x for x in data["@graph"] if isinstance(x, dict)])
                elif isinstance(data, list):
                    results.extend([x for x in data if isinstance(x, dict)])
            except Exception:
                continue
        return results

    json_ld_items = _extract_json_ld()

    if record_type == "NEWS":
        # 1. <meta property="article:published_time">
        for prop in ["article:published_time", "og:article:published_time", "parsely-pub-date", "sailthru.date"]:
            meta = (
                soup.find("meta", attrs={"property": prop})
                or soup.find("meta", attrs={"name": prop})
                or soup.find("meta", attrs={"itemprop": prop})
            )
            if meta and meta.get("content"):
                norm, is_date_only = _clean_and_norm(meta.get("content"))
                if norm:
                    return norm, is_date_only

        # 2. <meta property="datePublished">
        for prop in ["datePublished", "article:datePublished", "publish_date", "pubdate"]:
            meta = (
                soup.find("meta", attrs={"property": prop})
                or soup.find("meta", attrs={"name": prop})
                or soup.find("meta", attrs={"itemprop": prop})
            )
            if meta and meta.get("content"):
                norm, is_date_only = _clean_and_norm(meta.get("content"))
                if norm:
                    return norm, is_date_only

        # 3. JSON-LD
        for item in json_ld_items:
            itype = str(item.get("@type", "")).lower()
            if any(t in itype for t in ["newsarticle", "article", "blogposting", "techarticle", "webpage", "report"]):
                date_val = item.get("datePublished") or item.get("dateCreated")
                norm, is_date_only = _clean_and_norm(date_val)
                if norm:
                    return norm, is_date_only
        for item in json_ld_items:
            if "datePublished" in item:
                norm, is_date_only = _clean_and_norm(item["datePublished"])
                if norm:
                    return norm, is_date_only

        # 4. <time datetime="...">
        for t in soup.find_all("time"):
            dt_attr = t.get("datetime")
            if dt_attr:
                norm, is_date_only = _clean_and_norm(dt_attr)
                if norm:
                    return norm, is_date_only
            text = t.get_text(strip=True)
            if text:
                norm, is_date_only = _clean_and_norm(text)
                if norm:
                    return norm, is_date_only

        # 5. Visible publication-date elements
        for cls_pattern in ["publish", "post-date", "article-date", "entry-date", "byline-date", "timestamp"]:
            elem = soup.find(class_=re.compile(cls_pattern, re.IGNORECASE))
            if elem:
                norm, is_date_only = _clean_and_norm(elem.get_text(strip=True))
                if norm:
                    return norm, is_date_only

        # 6. Fallback visible text search for relative dates ("Posted 3 hours ago", etc.)
        for tag in soup.find_all(["span", "p", "div", "li"]):
            txt = tag.get_text().replace('\xa0', ' ').strip()
            if txt and len(txt) < 80 and any(w in txt.lower() for w in ["ago", "today", "yesterday"]):
                norm, is_date_only = _clean_and_norm(txt)
                if norm:
                    return norm, is_date_only

    elif record_type == "JOB":
        # 1. JSON-LD JobPosting datePosted
        for item in json_ld_items:
            itype = str(item.get("@type", "")).lower()
            if "jobposting" in itype:
                norm, is_date_only = _clean_and_norm(item.get("datePosted"))
                if norm:
                    return norm, is_date_only
        for item in json_ld_items:
            if "datePosted" in item:
                norm, is_date_only = _clean_and_norm(item["datePosted"])
                if norm:
                    return norm, is_date_only

        # 2. <meta property="datePosted">
        for prop in ["datePosted", "job:datePosted"]:
            meta = (
                soup.find("meta", attrs={"property": prop})
                or soup.find("meta", attrs={"name": prop})
                or soup.find("meta", attrs={"itemprop": prop})
            )
            if meta and meta.get("content"):
                norm, is_date_only = _clean_and_norm(meta.get("content"))
                if norm:
                    return norm, is_date_only

        # 3. <meta property="article:published_time"> / datePublished
        for prop in ["article:published_time", "datePublished"]:
            meta = (
                soup.find("meta", attrs={"property": prop})
                or soup.find("meta", attrs={"name": prop})
                or soup.find("meta", attrs={"itemprop": prop})
            )
            if meta and meta.get("content"):
                norm, is_date_only = _clean_and_norm(meta.get("content"))
                if norm:
                    return norm, is_date_only

        # 4. <time datetime="...">
        for t in soup.find_all("time"):
            dt_attr = t.get("datetime")
            if dt_attr:
                norm, is_date_only = _clean_and_norm(dt_attr)
                if norm:
                    return norm, is_date_only
            text = t.get_text(strip=True)
            if text:
                norm, is_date_only = _clean_and_norm(text)
                if norm:
                    return norm, is_date_only

        # 5. Visible posted date
        for cls_pattern in ["posted", "job-date", "listing-date", "date"]:
            elem = soup.find(class_=re.compile(cls_pattern, re.IGNORECASE))
            if elem:
                norm, is_date_only = _clean_and_norm(elem.get_text(strip=True))
                if norm:
                    return norm, is_date_only

        # 6. Fallback visible text search for relative dates ("Posted 3 weeks ago", etc.)
        for tag in soup.find_all(["span", "p", "div", "li"]):
            txt = tag.get_text().replace('\xa0', ' ').strip()
            if txt and len(txt) < 80 and any(w in txt.lower() for w in ["ago", "today", "yesterday"]):
                norm, is_date_only = _clean_and_norm(txt)
                if norm:
                    return norm, is_date_only

    return None, False


def extract_publication_date(
    html: str,
    record_type: str = "NEWS",
    now: Optional[Any] = None,
) -> Optional[str]:
    """
    Extract publication date as an ISO string. Preserves existing signature.
    """
    date_str, _ = extract_date_info(html, record_type=record_type, now=now)
    return date_str


def extract_candidate_links(
    html: str,
    source_url: str,
    record_type: str,
    max_items: int = MAX_ITEMS_PER_SOURCE,
) -> list[str]:
    """
    Identify individual article or job links from a category/board page.
    Applies source-aware rules, normalizes relative URLs, and removes duplicates.
    Limits output to max_items.
    """
    if not html or not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    record_type = record_type.upper()
    s_lower = source_url.lower()

    candidates: list[str] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        norm = normalize_item_url(href, base_url=source_url)
        if not norm or norm == source_url.rstrip('/'):
            continue

        p_lower = urlparse(norm).path.lower()
        if any(kw in p_lower for kw in EXCLUDED_PATH_KEYWORDS):
            continue

        is_match = False
        if record_type == "NEWS":
            if "techcrunch.com" in s_lower:
                if re.search(r'techcrunch\.com/\d{4}/\d{2}/\d{2}/[^/]+/?$', norm):
                    is_match = True
            elif "venturebeat.com" in s_lower:
                if "venturebeat.com" in norm:
                    parts = [p for p in urlparse(norm).path.strip('/').split('/') if p]
                    if len(parts) >= 2 and parts[0] not in {'category', 'tag', 'author', 'page', 'about', 'events', 'newsletters', 'community'}:
                        is_match = True
            elif "technologyreview.com" in s_lower:
                if re.search(r'technologyreview\.com/20\d\d/\d\d/\d\d/', norm) or re.search(r'technologyreview\.com/\d{4}/\d{2}/\d{2}/\d+/[^/]+', norm):
                    is_match = True
            elif "wired.com" in s_lower:
                if "wired.com/story/" in norm:
                    is_match = True
            elif "engadget.com" in s_lower:
                if "engadget.com" in norm and not any(x in p_lower for x in ['/category/', '/about/', '/tag/']):
                    if (
                        re.search(r'engadget\.com/\d{7}/[^/]+/?$', norm)
                        or re.search(r'engadget\.com/[^/]+/[^/]+-\d+\.html$', norm)
                        or ('/ai/' in p_lower and len(p_lower.strip('/').split('/')) >= 2)
                    ):
                        is_match = True
            else:
                # Generic fallback for other news sources
                parts = [p for p in urlparse(norm).path.strip('/').split('/') if p]
                if len(parts) >= 2 and not any(k in p_lower for k in ['/category/', '/tag/', '/author/', '/topic/']):
                    is_match = True

        elif record_type == "JOB":
            if "ycombinator.com" in s_lower:
                if "/companies/" in norm and "/jobs/" in norm:
                    is_match = True
            elif "builtin.com" in s_lower:
                if "/job/" in norm and re.search(r'/\d+$', norm):
                    is_match = True
            elif "remoteok.com" in s_lower:
                # Matches: /remote-jobs/remote-ai-response-analyst-imerit-technology-1137309
                # Rejects: /remote-jobs, /remote-jobs-in-*, /remote-*-jobs
                if "/remote-jobs/" in norm:
                    p_end = norm.rstrip('/').split('/')[-1]
                    if (
                        not p_end.startswith("remote-jobs-in-")
                        and not p_end.endswith("-jobs")
                        and p_end != "remote-jobs"
                        and re.search(r'\d+', p_end)
                    ):
                        is_match = True
            elif "workingnomads.com" in s_lower:
                # Matches: /jobs/senior-ai-engineer-lemonio-1797731
                # Rejects: /jobs, /jobs/css/..., /remote-*-jobs
                if "/jobs/" in norm:
                    p_end = norm.rstrip('/').split('/')[-1]
                    if (
                        p_end not in {'jobs', 'css', 'assets', 'fonts', 'img'}
                        and not any(norm.endswith(ext) for ext in ['.css', '.js', '.png', '.svg', '.ico', '.woff', '.woff2'])
                        and not p_end.endswith("-jobs")
                    ):
                        is_match = True
            elif "jobspresso.co" in s_lower:
                # Matches: /job/principal-product-manager-conversational-ai/
                # Rejects: /remote-work/, /remote-*-jobs/, /jobs/
                if "/job/" in norm:
                    p_end = norm.rstrip('/').split('/')[-1]
                    if not p_end.endswith(('-jobs', '-work')) and p_end != "job" and p_end != "jobs":
                        is_match = True
            else:
                # Generic fallback for other job sources
                if any(k in p_lower for k in ['/job/', '/jobs/', '/careers/']) and len(p_lower.strip('/').split('/')) >= 2:
                    is_match = True

        if is_match and norm not in seen:
            seen.add(norm)
            candidates.append(norm)
            if len(candidates) >= max_items:
                break

    return candidates


def extract_item_metadata(
    html: str,
    item_url: str,
    source_url: str,
    record_type: str,
    now: Optional[Any] = None,
) -> dict:
    """
    Extract structured metadata from an individual article or job page.
    Does not fabricate missing fields.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    record_type = record_type.upper()
    collected_at = _utc_now()

    # 1. Extract publication/posting date and date-only flag (Fix 4)
    actual_date, is_date_only = extract_date_info(html, record_type=record_type, now=now)

    # 2. Extract Title
    title = None
    og_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "twitter:title"})
    if og_title and og_title.get("content"):
        title = og_title.get("content").strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    company = None
    is_remote = None

    # 3. JSON-LD parsing for title, company, is_remote
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = s.get_text().strip()
            if not raw:
                continue
            data = json.loads(raw)
            items = []
            if isinstance(data, dict):
                items.append(data)
                if "@graph" in data and isinstance(data["@graph"], list):
                    items.extend([x for x in data["@graph"] if isinstance(x, dict)])
            elif isinstance(data, list):
                items.extend([x for x in data if isinstance(x, dict)])

            for item in items:
                itype = str(item.get("@type", "")).lower()
                if record_type == "NEWS" and any(t in itype for t in ["newsarticle", "article"]):
                    if not title and item.get("headline"):
                        title = item.get("headline")
                elif record_type == "JOB" and "jobposting" in itype:
                    if item.get("title"):
                        title = item.get("title")
                    hiring = item.get("hiringOrganization")
                    if isinstance(hiring, dict) and hiring.get("name"):
                        company = hiring.get("name")
                    elif isinstance(hiring, str):
                        company = hiring
                    loc_type = str(item.get("jobLocationType", "")).upper()
                    if loc_type == "TELECOMMUTE":
                        is_remote = True
                    desc = str(item.get("description", "")).lower()
                    if is_remote is None and "remote" in desc:
                        is_remote = True
        except Exception:
            continue

    if record_type == "JOB":
        # Extract company from YC URL if available
        if not company and "ycombinator.com/companies/" in item_url:
            m = re.search(r'ycombinator\.com/companies/([^/]+)/jobs', item_url)
            if m:
                company = m.group(1).replace("-", " ").title()
        if not company:
            site_name = soup.find("meta", attrs={"property": "og:site_name"})
            if site_name and site_name.get("content"):
                company = site_name.get("content").strip()
        if is_remote is None:
            text = soup.get_text().lower()
            if "remote" in text or "work from home" in text:
                is_remote = True

    # Construct schema conforming records (Part 6)
    if record_type == "NEWS":
        record = {
            "recordType": "NEWS",
            "source": {"url": source_url},
            "content": {
                "url": item_url,
                "title": title,
                "published_date": actual_date,
                "is_date_only": is_date_only,
            },
            "collected_at": collected_at,
            "raw_html": html,
            # Backward-compatible convenience attributes
            "record_type": "NEWS",
            "source_url": source_url,
            "item_url": item_url,
            "html": html,
            "published_date": actual_date,
            "is_date_only": is_date_only,
        }
    else:  # JOB
        record = {
            "recordType": "JOB",
            "source": {"url": source_url},
            "content": {
                "url": item_url,
                "company": company,
                "title": title,
                "role": title,
                "date": actual_date,
                "is_remote": is_remote,
                "is_date_only": is_date_only,
            },
            "collected_at": collected_at,
            "raw_html": html,
            # Backward-compatible convenience attributes
            "record_type": "JOB",
            "source_url": source_url,
            "item_url": item_url,
            "html": html,
            "date": actual_date,
            "is_date_only": is_date_only,
        }

    return record


class GeneralDataAgent:
    """
    Process raw crawl results into typed, source-preserved records.

    Usage:
        agent = GeneralDataAgent()
        records = agent.process(crawl_results, record_type="STARTUP")
    """

    def extract_links(
        self,
        html: str,
        source_url: str,
        record_type: str,
        max_items: int = MAX_ITEMS_PER_SOURCE,
    ) -> list[str]:
        """Extract candidate individual article/job URLs from category/board HTML."""
        return extract_candidate_links(html, source_url, record_type, max_items=max_items)

    def extract_metadata(
        self,
        html: str,
        item_url: str,
        source_url: str,
        record_type: str,
        now: Optional[Any] = None,
    ) -> dict:
        """Extract structured record metadata from an individual item HTML page."""
        return extract_item_metadata(html, item_url, source_url, record_type, now=now)

    def evaluate_freshness(
        self,
        record: dict,
        now: Optional[Any] = None,
    ) -> tuple[bool, str]:
        """
        Evaluate if a record is fresh within 24 hours.
        Returns (is_fresh, reason_code):
        - (True, "fresh")
        - (False, "missing_or_invalid_date")
        - (False, "stale")
        - (False, "future")
        """
        rec_type = record.get("recordType") or record.get("record_type", "")
        content = record.get("content", {})
        if rec_type == "NEWS":
            raw_date = content.get("published_date") or record.get("published_date")
        else:
            raw_date = content.get("date") or record.get("date")

        if not raw_date:
            return False, "missing_or_invalid_date"

        now_utc = normalize_datetime(now) if now is not None else datetime.now(timezone.utc)
        target_utc = normalize_datetime(raw_date)
        if target_utc is None or now_utc is None:
            return False, "missing_or_invalid_date"

        delta = (now_utc - target_utc).total_seconds()
        if delta < 0:
            return False, "future"
        if delta > 86400.0:
            return False, "stale"
        return True, "fresh"

    def process(
        self,
        crawl_results: list[dict],
        record_type: str,
        now: Optional[Any] = None,
    ) -> list[dict]:
        """
        Filter and tag a list of crawl results.
        Preserves existing functionality for whole-page records.

        Args:
            crawl_results: Output from IntelligentScrapingAgent.scrape().
            record_type:   One of STARTUP | PRODUCT | JOB | NEWS.
            now:           Optional reference datetime for deterministic freshness testing.

        Returns:
            List of dicts with keys: record_type, source_url, html, collected_at.
        """
        record_type = record_type.upper()
        if record_type not in {"STARTUP", "PRODUCT", "JOB", "NEWS"}:
            raise ValueError(
                f"Unsupported record_type '{record_type}'. "
                "Expected one of: STARTUP, PRODUCT, JOB, NEWS."
            )

        dispatch = {
            "STARTUP": self.process_startup,
            "PRODUCT": self.process_product,
            "JOB":     self.process_job,
            "NEWS":    self.process_news,
        }
        return dispatch[record_type](crawl_results, now=now)

    def process_startup(
        self,
        crawl_results: list[dict],
        now: Optional[Any] = None,
    ) -> list[dict]:
        """Preserve raw crawl results tagged as STARTUP records."""
        return self._preserve(crawl_results, "STARTUP", now=now)

    def process_product(
        self,
        crawl_results: list[dict],
        now: Optional[Any] = None,
    ) -> list[dict]:
        """Preserve raw crawl results tagged as PRODUCT records."""
        return self._preserve(crawl_results, "PRODUCT", now=now)

    def process_job(
        self,
        crawl_results: list[dict],
        now: Optional[Any] = None,
    ) -> list[dict]:
        """Preserve raw crawl results tagged as JOB records (with 24-hour freshness filtering)."""
        return self._preserve(crawl_results, "JOB", now=now)

    def process_news(
        self,
        crawl_results: list[dict],
        now: Optional[Any] = None,
    ) -> list[dict]:
        """Preserve raw crawl results tagged as NEWS records (with 24-hour freshness filtering)."""
        return self._preserve(crawl_results, "NEWS", now=now)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _preserve(
        self,
        crawl_results: list[dict],
        record_type: str,
        now: Optional[Any] = None,
    ) -> list[dict]:
        """
        Core logic: drop failures and empty HTML, stamp timestamp, tag type.
        For NEWS and JOB records, applies 24-hour freshness filtering based on publication date.
        """
        collected_at = _utc_now()
        output: list[dict] = []

        for result in crawl_results:
            if not result.get("success"):
                continue
            html: Optional[str] = result.get("html")
            if not html or not html.strip():
                continue

            # 24-Hour Freshness Filtering for NEWS and JOB records (Phase II)
            if record_type in {"NEWS", "JOB"}:
                date_val = (
                    result.get("published_date")
                    or result.get("date")
                    or result.get("published_at")
                )
                if not is_within_24_hours(date_val, now=now):
                    continue

            record = {
                "record_type":  record_type,
                "recordType":   record_type,
                "source_url":   result["url"],
                "html":         html,
                "collected_at": collected_at,
            }

            # Preserve publication date if available
            if record_type == "NEWS":
                pub_date = result.get("published_date") or result.get("date") or result.get("published_at")
                if pub_date is not None:
                    record["published_date"] = pub_date
            elif record_type == "JOB":
                job_date = result.get("date") or result.get("published_date") or result.get("published_at")
                if job_date is not None:
                    record["date"] = job_date

            output.append(record)

        return output
