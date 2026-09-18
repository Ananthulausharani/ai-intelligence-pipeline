"""
Unit tests for AITool schema (src.models.ai_tool).

Verifies:
1. Minimal instantiation with default values and entity_type fixed to 'tool'
2. Comprehensive instantiation across all 42 schema fields
3. Strict requirement of tool_name and rejection of empty/whitespace values
4. URL validation and graceful handling of empty strings as None
5. Date parsing (datetime, date, ISO string) and empty string handling
6. List field handling, None coercion to empty list, and comma-separated string coercion
7. Boolean field normalization and empty string handling
8. Fixed entity_type constraint (rejects non-'tool' values)
9. JSON serialization and round-trip via model_dump and model_dump_json
10. Google Sheets export formatting (to_sheet_row, get_sheet_columns, from_sheet_row)
"""

from datetime import date, datetime, timezone
import json
import os
import sys
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError

from src.models.ai_tool import AITool


class TestAIToolSchema(unittest.TestCase):
    """Test suite for the AITool Pydantic v2 schema."""

    def test_minimal_instantiation(self):
        """Test creating an AITool with only the required tool_name."""
        tool = AITool(tool_name="Cursor")

        # Identity
        self.assertEqual(tool.tool_name, "Cursor")
        self.assertIsNone(tool.company_developer)
        self.assertIsNone(tool.official_website)
        self.assertIsNone(tool.logo_url)
        self.assertIsNone(tool.country)
        self.assertIsNone(tool.version)
        self.assertIsNone(tool.launch_date)
        self.assertIsNone(tool.current_status)

        # Description
        self.assertIsNone(tool.short_description)
        self.assertIsNone(tool.detailed_overview)

        # Product lists default to empty lists
        self.assertEqual(tool.categories, [])
        self.assertEqual(tool.tags, [])
        self.assertEqual(tool.key_features, [])
        self.assertEqual(tool.main_use_cases, [])
        self.assertEqual(tool.ai_capabilities, [])
        self.assertEqual(tool.inputs, [])
        self.assertEqual(tool.outputs, [])
        self.assertEqual(tool.supported_platforms, [])
        self.assertEqual(tool.integrations, [])
        self.assertIsNone(tool.api_availability)
        self.assertIsNone(tool.open_source_status)
        self.assertIsNone(tool.signup_requirement)

        # Pricing
        self.assertIsNone(tool.pricing_model)
        self.assertIsNone(tool.starting_price)
        self.assertIsNone(tool.free_plan)
        self.assertIsNone(tool.free_trial)
        self.assertIsNone(tool.important_usage_limits)

        # Quality / Verification
        self.assertEqual(tool.pros, [])
        self.assertEqual(tool.cons, [])
        self.assertEqual(tool.limitations, [])
        self.assertIsNone(tool.ai_orbit_summary)
        self.assertIsNone(tool.usage_adoption_signals)
        self.assertIsNone(tool.quality_score)
        self.assertIsNone(tool.quality_score_breakdown)
        self.assertIsNone(tool.quality_score_rationale)
        self.assertIsNone(tool.last_verified_date)
        self.assertIsNone(tool.discovery_source)
        self.assertIsNone(tool.discovery_source_url)
        self.assertIsNone(tool.verification_source)
        self.assertIsNone(tool.verification_source_url)

        # Metadata
        self.assertIsNone(tool.record_id)
        self.assertEqual(tool.entity_type, "tool")
        self.assertIsInstance(tool.created_at, datetime)
        self.assertIsInstance(tool.updated_at, datetime)

    def test_full_instantiation(self):
        """Test creating an AITool with all fields populated."""
        launch_dt = datetime(2023, 3, 14, 0, 0, tzinfo=timezone.utc)
        verified_dt = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)
        created_dt = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        updated_dt = datetime(2026, 9, 18, 11, 0, tzinfo=timezone.utc)

        data = {
            "record_id": "tool-cursor-ai",
            "entity_type": "tool",
            "created_at": created_dt,
            "updated_at": updated_dt,
            "tool_name": "Cursor",
            "company_developer": "Anysphere",
            "official_website": "https://www.cursor.com",
            "logo_url": "https://www.cursor.com/assets/images/logo.png",
            "country": "United States",
            "version": "0.41.0",
            "launch_date": launch_dt,
            "current_status": "Active",
            "short_description": "An AI-powered code editor built for pair-programming with LLMs.",
            "detailed_overview": "Cursor is a fork of VS Code with deep AI integration.",
            "primary_task": "AI Code Generation & Editing",
            "categories": ["Developer Tools", "AI Coding Assistants"],
            "tags": ["code", "ai", "ide", "vscode", "llm"],
            "key_features": ["Multi-file editing", "Chat with codebase", "Copilot++"],
            "main_use_cases": ["Full-stack software engineering", "Code refactoring"],
            "ai_capabilities": ["Agentic multi-file edits", "Context-aware code completion"],
            "inputs": ["source code", "text prompts"],
            "outputs": ["code diffs", "explanations", "generated code"],
            "supported_platforms": ["macOS", "Windows", "Linux"],
            "integrations": ["GitHub", "GitLab", "VS Code Extensions"],
            "api_availability": True,
            "open_source_status": "Proprietary (VS Code fork)",
            "signup_requirement": "Account Required",
            "pricing_model": "Freemium",
            "starting_price": "$20/month",
            "free_plan": True,
            "free_trial": True,
            "important_usage_limits": "500 fast premium requests per month",
            "pros": ["Extremely fast completions", "Understands full repo context"],
            "cons": ["Requires paid tier for heavy usage", "Closed source core features"],
            "limitations": ["Limited mobile access", "Requires stable internet connection"],
            "ai_orbit_summary": "Top-tier AI editor leading the market in agentic coding workflows.",
            "usage_adoption_signals": "Over 100k developers and 30k stars in community rankings.",
            "quality_score": 88.5,
            "quality_score_breakdown": {"capability": 23.0, "usefulness": 18.0},
            "quality_score_rationale": "Exceptional capability and strong adoption signals.",
            "last_verified_date": verified_dt,
            "discovery_source": "Product Hunt",
            "discovery_source_url": "https://www.producthunt.com/posts/cursor-ai",
            "verification_source": "Official Documentation",
            "verification_source_url": "https://docs.cursor.com",
        }

        tool = AITool(**data)

        self.assertEqual(tool.tool_name, "Cursor")
        self.assertEqual(tool.company_developer, "Anysphere")
        self.assertEqual(str(tool.official_website), "https://www.cursor.com/")
        self.assertEqual(str(tool.logo_url), "https://www.cursor.com/assets/images/logo.png")
        self.assertEqual(tool.country, "United States")
        self.assertEqual(tool.version, "0.41.0")
        self.assertEqual(tool.launch_date, launch_dt)
        self.assertEqual(tool.current_status, "Active")
        self.assertEqual(tool.primary_task, "AI Code Generation & Editing")
        self.assertEqual(len(tool.categories), 2)
        self.assertEqual(len(tool.tags), 5)
        self.assertEqual(len(tool.key_features), 3)
        self.assertEqual(len(tool.main_use_cases), 2)
        self.assertEqual(len(tool.ai_capabilities), 2)
        self.assertEqual(len(tool.inputs), 2)
        self.assertEqual(len(tool.outputs), 3)
        self.assertEqual(len(tool.supported_platforms), 3)
        self.assertEqual(len(tool.integrations), 3)
        self.assertTrue(tool.api_availability)
        self.assertEqual(tool.open_source_status, "Proprietary (VS Code fork)")
        self.assertEqual(tool.signup_requirement, "Account Required")
        self.assertEqual(tool.pricing_model, "Freemium")
        self.assertEqual(tool.starting_price, "$20/month")
        self.assertTrue(tool.free_plan)
        self.assertTrue(tool.free_trial)
        self.assertEqual(tool.important_usage_limits, "500 fast premium requests per month")
        self.assertEqual(len(tool.pros), 2)
        self.assertEqual(len(tool.cons), 2)
        self.assertEqual(len(tool.limitations), 2)
        self.assertEqual(tool.last_verified_date, verified_dt)
        self.assertEqual(tool.record_id, "tool-cursor-ai")
        self.assertEqual(tool.entity_type, "tool")

    def test_required_tool_name(self):
        """Ensure tool_name cannot be omitted or empty."""
        with self.assertRaises(ValidationError):
            AITool()  # missing required field

        with self.assertRaises(ValidationError):
            AITool(tool_name="")  # empty string

        with self.assertRaises(ValidationError):
            AITool(tool_name="   ")  # whitespace only

        with self.assertRaises(ValidationError):
            AITool(tool_name=None)  # None

    def test_url_validation_and_null_handling(self):
        """Test URL validation using HttpUrl and empty string handling."""
        # Valid URLs
        tool = AITool(
            tool_name="Test Tool",
            official_website="https://ai.example.com/tool",
            logo_url="https://ai.example.com/logo.svg",
            discovery_source_url="https://discovery.example.com/item",
            verification_source_url="https://verify.example.com/page",
        )
        self.assertEqual(str(tool.official_website), "https://ai.example.com/tool")
        self.assertEqual(str(tool.logo_url), "https://ai.example.com/logo.svg")
        self.assertEqual(str(tool.discovery_source_url), "https://discovery.example.com/item")
        self.assertEqual(str(tool.verification_source_url), "https://verify.example.com/page")

        # Invalid URLs raise ValidationError
        with self.assertRaises(ValidationError):
            AITool(tool_name="Test Tool", official_website="not_a_valid_url")

        with self.assertRaises(ValidationError):
            AITool(tool_name="Test Tool", logo_url="ftp://invalid-scheme")

        # Empty and whitespace strings convert to None without error (strict null policy)
        tool_empty_urls = AITool(
            tool_name="Test Tool",
            official_website="",
            logo_url="   ",
            discovery_source_url="",
            verification_source_url=None,
        )
        self.assertIsNone(tool_empty_urls.official_website)
        self.assertIsNone(tool_empty_urls.logo_url)
        self.assertIsNone(tool_empty_urls.discovery_source_url)
        self.assertIsNone(tool_empty_urls.verification_source_url)

    def test_date_parsing_and_null_handling(self):
        """Test date parsing with datetime objects, date objects, ISO strings, and empty strings."""
        # ISO string with Z
        tool1 = AITool(
            tool_name="Tool 1",
            launch_date="2023-03-14T00:00:00Z",
            last_verified_date="2026-09-15T12:30:00Z",
        )
        self.assertIsInstance(tool1.launch_date, datetime)
        self.assertIsInstance(tool1.last_verified_date, datetime)

        # Date-only string
        tool2 = AITool(
            tool_name="Tool 2",
            launch_date="2023-03-14",
        )
        self.assertIsInstance(tool2.launch_date, datetime)
        self.assertEqual(tool2.launch_date.year, 2023)
        self.assertEqual(tool2.launch_date.month, 3)
        self.assertEqual(tool2.launch_date.day, 14)

        # datetime and date instances
        tool3 = AITool(
            tool_name="Tool 3",
            launch_date=date(2022, 11, 30),
            last_verified_date=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
        )
        self.assertIsInstance(tool3.launch_date, datetime)
        self.assertIsInstance(tool3.last_verified_date, datetime)

        # Empty strings resolve to None without raising error
        tool_empty_dates = AITool(
            tool_name="Tool Empty",
            launch_date="",
            last_verified_date="   ",
        )
        self.assertIsNone(tool_empty_dates.launch_date)
        self.assertIsNone(tool_empty_dates.last_verified_date)

    def test_list_field_coercion(self):
        """Verify list fields handle lists, None, and comma-separated strings."""
        # Standard list input
        tool = AITool(
            tool_name="List Tool",
            categories=["Dev", "Productivity"],
            tags=["fast", "smart"],
            key_features=["Feature A", "Feature B"],
            main_use_cases=["Use Case 1"],
            ai_capabilities=["LLM", "Agent"],
            inputs=["text", "audio"],
            outputs=["text", "image"],
            supported_platforms=["macOS", "Linux"],
            integrations=["Slack", "Jira"],
            pros=["Fast", "Intuitive"],
            cons=["Paid only"],
            limitations=["No offline support"],
        )
        self.assertEqual(tool.categories, ["Dev", "Productivity"])
        self.assertEqual(tool.tags, ["fast", "smart"])
        self.assertEqual(tool.pros, ["Fast", "Intuitive"])

        # None input coerces to empty list
        tool_none = AITool(
            tool_name="None List Tool",
            categories=None,
            tags=None,
            key_features=None,
            main_use_cases=None,
            ai_capabilities=None,
            inputs=None,
            outputs=None,
            supported_platforms=None,
            integrations=None,
            pros=None,
            cons=None,
            limitations=None,
        )
        self.assertEqual(tool_none.categories, [])
        self.assertEqual(tool_none.tags, [])
        self.assertEqual(tool_none.pros, [])
        self.assertEqual(tool_none.limitations, [])

        # Comma-separated string coerces to list of stripped strings
        tool_csv = AITool(
            tool_name="CSV List Tool",
            categories="Dev, Productivity, Search",
            tags="ai, ml , nlp ",
            inputs="text, code",
        )
        self.assertEqual(tool_csv.categories, ["Dev", "Productivity", "Search"])
        self.assertEqual(tool_csv.tags, ["ai", "ml", "nlp"])
        self.assertEqual(tool_csv.inputs, ["text", "code"])

    def test_entity_type_fixed_to_tool(self):
        """Verify entity_type is defaulted and fixed to 'tool'."""
        # Default
        tool = AITool(tool_name="Default Entity")
        self.assertEqual(tool.entity_type, "tool")

        # Explicit valid 'tool'
        tool_explicit = AITool(tool_name="Explicit Entity", entity_type="tool")
        self.assertEqual(tool_explicit.entity_type, "tool")

        # Invalid entity_type should fail validation
        with self.assertRaises(ValidationError):
            AITool(tool_name="Invalid Entity", entity_type="product")

        with self.assertRaises(ValidationError):
            AITool(tool_name="Invalid Entity", entity_type="startup")

    def test_boolean_and_union_fields(self):
        """Verify boolean normalization and string/bool union fields."""
        tool = AITool(
            tool_name="Bool Tool",
            free_plan="true",
            free_trial="false",
            api_availability="yes",
            open_source_status=True,
            signup_requirement="Optional",
        )
        self.assertTrue(tool.free_plan)
        self.assertFalse(tool.free_trial)
        self.assertTrue(tool.api_availability)
        self.assertTrue(tool.open_source_status)
        self.assertEqual(tool.signup_requirement, "Optional")

        # Empty strings resolve to None
        tool_empty = AITool(
            tool_name="Empty Bools",
            free_plan="",
            free_trial="",
            api_availability="",
            open_source_status="",
            signup_requirement="",
        )
        self.assertIsNone(tool_empty.free_plan)
        self.assertIsNone(tool_empty.free_trial)
        self.assertIsNone(tool_empty.api_availability)
        self.assertIsNone(tool_empty.open_source_status)
        self.assertIsNone(tool_empty.signup_requirement)

    def test_starting_price_formatting(self):
        """Verify starting_price accepts strings, numbers, and cleans whitespace."""
        tool1 = AITool(tool_name="Price 1", starting_price=19.99)
        self.assertEqual(tool1.starting_price, "$19.99")

        tool2 = AITool(tool_name="Price 2", starting_price=0)
        self.assertEqual(tool2.starting_price, "Free")

        tool3 = AITool(tool_name="Price 3", starting_price="$49/seat/mo")
        self.assertEqual(tool3.starting_price, "$49/seat/mo")

        tool4 = AITool(tool_name="Price 4", starting_price="")
        self.assertIsNone(tool4.starting_price)

    def test_json_serialization(self):
        """Verify model_dump and to_dict produce JSON-compliant serializable structures."""
        tool = AITool(
            tool_name="Claude Code",
            company_developer="Anthropic",
            official_website="https://claude.ai",
            categories=["Developer Tools", "CLI"],
            free_plan=False,
            launch_date="2025-02-24T00:00:00Z",
        )

        d = tool.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["tool_name"], "Claude Code")
        self.assertEqual(d["company_developer"], "Anthropic")
        self.assertEqual(d["official_website"], "https://claude.ai/")
        self.assertEqual(d["entity_type"], "tool")
        self.assertIsInstance(d["created_at"], str)  # serialized as ISO string

        # Ensure json.dumps works on the dictionary
        json_str = json.dumps(d)
        self.assertIn('"tool_name": "Claude Code"', json_str)

        # Test model_dump_json directly
        raw_json = tool.model_dump_json()
        parsed = json.loads(raw_json)
        self.assertEqual(parsed["tool_name"], "Claude Code")

    def test_google_sheets_serialization(self):
        """Verify Google Sheets export columns, row serialization, and reconstruction."""
        columns = AITool.get_sheet_columns()
        self.assertEqual(len(columns), 45)
        self.assertEqual(columns[0], "record_id")
        self.assertEqual(columns[1], "entity_type")
        self.assertEqual(columns[4], "tool_name")

        tool = AITool(
            record_id="tool-copilot",
            tool_name="GitHub Copilot",
            company_developer="GitHub",
            official_website="https://github.com/features/copilot",
            categories=["Developer Tools", "AI Assistant"],
            tags=["coding", "autocomplete"],
            free_plan=False,
            free_trial=True,
            starting_price="$10/month",
            pros=["Massive language support", "Seamless VS Code integration"],
            cons=["Telemetric lag", "Repetitive suggestions"],
            quality_score=85.0,
            quality_score_breakdown={"capability": 22.0, "usefulness": 18.0},
            quality_score_rationale="Solid adoption and high capability.",
        )

        row = tool.to_sheet_row()
        self.assertEqual(len(row), 45)

        # Check column-by-column mapping
        row_dict = dict(zip(columns, row))
        self.assertEqual(row_dict["record_id"], "tool-copilot")
        self.assertEqual(row_dict["entity_type"], "tool")
        self.assertEqual(row_dict["tool_name"], "GitHub Copilot")
        self.assertEqual(row_dict["company_developer"], "GitHub")
        self.assertEqual(row_dict["official_website"], "https://github.com/features/copilot")
        self.assertEqual(row_dict["categories"], "Developer Tools, AI Assistant")
        self.assertEqual(row_dict["tags"], "coding, autocomplete")
        self.assertEqual(row_dict["free_plan"], "False")
        self.assertEqual(row_dict["free_trial"], "True")
        self.assertEqual(row_dict["starting_price"], "$10/month")
        self.assertEqual(row_dict["pros"], "Massive language support, Seamless VS Code integration")
        self.assertEqual(row_dict["cons"], "Telemetric lag, Repetitive suggestions")
        self.assertEqual(row_dict["quality_score"], "85.0")
        self.assertIn('"capability": 22.0', row_dict["quality_score_breakdown"])
        self.assertEqual(row_dict["quality_score_rationale"], "Solid adoption and high capability.")

        # Strict null policy: unstated values must be empty string
        self.assertEqual(row_dict["country"], "")
        self.assertEqual(row_dict["version"], "")
        self.assertEqual(row_dict["ai_orbit_summary"], "")
        self.assertEqual(row_dict["verification_source_url"], "")

        # Reconstruct tool from row dict
        reconstructed = AITool.from_sheet_row(row_dict)
        self.assertEqual(reconstructed.tool_name, "GitHub Copilot")
        self.assertEqual(reconstructed.company_developer, "GitHub")
        self.assertEqual(reconstructed.categories, ["Developer Tools", "AI Assistant"])
        self.assertFalse(reconstructed.free_plan)
        self.assertTrue(reconstructed.free_trial)
        self.assertEqual(reconstructed.quality_score, 85.0)
        self.assertEqual(reconstructed.quality_score_breakdown, {"capability": 22.0, "usefulness": 18.0})
        self.assertEqual(reconstructed.quality_score_rationale, "Solid adoption and high capability.")
        self.assertIsNone(reconstructed.country)

        # Reconstruct tool from row list
        reconstructed_from_list = AITool.from_sheet_row(row)
        self.assertEqual(reconstructed_from_list.tool_name, "GitHub Copilot")
        self.assertEqual(reconstructed_from_list.starting_price, "$10/month")
        self.assertEqual(reconstructed_from_list.quality_score, 85.0)

    def test_quality_score_field_parsing(self):
        """Verify quality_score, breakdown, and rationale normalization and null safety."""
        # Clean numeric and JSON string inputs
        tool = AITool(
            tool_name="Score Test",
            quality_score="78.5",
            quality_score_breakdown='{"capability": 20, "activity": 15}',
            quality_score_rationale="   Good performance across all criteria.  ",
        )
        self.assertEqual(tool.quality_score, 78.5)
        self.assertEqual(tool.quality_score_breakdown, {"capability": 20, "activity": 15})
        self.assertEqual(tool.quality_score_rationale, "Good performance across all criteria.")

        # Empty strings resolve cleanly to None
        tool_empty = AITool(
            tool_name="Score Empty",
            quality_score="",
            quality_score_breakdown="",
            quality_score_rationale="   ",
        )
        self.assertIsNone(tool_empty.quality_score)
        self.assertIsNone(tool_empty.quality_score_breakdown)
        self.assertIsNone(tool_empty.quality_score_rationale)


if __name__ == "__main__":
    unittest.main()
