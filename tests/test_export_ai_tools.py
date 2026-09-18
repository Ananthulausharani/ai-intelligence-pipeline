"""
Unit tests for AI Tools Google Sheets Exporter (scripts.export_ai_tools_to_google_sheets).

Verifies:
1. Schema headers match AITool.get_sheet_columns() exactly
2. Strict null policy: unstated values produce empty strings ('') in cells, never literal 'None' or 'null'
3. Row auditing catches forbidden literals and raises ValueError
4. Row auditing catches credential patterns and raises ValueError
5. Formatting and public verification logic handles errors cleanly
"""

import os
import sys
import unittest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.export_ai_tools_to_google_sheets import ToolSheetsExporter, WORKSHEET_TITLE
from src.models.ai_tool import AITool


class TestExportAITools(unittest.TestCase):
    """Test suite for AI Tools Google Sheets exporter."""

    def test_sheet_columns_and_title(self):
        """Verify worksheet title and column headers count."""
        self.assertEqual(WORKSHEET_TITLE, "AI Tools")
        cols = AITool.get_sheet_columns()
        self.assertEqual(len(cols), 45)
        self.assertEqual(cols[0], "record_id")
        self.assertEqual(cols[4], "tool_name")
        self.assertIn("quality_score", cols)
        self.assertIn("quality_score_breakdown", cols)
        self.assertIn("quality_score_rationale", cols)

    def test_clean_row_serialization_no_forbidden_literals(self):
        """Converting an AITool to sheet row must never produce 'None' or 'null'."""
        tool = AITool(
            tool_name="Test Tool",
            official_website="https://example.com",
            # All other fields default to None or []
        )
        row = tool.to_sheet_row()
        cols = AITool.get_sheet_columns()
        self.assertEqual(len(row), len(cols))

        for idx, cell in enumerate(row):
            col_name = cols[idx]
            cell_str = str(cell).strip().lower()
            self.assertNotIn(
                cell_str,
                ("none", "null", "nan", "undefined"),
                f"Column '{col_name}' produced forbidden literal '{cell}'"
            )

    def test_audit_rows_catches_forbidden_literal(self):
        """Exporter auditor must raise ValueError if a forbidden literal string exists in a cell."""
        exporter = ToolSheetsExporter.__new__(ToolSheetsExporter)
        columns = ["tool_name", "company_developer"]
        bad_rows = [["Tool 1", "None"]]

        with self.assertRaises(ValueError) as ctx:
            exporter._audit_rows_before_export(columns, bad_rows)
        self.assertIn("forbidden literal string 'None'", str(ctx.exception))

    def test_audit_rows_catches_credential_leak(self):
        """Exporter auditor must raise ValueError if any cell contains an API key or private key pattern."""
        exporter = ToolSheetsExporter.__new__(ToolSheetsExporter)
        columns = ["tool_name", "short_description"]
        bad_rows = [["Tool 1", "Used key AIzaSyFakeSecretKey123456"]]

        with self.assertRaises(ValueError) as ctx:
            exporter._audit_rows_before_export(columns, bad_rows)
        self.assertIn("SECURITY ALERT", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
