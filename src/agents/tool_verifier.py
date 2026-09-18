"""
AI Tool Official Website Verification & Factual Enrichment Agent — Step 4 (Quality Refined).

Verifies candidate AI tools extracted in Step 3 against their official websites:
1. Resolves candidate's true product/company website (filtering out directories, social media, review sites).
2. Requires strong evidence of authenticity:
   - Domain identity consistency
   - Product-specific headings & title branding
   - Prominent brand content presence in body
   Classifies uncertain/weak branding as 'partially_verified' or 'unverified' rather than guessing.
3. Performs factual enrichment from official page evidence:
   - Inputs/Outputs strictly populated only when explicit action/format phrasing is found (no generic word inferences).
   - Factual pricing/free-plan/free-trial extracted exclusively from official page text (zero directory hints used).
   - Status marked only when supported by explicit availability signals or beta/waitlist flags (never assumed 'Active').
   - Official logo extracted only when served by the verified domain as a genuine brand asset or touch icon.
   - Company/Developer, country, launch date, and version strictly guarded against weak inference.
4. Records explicit verification statuses (verified, partially_verified, unverified, failed) and failure reasons.
5. Produces output compatible with canonical AITool schema.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from bs4 import BeautifulSoup
from pydantic import ValidationError

from src.entity.resolver import normalize_entity_name
from src.models.ai_tool import AITool

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Domains that must NEVER be claimed as an official product website
DISALLOWED_OFFICIAL_DOMAINS = {
    # Directory & aggregator domains
    "theresanaiforthat.com",
    "creati.ai",
    "futurepedia.io",
    "toolify.ai",
    "topai.tools",
    "aitools.fyi",
    "futuretools.io",
    "producthunt.com",
    "alternativeto.net",
    "g2.com",
    "capterra.com",
    "trustpilot.com",
    "saasworthy.com",
    "sourceforge.net",
    # News, blog & media sites
    "wsj.com",
    "techcrunch.com",
    "venturebeat.com",
    "wired.com",
    "forbes.com",
    "bloomberg.com",
    "medium.com",
    "substack.com",
    # Social media & community platforms
    "twitter.com",
    "x.com",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
    "discord.com",
    "discord.gg",
    "reddit.com",
    "t.me",
    "telegram.org",
    "tiktok.com",
    "github.blog",
}


# ---------------------------------------------------------------------------
# URL Validation & Normalization Helpers
# ---------------------------------------------------------------------------

def is_disallowed_official_domain(url: str) -> bool:
    """Check whether a URL belongs to a directory, social platform, or review site."""
    if not url or not isinstance(url, str):
        return True
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        host = netloc.split(":")[0].replace("www.", "")
        if not host:
            return True
        for disallowed in DISALLOWED_OFFICIAL_DOMAINS:
            if host == disallowed or host.endswith("." + disallowed):
                return True
        return False
    except Exception:
        return True


def clean_official_url(url: str) -> Optional[str]:
    """
    Clean and validate potential official website URL.
    Returns normalized URL string or None if invalid or disallowed.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None
        if is_disallowed_official_domain(url):
            return None

        # Clean query parameters, removing tracking parameters
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        tracking_prefixes = ("utm_", "ref", "fid", "aff", "fbclid", "gclid", "source")
        cleaned_query = [
            (k, v) for k, v in query_pairs
            if not any(k.lower().startswith(p) for p in tracking_prefixes)
        ]
        new_query = urllib.parse.urlencode(cleaned_query)

        path = parsed.path.rstrip("/")
        host = parsed.netloc.lower().replace("www.", "")
        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            host,
            path or "/",
            "",
            new_query,
            "",
        ))
        return normalized
    except Exception:
        return None


def is_allowed_asset_domain(asset_url: str, official_url: str) -> bool:
    """Check if an image/icon asset is served from the official domain or its subdomains/CDN."""
    try:
        asset_parsed = urllib.parse.urlparse(asset_url)
        official_parsed = urllib.parse.urlparse(official_url)
        asset_host = asset_parsed.netloc.lower().split(":")[0].replace("www.", "")
        official_host = official_parsed.netloc.lower().split(":")[0].replace("www.", "")

        if not asset_host or not official_host:
            return False
        # Exact match or subdomain (e.g., resource.wawebsender.com matches wawebsender.com)
        return asset_host == official_host or asset_host.endswith("." + official_host)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Strict Action-Oriented Input / Output Extraction
# ---------------------------------------------------------------------------

