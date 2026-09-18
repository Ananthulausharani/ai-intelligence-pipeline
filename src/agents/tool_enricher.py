"""
AI Tool LLM Description Enrichment Agent — Step 5.

Generates consistent, grounded, factual descriptions for verified AI tools:
1. 'short_description': 1–2 concise, factual sentences explaining what the tool does
   and the primary problem or use case it addresses. Specific rather than generic,
   no marketing hype, no unnecessary tool name repetition.
2. 'detailed_overview': 2–5 concise, factual sentences explaining:
   - What the tool does
   - Primary task / use case
   - Verified capabilities
   - Verified inputs / outputs (only when present in source data)
   - Verified pricing / access (only when present in source data)

Strict Evidence & Anti-Hallucination Rules:
- Never infer: company/developer, country, launch date, version, current status,
  pricing, free plan, free trial, API availability, open-source status, integrations,
  AI models used, user/adoption numbers, unsupported inputs, unsupported outputs.
- If fields are None/empty, omit them completely rather than guessing.
- Strictly avoid hype: 'revolutionary', 'powerful', 'best', 'leading', 'cutting-edge'.
- Ensure non-duplicative, distinct descriptions grounded in verified tool capabilities.
- Safe failure handling: Preserves existing description if LLM fails, never aborts the pipeline,
  records failure diagnostics, never fabricates fallback descriptions.
- Preserves all existing verified fields from data/output/verified_ai_tools.json
  and outputs data/output/enriched_ai_tools.json compatible with canonical AITool schema.
"""

from datetime import datetime, timezone
import json
import logging
import os
import re
import time
from typing import Any, Optional

from src.llm.orchestrator import LLMOrchestrator, orchestrator as default_orchestrator
from src.models.ai_tool import AITool

logger = logging.getLogger(__name__)

DISALLOWED_HYPE_WORDS = [
    r"\brevolutionary\b",
    r"\bcutting-edge\b",
    r"\bworld-class\b",
    r"\bgame-changing\b",
    r"\bstate-of-the-art\b",
    r"\bultimate\b",
    r"\bunmatched\b",
    r"\bunrivaled\b",
    r"\bseamlessly empowers\b",
]


def sanitize_description_text(text: str) -> str:
    """Clean unwanted markdown artifacts, quotes, and excessive whitespace."""
    if not text or not isinstance(text, str):
        return ""
    cleaned = text.strip()
    # Strip wrapping quotes
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    # Collapse internal whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned


def check_for_hype_words(text: str) -> list[str]:
    """Identify any prohibited marketing hype words in text."""
    found: list[str] = []
    text_lower = text.lower()
    for pattern in DISALLOWED_HYPE_WORDS:
        match = re.search(pattern, text_lower)
        if match:
            found.append(match.group(0))
    return found


def build_tool_evidence_prompt(record: dict[str, Any]) -> str:
    """
    Format verified tool attributes into a deterministic evidence prompt.
    Explicitly labels known facts vs unverified fields so LLM never guesses.
    """
    tool_name = record.get("tool_name", "Unknown Tool")
    primary_task = record.get("primary_task") or "Not verified"
    categories = record.get("categories") or []
    inputs = record.get("inputs") or []
    outputs = record.get("outputs") or []
    pricing_model = record.get("pricing_model") or "Not publicly verified"
    starting_price = record.get("starting_price") or "Not publicly verified"
    free_plan = record.get("free_plan")
    free_trial = record.get("free_trial")
    platforms = record.get("supported_platforms") or []
    integrations = record.get("integrations") or []
    api_available = record.get("api_availability")
    open_source = record.get("open_source_status")
    overview = record.get("detailed_overview") or record.get("short_description") or "No further page evidence"

    # Truncate raw overview if too long
    if len(overview) > 1500:
        overview = overview[:1500] + "..."

    prompt_lines = [
        f"Tool Name: {tool_name}",
        f"Primary Task: {primary_task}",
        f"Categories: {', '.join(categories) if categories else 'None'}",
        f"Verified Inputs: {', '.join(inputs) if inputs else 'None verified'}",
        f"Verified Outputs: {', '.join(outputs) if outputs else 'None verified'}",
        f"Verified Pricing Model: {pricing_model}",
        f"Verified Starting Price: {starting_price}",
        f"Verified Free Plan: {'Yes' if free_plan is True else ('No' if free_plan is False else 'Not verified')}",
        f"Verified Free Trial: {'Yes' if free_trial is True else ('No' if free_trial is False else 'Not verified')}",
        f"Supported Platforms: {', '.join(platforms) if platforms else 'None verified'}",
        f"Verified Integrations: {', '.join(integrations) if integrations else 'None verified'}",
        f"API Available: {'Yes' if api_available is True else 'Not verified'}",
        f"Open Source: {open_source or 'Not verified'}",
        "Official Page Context / Evidence:",
        f"{overview}",
    ]

    return "\n".join(prompt_lines)


