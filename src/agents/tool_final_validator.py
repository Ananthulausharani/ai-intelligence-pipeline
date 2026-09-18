"""
Final Grounding & Cleanliness Validator for AI Tools — Step 6.

Enforces the 8 mandatory validation gates before Google Sheets export:
1. Required identity (tool name exists, canonical official URL exists)
2. Verification status acceptable (verified or partially_verified, no directory-only records)
3. Description presence (short description and detailed overview exist)
4. Description quality & grounding (no unsupported claims or hype language)
5. Null correctness (unknown fields are None, empty lists are [], no generic placeholders)
6. Duplicate detection (no duplicate canonical domains or product URLs)
7. Official links & logo authenticity (official domain canonical, logo host authorized)
8. Data cleanliness (reject literal strings 'None', 'null', 'N/A', 'Unknown', 'undefined', 'NaN')
"""

import logging
import re
from typing import Any, Optional, Union
from urllib.parse import urlparse

from src.models.ai_tool import AITool

logger = logging.getLogger(__name__)

# Forbidden literal strings where None / empty list should be used
FORBIDDEN_LITERALS = frozenset({
    "none",
    "null",
    "n/a",
    "na",
    "unknown",
    "undefined",
    "nan",
    "nil",
    "not available",
    "not specified",
    "tbd",
    "todo",
})

# Forbidden hype words that violate grounding guidelines
HYPE_WORDS = (
    "revolutionary",
    "game-changing",
    "disruptive",
    "unmatched",
    "unparalleled",
    "world's best",
    "miracle",
    "unprecedented",
)

# Known directory domains that cannot be official product websites
DIRECTORY_DOMAINS = frozenset({
    "theresanaiforthat.com",
    "creati.ai",
    "producthunt.com",
    "futurepedia.io",
    "toolify.ai",
    "topai.tools",
    "aitools.fyi",
})

# Permitted CDN and asset host patterns for logos
AUTHORIZED_LOGO_HOST_SUFFIXES = (
    "googleusercontent.com",
    "githubusercontent.com",
    "amazonaws.com",
    "cloudfront.net",
    "wp.com",
    "cloudflare.com",
    "fastly.net",
    "cloudinary.com",
    "vercel.app",
    "supabase.co",
)


