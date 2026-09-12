"""
Offline Manual Test Suite for Step 27A — Verified Research Paper Harvesting.

Verifies:
1. ResearchPaper schema validation
2. arXiv metadata extraction
3. Pagination traversal
4. arXiv ID deduplication
5. Paper URL deduplication
6. Source URL traceability
7. Missing GitHub allowed
8. github_stars integer or null validation
9. No fabricated stars
10. Publication date comes from arXiv metadata
11. Malformed records rejected
12. API failure isolation
13. Large target harvesting stops at target
14. Zero synthetic records
15. Output contains unique valid papers

All tests use deterministic offline fixtures and do not call external APIs.
"""

import asyncio
import os
import re
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.agent3_research import (
    ResearchPaperAgent,
    _arxiv_id_from_url,
    _parse_entry,
    _enrich_papers_async,
)
from src.llm.schemas import ResearchPaper, ResearchPaperContent, Source

# ---------------------------------------------------------------------------
# Offline XML Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ATOM_ENTRY = """
<entry xmlns="http://www.w3.org/2005/Atom">
  <id>http://arxiv.org/abs/2401.00001v1</id>
  <updated>2024-01-02T10:00:00Z</updated>
  <published>2024-01-01T12:00:00Z</published>
  <title>  Advances in Multi-Agent Reinforcement Learning
          with Foundation Models  </title>
  <summary>We introduce a novel framework for multi-agent reasoning.</summary>
  <author>
    <name>Jane Doe</name>
  </author>
  <author>
    <name>John Smith</name>
  </author>
  <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
  <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
</entry>
"""

SAMPLE_ATOM_FEED_BATCH_1 = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <published>2024-01-01T12:00:00Z</published>
    <title>Paper One: Foundational AI</title>
    <author><name>Alice Researcher</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <published>2024-01-02T12:00:00Z</published>
    <title>Paper Two: Deep Vision Models</title>
    <author><name>Bob Scientist</name></author>
  </entry>
</feed>
"""

SAMPLE_ATOM_FEED_BATCH_2 = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2401.00003v1</id>
    <published>2024-01-03T12:00:00Z</published>
    <title>Paper Three: Natural Language Frontiers</title>
    <author><name>Charlie Linguist</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v2</id>
    <published>2024-01-04T12:00:00Z</published>
    <title>Paper One: Foundational AI (Updated)</title>
    <author><name>Alice Researcher</name></author>
  </entry>