class ToolEnricher:
    """
    LLM Enrichment Agent for AI Tools.
    Reuses LLMOrchestrator to produce concise, factual, non-hallucinatory descriptions.
    """

    def __init__(
        self,
        orchestrator: Optional[LLMOrchestrator] = None,
        request_delay_sec: float = 0.5,
    ):
        self.orchestrator = orchestrator or default_orchestrator
        self.request_delay_sec = request_delay_sec
        self.stats: dict[str, Any] = {
            "records_loaded": 0,
            "records_attempted": 0,
            "descriptions_successfully_generated": 0,
            "failures": 0,
            "skipped_unverified": 0,
            "records_with_missing_descriptions": 0,
            "providers_used": set(),
            "elapsed_time_sec": 0.0,
            "errors": [],
        }

    def enrich_tool_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a single verified tool record with LLM descriptions.
        Retains ALL verified fields and updates only description and enrichment metadata.
        """
        self.stats["records_attempted"] += 1
        enriched = dict(record)  # Shallow copy to preserve all fields
        tool_name = enriched.get("tool_name", "Unknown")
        now_iso = datetime.now(timezone.utc).isoformat()

        # If candidate was not verified against official website, do not hallucinate descriptions
        status = enriched.get("verification_status")
        if status not in ("verified", "partially_verified"):
            logger.info("Skipping LLM description generation for %s (status: %s)", tool_name, status)
            self.stats["skipped_unverified"] += 1
            enriched["enrichment_status"] = "skipped_unverified"
            enriched["updated_at"] = now_iso
            return enriched

        evidence_text = build_tool_evidence_prompt(enriched)

        try:
            extraction = self.orchestrator.extract(
                text=evidence_text,
                record_type="AI_TOOL_DESCRIPTION",
            )
        except Exception as exc:
            logger.warning("LLM extraction call exception for %s: %s", tool_name, exc)
            extraction = {"success": False, "provider": None, "data": None, "error": str(exc)}

        if extraction.get("success") and isinstance(extraction.get("data"), dict):
            data = extraction["data"]
            short_desc = sanitize_description_text(data.get("short_description") or "")
            detailed_overview = sanitize_description_text(data.get("detailed_overview") or "")

            # Check and clean hype words
            short_hype = check_for_hype_words(short_desc)
            detailed_hype = check_for_hype_words(detailed_overview)
            if short_hype or detailed_hype:
                logger.info("Detected hype words (%s) in descriptions for %s; cleaning...", short_hype + detailed_hype, tool_name)
                for h in short_hype + detailed_hype:
                    short_desc = re.sub(rf"\b{re.escape(h)}\b", "", short_desc, flags=re.IGNORECASE).strip()
                    detailed_overview = re.sub(rf"\b{re.escape(h)}\b", "", detailed_overview, flags=re.IGNORECASE).strip()
                short_desc = re.sub(r"\s+", " ", short_desc)
                detailed_overview = re.sub(r"\s+", " ", detailed_overview)

            if short_desc and detailed_overview:
                enriched["short_description"] = short_desc
                enriched["detailed_overview"] = detailed_overview
                enriched["enrichment_status"] = "enriched"
                enriched["enrichment_provider"] = extraction.get("provider")
                enriched["updated_at"] = now_iso
                self.stats["descriptions_successfully_generated"] += 1
                if extraction.get("provider"):
                    self.stats["providers_used"].add(extraction["provider"])
                return enriched

        # If LLM generation failed or returned incomplete descriptions:
        # Preserve existing verified descriptions if present, never fabricate fallbacks
        self.stats["failures"] += 1
        err_msg = extraction.get("error") or "LLM returned empty description fields."
        logger.warning("Failed to enrich %s: %s", tool_name, err_msg)
        self.stats["errors"].append(f"{tool_name}: {err_msg}")

        enriched["enrichment_status"] = "failed"
        enrichment_errors = list(enriched.get("enrichment_errors") or [])
        enrichment_errors.append(err_msg)
        enriched["enrichment_errors"] = enrichment_errors
        enriched["updated_at"] = now_iso

        if not enriched.get("short_description") and not enriched.get("detailed_overview"):
            self.stats["records_with_missing_descriptions"] += 1

        return enriched

    def enrich_records(
        self,
        records: list[dict[str, Any]],
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Enrich a batch of verified records up to limit."""
        start_time = time.time()
        self.stats["records_loaded"] = len(records)
        subset = records[:limit] if limit else records
        results: list[dict[str, Any]] = []

        for idx, rec in enumerate(subset, 1):
            name = rec.get("tool_name", "Unknown")
            logger.info("[%d/%d] Enriching tool: %s", idx, len(subset), name)
            enriched_rec = self.enrich_tool_record(rec)
            results.append(enriched_rec)

            if self.request_delay_sec > 0 and idx < len(subset):
                time.sleep(self.request_delay_sec)

        self.stats["elapsed_time_sec"] = round(time.time() - start_time, 2)
        return results

    def enrich_and_save(
        self,
        input_file: str = "data/output/verified_ai_tools.json",
        output_file: str = "data/output/enriched_ai_tools.json",
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Load verified tools, enrich descriptions, and save to enriched_ai_tools.json."""
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")

        with open(input_file, "r", encoding="utf-8") as f:
            verified_records = json.load(f)

        enriched_records = self.enrich_records(verified_records, limit=limit)

        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(enriched_records, f, indent=2, ensure_ascii=False)

        logger.info("Saved %d enriched AI tools to %s", len(enriched_records), output_file)
        return enriched_records
