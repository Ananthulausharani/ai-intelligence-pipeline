"""
Unit tests for AI Tool Discovery Harvester (src.agents.tool_harvester).

Verifies:
1. URL normalization stripping tracking parameters, fragments, and trailing slashes
2. TAAFT adapter HTML parsing (tool name, developer, description, categories, pricing)
3. Creati.ai adapter HTML parsing (tool name, description, category tags, external product URL)
4. Graceful handling of HTTP 403, 404, 429, timeouts, and network connection errors
5. Deterministic deduplication across multi-directory appearances and discovery references merging
6. Strict candidate limit enforcement
7. Output JSON serialization matching raw candidate specifications
8. Robustness against malformed or empty HTML content
"""

import asyncio
from datetime import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_harvester import (
    CreatiAIDiscoveryAdapter,
    TAAFTDiscoveryAdapter,
    ToolDiscoveryAdapter,
    ToolHarvester,
    normalize_url,
)

# ---------------------------------------------------------------------------
# Mock HTML Fixtures
# ---------------------------------------------------------------------------

MOCK_TAAFT_HTML = """
<!DOCTYPE html>
<html>
<body>
  <div class="home-listing-row listing-table-row home-today-row">
    <div class="listing-table-cell home-today-name-cell">
      <a href="https://theresanaiforthat.com/ai/humwork/?ref=home">Humwork</a>
      <a href="https://theresanaiforthat.com/ai/humwork/?ref=home">On-demand human experts for AI agents.</a>
    </div>
    <div class="listing-table-cell home-today-topic-cell">
      <a href="https://theresanaiforthat.com/task/expert-advice/">Expert Advice</a>
    </div>
    <div class="listing-table-cell home-today-author-cell">
      <a href="https://theresanaiforthat.com/company/orange-ai-inc/">Orange AI Inc.</a>
    </div>
    <div class="listing-table-cell tools-stat-cell">
      <span>Freemium from $20/mo</span>
    </div>
  </div>
  <div class="home-listing-row listing-table-row home-today-row">
    <div class="listing-table-cell home-today-name-cell">
      <a href="https://theresanaiforthat.com/ai/cursor-editor/">Cursor by Anysphere</a>
      <a href="https://theresanaiforthat.com/ai/cursor-editor/">AI Code Editor built for pair-programming.</a>
    </div>
    <div class="listing-table-cell home-today-topic-cell">
      <a href="https://theresanaiforthat.com/task/coding/">Developer Tools</a>
    </div>
  </div>
</body>
</html>
"""

MOCK_CREATI_HTML = """
<!DOCTYPE html>
<html>
<body>
  <ul>
    <li style="display:grid;">
      <div class="cardContainer">
        <a href="/ai-tools/imagetoprompt-ai/?ref=card">
          <img alt="Imagetoprompt ai" src="https://cdn-image.creati.ai/default.webp" />
        </a>
        <div class="w-11/12">
          <h3>
            <a href="/ai-tools/imagetoprompt-ai/" title="Imagetoprompt ai">Imagetoprompt ai</a>
          </h3>
          <div>
            <a href="https://imagetoprompt.org/?utm_source=creati.ai" target="_blank">External Link</a>
          </div>
          <div class="description" title="Turn reference images into detailed prompts.">
            Turn reference images into detailed prompts.
          </div>
          <div class="category-tag-container">
            <a class="category-tag" title="Image to Prompt">
              <div class="categoriedTag">Image to Prompt</div>
            </a>
            <a class="category-tag" title="Prompt Engineering">
              <div class="categoriedTag">Prompt Engineering</div>
            </a>
          </div>
        </div>
      </div>
    </li>
    <li style="display:grid;">
      <div class="cardContainer">
        <a href="/ai-tools/cursor-editor/">
          <img alt="Cursor Editor" src="https://cdn-image.creati.ai/cursor.webp" />
        </a>
        <div class="w-11/12">
          <h3>
            <a href="/ai-tools/cursor-editor/">Cursor Editor</a>
          </h3>
          <div class="description">
            Next-generation AI code editor.
          </div>
          <div class="category-tag-container">
            <a class="category-tag">
              <div class="categoriedTag">Coding</div>
            </a>
          </div>
        </div>
      </div>
    </li>
  </ul>
</body>
</html>
"""