EXPLICIT_INPUT_PATTERNS = [
    (
        r"\b(?:upload|drag\s+and\s+drop|import|attach|paste|select|drop)\s+(?:[^.!?\n]{0,40})?\b(?:image|photo|picture|screenshot|jpg|png|webp|graphic)s?\b|"
        r"\b(?:image|photo|picture)\s+(?:upload|input|to\s+prompt|describer)\b|"
        r"\b(?:turn|convert)\s+(?:any\s+)?(?:image|photo|picture)s?\s+into\b|"
        r"\bsupported\s+(?:inputs?|formats?|files?):?.*?\b(?:jpe?g|png|webp|images?)\b",
        "Image",
    ),
    (
        r"\b(?:enter|type|input|paste|write|submit|provide)\s+(?:[^.!?\n]{0,40})?\b(?:text|prompt|question|query|message|article|content|paragraph)s?\b|"
        r"\b(?:from|with)\s+(?:a\s+)?(?:text\s+prompt|text\s+description)s?\b|"
        r"\btext-to-(?:image|video|speech|audio|code|3d|prompt)\b|"
        r"\b(?:chat\s+with|ask)\s+(?:ai|assistant|questions?)\b",
        "Text",
    ),
    (
        r"\b(?:upload|import|attach|drop|select)\s+(?:[^.!?\n]{0,40})?\b(?:pdf|documents?|docx?|files?|papers?|ebooks?)\b|"
        r"\b(?:chat\s+with|analyze|extract\s+from|read)\s+(?:your\s+)?(?:pdf|documents?|files?)\b|"
        r"\bsupported\s+(?:inputs?|formats?|files?):?.*?\b(?:pdf|docx?|txt)\b",
        "PDF / Document",
    ),
    (
        r"\b(?:paste|input|upload|import|enter)\s+(?:[^.!?\n]{0,40})?\b(?:source\s+code|code|scripts?|repo|repository|code\s+snippets?)\b|"
        r"\bcode-to-(?:code|doc|text)\b",
        "Code",
    ),
    (
        r"\b(?:upload|import|record|provide|drop)\s+(?:[^.!?\n]{0,40})?\b(?:audio|voice|speech|recording|mp3|wav)s?\b|"
        r"\b(?:audio-to-text|speech-to-text|voice\s+input)\b",
        "Audio",
    ),
    (
        r"\b(?:upload|import|drop|provide|attach)\s+(?:[^.!?\n]{0,40})?\b(?:video|mp4|clip|footage|recording)s?\b|"
        r"\bvideo-to-(?:video|text|audio)\b",
        "Video",
    ),
    (
        r"\b(?:enter|paste|input|provide|submit)\s+(?:[^.!?\n]{0,40})?\b(?:url|link|webpage|website\s+url)s?\b|"
        r"\b(?:summarize|analyze|extract\s+from)\s+(?:any\s+)?(?:url|link|webpage|website)\b",
        "URL",
    ),
    (
        r"\b(?:upload|import|drop|attach)\s+(?:[^.!?\n]{0,40})?\b(?:csv|spreadsheets?|excel|xlsx?)\b",
        "Spreadsheet / CSV",
    ),
]

