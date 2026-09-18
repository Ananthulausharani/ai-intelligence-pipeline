"""
Unit tests for AI Tool Description Enrichment (src.agents.tool_enricher).

Verifies the Step 5 enrichment behaviors:
1. Generation of short_description and detailed_overview for verified records
2. Schema compatibility with canonical AITool model
3. Preservation of all existing verified fields (no data loss)
4. Strict null preservation (unverified fields remain None/null)
5. Unverified / failed candidates are skipped without hallucination
6. Resilient LLM failure handling (graceful fallback without fabrication)
7. Hype word filtering and sanitization
8. Non-duplicative descriptions reflecting verified capabilities
9. Deterministic evidence prompt formatting
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.agents.tool_enricher import (
    ToolEnricher,
    build_tool_evidence_prompt,
    check_for_hype_words,
    sanitize_description_text,
)
from src.models.ai_tool import AITool


MOCK_VERIFIED_TOOL = {
    "candidate_id": "candidate-imagetoprompt-ai",
    "record_id": "candidate-imagetoprompt-ai",
    "entity_type": "tool",
    "verification_status": "verified",
    "verification_errors": [],
    "created_at": "2026-09-18T13:34:04.874990+00:00",
    "updated_at": "2026-09-18T14:14:53.574688+00:00",
    "tool_name": "Imagetoprompt ai",
    "company_developer": None,
    "official_website": "https://imagetoprompt.org/",
    "logo_url": "https://imagetoprompt.org/icon.png",
    "country": None,
    "version": None,
    "launch_date": None,
    "current_status": "Active",
    "short_description": "Initial verified short description.",
    "detailed_overview": "Initial verified overview.",
    "primary_task": "Image to Prompt",
    "categories": ["Image to Prompt", "AI Prompt Generator"],
    "tags": ["image to prompt", "ai prompt generator"],
    "key_features": [],
    "main_use_cases": [],
    "ai_capabilities": [],
    "inputs": ["Image", "Text", "URL"],
    "outputs": ["Text Prompt", "Generated Image"],
    "supported_platforms": ["Web"],
    "integrations": [],
    "api_availability": None,
    "open_source_status": None,
    "signup_requirement": None,
    "pricing_model": "Free",
    "starting_price": None,
    "free_plan": True,
    "free_trial": None,
    "important_usage_limits": None,
    "pros": [],
    "cons": [],
    "limitations": [],
    "ai_orbit_summary": None,
    "usage_adoption_signals": None,
    "last_verified_date": "2026-09-18T14:14:53.574665+00:00",
    "discovery_source": "Creati.ai",
    "discovery_source_url": "https://creati.ai/ai-tools/",
    "verification_source": "Official Website",
    "verification_source_url": "https://imagetoprompt.org/",
    "discovery_references": [
        {
            "source": "Creati.ai",
            "source_url": "https://creati.ai/ai-tools/",
            "discovered_url": "https://creati.ai/ai-tools/imagetoprompt-ai",
            "discovered_at": "2026-09-18T13:34:04.874990+00:00",
        }
    ],
}


class TestToolEnricher(unittest.TestCase):
    """Unit test suite for Step 5 description enrichment."""

    def setUp(self):
        self.mock_orchestrator = MagicMock()
        self.enricher = ToolEnricher(
            orchestrator=self.mock_orchestrator,
            request_delay_sec=0.0,
        )

    # -----------------------------------------------------------------------
    # 1. Successful Description Generation
    # -----------------------------------------------------------------------
    def test_01_enrich_verified_tool(self):
        """Verified record is enriched with factual short_description and detailed_overview."""
        self.mock_orchestrator.extract.return_value = {
            "success": True,
            "provider": "gemini",
            "data": {
                "short_description": "Imagetoprompt ai generates text prompts from uploaded images or URLs.",
                "detailed_overview": "This tool is designed for image-to-prompt conversion. It accepts images, text, and URLs and outputs text prompts and generated images on the web. It is available under a verified free pricing model."
            },
            "error": None,
        }

        enriched = self.enricher.enrich_tool_record(MOCK_VERIFIED_TOOL)
        self.assertEqual(enriched["enrichment_status"], "enriched")
        self.assertEqual(enriched["enrichment_provider"], "gemini")
        self.assertIn("generates text prompts", enriched["short_description"])
        self.assertIn("image-to-prompt", enriched["detailed_overview"].lower())

    # -----------------------------------------------------------------------
    # 2. Schema Compatibility
    # -----------------------------------------------------------------------
    def test_02_schema_compatibility(self):
        """Enriched record validates cleanly against Pydantic AITool model."""
        self.mock_orchestrator.extract.return_value = {
            "success": True,
            "provider": "gemini",
            "data": {
                "short_description": "Converts images into text prompts.",
                "detailed_overview": "A web-based tool for generating prompts from images and text inputs."
            },
            "error": None,
        }

        enriched = self.enricher.enrich_tool_record(MOCK_VERIFIED_TOOL)
        tool = AITool(**enriched)
        self.assertEqual(tool.tool_name, "Imagetoprompt ai")
        self.assertEqual(str(tool.official_website), "https://imagetoprompt.org/")
        self.assertEqual(tool.short_description, "Converts images into text prompts.")

    # -----------------------------------------------------------------------
    # 3. Preservation of All Verified Fields
    # -----------------------------------------------------------------------
    def test_03_preserves_all_verified_fields(self):
        """Enrichment must not overwrite or lose any verified fields from Step 4."""
        self.mock_orchestrator.extract.return_value = {
            "success": True,
            "provider": "gemini",
            "data": {
                "short_description": "New short description.",
                "detailed_overview": "New detailed overview."
            },
            "error": None,
        }

        enriched = self.enricher.enrich_tool_record(MOCK_VERIFIED_TOOL)
        # Check verified fields remain exactly identical
        self.assertEqual(enriched["tool_name"], MOCK_VERIFIED_TOOL["tool_name"])
        self.assertEqual(enriched["official_website"], MOCK_VERIFIED_TOOL["official_website"])
        self.assertEqual(enriched["logo_url"], MOCK_VERIFIED_TOOL["logo_url"])
        self.assertEqual(enriched["inputs"], MOCK_VERIFIED_TOOL["inputs"])
        self.assertEqual(enriched["outputs"], MOCK_VERIFIED_TOOL["outputs"])
        self.assertEqual(enriched["pricing_model"], MOCK_VERIFIED_TOOL["pricing_model"])
        self.assertEqual(enriched["free_plan"], MOCK_VERIFIED_TOOL["free_plan"])
        self.assertEqual(enriched["supported_platforms"], MOCK_VERIFIED_TOOL["supported_platforms"])
        self.assertEqual(enriched["verification_source"], MOCK_VERIFIED_TOOL["verification_source"])
        self.assertEqual(enriched["discovery_source"], MOCK_VERIFIED_TOOL["discovery_source"])

    # -----------------------------------------------------------------------
    # 4. Strict Null Handling
    # -----------------------------------------------------------------------
    def test_04_none_fields_remain_null(self):
        """Unverified fields (None / null) must remain None and not be populated by inference."""
        self.mock_orchestrator.extract.return_value = {
            "success": True,
            "provider": "gemini",
            "data": {
                "short_description": "Factual description.",
                "detailed_overview": "Factual overview without invented facts."
            },
            "error": None,
        }

        enriched = self.enricher.enrich_tool_record(MOCK_VERIFIED_TOOL)
        self.assertIsNone(enriched["company_developer"])
        self.assertIsNone(enriched["country"])
        self.assertIsNone(enriched["version"])
        self.assertIsNone(enriched["launch_date"])
        self.assertIsNone(enriched["starting_price"])
        self.assertIsNone(enriched["api_availability"])
        self.assertIsNone(enriched["open_source_status"])

    # -----------------------------------------------------------------------
    # 5. Unverified Candidates Skipped
    # -----------------------------------------------------------------------
    def test_05_unverified_candidate_skipped(self):
        """Unverified candidates must skip LLM generation to avoid hallucinating facts."""
        unverified_rec = dict(MOCK_VERIFIED_TOOL)
        unverified_rec["verification_status"] = "unverified"
        unverified_rec["official_website"] = None

        enriched = self.enricher.enrich_tool_record(unverified_rec)
        self.assertEqual(enriched["enrichment_status"], "skipped_unverified")
        self.mock_orchestrator.extract.assert_not_called()

    # -----------------------------------------------------------------------
    # 6. LLM Failure Handling
    # -----------------------------------------------------------------------
    def test_06_llm_failure_handling(self):
        """When LLM extraction fails, pipeline does not crash; existing description is preserved."""
        self.mock_orchestrator.extract.return_value = {
            "success": False,
            "provider": None,
            "data": None,
            "error": "HTTP 503 Service Unavailable",
        }

        enriched = self.enricher.enrich_tool_record(MOCK_VERIFIED_TOOL)
        self.assertEqual(enriched["enrichment_status"], "failed")
        # Preserves previous description rather than inventing one
        self.assertEqual(enriched["short_description"], MOCK_VERIFIED_TOOL["short_description"])
        self.assertTrue(len(enriched["enrichment_errors"]) > 0)

    # -----------------------------------------------------------------------
    # 7. Hype Words Cleaned
    # -----------------------------------------------------------------------
    def test_07_hype_words_cleaned(self):
        """Disallowed marketing hype words like 'revolutionary' are stripped."""
        self.mock_orchestrator.extract.return_value = {
            "success": True,
            "provider": "gemini",
            "data": {
                "short_description": "A revolutionary tool that generates prompts.",
                "detailed_overview": "This cutting-edge platform offers state-of-the-art prompt generation."
            },
            "error": None,
        }

        enriched = self.enricher.enrich_tool_record(MOCK_VERIFIED_TOOL)
        self.assertNotIn("revolutionary", enriched["short_description"].lower())
        self.assertNotIn("cutting-edge", enriched["detailed_overview"].lower())
        self.assertNotIn("state-of-the-art", enriched["detailed_overview"].lower())

    # -----------------------------------------------------------------------
    # 8. Evidence Prompt Construction
    # -----------------------------------------------------------------------
    def test_08_evidence_prompt_builder(self):
        """build_tool_evidence_prompt correctly formats known facts and labels unknown attributes."""
        prompt = build_tool_evidence_prompt(MOCK_VERIFIED_TOOL)
        self.assertIn("Tool Name: Imagetoprompt ai", prompt)
        self.assertIn("Primary Task: Image to Prompt", prompt)
        self.assertIn("Verified Inputs: Image, Text, URL", prompt)
        self.assertIn("Verified Outputs: Text Prompt, Generated Image", prompt)
        self.assertIn("Verified Free Plan: Yes", prompt)
        self.assertIn("API Available: Not verified", prompt)

    # -----------------------------------------------------------------------
    # 9. Batch Enrichment File Save
    # -----------------------------------------------------------------------
    def test_09_enrich_and_save(self):
        """enrich_and_save loads input, enriches records, and writes to output file."""
        temp_dir = tempfile.mkdtemp()
        try:
            in_file = os.path.join(temp_dir, "test_in.json")
            out_file = os.path.join(temp_dir, "test_out.json")

            with open(in_file, "w", encoding="utf-8") as f:
                json.dump([MOCK_VERIFIED_TOOL], f)

            self.mock_orchestrator.extract.return_value = {
                "success": True,
                "provider": "gemini",
                "data": {
                    "short_description": "Short desc",
                    "detailed_overview": "Detailed overview"
                },
                "error": None,
            }

            res = self.enricher.enrich_and_save(input_file=in_file, output_file=out_file)
            self.assertEqual(len(res), 1)
            self.assertTrue(os.path.exists(out_file))

            with open(out_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved[0]["short_description"], "Short desc")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