</feed>
"""


class TestResearchPaperHarvesting(unittest.TestCase):

    def setUp(self):
        self.agent = ResearchPaperAgent()

    # 1. Schema Validation
    def test_research_paper_schema_validation(self):
        doc = {
            "schemaVersion": "1.0",
            "recordType": "RESEARCH_PAPER",
            "source": {
                "name": "arXiv",
                "url": "https://export.arxiv.org/api/query?id_list=2401.00001",
            },
            "content": {
                "title": "A Great AI Paper",
                "authors": ["Alice Smith", "Bob Jones"],
                "paper_url": "https://arxiv.org/abs/2401.00001",
                "github_url": "https://github.com/org/repo",
                "github_stars": 1500,
                "published_date": "2024-01-01T12:00:00Z",
            },
            "title": "A Great AI Paper",
            "authors": ["Alice Smith", "Bob Jones"],
            "paper_url": "https://arxiv.org/abs/2401.00001",
            "github_url": "https://github.com/org/repo",
            "github_stars": 1500,
            "published_date": "2024-01-01T12:00:00Z",
            "collectedAt": "2026-09-12T12:00:00Z",
        }
        validated = ResearchPaper.model_validate(doc)
        self.assertEqual(validated.recordType, "RESEARCH_PAPER")
        self.assertEqual(str(validated.content.paper_url), "https://arxiv.org/abs/2401.00001")
        self.assertEqual(validated.content.github_stars, 1500)
        self.assertEqual(doc.get("github_url"), "https://github.com/org/repo")
        self.assertEqual(doc.get("github_stars"), 1500)

    # 2. arXiv Metadata Extraction
    def test_arxiv_metadata_extraction(self):
        elem = ET.fromstring(SAMPLE_ATOM_ENTRY)
        parsed = _parse_entry(elem)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["arxiv_id"], "2401.00001")
        self.assertEqual(parsed["paper_url"], "https://arxiv.org/abs/2401.00001")
        self.assertEqual(
            parsed["title"],
            "Advances in Multi-Agent Reinforcement Learning with Foundation Models",
        )
        self.assertEqual(parsed["authors"], ["Jane Doe", "John Smith"])
        self.assertEqual(parsed["published_date"], "2024-01-01T12:00:00Z")
        self.assertEqual(parsed["source_url"], "https://export.arxiv.org/api/query?id_list=2401.00001")
        self.assertIsNone(parsed["github_url"])
        self.assertIsNone(parsed["github_stars"])

    # 3. Pagination Traversal
    def test_pagination_traversal(self):
        calls = []

        def mock_http_get(url, extra_headers=None):
            calls.append(url)
            if "start=0" in url:
                return SAMPLE_ATOM_FEED_BATCH_1.encode("utf-8")
            elif "start=2" in url:
                return SAMPLE_ATOM_FEED_BATCH_2.encode("utf-8")
            return b"<feed xmlns='http://www.w3.org/2005/Atom'></feed>"

        with patch("src.agents.agent3_research._http_get", side_effect=mock_http_get):
            papers, report = self.agent.harvest_papers(
                target=3,
                batch_size=2,
                inter_batch_delay=0.0,
                enrich_github=False,
            )

        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(any("start=0" in c for c in calls))
        self.assertTrue(any("start=2" in c for c in calls))
        self.assertEqual(len(papers), 3)

    # 4. arXiv ID Deduplication
    def test_arxiv_id_deduplication(self):
        entry_v1 = """
        <entry xmlns="http://www.w3.org/2005/Atom">
          <id>http://arxiv.org/abs/2401.99999v1</id>
          <published>2024-01-01T00:00:00Z</published>
          <title>Test Title</title>
          <author><name>Author</name></author>
        </entry>
        """
        entry_v2 = """
        <entry xmlns="http://www.w3.org/2005/Atom">
          <id>http://arxiv.org/abs/2401.99999v2</id>
          <published>2024-01-02T00:00:00Z</published>
          <title>Test Title (v2)</title>
          <author><name>Author</name></author>
        </entry>
        """
        p1 = _parse_entry(ET.fromstring(entry_v1))
        p2 = _parse_entry(ET.fromstring(entry_v2))

        self.assertEqual(p1["arxiv_id"], "2401.99999")
        self.assertEqual(p2["arxiv_id"], "2401.99999")

        feed_with_dups = f"""<feed xmlns="http://www.w3.org/2005/Atom">
        {entry_v1}
        {entry_v2}
        </feed>"""

        with patch("src.agents.agent3_research._http_get", return_value=feed_with_dups.encode("utf-8")):
            papers, report = self.agent.harvest_papers(
                target=5,
                batch_size=10,
                inter_batch_delay=0.0,
                enrich_github=False,
            )

        self.assertEqual(len(papers), 1)
        self.assertEqual(report["duplicates_removed"], 1)

    # 5. Paper URL Deduplication
    def test_paper_url_deduplication(self):
        feed = """<feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2405.11111v1</id>
            <published>2024-05-01T00:00:00Z</published>
            <title>Identical Paper 1</title>
            <author><name>Author A</name></author>
          </entry>
          <entry>
            <id>https://arxiv.org/abs/2405.11111</id>
            <published>2024-05-01T00:00:00Z</published>
            <title>Identical Paper 2</title>
            <author><name>Author A</name></author>
          </entry>
        </feed>"""

        with patch("src.agents.agent3_research._http_get", return_value=feed.encode("utf-8")):
            papers, report = self.agent.harvest_papers(
                target=5,
                batch_size=10,
                inter_batch_delay=0.0,
                enrich_github=False,
            )

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["paper_url"], "https://arxiv.org/abs/2405.11111")
        self.assertEqual(report["duplicates_removed"], 1)

    # 6. Source URL Traceability
    def test_source_url_traceability(self):
        elem = ET.fromstring(SAMPLE_ATOM_ENTRY)
        parsed = _parse_entry(elem)
        self.assertEqual(parsed["source_url"], "https://export.arxiv.org/api/query?id_list=2401.00001")
        self.assertEqual(parsed["paper_url"], "https://arxiv.org/abs/2401.00001")

        with patch("src.agents.agent3_research._http_get", return_value=SAMPLE_ATOM_FEED_BATCH_1.encode("utf-8")):
            papers, report = self.agent.harvest_papers(
                target=2,
                batch_size=2,
                inter_batch_delay=0.0,
                enrich_github=False,
            )

        for p in papers:
            self.assertEqual(p["source"]["name"], "arXiv")
            self.assertIn("https://export.arxiv.org/api/query?id_list=", str(p["source"]["url"]))
            self.assertIn("https://arxiv.org/abs/", str(p["paper_url"]))
            self.assertIn("https://arxiv.org/abs/", str(p["content"]["paper_url"]))

    # 7. Missing GitHub Allowed
    def test_missing_github_allowed(self):
        doc = {
            "schemaVersion": "1.0",
            "recordType": "RESEARCH_PAPER",
            "source": {
                "name": "arXiv",
                "url": "https://export.arxiv.org/api/query?id_list=2401.00001",
            },
            "content": {
                "title": "Theoretical Paper Without Code",
                "authors": ["Mathematician"],
                "paper_url": "https://arxiv.org/abs/2401.00001",
                "github_url": None,
                "github_stars": None,
                "published_date": "2024-01-01T12:00:00Z",
            },
            "title": "Theoretical Paper Without Code",
            "authors": ["Mathematician"],
            "paper_url": "https://arxiv.org/abs/2401.00001",
            "github_url": None,
            "github_stars": None,
            "published_date": "2024-01-01T12:00:00Z",
        }
        validated = ResearchPaper.model_validate(doc)
        self.assertIsNone(validated.content.github_url)
        self.assertIsNone(validated.content.github_stars)
        self.assertIsNone(doc.get("github_url"))
        self.assertIsNone(doc.get("github_stars"))

    # 8. github_stars Integer or Null Validation
    def test_github_stars_integer_or_null(self):
        # Valid integer
        c1 = ResearchPaperContent(
            title="T",
            authors=["A"],
            paper_url="https://arxiv.org/abs/2401.00001",
            github_url="https://github.com/org/repo",
            github_stars=42,
            published_date="2024-01-01T00:00:00Z",
        )
        self.assertEqual(c1.github_stars, 42)

        # Valid None
        c2 = ResearchPaperContent(
            title="T",
            authors=["A"],
            paper_url="https://arxiv.org/abs/2401.00001",
            github_url=None,
            github_stars=None,
            published_date="2024-01-01T00:00:00Z",
        )
        self.assertIsNone(c2.github_stars)

        # Invalid string that cannot be int
        with self.assertRaises(Exception):
            ResearchPaperContent(
                title="T",
                authors=["A"],
                paper_url="https://arxiv.org/abs/2401.00001",
                github_stars="lots_of_stars",
                published_date="2024-01-01T00:00:00Z",
            )

    # 9. No Fabricated Stars
    def test_no_fabricated_stars(self):
        papers = [
            {"arxiv_id": "2401.00001", "paper_url": "https://arxiv.org/abs/2401.00001", "github_url": None, "github_stars": None},
        ]
        # Simulate HF returning a repo without stars
        mock_hf_resp = MagicMock()
        mock_hf_resp.status = 200
        mock_hf_resp.text = AsyncMock(return_value='{"githubRepo": "https://github.com/user/code", "githubStars": null}')

        async def run_enrich():
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_get.return_value.__aenter__.return_value = mock_hf_resp
                await _enrich_papers_async(papers, max_concurrency=1)

        asyncio.run(run_enrich())
        self.assertEqual(papers[0]["github_url"], "https://github.com/user/code")
        self.assertIsNone(papers[0]["github_stars"], "Stars must remain None, never converted to 0 or guessed")

    # 10. Publication Date From Metadata
    def test_published_date_from_metadata(self):
        elem = ET.fromstring(SAMPLE_ATOM_ENTRY)
        parsed = _parse_entry(elem)
        self.assertEqual(parsed["published_date"], "2024-01-01T12:00:00Z")
        self.assertNotEqual(parsed["published_date"], parsed["collected_at"])

    # 11. Malformed Records Rejected
    def test_malformed_records_rejected(self):
        # Missing title
        no_title = ET.fromstring("""<entry xmlns="http://www.w3.org/2005/Atom">
          <id>http://arxiv.org/abs/2401.00001</id>
          <published>2024-01-01T00:00:00Z</published>
          <author><name>Author</name></author>
        </entry>""")
        self.assertIsNone(_parse_entry(no_title))

        # Missing authors
        no_authors = ET.fromstring("""<entry xmlns="http://www.w3.org/2005/Atom">
          <id>http://arxiv.org/abs/2401.00001</id>
          <title>A Title</title>
          <published>2024-01-01T00:00:00Z</published>
        </entry>""")
        self.assertIsNone(_parse_entry(no_authors))

        # Missing published date
        no_pub = ET.fromstring("""<entry xmlns="http://www.w3.org/2005/Atom">
          <id>http://arxiv.org/abs/2401.00001</id>
          <title>A Title</title>
          <author><name>Author</name></author>
        </entry>""")
        self.assertIsNone(_parse_entry(no_pub))

    # 12. API Failure Isolation
    def test_api_failure_isolation(self):
        # Even if network raises an exception, harvest_papers handles it gracefully
        with patch("src.agents.agent3_research._http_get", side_effect=Exception("Connection reset")):
            papers, report = self.agent.harvest_papers(
                target=5,
                batch_size=5,
                inter_batch_delay=0.0,
                enrich_github=False,
            )
        self.assertEqual(len(papers), 0)
        self.assertEqual(report["status"], "FAIL")
        self.assertGreaterEqual(report["failures_and_retries"], 3)

    # 13. Target Stopping
    def test_large_target_stopping(self):
        # Batch provides 2 entries. Target is 1. Should stop after 1.
        with patch("src.agents.agent3_research._http_get", return_value=SAMPLE_ATOM_FEED_BATCH_1.encode("utf-8")):
            papers, report = self.agent.harvest_papers(
                target=1,
                batch_size=10,
                inter_batch_delay=0.0,
                enrich_github=False,
            )
        self.assertEqual(len(papers), 1)
        self.assertEqual(report["verified_unique_papers"], 1)

    # 14. Zero Synthetic Records
    def test_zero_synthetic_records(self):
        with patch("src.agents.agent3_research._http_get", return_value=SAMPLE_ATOM_FEED_BATCH_1.encode("utf-8")):
            papers, report = self.agent.harvest_papers(
                target=2,
                batch_size=2,
                inter_batch_delay=0.0,
                enrich_github=False,
            )

        arxiv_regex = re.compile(r"^https://arxiv\.org/abs/\d{4}\.\d{4,5}")
        for p in papers:
            self.assertTrue(arxiv_regex.match(str(p["paper_url"])), f"Invalid paper URL: {p['paper_url']}")
            self.assertEqual(p["source"]["name"], "arXiv")

        self.assertEqual(report["fabricated_records"], 0)

    # 15. Unique Valid Output
    def test_unique_valid_output(self):
        def mock_http_get(url, extra_headers=None):
            if "start=0" in url:
                return SAMPLE_ATOM_FEED_BATCH_1.encode("utf-8")
            elif "start=2" in url:
                return SAMPLE_ATOM_FEED_BATCH_2.encode("utf-8")
            return b"<feed xmlns='http://www.w3.org/2005/Atom'></feed>"

        with patch("src.agents.agent3_research._http_get", side_effect=mock_http_get):
            papers, report = self.agent.harvest_papers(
                target=3,
                batch_size=2,
                inter_batch_delay=0.0,
                enrich_github=False,
            )

        ids = [p["source"]["url"].split("id_list=")[-1] for p in papers]
        urls = [str(p["paper_url"]) for p in papers]

        # Verify 100% uniqueness
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(urls), len(set(urls)))

        # Verify 100% schema validity
        for p in papers:
            model = ResearchPaper.model_validate(p)
            self.assertEqual(model.recordType, "RESEARCH_PAPER")


if __name__ == "__main__":
    unittest.main(verbosity=2)