EXPLICIT_OUTPUT_PATTERNS = [
    (
        r"\b(?:generat(?:e|es|ing)|creat(?:e|es|ing)|produc(?:e|es|ing)|turn\s+.*?\s+into)\s+(?:[^.!?\n]{0,40})?\b(?:text\s+)?prompts?\b|"
        r"\b(?:output|result|generates?):?\s*(?:text\s+)?prompts?\b|"
        r"\bimage-to-prompt\b",
        "Text Prompt",
    ),
    (
        r"\b(?:generat(?:e|es|ing)|creat(?:e|es|ing)|produc(?:e|es|ing)|render(?:s|ing)?)\s+(?:[^.!?\n]{0,40})?\b(?:images?|artworks?|visuals?|illustrations?|photos?)\b|"
        r"\btext-to-image\b|"
        r"\b(?:ai\s+image\s+generator|4k\s+ai\s+image\s+generator)\b|"
        r"\b(?:output|generates?):?\s*(?:images?|illustrations?)\b",
        "Generated Image",
    ),
    (
        r"\b(?:generat(?:e|es|ing)|creat(?:e|es|ing)|produc(?:e|es|ing)|provid(?:e|es|ing)|build(?:s|ing)?)\s+(?:[^.!?\n]{0,40})?\b(?:summar(?:y|ies))\b|"
        r"\bsummariz(?:e|es|ing)\s+(?:your|any|the|text|articles?|documents?|videos?|webpages?)\b|"
        r"\b(?:output|result):?\s*summar(?:y|ies)\b",
        "Summary",
    ),
    (
        r"\b(?:transcrib(?:e|es|ing)|generat(?:e|es|ing))\s+(?:[^.!?\n]{0,40})?\btranscripts?\b|"
        r"\b(?:speech-to-text|audio-to-text)\b|"
        r"\b(?:output|result):?\s*transcripts?\b",
        "Transcript",
    ),
    (
        r"\b(?:generat(?:e|es|ing)|writ(?:e|es|ing)|produc(?:e|es|ing))\s+(?:[^.!?\n]{0,40})?\b(?:code|scripts?|code\s+snippets?|programs?)\b|"
        r"\btext-to-code\b|"
        r"\b(?:output|generates?):?\s*code\b",
        "Code",
    ),
    (
        r"\b(?:generat(?:e|es|ing)|creat(?:e|es|ing)|produc(?:e|es|ing))\s+(?:[^.!?\n]{0,40})?\b(?:voiceovers?|audio|speech|voices?)\b|"
        r"\btext-to-speech\b|"
        r"\b(?:output|generates?):?\s*(?:audio|voice|speech)\b",
        "Audio",
    ),
    (
        r"\b(?:generat(?:e|es|ing)|creat(?:e|es|ing)|produc(?:e|es|ing)|render(?:s|ing)?)\s+(?:[^.!?\n]{0,40})?\b(?:videos?|animations?|clips?)\b|"
        r"\b(?:text-to-video|image-to-video)\b|"
        r"\b(?:output|generates?):?\s*videos?\b",
        "Video",
    ),
    (
        r"\b(?:generat(?:e|es|ing)|creat(?:e|es|ing)|produc(?:e|es|ing))\s+(?:[^.!?\n]{0,40})?\b(?:reports?|audits?|analyses|analytics)\b|"
        r"\b(?:detection\s+report|ai\s+detector\s+score|detection\s+score)\b|"
        r"\b(?:output|result):?\s*reports?\b",
        "Report",
    ),
]

PLATFORM_KEYWORDS = [
    ("web", "Web"),
    ("macos", "macOS"),
    ("mac os", "macOS"),
    ("windows", "Windows"),
    ("linux", "Linux"),
    ("ios", "iOS"),
    ("android", "Android"),
    ("chrome extension", "Chrome Extension"),
    ("vs code", "VS Code Extension"),
    ("vscode", "VS Code Extension"),
    ("figma plugin", "Figma Plugin"),
]

INTEGRATION_KEYWORDS = [
    ("github", "GitHub"),
    ("gitlab", "GitLab"),
    ("slack", "Slack"),
    ("discord", "Discord"),
    ("notion", "Notion"),
    ("google drive", "Google Drive"),
    ("figma", "Figma"),
    ("zapier", "Zapier"),
    ("hubspot", "HubSpot"),
    ("shopify", "Shopify"),
    ("wordpress", "WordPress"),
]


def extract_concrete_inputs_outputs(html: str, text: str) -> tuple[list[str], list[str]]:
    """
    Extract strictly verified concrete input and output types from official page content.
    Requires explicit action/format phrasing. Generic word appearances are ignored.
    """
    # Use clean text to avoid matching HTML tags, attributes, or script links
    text_lower = text.lower()
    inputs: list[str] = []
    outputs: list[str] = []

    for pattern, label in EXPLICIT_INPUT_PATTERNS:
        if re.search(pattern, text_lower) and label not in inputs:
            inputs.append(label)

    for pattern, label in EXPLICIT_OUTPUT_PATTERNS:
        if re.search(pattern, text_lower) and label not in outputs:
            outputs.append(label)

    return inputs, outputs


def extract_platforms_and_integrations(text: str) -> tuple[list[str], list[str]]:
    """Extract mentioned platforms and software integrations from page text."""
    text_lower = text.lower()
    platforms: list[str] = []
    integrations: list[str] = []

    for needle, label in PLATFORM_KEYWORDS:
        if re.search(rf"\b{re.escape(needle)}\b", text_lower) and label not in platforms:
            platforms.append(label)

    for needle, label in INTEGRATION_KEYWORDS:
        if re.search(rf"\b{re.escape(needle)}\b", text_lower) and label not in integrations:
            integrations.append(label)

    return platforms, integrations


