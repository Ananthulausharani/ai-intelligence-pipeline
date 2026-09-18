"""
Unit tests for AI Tool Official Website Verifier (src.agents.tool_verifier).

Verifies the required verification and quality-correction behaviors:
1. Official URL extraction and normalization
2. Directory URLs (TAAFT, Creati.ai, etc.) are never treated as official websites
3. Official website verification with strong branding matching
4. Weak branding match results in partially_verified or unverified (never false-positive verified)
5. Generic page keywords do NOT create inputs/outputs
6. Explicit input/output action wording is accepted
7. Official logo / favicon handling (domain-restricted, no guessed paths)
8. Uncertain pricing remains null (zero directory hints used)
9. Uncertain status remains null (never defaulted to Active solely on HTTP 200)
10. Missing official URL handled gracefully
11. HTTP 403 Forbidden error handling
12. HTTP 404 Not Found error handling
13. HTTP 429 Too Many Requests error handling
14. Timeout and network connection error handling
15. Strict null handling (unverified attributes remain None)
16. Output compatibility with canonical AITool schema
"""

from datetime import datetime
import json
import os
import shutil
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from bs4 import BeautifulSoup

from src.agents.tool_verifier import (
    ToolVerifier,
    clean_official_url,
    determine_current_status,
    extract_concrete_inputs_outputs,
    extract_official_logo,
    extract_platforms_and_integrations,
    extract_pricing_evidence,
    is_allowed_asset_domain,
    is_disallowed_official_domain,
    verify_page_authenticity,
)
from src.models.ai_tool import AITool

MOCK_OFFICIAL_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Imagetoprompt AI - Free Image to Prompt Tool</title>
  <meta name="description" content="Turn any image or photo into a detailed text prompt for Midjourney and Flux." />
  <link rel="apple-touch-icon" href="/assets/icon-192.png" />
  <meta property="og:image" content="https://imagetoprompt.org/assets/brand-logo.png" />
</head>
<body>
  <h1>Transform Visuals into Prompts with Imagetoprompt</h1>
  <p>Upload an image or document to generate text prompts, scripts, and summaries.</p>
  <p>Works seamlessly on Web, macOS, and as a Chrome Extension with GitHub integration.</p>
  <p>Pricing: 100% free plan available, or upgrade for $15/month for unlimited generations. 7-day free trial included.</p>
  <a href="/app" class="btn">Get Started Now</a>
  <footer>
    <p>© 2026 PromptCraft Technologies Inc. All rights reserved.</p>
  </footer>
</body>
</html>
"""

MOCK_GENERIC_KEYWORDS_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Acme General Blog</title>
</head>
<body>
  <p>Here is an image of the team. We like writing text. The code of conduct is online.</p>
  <p>Watch our video. Visit this url. Listen to the audio of our podcast.</p>
</body>
</html>
"""

MOCK_MINIMAL_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Simple AI Tool</title>
</head>
<body>
  <h1>Welcome to Simple AI</h1>
  <p>Learn about technology and machine learning innovations.</p>
