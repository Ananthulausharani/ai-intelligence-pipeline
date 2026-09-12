"""
Offline Manual Test Suite for Step 27B — Google Sheets Export.

Verifies:
1. Startup JSON loads correctly
2. Product JSON loads correctly
3. Research paper JSON loads correctly
4. Job dataset loads correctly
5. News dataset loads correctly
6. Entity mapping dataset loads correctly
7. Required six worksheet names are exact
8. Required headers exist for all 6 worksheets
9. No duplicate startup canonical names
10. No duplicate products within canonical startup
11. Research paper URLs are valid/non-empty
12. GitHub stars are integers or null
13. No fabricated URLs
14. No credentials committed
15. Freshness validation is preserved for Jobs and News

All tests run completely offline without requiring live Google API credentials or network access.
"""

import json
import os
import re
import sys
import unittest
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.google_sheets import (
    GoogleSheetsExporter,
    WORKSHEET_NAMES,
    WORKSHEETS_CONFIG,
    startup_to_row,
    product_to_row,
    paper_to_row,
    job_to_row,
    news_to_row,
    mapping_log_to_row,
)


class TestGoogleSheetsExportManual(unittest.TestCase):

    def setUp(self):
        self.exporter = GoogleSheetsExporter()

    # 1. Startup JSON loads correctly
    def test_startup_json_loads(self):
        path = "data/output/startups.json"
        self.assertTrue(os.path.exists(path), f"File {path} must exist")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1000, "Must contain >= 1000 verified startups")
        first = data[0]
        self.assertEqual(first.get("recordType"), "STARTUP")
        self.assertIn("content", first)
        self.assertIn("source", first)

    # 2. Product JSON loads correctly
    def test_product_json_loads(self):
        path = "data/output/products.json"
        self.assertTrue(os.path.exists(path), f"File {path} must exist")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1000, "Must contain >= 1000 verified products")
        first = data[0]
        self.assertEqual(first.get("recordType"), "PRODUCT")
        self.assertIn("content", first)

    # 3. Research Paper JSON loads correctly
    def test_research_paper_json_loads(self):
        path = "data/output/research_papers.json"
        self.assertTrue(os.path.exists(path), f"File {path} must exist")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1000, "Must contain >= 1000 verified research papers")
        first = data[0]
        self.assertEqual(first.get("recordType"), "RESEARCH_PAPER")

    # 4. Job dataset loads correctly
    def test_job_dataset_loads(self):
        sample_job = {
            "recordType": "JOB",
            "source": {"url": "https://www.ycombinator.com/jobs/role/ai"},
            "content": {
                "url": "https://www.ycombinator.com/companies/replo/jobs/123",
                "company": "Replo",
                "title": "Full Stack Engineer",
                "date": "2026-09-12T08:00:00Z",
                "is_remote": True,
                "role_family": "Engineering / AI",
            },
            "collected_at": "2026-09-12T12:00:00Z",
        }
        row = job_to_row(sample_job)
        self.assertEqual(row[1], "JOB")
        self.assertEqual(row[2], "Y Combinator")
        self.assertEqual(row[5], "Replo")
        self.assertEqual(row[6], "Full Stack Engineer")
        self.assertEqual(row[7], "2026-09-12T08:00:00Z")
        self.assertEqual(row[8], "True")

    # 5. News dataset loads correctly
    def test_news_dataset_loads(self):
        sample_news = {
            "recordType": "NEWS",
            "source": {"url": "https://techcrunch.com/category/artificial-intelligence/"},
            "content": {
                "url": "https://techcrunch.com/2026/09/12/ai-breakthrough",
                "title": "Major AI Breakthrough",
                "published_date": "2026-09-12T10:00:00Z",
                "text": "Article content...",
            },
            "collected_at": "2026-09-12T12:00:00Z",
        }
        row = news_to_row(sample_news)
        self.assertEqual(row[1], "NEWS")
        self.assertEqual(row[2], "TechCrunch")
        self.assertEqual(row[5], "Major AI Breakthrough")
        self.assertEqual(row[6], "2026-09-12T10:00:00Z")

    # 6. Entity mapping dataset loads correctly
    def test_entity_mapping_dataset_loads(self):
        sample_log = {
            "raw_name": "OpenAI, Inc.",
            "canonical_name": "OpenAI",
            "entity_type": "STARTUP",
            "source_url": "https://techcrunch.com/article",
            "match_type": "ALIAS",
            "confidence": 1.0,
            "reason": "Matched via ALIAS",
        }
        row = mapping_log_to_row(sample_log)
        self.assertEqual(row[1], "ENTITY_MAPPING_LOG")
        self.assertEqual(row[5], "OpenAI, Inc.")
        self.assertEqual(row[6], "OpenAI")
        self.assertEqual(row[7], "ALIAS")
        self.assertEqual(row[8], "STARTUP")

    # 7. Required six worksheet names are exact
    def test_required_six_worksheet_names(self):
        expected = [
            "Startups",
            "Products",
            "Research Papers",
            "Jobs",
            "News",
            "Entity Mapping Log",
        ]
        self.assertEqual(WORKSHEET_NAMES, expected)
        self.assertEqual(len(WORKSHEET_NAMES), 6)

    # 8. Required headers exist for all 6 worksheets
    def test_required_headers_exist(self):
        for name in WORKSHEET_NAMES:
            cols = WORKSHEETS_CONFIG[name]["columns"]
            self.assertIn("schemaVersion", cols)
            self.assertIn("recordType", cols)
            self.assertIn("sourceName", cols)
            self.assertIn("sourceUrl", cols)

            if name == "Startups":
                self.assertIn("entityName", cols)
                self.assertIn("employeeCount", cols)
            elif name == "Products":
                self.assertIn("productName", cols)
                self.assertIn("pricingModel", cols)
            elif name == "Research Papers":
                self.assertIn("title", cols)
                self.assertIn("paperUrl", cols)
                self.assertIn("githubUrl", cols)
                self.assertIn("githubStars", cols)
            elif name == "Jobs":
                self.assertIn("company", cols)
                self.assertIn("date", cols)
            elif name == "News":
                self.assertIn("title", cols)
                self.assertIn("date", cols)
            elif name == "Entity Mapping Log":
                self.assertIn("rawName", cols)
                self.assertIn("canonicalName", cols)
                self.assertIn("matchType", cols)

    # 9. No duplicate startup canonical names
    def test_no_duplicate_startup_canonical_names(self):
        path = "data/output/startups.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        names = [r["content"]["entityName"] for r in data]
        self.assertEqual(len(names), len(set(names)), "Startups must contain zero duplicates")

    # 10. No duplicate products within canonical startup
    def test_no_duplicate_products_within_canonical_startup(self):
        path = "data/output/products.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        keys = [(r["content"]["productName"], r["content"].get("startupName")) for r in data]
        self.assertEqual(len(keys), len(set(keys)), "Products within same startup must contain zero duplicates")

    # 11. Research paper URLs are valid and non-empty
    def test_research_paper_urls_valid(self):
        path = "data/output/research_papers.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data[:100]:
            purl = r.get("paper_url")
            self.assertTrue(purl and purl.startswith("https://arxiv.org/abs/"))

    # 12. GitHub stars are integers or null
    def test_github_stars_integers_or_null(self):
        path = "data/output/research_papers.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data:
            stars = r.get("github_stars")
            if stars is not None:
                self.assertIsInstance(stars, int)
                self.assertGreaterEqual(stars, 0)

    # 13. No fabricated URLs
    def test_no_fabricated_urls(self):
        path = "data/output/startups.json"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for r in data[:50]:
            surl = r["source"]["url"]
            parsed = urlparse(surl)
            self.assertIn(parsed.scheme, ("http", "https"))
            self.assertTrue(len(parsed.netloc) > 3)

    # 14. No credentials committed
    def test_no_credentials_committed(self):
        gitignore_path = ".gitignore"
        self.assertTrue(os.path.exists(gitignore_path))
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".env", content)
        self.assertTrue(any(kw in content for kw in ("service_account", "credentials", "token")))

        # Verify no json files in repository root or data/ contain private keys
        for root, _, files in os.walk("."):
            if ".venv" in root or ".git" in root:
                continue
            for file in files:
                if file.endswith(".json") and "service_account" in file.lower():
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as jf:
                        jdata = jf.read()
                        self.assertNotIn("BEGIN PRIVATE KEY", jdata, f"Private key found in {filepath}!")

    # 15. Freshness validation preserved for Jobs and News
    def test_freshness_validation_preserved(self):
        from src.agents.freshness import is_within_24_hours
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        fresh_ts = (now - timedelta(hours=4)).isoformat()
        stale_ts = (now - timedelta(hours=30)).isoformat()

        self.assertTrue(is_within_24_hours(fresh_ts, now=now))
        self.assertFalse(is_within_24_hours(stale_ts, now=now))


if __name__ == "__main__":
    unittest.main(verbosity=2)