def extract_pricing_evidence(html: str, text: str, raw_hints: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Extract verified pricing model, starting price, and plan flags exclusively from the official page.
    Never infers pricing from directory hints, free homepages, or standard signups.
    """
    text_lower = text.lower()
    pricing_model: Optional[str] = None
    free_plan: Optional[bool] = None
    free_trial: Optional[bool] = None
    starting_price: Optional[str] = None
    usage_limits: Optional[str] = None

    # Free plan: requires explicit plan/tier wording, not incidental use of the word 'free'
    if any(k in text_lower for k in ("100% free", "free plan", "free tier", "free forever", "free version available", "free edition")):
        free_plan = True

    # Free trial: requires explicit trial statement
    if any(k in text_lower for k in ("free trial", "start your free trial", "start free trial", "7-day trial", "14-day trial", "30-day trial", "free for 14 days", "free for 7 days")):
        free_trial = True

    # Starting price extraction ($XX/month, $XX/mo, $XX/year)
    price_match = re.search(r"\$(\d+(?:\.\d{2})?)\s*(?:/|\bper\b)\s*(?:month|mo|year|seat)\b", text, re.IGNORECASE)
    if price_match:
        starting_price = f"${price_match.group(1)}/month"

    # Pricing model determination based strictly on official page evidence
    has_paid_signals = bool(starting_price or any(k in text_lower for k in ("pro plan", "paid plan", "premium plan", "pricing", "subscription", "upgrade to pro")))
    if free_plan is True and has_paid_signals:
        pricing_model = "Freemium"
    elif free_plan is True and not has_paid_signals:
        pricing_model = "Free"
    elif "freemium" in text_lower:
        pricing_model = "Freemium"
    elif starting_price or ("subscription" in text_lower and any(sym in text for sym in ("$", "€", "£"))):
        pricing_model = "Paid"

    return {
        "pricing_model": pricing_model,
        "starting_price": starting_price,
        "free_plan": free_plan,
        "free_trial": free_trial,
        "important_usage_limits": usage_limits,
    }


def determine_current_status(soup: BeautifulSoup, text: str, page_title: str) -> Optional[str]:
    """
    Determine product availability status from explicit page evidence.
    Never marks a product 'Active' solely because its webpage responded.
    """
    combined_lower = f"{page_title} {text[:2000]}".lower()

    if any(k in combined_lower for k in ("in beta", "public beta", "private beta", "beta version", "join beta")):
        return "Beta"
    if any(k in combined_lower for k in ("join waitlist", "join the waitlist", "coming soon", "request early access", "pre-launch")):
        return "Pre-launch"
    if any(k in combined_lower for k in ("discontinued", "shutting down", "shut down", "service has ended", "no longer available")):
        return "Discontinued"

    # Active status requires explicit availability call to action or interactive tool interface
    has_live_cta = any(k in combined_lower for k in (
        "available now", "get started", "launch app", "web app live",
        "try it now", "start generating", "generate now", "try for free",
        "download extension", "add to chrome", "install now"
    ))
    has_interactive_widget = bool(
        soup.find("form") and (soup.find("input", type="file") or soup.find("textarea"))
    )

    if has_live_cta or has_interactive_widget:
        return "Active"

    return None


def extract_official_logo(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    Extract verified official logo or icon from page HTML without fabricating fake URLs.
    Guarantees asset is served from verified official domain.
    Preference order:
    1. apple-touch-icon or large app icon link served by official domain
    2. Explicit brand <img> element labeled as logo in header/nav
    3. og:image only if explicitly named logo/icon/brand
    4. Standard favicon explicitly declared in <head> and served by official domain
    """
    # 1. High-resolution touch icon or dedicated app icon
    touch_icons = soup.find_all("link", rel=lambda r: r and any(x in str(r).lower() for x in ("apple-touch-icon", "icon")))
    for icon in touch_icons:
        href = (icon.get("href") or "").strip()
        if href:
            full = urllib.parse.urljoin(base_url, href)
            if full.startswith("http") and is_allowed_asset_domain(full, base_url):
                # Prioritize touch icons, svgs, or sized pngs
                rel_str = str(icon.get("rel")).lower()
                if "apple-touch-icon" in rel_str or any(ext in full.lower() for ext in (".svg", "192", "96", "32", "png")):
                    return full

    # 2. Explicit logo img element in header/nav
    header_nav = soup.find(["header", "nav"]) or soup
    logo_img = header_nav.find("img", attrs={"alt": re.compile(r"logo", re.I)}) or header_nav.find("img", class_=re.compile(r"logo", re.I))
    if logo_img and logo_img.get("src"):
        src = logo_img.get("src").strip()
        full = urllib.parse.urljoin(base_url, src)
        if full.startswith("http") and is_allowed_asset_domain(full, base_url):
            return full

    # 3. og:image if named as logo/mark/icon
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        content = og_img.get("content").strip()
        full = urllib.parse.urljoin(base_url, content)
        if full.startswith("http") and is_allowed_asset_domain(full, base_url):
            if any(k in full.lower() for k in ("logo", "brand", "icon", "mark", "avatar")):
                return full

    # 4. Standard favicon explicitly declared in head
    for icon in touch_icons:
        href = (icon.get("href") or "").strip()
        if href:
            full = urllib.parse.urljoin(base_url, href)
            if full.startswith("http") and is_allowed_asset_domain(full, base_url):
                return full

    # Never fabricate /logo.png or /favicon.ico if not declared in HTML
    return None


def verify_page_authenticity(
    tool_name: str,
    official_url: str,
    soup: BeautifulSoup,
    body_text: str,
) -> tuple[str, list[str]]:
    """
    Verify whether the website truly represents the named AI tool using multi-point evidence:
    - Domain identity consistency
    - Page title and main heading (H1) branding
    - Prominent brand content presence in body
    - Brand logo references

    Returns:
        (status, errors) where status is 'verified', 'partially_verified', or 'unverified'
    """
    errors: list[str] = []

    # 1. Clean and normalize tool name
    core_name = re.split(r"[:\-\|\(]", tool_name)[0].strip()
    norm_tool = normalize_entity_name(tool_name).lower()
    norm_core = normalize_entity_name(core_name).lower()

    # 2. Domain brand match check
    parsed = urllib.parse.urlparse(official_url)
    host = parsed.netloc.lower().replace("www.", "").split(":")[0]
    domain_slug = re.sub(r"\.(com|org|net|ai|io|co|app|dev|tools|xyz|so|me|cc)$", "", host)
    domain_clean = re.sub(r"[^a-z0-9]", "", domain_slug)
    core_clean = re.sub(r"[^a-z0-9]", "", norm_core)
    brand_clean = re.sub(r"(?:ai|app|tool|bot|io|generator|detector|pro)$", "", core_clean).strip() or core_clean

    domain_match = False
    if brand_clean and (brand_clean in domain_clean or domain_clean in brand_clean):
        domain_match = True
    elif core_clean and (core_clean in domain_clean or domain_clean in core_clean):
        domain_match = True
    elif core_clean:
        core_words = [
            w for w in re.split(r"[^a-z0-9]+", norm_core)
            if len(w) > 2 and w not in ("the", "for", "and", "tool", "app", "pro", "free", "ai")
        ]
        if core_words and all(w in domain_clean for w in core_words):
            domain_match = True

    # 3. Title and Heading (H1) match check
    page_title = soup.title.get_text(strip=True).lower() if soup.title else ""
    page_title_clean = re.sub(r"[^a-z0-9]", "", page_title)
    h1_tags = [h.get_text(strip=True).lower() for h in soup.find_all("h1")]
    h1_text = " ".join(h1_tags)
    h1_clean = re.sub(r"[^a-z0-9]", "", h1_text)

    in_title = bool(
        norm_core in page_title
        or (brand_clean and brand_clean in page_title_clean)
        or (domain_clean and domain_clean in page_title_clean)
    )
    in_h1 = bool(
        norm_core in h1_text
        or (brand_clean and brand_clean in h1_clean)
        or (domain_clean and domain_clean in h1_clean)
    )

    # 4. Body prominence check
    body_lower = body_text.lower()
    body_clean = re.sub(r"[^a-z0-9]", " ", body_lower)
    mentions = len(re.findall(rf"\b{re.escape(norm_core)}\b", body_lower))
    if mentions == 0 and brand_clean:
        mentions = len(re.findall(rf"\b{re.escape(brand_clean)}\b", body_clean))

    # 5. Header / logo alt branding check
    header_brand = False
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").lower()
        cls = " ".join(img.get("class") or []).lower()
        if ("logo" in alt or "logo" in cls) and (
            norm_core in alt or (brand_clean and brand_clean in re.sub(r"[^a-z0-9]", "", alt))
        ):
            header_brand = True
            break

    # Evaluation:
    # Verified requires strong, corroborating evidence:
    # (Domain matches brand AND (Title or H1 or prominent body mentions >= 2))
    # OR (Title matches AND H1 matches AND prominent body mentions >= 2)
    if domain_match and (in_title or in_h1 or mentions >= 2):
        return "verified", []
    elif in_title and in_h1 and mentions >= 2:
        return "verified", []

    # Partial verification: brand is present on page but domain is not dedicated or title lacks product identity
    if in_title or in_h1 or mentions >= 1:
        msg = f"Partial branding evidence for '{tool_name}' on domain '{host}' (title: '{page_title[:60]}', mentions: {mentions})"
        errors.append(msg)
        return "partially_verified", errors

    # Unverified: no substantial product branding found
    msg = f"Insufficient branding evidence for '{tool_name}' on official page title '{page_title[:60]}'"
    errors.append(msg)
    return "unverified", errors


# ---------------------------------------------------------------------------
# Tool Verifier Agent
# ---------------------------------------------------------------------------

class ToolVerifier:
    """
    Verifies candidate AI tools by fetching and inspecting their official websites.
    Enforces strict zero-fabrication rules, honest status classification,
    and output compatibility with the canonical AITool schema.
    """

    def __init__(self, timeout_sec: float = 12.0, request_delay_sec: float = 0.5):
        self.timeout_sec = timeout_sec
        self.request_delay_sec = request_delay_sec
        self.stats: dict[str, Any] = {
            "candidates_loaded": 0,
            "candidates_attempted": 0,
            "verified": 0,
            "partially_verified": 0,
            "unverified": 0,
            "failed": 0,
            "official_websites_resolved": 0,
            "logos_resolved": 0,
            "network_failures": 0,
            "errors": [],
        }

    def fetch_page(self, url: str) -> tuple[Optional[int], Optional[str], Optional[str]]:
        """
        Safely fetch raw HTML from a target URL.
        Returns: (status_code, html_content, error_message)
        """
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                status = getattr(resp, "status", 200)
                html = resp.read().decode("utf-8", errors="replace")
                return status, html, None
        except urllib.error.HTTPError as exc:
            self.stats["network_failures"] += 1
            if exc.code == 403:
                msg = "HTTP 403 Forbidden — site blocked automated access"
            elif exc.code == 404:
                msg = "HTTP 404 Not Found"
            elif exc.code == 429:
                msg = "HTTP 429 Too Many Requests"
            else:
                msg = f"HTTP Error {exc.code}: {exc.reason}"
            return exc.code, None, msg
        except urllib.error.URLError as exc:
            self.stats["network_failures"] += 1
            return None, None, f"Connection error: {exc.reason}"
        except (TimeoutError, socket.timeout):
            self.stats["network_failures"] += 1
            return None, None, "Request timed out"
        except Exception as exc:
            self.stats["network_failures"] += 1
            return None, None, f"Unexpected fetch error: {exc}"

    def resolve_official_website(self, candidate: dict[str, Any]) -> tuple[Optional[str], list[str]]:
        """
        Determine candidate's actual official product website.
        Follows directory external links, or inspects discovery permalinks when available.
        Ensures directory, review, and social media URLs are never accepted as official.
        """
        errors: list[str] = []

        # 1. Check if external_product_url already captured in discovery raw_metadata
        ext_url = candidate.get("raw_metadata", {}).get("external_product_url")
        if ext_url:
            clean_url = clean_official_url(ext_url)
            if clean_url:
                return clean_url, errors
            else:
                errors.append(f"Discovered external URL was invalid or disallowed: {ext_url}")

        # 2. Check discovered_url
        disc_url = candidate.get("discovered_url", "")
        if not disc_url:
            errors.append("No discovered URL or external product URL provided")
            return None, errors

        # If discovered_url itself is already an external website (not a directory)
        clean_disc = clean_official_url(disc_url)
        if clean_disc and not is_disallowed_official_domain(disc_url):
            return clean_disc, errors

        # 3. Discovered URL is a directory permalink (e.g. TAAFT / Creati.ai):
        # Fetch the directory page to locate outbound product link
        logger.debug("Attempting to resolve official website from directory page: %s", disc_url)
        status, html, err = self.fetch_page(disc_url)
        if err or not html:
            errors.append(f"Directory listing unavailable: {err or f'status {status}'}")
            return None, errors

        # Parse directory page for outbound links
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if href.startswith("http"):
                clean_candidate = clean_official_url(href)
                if clean_candidate and not is_disallowed_official_domain(clean_candidate):
                    return clean_candidate, errors

        errors.append("No eligible official product website link found on directory page")
        return None, errors

    def verify_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        """
        Verify a single candidate record against its resolved official website.
        Extracts factual evidence, evaluates status, and constructs a verified record.
        """
        self.stats["candidates_attempted"] += 1
        tool_name = candidate.get("tool_name", "")
        candidate_id = candidate.get("candidate_id") or f"candidate-{normalize_entity_name(tool_name).replace(' ', '-')}"
        verification_errors: list[str] = []

        # 1. Resolve official website
        official_url, resolve_errors = self.resolve_official_website(candidate)
        verification_errors.extend(resolve_errors)

        if not official_url:
            self.stats["unverified"] += 1
            return self._build_record(
                candidate=candidate,
                candidate_id=candidate_id,
                official_url=None,
                verification_status="unverified",
                verification_errors=verification_errors,
            )

        self.stats["official_websites_resolved"] += 1

        # Rate-limiting delay between external site requests
        if self.request_delay_sec > 0:
            time.sleep(self.request_delay_sec)

        # 2. Fetch official website
        status, html, fetch_error = self.fetch_page(official_url)
        if fetch_error or not html or status != 200:
            verification_errors.append(f"Official website failed ({official_url}): {fetch_error or f'HTTP {status}'}")
            self.stats["failed"] += 1
            return self._build_record(
                candidate=candidate,
                candidate_id=candidate_id,
                official_url=official_url,
                verification_status="failed",
                verification_errors=verification_errors,
            )

        # 3. Parse and verify page authenticity
        soup = BeautifulSoup(html, "html.parser")
        # Remove script and style elements from text extraction
        for element in soup(["script", "style", "noscript"]):
            element.extract()

        page_title = soup.title.get_text(strip=True) if soup.title else ""
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag.get("content").strip()

        body_sample = soup.get_text(separator=" ", strip=True)

        # Robust multi-point authenticity verification
        verification_status, auth_errors = verify_page_authenticity(
            tool_name=tool_name,
            official_url=official_url,
            soup=soup,
            body_text=body_sample,
        )
        verification_errors.extend(auth_errors)
        self.stats[verification_status] += 1

        # 4. Extract factual enrichment
        short_desc = meta_desc or candidate.get("short_description")
        detailed_overview = body_sample[:500] if len(body_sample) > 100 else short_desc

        # Status: derived strictly from explicit page evidence
        current_status = determine_current_status(soup, body_sample, page_title)

        # Concrete inputs and outputs: action-oriented patterns only
        concrete_inputs, concrete_outputs = extract_concrete_inputs_outputs(html, body_sample)

        # Platforms and integrations
        platforms, integrations = extract_platforms_and_integrations(body_sample)
        if not platforms and official_url.startswith("http"):
            platforms = ["Web"]

        # API availability: strictly guarded
        api_availability: Optional[bool] = None
        if re.search(r"\b(rest api|api docs?|api access|developer api)\b", body_sample, re.IGNORECASE):
            api_availability = True

        # Open source status: strictly guarded
        open_source_status: Optional[str] = None
        github_link = soup.find("a", href=lambda h: h and "github.com/" in h)
        if github_link and re.search(r"\b(open source|apache 2\.0|mit license|gpl)\b", body_sample, re.IGNORECASE):
            open_source_status = "Open Source"

        # Pricing evidence: extracted strictly from official page, zero directory hints
        pricing_data = extract_pricing_evidence(html, body_sample, raw_hints=None)

        # Logo discovery: verified domain asset only
        logo_url = extract_official_logo(soup, official_url)
        if logo_url:
            self.stats["logos_resolved"] += 1

        # Verified categories and tags
        categories = list(candidate.get("categories") or [])
        tags = list(candidate.get("tags") or [])

        # Company / Developer: strictly guarded, avoid messy footer boilerplate
        company_developer = candidate.get("company_developer")
        if not company_developer:
            footer = soup.find("footer")
            if footer:
                cr_match = re.search(r"(?:©|\bCopyright\b)\s*(?:20\d\d\s*)?([A-Z][A-Za-z0-9\s,\.\-&]+(?:Inc\.|LLC|Ltd\.|GmbH|Technologies|Labs|AI|Corporation|Corp\.))\b", footer.get_text())
                if cr_match:
                    clean_cr = cr_match.group(1).strip()
                    if 3 < len(clean_cr) < 50:
                        company_developer = clean_cr

        now_iso = datetime.now(timezone.utc).isoformat()

        record = self._build_record(
            candidate=candidate,
            candidate_id=candidate_id,
            official_url=official_url,
            verification_status=verification_status,
            verification_errors=verification_errors,
            company_developer=company_developer,
            logo_url=logo_url,
            short_description=short_desc,
            detailed_overview=detailed_overview,
            current_status=current_status,
            categories=categories,
            tags=tags,
            inputs=concrete_inputs,
            outputs=concrete_outputs,
            supported_platforms=platforms,
            integrations=integrations,
            api_availability=api_availability,
            open_source_status=open_source_status,
            pricing_model=pricing_data["pricing_model"],
            starting_price=pricing_data["starting_price"],
            free_plan=pricing_data["free_plan"],
            free_trial=pricing_data["free_trial"],
            important_usage_limits=pricing_data["important_usage_limits"],
            last_verified_date=now_iso,
        )
        return record

    def _build_record(
        self,
        candidate: dict[str, Any],
        candidate_id: str,
        official_url: Optional[str],
        verification_status: str,
        verification_errors: list[str],
        company_developer: Optional[str] = None,
        logo_url: Optional[str] = None,
        short_description: Optional[str] = None,
        detailed_overview: Optional[str] = None,
        current_status: Optional[str] = None,
        categories: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        inputs: Optional[list[str]] = None,
        outputs: Optional[list[str]] = None,
        supported_platforms: Optional[list[str]] = None,
        integrations: Optional[list[str]] = None,
        api_availability: Optional[Any] = None,
        open_source_status: Optional[Any] = None,
        pricing_model: Optional[str] = None,
        starting_price: Optional[str] = None,
        free_plan: Optional[bool] = None,
        free_trial: Optional[bool] = None,
        important_usage_limits: Optional[str] = None,
        last_verified_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Construct verified record dictionary compatible with AITool schema."""
        now_iso = datetime.now(timezone.utc).isoformat()
        tool_name = candidate.get("tool_name") or "Unnamed Tool"

        verification_source = "Official Website" if official_url else None
        verification_source_url = official_url if official_url else None

        record = {
            # Metadata & Verification
            "candidate_id": candidate_id,
            "record_id": candidate_id,
            "entity_type": "tool",
            "verification_status": verification_status,
            "verification_errors": verification_errors,
            "created_at": candidate.get("discovery_timestamp") or now_iso,
            "updated_at": now_iso,
            # Identity
            "tool_name": tool_name,
            "company_developer": company_developer or candidate.get("company_developer"),
            "official_website": official_url,
            "logo_url": logo_url,
            "country": None,
            "version": None,
            "launch_date": None,
            "current_status": current_status,
            # Description
            "short_description": short_description or candidate.get("short_description"),
            "detailed_overview": detailed_overview,
            # Product
            "primary_task": (categories[0] if categories else None),
            "categories": categories or list(candidate.get("categories") or []),
            "tags": tags or list(candidate.get("tags") or []),
            "key_features": [],
            "main_use_cases": [],
            "ai_capabilities": [],
            "inputs": inputs or [],
            "outputs": outputs or [],
            "supported_platforms": supported_platforms or [],
            "integrations": integrations or [],
            "api_availability": api_availability,
            "open_source_status": open_source_status,
            "signup_requirement": None,
            # Pricing (guarded: no directory hint fallback)
            "pricing_model": pricing_model,
            "starting_price": starting_price,
            "free_plan": free_plan,
            "free_trial": free_trial,
            "important_usage_limits": important_usage_limits,
            # Quality & Traceability
            "pros": [],
            "cons": [],
            "limitations": [],
            "ai_orbit_summary": None,
            "usage_adoption_signals": None,
            "last_verified_date": last_verified_date,
            "discovery_source": candidate.get("discovery_source"),
            "discovery_source_url": candidate.get("discovery_source_url"),
            "verification_source": verification_source,
            "verification_source_url": verification_source_url,
            "discovery_references": candidate.get("discovery_references") or [],
        }
        return record

    def verify_candidates(
        self,
        candidates: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Verify up to limit candidate records."""
        self.stats["candidates_loaded"] = len(candidates)
        subset = candidates[:limit]
        results: list[dict[str, Any]] = []

        for idx, cand in enumerate(subset, 1):
            name = cand.get("tool_name", "Unknown")
            logger.info("[%d/%d] Verifying candidate: %s", idx, len(subset), name)
            verified_rec = self.verify_candidate(cand)
            results.append(verified_rec)

        return results

    def verify_and_save(
        self,
        input_file: str = "data/output/raw_ai_tools.json",
        output_file: str = "data/output/verified_ai_tools.json",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Load raw candidates, verify up to limit, and save results."""
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")

        with open(input_file, "r", encoding="utf-8") as f:
            raw_candidates = json.load(f)

        verified = self.verify_candidates(raw_candidates, limit=limit)

        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(verified, f, indent=2, ensure_ascii=False)

        logger.info("Saved %d verified AI tools to %s", len(verified), output_file)
        return verified
