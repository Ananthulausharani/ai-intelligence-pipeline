"""
Unit tests for AI Tool Quality Scorer (src.agents.tool_quality_scorer).

Verifies:
1. Exact 8 criteria weights and total = 100.0
2. Conservative scoring on missing evidence
3. High scoring on verified, high-capability tools
4. Rejection evaluation for dead, unverified, and low-scoring tools
5. Tier classifications match guideline boundaries
6. Input compatibility with both dicts and AITool instances
"""

from datetime import datetime, timezone
import os
import sys
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_quality_scorer import ToolQualityScorer, WEIGHTS, THRESHOLDS
from src.models.ai_tool import AITool


class TestToolQualityScorer(unittest.TestCase):
    """Test suite for ToolQualityScorer."""

    def setUp(self):
        self.scorer = ToolQualityScorer(minimum_qualifying_score=70.0, reject_threshold=60.0)

    def test_weights_sum_to_one_hundred(self):
        """Ensure all 8 criteria exist with exact weights summing to 100.0."""
        expected_weights = {
            "capability": 25.0,
            "usefulness": 20.0,
            "adoption": 15.0,
            "activity": 15.0,
            "maturity": 10.0,
            "recency": 5.0,
            "differentiation": 5.0,
            "information_quality": 5.0,
        }
        self.assertEqual(WEIGHTS, expected_weights)
        self.assertEqual(sum(WEIGHTS.values()), 100.0)

    def test_conservative_scoring_on_minimal_tool(self):
        """A minimal tool with no verified facts must score conservatively (< 60)."""
        minimal_record = {
            "tool_name": "Unknown Tool",
            "verification_status": "unverified",
        }
        score, breakdown, rationale = self.scorer.score_record(minimal_record)

        self.assertLess(score, 60.0)
        self.assertEqual(len(breakdown), 8)
        self.assertIn("Tier: Reject", rationale)

        # Evaluate rejection
        is_rejected, reason = self.scorer.evaluate_rejection(minimal_record, score)
        self.assertTrue(is_rejected)
        self.assertIsNotNone(reason)

    def test_exceptional_tool_scoring(self):
        """A comprehensively verified tool with strong adoption and capabilities scores >= 80."""
        record = {
            "tool_name": "Cursor AI",
            "company_developer": "Anysphere",
            "official_website": "https://www.cursor.com",
            "logo_url": "https://www.cursor.com/logo.png",
            "primary_task": "AI Code Generation & Agentic Editing",
            "categories": ["Developer Tools", "AI Coding Assistants"],
            "inputs": ["source code", "text prompts"],
            "outputs": ["code diffs", "explanations", "generated code"],
            "supported_platforms": ["macOS", "Windows", "Linux", "VS Code"],
            "api_availability": True,
            "current_status": "Active",
            "pricing_model": "Freemium",
            "starting_price": "$20/month",
            "version": "0.41.0",
            "launch_date": "2024-03-01T00:00:00Z",
            "short_description": "An AI code editor built for deep repository indexing and pair-programming.",
            "detailed_overview": "Cursor provides multi-file agentic edits, code review, and prompt-driven diffs.",
            "usage_adoption_signals": "Over 100,000 active developers and 30,000 stars.",
            "discovery_references": [
                {"source": "There's An AI For That", "source_url": "https://theresanaiforthat.com/"},
                {"source": "Creati.ai", "source_url": "https://creati.ai/ai-tools/"},
            ],
            "verification_status": "verified",
            "last_verified_date": datetime.now(timezone.utc).isoformat(),
        }

        score, breakdown, rationale = self.scorer.score_record(record)
        self.assertGreaterEqual(score, 80.0)
        self.assertLessEqual(score, 100.0)
        self.assertIn(self.scorer.classify_tier(score), ("Exceptional", "Excellent"))

        is_rejected, reason = self.scorer.evaluate_rejection(record, score)
        self.assertFalse(is_rejected)
        self.assertIsNone(reason)

    def test_rejection_criteria_dead_tool(self):
        """A dead or discontinued tool must be rejected regardless of past score."""
        record = {
            "tool_name": "Dead Tool",
            "official_website": "https://deadtool.example.com",
            "current_status": "Dead",
            "short_description": "A discontinued AI tool.",
            "detailed_overview": "This tool was shut down and is no longer functioning.",
            "verification_status": "verified",
        }
        score, _, _ = self.scorer.score_record(record)
        is_rejected, reason = self.scorer.evaluate_rejection(record, score)
        self.assertTrue(is_rejected)
        self.assertIn("inactive/deprecated", reason.lower())

    def test_rejection_directory_url_as_official_website(self):
        """A tool pointing to a directory URL as its official website must be rejected."""
        record = {
            "tool_name": "Directory Spammer",
            "official_website": "https://theresanaiforthat.com/ai/spammer",
            "verification_status": "verified",
            "short_description": "Some tool.",
            "detailed_overview": "Detailed overview of the tool.",
        }
        is_rejected, reason = self.scorer.evaluate_rejection(record, 75.0)
        self.assertTrue(is_rejected)
        self.assertIn("Directory URL cannot serve as official product website", reason)

    def test_aitool_instance_compatibility(self):
        """Verify scoring works identically on AITool instance and dict."""
        tool = AITool(
            tool_name="Imagetoprompt ai",
            official_website="https://imagetoprompt.org/",
            logo_url="https://imagetoprompt.org/icon.png",
            primary_task="Image to Prompt",
            categories=["Image to Prompt", "AI Prompt Generator"],
            inputs=["Image", "Text"],
            outputs=["Text Prompt"],
            supported_platforms=["Web"],
            current_status="Active",
            pricing_model="Free",
            free_plan=True,
            short_description="Converts uploaded images into text prompts.",
            detailed_overview="A web-based tool allowing users to upload images and generate prompts.",
            last_verified_date=datetime.now(timezone.utc),
            verification_source="Official Website",
        )
        score_obj, breakdown_obj, _ = self.scorer.score_record(tool)
        score_dict, breakdown_dict, _ = self.scorer.score_record(tool.to_dict())

        self.assertEqual(score_obj, score_dict)
        self.assertEqual(breakdown_obj, breakdown_dict)
        self.assertGreaterEqual(score_obj, 55.0)

    def test_tier_classification(self):
        """Verify tier classifications match guideline specs."""
        self.assertEqual(self.scorer.classify_tier(95.0), "Exceptional")
        self.assertEqual(self.scorer.classify_tier(90.0), "Exceptional")
        self.assertEqual(self.scorer.classify_tier(85.0), "Excellent")
        self.assertEqual(self.scorer.classify_tier(80.0), "Excellent")
        self.assertEqual(self.scorer.classify_tier(75.0), "Good")
        self.assertEqual(self.scorer.classify_tier(70.0), "Good")
        self.assertEqual(self.scorer.classify_tier(65.0), "Average / Skip")
        self.assertEqual(self.scorer.classify_tier(59.9), "Reject")
        self.assertEqual(self.scorer.classify_tier(40.0), "Reject")


if __name__ == "__main__":
    unittest.main()