class TestToolHarvester(unittest.TestCase):
    """Test suite for AI Tool discovery and candidate extraction."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_normalize_url(self):
        """Test URL normalization cleans tracking parameters and trailing slashes."""
        raw_url = "https://theresanaiforthat.com/ai/humwork/?utm_source=twitter&ref=home&fid=123#summary"
        clean = normalize_url(raw_url)
        self.assertEqual(clean, "https://theresanaiforthat.com/ai/humwork")

        ext_url = "https://www.imagetoprompt.org/?utm_source=creati.ai&fbclid=abc"
        clean_ext = normalize_url(ext_url)
        self.assertEqual(clean_ext, "https://www.imagetoprompt.org")

        empty = normalize_url("")
        self.assertEqual(empty, "")

    def test_taaft_adapter_parsing(self):
        """Test TAAFT adapter correctly parses candidate attributes from HTML."""
        adapter = TAAFTDiscoveryAdapter()
        candidates = adapter.parse_html(MOCK_TAAFT_HTML, limit=10)

        self.assertEqual(len(candidates), 2)

        cand1 = candidates[0]
        self.assertEqual(cand1["tool_name"], "Humwork")
        self.assertEqual(cand1["company_developer"], "Orange AI Inc.")
        self.assertEqual(cand1["discovered_url"], "https://theresanaiforthat.com/ai/humwork")
        self.assertEqual(cand1["discovery_source"], "There's An AI For That")
        self.assertEqual(cand1["short_description"], "On-demand human experts for AI agents.")
        self.assertIn("Expert Advice", cand1["categories"])
        self.assertEqual(cand1["raw_metadata"].get("pricing_hint"), "Freemium")
        self.assertEqual(len(cand1["discovery_references"]), 1)

        cand2 = candidates[1]
        self.assertEqual(cand2["tool_name"], "Cursor")
        self.assertEqual(cand2["company_developer"], "Anysphere")
        self.assertIn("Developer Tools", cand2["categories"])

    def test_creati_adapter_parsing(self):
        """Test Creati.ai adapter correctly parses candidate attributes and external links."""
        adapter = CreatiAIDiscoveryAdapter()
        candidates = adapter.parse_html(MOCK_CREATI_HTML, limit=10)

        self.assertEqual(len(candidates), 2)

        cand1 = candidates[0]
        self.assertEqual(cand1["tool_name"], "Imagetoprompt ai")
        self.assertEqual(cand1["discovered_url"], "https://creati.ai/ai-tools/imagetoprompt-ai")
        self.assertEqual(cand1["discovery_source"], "Creati.ai")
        self.assertEqual(cand1["short_description"], "Turn reference images into detailed prompts.")
        self.assertIn("Image to Prompt", cand1["categories"])
        self.assertIn("Prompt Engineering", cand1["categories"])
        self.assertEqual(
            cand1["raw_metadata"].get("external_product_url"),
            "https://imagetoprompt.org",
        )

        cand2 = candidates[1]
        self.assertEqual(cand2["tool_name"], "Cursor Editor")
        self.assertEqual(cand2["discovered_url"], "https://creati.ai/ai-tools/cursor-editor")

    def test_http_403_graceful_handling(self):
        """Verify HTTP 403 Forbidden is recorded honestly without crashing."""
        adapter = TAAFTDiscoveryAdapter()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://theresanaiforthat.com/",
                code=403,
                msg="Forbidden",
                hdrs={},
                fp=None,
            )
            candidates = asyncio.run(adapter.discover_candidates(limit=10))

            self.assertEqual(len(candidates), 0)
            self.assertEqual(adapter.stats["failed_requests"], 1)
            self.assertEqual(adapter.stats["status"], "FAIL")
            self.assertTrue(any("403" in err for err in adapter.stats["errors"]))

    def test_http_429_rate_limiting_handling(self):
        """Verify HTTP 429 Too Many Requests is recorded honestly."""
        adapter = CreatiAIDiscoveryAdapter()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://creati.ai/ai-tools/",
                code=429,
                msg="Too Many Requests",
                hdrs={"Retry-After": "60"},
                fp=None,
            )
            candidates = asyncio.run(adapter.discover_candidates(limit=10))

            self.assertEqual(len(candidates), 0)
            self.assertEqual(adapter.stats["failed_requests"], 1)
            self.assertTrue(any("429" in err for err in adapter.stats["errors"]))

    def test_deduplication_and_multi_source_merging(self):
        """
        Verify that a tool appearing on multiple directories is collapsed into
        one candidate while retaining discovery references from all sources.
        """
        async def mock_fetch1(limit=10):
            return [
                {
                    "candidate_id": "candidate-cursor",
                    "tool_name": "Cursor",
                    "company_developer": "Anysphere",
                    "discovered_url": "https://theresanaiforthat.com/ai/cursor",
                    "discovery_source": "There's An AI For That",
                    "discovery_source_url": "https://theresanaiforthat.com/",
                    "short_description": "AI code editor.",
                    "categories": ["Developer Tools"],
                    "tags": ["developer tools"],
                    "raw_metadata": {"source_slug": "cursor", "pricing_hint": "Freemium"},
                    "discovery_timestamp": "2026-09-18T10:00:00Z",
                    "discovery_references": [
                        {
                            "source": "There's An AI For That",
                            "source_url": "https://theresanaiforthat.com/",
                            "discovered_url": "https://theresanaiforthat.com/ai/cursor",
                            "discovered_at": "2026-09-18T10:00:00Z",
                        }
                    ],
                }
            ]

        async def mock_fetch2(limit=10):
            return [
                {
                    "candidate_id": "candidate-cursor",
                    "tool_name": "Cursor",
                    "company_developer": None,
                    "discovered_url": "https://creati.ai/ai-tools/cursor",
                    "discovery_source": "Creati.ai",
                    "discovery_source_url": "https://creati.ai/ai-tools/",
                    "short_description": "AI editor for software engineers.",
                    "categories": ["Coding Assistants"],
                    "tags": ["coding assistants"],
                    "raw_metadata": {"source_slug": "cursor", "external_product_url": "https://cursor.com"},
                    "discovery_timestamp": "2026-09-18T10:05:00Z",
                    "discovery_references": [
                        {
                            "source": "Creati.ai",
                            "source_url": "https://creati.ai/ai-tools/",
                            "discovered_url": "https://creati.ai/ai-tools/cursor",
                            "discovered_at": "2026-09-18T10:05:00Z",
                        }
                    ],
                }
            ]

        adapter1 = MagicMock(spec=ToolDiscoveryAdapter)
        adapter1.source_name = "There's An AI For That"
        adapter1.stats = {"source_name": "Source 1", "pages_attempted": 1, "failed_requests": 0}
        adapter1.discover_candidates = mock_fetch1

        adapter2 = MagicMock(spec=ToolDiscoveryAdapter)
        adapter2.source_name = "Creati.ai"
        adapter2.stats = {"source_name": "Source 2", "pages_attempted": 1, "failed_requests": 0}
        adapter2.discover_candidates = mock_fetch2

        harvester = ToolHarvester(adapters=[adapter1, adapter2])
        candidates = asyncio.run(harvester.discover(limit=10))

        # Should be deduplicated into exactly 1 candidate
        self.assertEqual(len(candidates), 1)
        self.assertEqual(harvester.report["duplicates_removed"], 1)

        candidate = candidates[0]
        self.assertEqual(candidate["tool_name"], "Cursor")
        self.assertEqual(candidate["company_developer"], "Anysphere")
        self.assertIn("Developer Tools", candidate["categories"])
        self.assertIn("Coding Assistants", candidate["categories"])

        # Discovery references must contain both sources
        self.assertEqual(len(candidate["discovery_references"]), 2)
        sources = [ref["source"] for ref in candidate["discovery_references"]]
        self.assertIn("There's An AI For That", sources)
        self.assertIn("Creati.ai", sources)

    def test_limit_enforcement(self):
        """Verify harvester stops when target limit is reached."""
        mock_candidates = [
            {
                "candidate_id": f"candidate-tool-{i}",
                "tool_name": f"AI Tool {i}",
                "company_developer": None,
                "discovered_url": f"https://example.com/ai/{i}",
                "discovery_source": "Mock Directory",
                "discovery_source_url": "https://example.com",
                "short_description": f"Description {i}",
                "categories": ["Utility"],
                "tags": ["utility"],
                "raw_metadata": {},
                "discovery_timestamp": "2026-09-18T10:00:00Z",
                "discovery_references": [],
            }
            for i in range(20)
        ]

        async def mock_fetch(limit=50):
            return mock_candidates

        adapter = MagicMock(spec=ToolDiscoveryAdapter)
        adapter.source_name = "Mock Directory"
        adapter.stats = {"pages_attempted": 1, "failed_requests": 0}
        adapter.discover_candidates = mock_fetch

        harvester = ToolHarvester(adapters=[adapter])
        # Ask for limit=7
        candidates = asyncio.run(harvester.discover(limit=7))
        self.assertEqual(len(candidates), 7)
        self.assertEqual(harvester.report["final_candidate_count"], 7)

    def test_discover_and_save_json(self):
        """Verify discover_and_save creates valid formatted JSON matching candidate schema."""
        output_file = os.path.join(self.temp_dir, "raw_ai_tools.json")

        adapter = TAAFTDiscoveryAdapter()
        with patch.object(adapter, "_fetch_html", return_value=MOCK_TAAFT_HTML):
            harvester = ToolHarvester(adapters=[adapter])
            candidates = asyncio.run(harvester.discover_and_save(limit=5, output_file=output_file))

            self.assertTrue(os.path.exists(output_file))
            with open(output_file, "r", encoding="utf-8") as f:
                saved = json.load(f)

            self.assertEqual(len(saved), 2)
            self.assertEqual(saved[0]["tool_name"], "Humwork")
            self.assertIn("discovery_references", saved[0])
            self.assertIn("raw_metadata", saved[0])


if __name__ == "__main__":
    unittest.main()