class ToolFinalValidator:
    """
    Validates curated AI Tool records against strict data quality,
    grounding, cleanliness, and null-safety standards.
    """

    def __init__(self):
        self.stats = {
            "records_evaluated": 0,
            "records_passed": 0,
            "records_failed": 0,
            "failure_reasons": {},
        }

    def validate_dataset(
        self, records: list[Union[dict[str, Any], AITool]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Validate an entire list of AI Tool records.
        Ensures uniqueness across official domains and canonical URLs across the batch.

        Returns:
            (passed_records, failed_audit_records)
        """
        self.stats["records_evaluated"] = len(records)
        passed: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        seen_domains: set[str] = set()
        seen_urls: set[str] = set()

        for item in records:
            rec = item.to_dict() if isinstance(item, AITool) else dict(item)
            is_valid, errors = self.validate_record(rec, seen_domains, seen_urls)

            if is_valid:
                passed.append(rec)
                self.stats["records_passed"] += 1
            else:
                self.stats["records_failed"] += 1
                failed_entry = {
                    "tool_name": rec.get("tool_name", "Unknown"),
                    "official_website": rec.get("official_website"),
                    "errors": errors,
                }
                failed.append(failed_entry)
                for err in errors:
                    err_type = err.split(":")[0]
                    self.stats["failure_reasons"][err_type] = self.stats["failure_reasons"].get(err_type, 0) + 1

        logger.info(
            "Final Validation: %d evaluated, %d passed, %d failed",
            self.stats["records_evaluated"],
            self.stats["records_passed"],
            self.stats["records_failed"],
        )
        return passed, failed

    def validate_record(
        self,
        record: dict[str, Any],
        seen_domains: Optional[set[str]] = None,
        seen_urls: Optional[set[str]] = None,
    ) -> tuple[bool, list[str]]:
        """
        Validate an individual AI Tool record against all 8 gates.

        Returns:
            (is_valid, list_of_error_messages)
        """
        errors: list[str] = []

        # -------------------------------------------------------------------
        # 1. Required Identity
        # -------------------------------------------------------------------
        tool_name = record.get("tool_name")
        if not tool_name or not str(tool_name).strip():
            errors.append("Identity: missing or empty tool_name")

        website = record.get("official_website")
        if not website or not str(website).strip():
            errors.append("Identity: missing canonical official_website")
        else:
            website_str = str(website).strip()
            parsed_web = urlparse(website_str)
            if not parsed_web.scheme or not parsed_web.netloc:
                errors.append(f"Identity: invalid official_website URL '{website_str}'")

        # -------------------------------------------------------------------
        # 2. Verification
        # -------------------------------------------------------------------
        v_status = str(record.get("verification_status") or "").lower()
        if v_status not in ("verified", "partially_verified"):
            errors.append(f"Verification: invalid verification_status '{v_status}' (must be verified or partially_verified)")

        if website:
            web_host = urlparse(str(website)).netloc.lower().split(":")[0]
            if web_host.startswith("www."):
                web_host = web_host[4:]
            if web_host in DIRECTORY_DOMAINS:
                errors.append(f"Verification: directory URL cannot serve as official product website ('{web_host}')")

        # -------------------------------------------------------------------
        # 3. Description Presence
        # -------------------------------------------------------------------
        short_desc = record.get("short_description")
        if not short_desc or not str(short_desc).strip():
            errors.append("Description: missing short_description")

        detailed_overview = record.get("detailed_overview")
        if not detailed_overview or not str(detailed_overview).strip():
            errors.append("Description: missing detailed_overview")

        # -------------------------------------------------------------------
        # 4. Description Quality & Grounding
        # -------------------------------------------------------------------
        combined_text = f"{short_desc or ''} {detailed_overview or ''}".lower()
        for hype in HYPE_WORDS:
            if re.search(rf"\b{re.escape(hype)}\b", combined_text):
                errors.append(f"Description Quality: contains marketing hype word '{hype}'")

        # Check for pricing claims in description when pricing is unstated
        if not record.get("pricing_model") and not record.get("starting_price"):
            if re.search(r"\$\d+(?:\.\d+)?\s*(?:/|\bper\b)", combined_text):
                errors.append("Description Grounding: contains specific dollar pricing claim while pricing metadata is unverified/None")

        # -------------------------------------------------------------------
        # 5. Null Correctness & Generic Placeholders
        # -------------------------------------------------------------------
        # Check scalar optional fields for placeholder strings like "[Company Name]", "<TODO>", etc.
        for field in (
            "company_developer", "country", "version", "current_status",
            "primary_task", "pricing_model", "starting_price", "important_usage_limits"
        ):
            val = record.get(field)
            if val is not None:
                val_str = str(val).strip()
                if (val_str.startswith("[") and val_str.endswith("]")) or (val_str.startswith("<") and val_str.endswith(">")):
                    errors.append(f"Null Correctness: field '{field}' contains placeholder value '{val_str}'")

        # -------------------------------------------------------------------
        # 6. Duplicate Detection (Domain & URL)
        # -------------------------------------------------------------------
        if website and seen_domains is not None:
            web_host = urlparse(str(website)).netloc.lower().split(":")[0]
            if web_host.startswith("www."):
                web_host = web_host[4:]
            if web_host in seen_domains:
                errors.append(f"Duplicate: duplicate official domain '{web_host}' detected across dataset")
            else:
                seen_domains.add(web_host)

        if website and seen_urls is not None:
            clean_url = str(website).strip().split("?")[0].rstrip("/").lower()
            if clean_url in seen_urls:
                errors.append(f"Duplicate: duplicate canonical product URL '{clean_url}' detected across dataset")
            else:
                seen_urls.add(clean_url)

        # -------------------------------------------------------------------
        # 7. Official Links & Logo Authenticity
        # -------------------------------------------------------------------
        logo_url = record.get("logo_url")
        if logo_url:
            logo_str = str(logo_url).strip()
            parsed_logo = urlparse(logo_str)
            if not parsed_logo.scheme or not parsed_logo.netloc:
                errors.append(f"Official Links: invalid logo_url '{logo_str}'")
            else:
                logo_host = parsed_logo.netloc.lower().split(":")[0]
                if logo_host.startswith("www."):
                    logo_host = logo_host[4:]
                official_host = urlparse(str(website)).netloc.lower().split(":")[0] if website else ""
                if official_host.startswith("www."):
                    official_host = official_host[4:]

                # Logo must be hosted on official domain or authorized CDN
                is_official_host = bool(official_host and (logo_host == official_host or logo_host.endswith("." + official_host)))
                is_authorized_cdn = any(logo_host.endswith(s) for s in AUTHORIZED_LOGO_HOST_SUFFIXES)

                if not is_official_host and not is_authorized_cdn:
                    errors.append(f"Official Links: logo host '{logo_host}' is neither official domain nor authorized CDN")

        # -------------------------------------------------------------------
        # 8. Data Cleanliness (Reject Literal 'None', 'null', 'N/A', etc.)
        # -------------------------------------------------------------------
        scalar_fields = [
            "company_developer", "country", "version", "current_status",
            "primary_task", "pricing_model", "starting_price", "important_usage_limits",
            "ai_orbit_summary", "usage_adoption_signals", "record_id",
            "discovery_source", "verification_source", "short_description", "detailed_overview"
        ]
        for field in scalar_fields:
            val = record.get(field)
            if val is not None and isinstance(val, str):
                cleaned_val = val.strip().lower()
                if cleaned_val in FORBIDDEN_LITERALS:
                    errors.append(f"Data Cleanliness: field '{field}' contains literal string '{val}' instead of proper null")

        list_fields = [
            "categories", "tags", "key_features", "main_use_cases",
            "ai_capabilities", "inputs", "outputs", "supported_platforms",
            "integrations", "pros", "cons", "limitations"
        ]
        for field in list_fields:
            items = record.get(field)
            if items is not None and isinstance(items, list):
                for item in items:
                    if isinstance(item, str) and item.strip().lower() in FORBIDDEN_LITERALS:
                        errors.append(f"Data Cleanliness: list field '{field}' contains forbidden literal item '{item}'")

        is_valid = len(errors) == 0
        return is_valid, errors
