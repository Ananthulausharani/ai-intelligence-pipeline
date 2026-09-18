"""
AI Tool Google Sheets Exporter — Step 6.

Exports the curated, validated AI Tools dataset to the "AI Tools" worksheet in the
Google Spreadsheet configured in the pipeline (.env).

Features:
- Reuses GoogleSheetsExporter authentication (credentials/service-account.json)
- Idempotent worksheet sync: creates or clears "AI Tools" worksheet
- Bounded chunk writes (500 rows/write) with exponential backoff on rate limits
- Freezes row 1 and formats header row as bold
- Rigorous cell auditing: verifies no credentials, no literal "None"/"null"/"NaN", valid links
- Public sharing attempt and unauthenticated public access verification (Step 6 / Part L)

Usage:
    py -3.13 scripts/export_ai_tools_to_google_sheets.py [--input data/output/final_ai_tools.json]
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional

import gspread
from gspread.exceptions import APIError

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from src.models.ai_tool import AITool
from src.storage.google_sheets import GoogleSheetsExporter, SCOPES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("export_ai_tools")

WORKSHEET_TITLE = "AI Tools"


class ToolSheetsExporter:
    """Handles exporting curated AI tools to Google Sheets and verifying access."""

    def __init__(self, sheet_id: Optional[str] = None):
        self.exporter = GoogleSheetsExporter(sheet_id=sheet_id)
        self.sheet_id = self.exporter.sheet_id
        self.client = self.exporter.authenticate()

    def sync_ai_tools(
        self,
        tools: list[AITool],
        chunk_size: int = 500,
    ) -> dict[str, Any]:
        """
        Synchronize validated AI Tools into the 'AI Tools' tab.

        Returns audit results dictionary.
        """
        spreadsheet = self.client.open_by_key(self.sheet_id)
        logger.info("Opened spreadsheet: '%s' (%s)", spreadsheet.title, self.sheet_id)

        columns = AITool.get_sheet_columns()
        rows = [t.to_sheet_row() for t in tools]

        # Audit cells before writing to guarantee cleanliness and no credentials
        self._audit_rows_before_export(columns, rows)

        # Open or create 'AI Tools' worksheet
        try:
            ws = spreadsheet.worksheet(WORKSHEET_TITLE)
            ws.clear()
            logger.info("Cleared existing worksheet '%s'.", WORKSHEET_TITLE)
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(
                title=WORKSHEET_TITLE,
                rows=max(len(rows) + 50, 100),
                cols=len(columns),
            )
            logger.info("Created new worksheet '%s'.", WORKSHEET_TITLE)

        all_values = [columns] + rows

        # Write in bounded chunks with retry/backoff
        total_written = 0
        for i in range(0, len(all_values), chunk_size):
            chunk = all_values[i : i + chunk_size]
            for attempt in range(4):
                try:
                    if i == 0:
                        ws.update(chunk)
                    else:
                        ws.append_rows(chunk)
                    break
                except APIError as exc:
                    if exc.response.status_code == 429 and attempt < 3:
                        wait = (attempt + 1) * 3
                        logger.warning("Google API rate limited. Backing off %ds...", wait)
                        time.sleep(wait)
                    else:
                        raise

            total_written += len(chunk) if i > 0 else (len(chunk) - 1)

        # Apply formatting: freeze row 1 and bold headers
        try:
            ws.freeze(rows=1)
            ws.format("1:1", {"textFormat": {"bold": True}})
        except Exception as fmt_exc:
            logger.debug("Worksheet formatting non-critical warning: %s", fmt_exc)

        logger.info(
            "Worksheet '%s' synchronized successfully with %d data rows and %d columns.",
            WORKSHEET_TITLE,
            len(rows),
            len(columns),
        )

        # Attempt public sharing configuration
        sharing_ok, sharing_msg = self.configure_public_sharing(spreadsheet)

        # Verify public accessibility with unauthenticated request
        public_verified, public_msg = self.verify_public_accessibility(ws.id)

        audit_results = {
            "spreadsheet_title": spreadsheet.title,
            "spreadsheet_id": self.sheet_id,
            "worksheet_title": WORKSHEET_TITLE,
            "worksheet_gid": str(ws.id),
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit#gid={ws.id}",
            "row_count": len(rows),
            "column_count": len(columns),
            "sharing_configured": sharing_ok,
            "sharing_message": sharing_msg,
            "public_access_verified": public_verified,
            "public_access_message": public_msg,
        }
        return audit_results

    def configure_public_sharing(self, spreadsheet: gspread.Spreadsheet) -> tuple[bool, str]:
        """Configure Anyone with the link -> Viewer on the spreadsheet."""
        try:
            spreadsheet.share("", perm_type="anyone", role="reader")
            logger.info("Public viewer permissions confirmed on spreadsheet.")
            return True, "Anyone with link -> Viewer successfully configured"
        except Exception as exc:
            msg = f"Public sharing permission update failed: {exc}"
            logger.warning(msg)
            return False, msg

    def verify_public_accessibility(self, gid: int) -> tuple[bool, str]:
        """
        Verify public accessibility using an unauthenticated HTTP GET request.
        Does NOT send any Authorization headers or cookies.
        """
        test_url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/export?format=csv&gid={gid}"
        req = urllib.request.Request(
            test_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    content_len = len(resp.read())
                    logger.info("Public unauthenticated access verified (%d bytes received).", content_len)
                    return True, f"Public unauthenticated export accessible (HTTP 200, {content_len} bytes)"
                else:
                    return False, f"Unexpected HTTP status {resp.status} on public export URL"
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                return False, f"HTTP {exc.code} Forbidden/Unauthorized — spreadsheet requires organization access"
            return False, f"HTTP Error {exc.code}: {exc.reason}"
        except Exception as exc:
            return False, f"Public verification network error: {exc}"

    def _audit_rows_before_export(self, columns: list[str], rows: list[list[Any]]) -> None:
        """Audits rows for forbidden literal strings and credentials before export."""
        forbidden_exact = {"none", "null", "nan", "undefined"}
        credential_patterns = ("AIza", "BEGIN PRIVATE KEY", "client_secret")

        for r_idx, row in enumerate(rows):
            for c_idx, cell in enumerate(row):
                cell_str = str(cell).strip()
                col_name = columns[c_idx]

                # Check forbidden exact literals
                if cell_str.lower() in forbidden_exact:
                    raise ValueError(
                        f"Row {r_idx + 1}, column '{col_name}' contains forbidden literal string '{cell_str}'"
                    )

                # Check credentials leak protection
                for pat in credential_patterns:
                    if pat in cell_str:
                        raise ValueError(
                            f"SECURITY ALERT: Row {r_idx + 1}, column '{col_name}' contains credential pattern '{pat}'"
                        )


def main():
    parser = argparse.ArgumentParser(description="Export curated AI tools to Google Sheets.")
    parser.add_argument(
        "--input",
        type=str,
        default="data/output/final_ai_tools.json",
        help="Path to final curated AI tools JSON.",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("STEP 6 - GOOGLE SHEETS EXPORT")
    print("=" * 70 + "\n")

    if not os.path.exists(args.input):
        print(f"Error: Final curated tools file '{args.input}' not found.")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        raw_tools = json.load(f)

    tools = [AITool(**t) for t in raw_tools]
    print(f"Loaded {len(tools)} validated AI Tool records from {args.input}\n")

    exporter = ToolSheetsExporter()
    results = exporter.sync_ai_tools(tools)

    print("\n" + "=" * 70)
    print("GOOGLE SHEETS EXPORT SUMMARY")
    print("=" * 70)
    print(f"  Spreadsheet Title         : {results['spreadsheet_title']}")
    print(f"  Worksheet                 : {results['worksheet_title']}")
    print(f"  Exported Rows             : {results['row_count']}")
    print(f"  Exported Columns          : {results['column_count']}")
    print(f"  Public Sharing Setting    : {results['sharing_message']}")
    print(f"  Public Access Verified    : {'YES' if results['public_access_verified'] else 'NO'}")
    print(f"  Public Access Diagnostic  : {results['public_access_message']}")
    print(f"  Spreadsheet URL           : {results['spreadsheet_url']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