</body>
</html>
"""


class TestToolVerifier(unittest.TestCase):
    """Unit test suite for Step 4 website verification and enrichment."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.verifier = ToolVerifier(timeout_sec=5.0, request_delay_sec=0.0)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -----------------------------------------------------------------------
    # 1. Official URL extraction
    # -----------------------------------------------------------------------
    def test_01_official_url_extraction(self):
        """Test candidate external product URL is extracted, cleaned, and normalized."""
        candidate = {
            "candidate_id": "cand-test",
            "tool_name": "Test Tool",
            "discovered_url": "https://creati.ai/ai-tools/test-tool",
            "raw_metadata": {
                "external_product_url": "https://www.testtool.ai/?utm_source=creati&ref=card"
            }
        }
        url, errors = self.verifier.resolve_official_website(candidate)
        self.assertEqual(url, "https://testtool.ai/")
        self.assertEqual(len(errors), 0)

    # -----------------------------------------------------------------------
    # 2. Directory URL is not treated as official website
    # -----------------------------------------------------------------------
    def test_02_directory_url_not_treated_as_official(self):
        """Directories, review sites, and social media URLs must be rejected as official."""
        disallowed_samples = [
            "https://theresanaiforthat.com/ai/humwork",
            "https://creati.ai/ai-tools/imagetoprompt",
            "https://www.producthunt.com/posts/test",
            "https://twitter.com/mytool",
            "https://x.com/mytool",
            "https://www.g2.com/products/test",
            "https://discord.gg/invite",
        ]
        for url in disallowed_samples:
            self.assertTrue(
                is_disallowed_official_domain(url),
                f"URL should be disallowed: {url}",
            )
            self.assertIsNone(
                clean_official_url(url),
                f"clean_official_url should return None for: {url}",
            )

    # -----------------------------------------------------------------------
    # 3. Strong official website verification
    # -----------------------------------------------------------------------
    def test_03_official_website_verification(self):
        """When official site domain, title, and body match tool name, status is verified."""
        candidate = {
            "candidate_id": "cand-img",
            "tool_name": "Imagetoprompt AI",
            "discovered_url": "https://creati.ai/ai-tools/imagetoprompt-ai",
            "raw_metadata": {"external_product_url": "https://imagetoprompt.org"}
        }
        with patch.object(self.verifier, "fetch_page", return_value=(200, MOCK_OFFICIAL_HTML, None)):
            rec = self.verifier.verify_candidate(candidate)
            self.assertEqual(rec["verification_status"], "verified")
            self.assertEqual(rec["official_website"], "https://imagetoprompt.org/")
            self.assertEqual(rec["verification_source"], "Official Website")
            self.assertEqual(rec["verification_source_url"], "https://imagetoprompt.org/")

    # -----------------------------------------------------------------------
    # 4. Weak branding match => not verified (partially_verified / unverified)
    # -----------------------------------------------------------------------
    def test_04_weak_branding_match_not_verified(self):
        """A page on an unrelated domain with no clear branding must not be verified."""
        soup = BeautifulSoup(MOCK_MINIMAL_HTML, "html.parser")
        # Tool name is 'CloudMaster Optimizer' on 'https://simple.ai'
        status, errors = verify_page_authenticity(
            tool_name="CloudMaster Optimizer",
            official_url="https://simple.ai/",
            soup=soup,
            body_text=soup.get_text(),
        )
        self.assertIn(status, ("partially_verified", "unverified"))
        self.assertTrue(len(errors) > 0)

        # Candidate verification test
        candidate = {
            "candidate_id": "cand-weak",
            "tool_name": "CloudMaster Optimizer",
            "raw_metadata": {"external_product_url": "https://simple.ai"}
        }
        with patch.object(self.verifier, "fetch_page", return_value=(200, MOCK_MINIMAL_HTML, None)):
            rec = self.verifier.verify_candidate(candidate)
            self.assertNotEqual(rec["verification_status"], "verified")
            self.assertIn(rec["verification_status"], ("partially_verified", "unverified"))

    # -----------------------------------------------------------------------
    # 5. Generic page keywords do NOT create inputs/outputs
    # -----------------------------------------------------------------------
    def test_05_generic_keywords_do_not_create_inputs_outputs(self):
        """Mere mention of 'image', 'text', 'code', 'video' must NOT produce inputs or outputs."""
        soup = BeautifulSoup(MOCK_GENERIC_KEYWORDS_HTML, "html.parser")
        text = soup.get_text()
        inputs, outputs = extract_concrete_inputs_outputs(MOCK_GENERIC_KEYWORDS_HTML, text)
        self.assertEqual(inputs, [])
        self.assertEqual(outputs, [])

    # -----------------------------------------------------------------------
    # 6. Explicit input / output wording is accepted
    # -----------------------------------------------------------------------
    def test_06_explicit_input_output_wording_accepted(self):
        """Explicit action phrases like 'upload an image', 'generate text prompts' are extracted."""
        soup = BeautifulSoup(MOCK_OFFICIAL_HTML, "html.parser")
        text = soup.get_text()
        inputs, outputs = extract_concrete_inputs_outputs(MOCK_OFFICIAL_HTML, text)
        self.assertIn("Image", inputs)
        self.assertIn("PDF / Document", inputs)
        self.assertIn("Text Prompt", outputs)
        self.assertIn("Summary", outputs)
        # Verify vague generic items are rejected
        self.assertNotIn("Data", inputs)
        self.assertNotIn("AI", outputs)

    # -----------------------------------------------------------------------
    # 7. Official logo & favicon handling
    # -----------------------------------------------------------------------
    def test_07_logo_and_favicon_handling(self):
        """Favicons and icons must be on the verified domain and not fabricated."""
        soup = BeautifulSoup(MOCK_OFFICIAL_HTML, "html.parser")
        logo = extract_official_logo(soup, "https://imagetoprompt.org")
        self.assertEqual(logo, "https://imagetoprompt.org/assets/icon-192.png")

        # Test external domain favicon is rejected
        external_icon_html = """
        <html><head>
          <link rel="icon" href="https://thirdparty-tracker.com/bad-icon.png" />
        </head><body></body></html>
        """
        soup_ext = BeautifulSoup(external_icon_html, "html.parser")
        self.assertIsNone(extract_official_logo(soup_ext, "https://myproduct.com"))

        # Test asset domain helper
        self.assertTrue(is_allowed_asset_domain("https://resource.myproduct.com/icon.png", "https://myproduct.com"))
        self.assertFalse(is_allowed_asset_domain("https://otherdomain.com/icon.png", "https://myproduct.com"))

    # -----------------------------------------------------------------------
    # 8. No fabricated logo URL when page has no icons
    # -----------------------------------------------------------------------
    def test_08_no_fabricated_logo_url(self):
        """When page contains no declared logo/icon, logo_url must remain None."""
        soup = BeautifulSoup(MOCK_MINIMAL_HTML, "html.parser")
        logo = extract_official_logo(soup, "https://simple.ai")
        self.assertIsNone(logo)

    # -----------------------------------------------------------------------
    # 9. Uncertain pricing remains null (no directory hint inference)
    # -----------------------------------------------------------------------
    def test_09_uncertain_pricing_remains_null(self):
        """If official page lacks explicit plan or pricing statements, pricing fields stay None."""
        pricing = extract_pricing_evidence(MOCK_MINIMAL_HTML, MOCK_MINIMAL_HTML, raw_hints={"pricing_hint": "Freemium"})
        self.assertIsNone(pricing["pricing_model"])
        self.assertIsNone(pricing["starting_price"])
        self.assertIsNone(pricing["free_plan"])
        self.assertIsNone(pricing["free_trial"])

    # -----------------------------------------------------------------------
    # 10. Explicit pricing extraction
    # -----------------------------------------------------------------------
    def test_10_explicit_pricing_extraction(self):
        """Explicit pricing phrases are accurately extracted."""
        soup = BeautifulSoup(MOCK_OFFICIAL_HTML, "html.parser")
        pricing = extract_pricing_evidence(MOCK_OFFICIAL_HTML, soup.get_text(), raw_hints=None)
        self.assertEqual(pricing["starting_price"], "$15/month")
        self.assertTrue(pricing["free_plan"])
        self.assertTrue(pricing["free_trial"])
        self.assertEqual(pricing["pricing_model"], "Freemium")

    # -----------------------------------------------------------------------
    # 11. Uncertain status remains null (never assumed Active)
    # -----------------------------------------------------------------------
    def test_11_uncertain_status_remains_null(self):
        """Status must NOT default to Active solely on 200 OK without availability evidence."""
        soup = BeautifulSoup(MOCK_MINIMAL_HTML, "html.parser")
        status = determine_current_status(soup, soup.get_text(), "Simple AI Tool")
        self.assertIsNone(status)

        # But when live CTA is present:
        soup_active = BeautifulSoup(MOCK_OFFICIAL_HTML, "html.parser")
        status_active = determine_current_status(soup_active, soup_active.get_text(), "Imagetoprompt AI")
        self.assertEqual(status_active, "Active")

    # -----------------------------------------------------------------------
    # 12. Missing official URL
    # -----------------------------------------------------------------------
    def test_12_missing_official_url(self):
        """Candidate with no external URL and failed directory fetch is unverified."""
        candidate = {
            "candidate_id": "cand-none",
            "tool_name": "Ghost Tool",
            "discovered_url": "https://theresanaiforthat.com/ai/ghost-tool",
            "raw_metadata": {}
        }
        with patch.object(self.verifier, "fetch_page", return_value=(403, None, "HTTP 403 Forbidden")):
            rec = self.verifier.verify_candidate(candidate)
            self.assertEqual(rec["verification_status"], "unverified")
            self.assertIsNone(rec["official_website"])
            self.assertTrue(len(rec["verification_errors"]) > 0)

    # -----------------------------------------------------------------------
    # 13. HTTP error handling (403, 404, 429, timeout)
    # -----------------------------------------------------------------------
    def test_13_http_errors_and_timeout_handling(self):
        """Test HTTP 403, 404, 429, and timeouts are classified as failed with clear messages."""
        for code, msg in [
            (403, "HTTP 403 Forbidden — site blocked automated access"),
            (404, "HTTP 404 Not Found"),
            (429, "HTTP 429 Too Many Requests"),
            (None, "Request timed out"),
        ]:
            candidate = {
                "candidate_id": f"cand-{code}",
                "tool_name": f"Error Tool {code}",
                "raw_metadata": {"external_product_url": f"https://error-{code}.ai"}
            }
            with patch.object(self.verifier, "fetch_page", return_value=(code, None, msg)):
                rec = self.verifier.verify_candidate(candidate)
                self.assertEqual(rec["verification_status"], "failed")
                self.assertTrue(len(rec["verification_errors"]) > 0)

    # -----------------------------------------------------------------------
    # 14. Strict null handling (no fabrication of developer/country/version)
    # -----------------------------------------------------------------------
    def test_14_strict_null_handling(self):
        """Unstated fields must remain None / empty list without fabrication."""
        candidate = {
            "candidate_id": "cand-min",
            "tool_name": "Simple AI",
            "raw_metadata": {"external_product_url": "https://simple.ai"}
        }
        with patch.object(self.verifier, "fetch_page", return_value=(200, MOCK_MINIMAL_HTML, None)):
            rec = self.verifier.verify_candidate(candidate)
            self.assertIsNone(rec["logo_url"])
            self.assertIsNone(rec["company_developer"])
            self.assertIsNone(rec["starting_price"])
            self.assertIsNone(rec["api_availability"])
            self.assertIsNone(rec["open_source_status"])
            self.assertIsNone(rec["country"])
            self.assertIsNone(rec["version"])
            self.assertIsNone(rec["launch_date"])
            self.assertEqual(rec["integrations"], [])

    # -----------------------------------------------------------------------
    # 15. Output compatibility with AITool schema
    # -----------------------------------------------------------------------
    def test_15_output_compatibility_with_aitool_schema(self):
        """Verified record must validate cleanly against Pydantic AITool model."""
        candidate = {
            "candidate_id": "cand-full",
            "tool_name": "Imagetoprompt AI",
            "discovery_source": "Creati.ai",
            "discovery_source_url": "https://creati.ai/ai-tools/",
            "raw_metadata": {"external_product_url": "https://imagetoprompt.org"}
        }
        with patch.object(self.verifier, "fetch_page", return_value=(200, MOCK_OFFICIAL_HTML, None)):
            rec = self.verifier.verify_candidate(candidate)
            tool = AITool(**rec)
            self.assertEqual(tool.tool_name, "Imagetoprompt AI")
            self.assertEqual(str(tool.official_website), "https://imagetoprompt.org/")
            self.assertEqual(tool.entity_type, "tool")
            self.assertIn("Image", tool.inputs)
            self.assertIn("Text Prompt", tool.outputs)
            self.assertEqual(tool.starting_price, "$15/month")


if __name__ == "__main__":
    unittest.main()
