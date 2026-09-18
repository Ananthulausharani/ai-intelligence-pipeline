"""
Unit tests for AI Tool Deduplicator (src.agents.tool_deduplicator).

Verifies:
1. Same official domain deduplication and merging
2. Same product URL deduplication
3. Multi-directory listing deduplication (TAAFT + Creati.ai -> 1 record)
4. Slight name variations with same product identity
5. Genuinely different products with similar names are NOT merged
6. Preservation of discovery references and strongest verified evidence
"""

import os
import sys
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_deduplicator import ToolDeduplicator, extract_canonical_domain, normalize_clean_url
from src.models.ai_tool import AITool


class TestToolDeduplicator(unittest.TestCase):
    """Test suite for ToolDeduplicator."""

    def setUp(self):
        self.dedup = ToolDeduplicator()

    def test_same_official_domain_merging(self):
        """Records pointing to the same official domain must be merged into one."""
        records = [
            {
                "tool_name": "Cursor",
                "official_website": "https://www.cursor.com",
                "company_developer": "Anysphere",
                "categories": ["Developer Tools"],
                "discovery_references": [
                    {"source": "There's An AI For That", "discovered_url": "https://taaft.com/ai/cursor"}
                ],
            },
            {
                "tool_name": "Cursor Editor",
                "official_website": "https://cursor.com/features",
                "categories": ["AI Assistant"],
                "discovery_references": [
                    {"source": "Creati.ai", "discovered_url": "https://creati.ai/ai-tools/cursor"}
                ],
            },
        ]

        result = self.dedup.deduplicate(records)
        self.assertEqual(len(result), 1)
        merged = result[0]
        self.assertEqual(merged["tool_name"], "Cursor")
        self.assertEqual(merged["company_developer"], "Anysphere")
        # Categories merged
        self.assertIn("Developer Tools", merged["categories"])
        self.assertIn("AI Assistant", merged["categories"])
        # Both discovery references preserved
        self.assertEqual(len(merged["discovery_references"]), 2)

    def test_same_product_url_merging(self):
        """Records with the same product URL must be merged."""
        records = [
            {
                "tool_name": "v0 by Vercel",
                "official_website": "https://v0.dev/?utm_source=directory",
                "categories": ["UI Generator"],
            },
            {
                "tool_name": "v0",
                "official_website": "https://v0.dev",
                "company_developer": "Vercel",
                "categories": ["Frontend"],
            },
        ]

        result = self.dedup.deduplicate(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["company_developer"], "Vercel")

    def test_directory_duplicates(self):
        """Multiple directory listings of the same tool must produce ONE record."""
        records = [
            {
                "tool_name": "Midjourney",
                "official_website": "https://midjourney.com",
                "discovery_source": "There's An AI For That",
                "discovery_references": [{"source": "TAAFT", "discovered_url": "https://taaft.com/ai/midjourney"}],
            },
            {
                "tool_name": "Midjourney",
                "official_website": "https://midjourney.com",
                "discovery_source": "Creati.ai",
                "discovery_references": [{"source": "Creati.ai", "discovered_url": "https://creati.ai/ai-tools/midjourney"}],
            },
        ]

        result = self.dedup.deduplicate(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["discovery_references"]), 2)

    def test_slight_naming_differences_same_product(self):
        """Tools with slight name variations and same domain/company must merge."""
        records = [
            {
                "tool_name": "GitHub Copilot",
                "company_developer": "GitHub",
                "official_website": "https://github.com/features/copilot",
            },
            {
                "tool_name": "Copilot by GitHub",
                "company_developer": "GitHub",
                "official_website": "https://github.com/features/copilot",
            },
        ]

        result = self.dedup.deduplicate(records)
        self.assertEqual(len(result), 1)

    def test_different_products_similar_names_not_merged(self):
        """Distinct products with similar names and different official domains must NOT be merged."""
        records = [
            {
                "tool_name": "Writer",
                "company_developer": "Writer Inc.",
                "official_website": "https://writer.com",
            },
            {
                "tool_name": "Writer",
                "company_developer": "AI Writer Co",
                "official_website": "https://aiwriter.io",
            },
        ]

        result = self.dedup.deduplicate(records)
        self.assertEqual(len(result), 2)
        domains = {r["official_website"] for r in result}
        self.assertEqual(domains, {"https://writer.com", "https://aiwriter.io"})

    def test_preserves_verified_evidence_over_unverified(self):
        """Merging preserves verified status and verified source over unverified."""
        records = [
            {
                "tool_name": "Claude",
                "verification_status": "unverified",
                "official_website": "https://claude.ai",
            },
            {
                "tool_name": "Claude AI",
                "verification_status": "verified",
                "official_website": "https://claude.ai",
                "verification_source": "Official Website",
                "company_developer": "Anthropic",
            },
        ]

        result = self.dedup.deduplicate(records)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["verification_status"], "verified")
        self.assertEqual(result[0]["company_developer"], "Anthropic")
        self.assertEqual(result[0]["verification_source"], "Official Website")


if __name__ == "__main__":
    unittest.main()
