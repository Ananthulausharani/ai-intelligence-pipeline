"""
AI Tool Deduplication Engine — Step 6.

Deterministic deduplication implementing the guideline's identity rules:
1. Official domain
2. Company / developer
3. Product name
4. Product URL
5. Underlying product identity

Merging strategy:
- Preserves all unique discovery references
- Preserves strongest verified evidence (verified > partially_verified > unverified)
- Retains canonical official URL
- Merges multi-category, tag, modality, and platform arrays
- Does not merge genuinely different products with similar names
"""

import logging
from typing import Any, Optional, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src.entity.resolver import normalize_entity_name
from src.models.ai_tool import AITool

logger = logging.getLogger(__name__)


def extract_canonical_domain(url: Optional[str]) -> str:
    """Extract clean domain without www., subdomains for directories, or tracking."""
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower().split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def normalize_clean_url(url: Optional[str]) -> str:
    """Normalize URL by stripping tracking parameters, fragments, and trailing slashes."""
    if not url or not isinstance(url, str):
        return ""
    url_clean = url.strip()
    try:
        parsed = urlparse(url_clean)
        if not parsed.scheme or not parsed.netloc:
            return url_clean
        # Strip common advertising/tracking query parameters
        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        tracking_prefixes = ("utm_", "ref", "fid", "aff", "fbclid", "gclid", "source")
        cleaned_query = [
            (k, v) for k, v in query_pairs
            if not any(k.lower().startswith(p) for p in tracking_prefixes)
        ]
        new_query = urlencode(cleaned_query)
        path = parsed.path.rstrip("/")
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]

        return urlunparse((
            parsed.scheme.lower(),
            netloc,
            path,
            "",
            new_query,
            "",
        ))
    except Exception:
        return url_clean.split("?")[0].rstrip("/")


