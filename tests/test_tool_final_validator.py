"""
Unit tests for AI Tool Final Validator (src.agents.tool_final_validator).

Verifies all 8 validation gates:
1. Identity
2. Verification
3. Description presence
4. Description quality & grounding
5. Null correctness
6. Duplicate detection across dataset
7. Official links and logo authenticity
8. Data cleanliness (rejection of literal 'None', 'null', 'N/A', etc.)
"""

import os
import sys
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_final_validator import ToolFinalValidator


class TestToolFinalValidator(unittest.TestCase):
    """Test suite for ToolFinalValidator."""

    def setUp(self):
        self.validator = ToolFinalValidator()
        self.valid_record = {
            "tool_name": "Claude Code",
            "company_developer": "Anthropic",
            "official_website": "https://claude.ai/code",
            "logo_url": "https://claude.ai/assets/logo.png",
            "verification_status": "verified",
            "current_status": "Active",
            "short_description": "An agentic coding CLI tool that assists with repo-wide code changes.",
            "detailed_overview": "Claude Code runs inside the developer terminal, parsing codebase structure and executing tests.",
            "categories": ["Developer Tools", "CLI"],
            "inputs": ["source code", "terminal command"],
            "outputs": ["diff", "test results"],
            "pricing_model": "Usage-Based",
        }

    def test_valid_record_passes(self):
        """A clean, verified, grounded record must pass validation."""
        is_valid, errors = self.validator.validate_record(self.valid_record)
        self.assertTrue(is_valid, f"Validation failed with: {errors}")
        self.assertEqual(len(errors), 0)

    def test_missing_identity_rejected(self):
        """Records with missing tool_name or official_website must fail."""
        rec_no_name = dict(self.valid_record, tool_name="")
        is_valid, errors = self.validator.validate_record(rec_no_name)
        self.assertFalse(is_valid)
        self.assertTrue(any("Identity: missing" in e for e in errors))

        rec_no_web = dict(self.valid_record, official_website=None)
        is_valid, errors = self.validator.validate_record(rec_no_web)
        self.assertFalse(is_valid)
        self.assertTrue(any("Identity: missing" in e for e in errors))

    def test_unverified_status_rejected(self):
        """Records with unverified status must fail."""
        rec_unverified = dict(self.valid_record, verification_status="unverified")
        is_valid, errors = self.validator.validate_record(rec_unverified)
        self.assertFalse(is_valid)
        self.assertTrue(any("Verification: invalid verification_status" in e for e in errors))

    def test_directory_url_as_official_website_rejected(self):
        """Directory URLs cannot serve as official website."""
        rec_dir = dict(self.valid_record, official_website="https://creati.ai/ai-tools/claude")
        is_valid, errors = self.validator.validate_record(rec_dir)
        self.assertFalse(is_valid)
        self.assertTrue(any("directory URL cannot serve as official" in e for e in errors))

    def test_missing_descriptions_rejected(self):
        """Records missing short_description or detailed_overview must fail."""
        rec_no_short = dict(self.valid_record, short_description=None)
        is_valid, errors = self.validator.validate_record(rec_no_short)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing short_description" in e for e in errors))

        rec_no_overview = dict(self.valid_record, detailed_overview="")
        is_valid, errors = self.validator.validate_record(rec_no_overview)
        self.assertFalse(is_valid)
        self.assertTrue(any("missing detailed_overview" in e for e in errors))

    def test_marketing_hype_rejected(self):
        """Descriptions with ungrounded hype words must fail."""
        rec_hype = dict(
            self.valid_record,
            short_description="A revolutionary tool that transforms your workflow.",
        )
        is_valid, errors = self.validator.validate_record(rec_hype)
        self.assertFalse(is_valid)
        self.assertTrue(any("marketing hype word" in e for e in errors))

    def test_literal_none_null_strings_rejected(self):
        """Literal strings 'None', 'null', 'N/A' in fields must fail."""
        # Scalar field with 'None'
        rec_literal = dict(self.valid_record, country="None")
        is_valid, errors = self.validator.validate_record(rec_literal)
        self.assertFalse(is_valid)
        self.assertTrue(any("Data Cleanliness" in e and "country" in e for e in errors))

        # List field with 'N/A'
        rec_list_literal = dict(self.valid_record, inputs=["source code", "N/A"])
        is_valid, errors = self.validator.validate_record(rec_list_literal)
        self.assertFalse(is_valid)
        self.assertTrue(any("Data Cleanliness" in e and "inputs" in e for e in errors))

    def test_placeholder_strings_rejected(self):
        """Generic placeholder strings like '[Company Name]' must fail."""
        rec_ph = dict(self.valid_record, company_developer="[Company Name]")
        is_valid, errors = self.validator.validate_record(rec_ph)
        self.assertFalse(is_valid)
        self.assertTrue(any("Null Correctness" in e for e in errors))

    def test_unauthorized_logo_host_rejected(self):
        """Logo hosted on an unrelated non-CDN domain must fail."""
        rec_bad_logo = dict(self.valid_record, logo_url="https://unrelated-domain.xyz/logo.png")
        is_valid, errors = self.validator.validate_record(rec_bad_logo)
        self.assertFalse(is_valid)
        self.assertTrue(any("logo host 'unrelated-domain.xyz' is neither" in e for e in errors))

    def test_dataset_duplicate_detection(self):
        """Dataset validator must flag duplicate domains and URLs."""
        rec1 = dict(
            self.valid_record,
            tool_name="Tool 1",
            official_website="https://example.com/one",
            logo_url="https://example.com/logo1.png",
        )
        rec2 = dict(
            self.valid_record,
            tool_name="Tool 2",
            official_website="https://example.com/two",
            logo_url="https://example.com/logo2.png",
        )

        passed, failed = self.validator.validate_dataset([rec1, rec2])
        self.assertEqual(len(passed), 1)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["tool_name"], "Tool 2")
        self.assertTrue(any("duplicate official domain" in e for e in failed[0]["errors"]))


if __name__ == "__main__":
    unittest.main()