class ToolDeduplicator:
    """
    Deterministic deduplication and record merger for AI Tool candidate records.
    """

    DIRECTORY_DOMAINS = {
        "theresanaiforthat.com",
        "creati.ai",
        "producthunt.com",
        "futurepedia.io",
        "toolify.ai",
        "topai.tools",
    }

    def __init__(self):
        self.stats: dict[str, int] = {
            "total_input_records": 0,
            "unique_retained_records": 0,
            "duplicates_merged": 0,
            "domain_matches": 0,
            "product_url_matches": 0,
            "name_developer_matches": 0,
        }

    def deduplicate(
        self, records: list[Union[dict[str, Any], AITool]]
    ) -> list[Union[dict[str, Any], AITool]]:
        """
        Deduplicate a list of AI Tool records deterministically.
        Supports both dict and AITool objects, returning items of the same type.
        """
        self.stats["total_input_records"] = len(records)
        unique_records: list[dict[str, Any]] = []
        is_aitool_input = bool(records and isinstance(records[0], AITool))

        # Lookup indices
        by_domain: dict[str, dict[str, Any]] = {}
        by_product_url: dict[str, dict[str, Any]] = {}
        by_name: dict[str, dict[str, Any]] = {}

        for item in records:
            rec = item.to_dict() if isinstance(item, AITool) else dict(item)

            tool_name = rec.get("tool_name", "")
            norm_name = normalize_entity_name(tool_name)
            if not norm_name:
                continue

            official_url = rec.get("official_website") or ""
            domain = extract_canonical_domain(str(official_url))
            norm_url = normalize_clean_url(str(official_url))

            # Disregard generic directory domains as official tool domains
            is_valid_official_domain = bool(domain and domain not in self.DIRECTORY_DOMAINS)

            # Check for existing duplicate
            existing_match: Optional[dict[str, Any]] = None
            match_reason = ""

            if is_valid_official_domain and domain in by_domain:
                existing_match = by_domain[domain]
                match_reason = "domain"
                self.stats["domain_matches"] += 1
            elif norm_url and norm_url in by_product_url and not any(d in norm_url for d in self.DIRECTORY_DOMAINS):
                existing_match = by_product_url[norm_url]
                match_reason = "product_url"
                self.stats["product_url_matches"] += 1
            elif norm_name in by_name:
                cand = by_name[norm_name]
                # Compare company or verify that neither has conflicting distinct domains
                existing_dev = normalize_entity_name(cand.get("company_developer") or "")
                rec_dev = normalize_entity_name(rec.get("company_developer") or "")
                cand_domain = extract_canonical_domain(str(cand.get("official_website") or ""))

                # If domains match or one is missing, and developers don't conflict, merge
                if (not domain or not cand_domain or domain == cand_domain) and (
                    not existing_dev or not rec_dev or existing_dev == rec_dev
                ):
                    existing_match = cand
                    match_reason = "name_developer"
                    self.stats["name_developer_matches"] += 1

            if existing_match is not None:
                self.stats["duplicates_merged"] += 1
                self._merge_into(existing_match, rec)
                continue

            # New unique record
            unique_records.append(rec)
            by_name[norm_name] = rec
            if is_valid_official_domain:
                by_domain[domain] = rec
            if norm_url and not any(d in norm_url for d in self.DIRECTORY_DOMAINS):
                by_product_url[norm_url] = rec

        self.stats["unique_retained_records"] = len(unique_records)
        logger.info(
            "Deduplication complete: %d inputs -> %d unique (%d duplicates merged)",
            self.stats["total_input_records"],
            self.stats["unique_retained_records"],
            self.stats["duplicates_merged"],
        )

        if is_aitool_input:
            return [AITool(**r) for r in unique_records]
        return unique_records

    def _merge_into(self, target: dict[str, Any], source: dict[str, Any]) -> None:
        """
        Merge source record into target record deterministically:
        - Combine discovery references
        - Prefer verified evidence over unverified
        - Merge multi-valued lists
        - Fill missing fields
        """
        # 1. Merge discovery references preserving source traceability
        existing_refs = target.get("discovery_references") or []
        existing_source_urls = {
            (r.get("source"), r.get("discovered_url")) for r in existing_refs if isinstance(r, dict)
        }
        for new_ref in source.get("discovery_references") or []:
            if isinstance(new_ref, dict):
                key = (new_ref.get("source"), new_ref.get("discovered_url"))
                if key not in existing_source_urls:
                    existing_refs.append(new_ref)
                    existing_source_urls.add(key)
        target["discovery_references"] = existing_refs

        # 2. Prefer verified verification status
        target_v = str(target.get("verification_status") or "").lower()
        source_v = str(source.get("verification_status") or "").lower()
        if target_v != "verified" and source_v == "verified":
            target["verification_status"] = "verified"
            target["official_website"] = source.get("official_website") or target.get("official_website")
            target["verification_source"] = source.get("verification_source") or target.get("verification_source")
            target["verification_source_url"] = source.get("verification_source_url") or target.get("verification_source_url")

        # 3. Canonical official website: prefer clean root domain without extra query params
        target_url = str(target.get("official_website") or "")
        source_url = str(source.get("official_website") or "")
        if not target_url and source_url:
            target["official_website"] = source_url
        elif target_url and source_url and len(source_url) < len(target_url) and "?" not in source_url:
            # Shorter clean URL without queries preferred as canonical
            target["official_website"] = source_url

        # 4. Fill in missing scalar fields
        for field in (
            "company_developer", "logo_url", "country", "version", "launch_date",
            "current_status", "primary_task", "pricing_model", "starting_price",
            "free_plan", "free_trial", "important_usage_limits", "api_availability",
            "open_source_status", "signup_requirement", "short_description",
            "detailed_overview", "ai_orbit_summary", "usage_adoption_signals"
        ):
            if target.get(field) is None and source.get(field) is not None:
                target[field] = source[field]

        # 5. Merge multi-valued lists
        for list_field in (
            "categories", "tags", "key_features", "main_use_cases",
            "ai_capabilities", "inputs", "outputs", "supported_platforms",
            "integrations", "pros", "cons", "limitations"
        ):
            target_list = target.get(list_field) or []
            source_list = source.get(list_field) or []
            for item in source_list:
                if item and item not in target_list:
                    target_list.append(item)
            target[list_field] = target_list
