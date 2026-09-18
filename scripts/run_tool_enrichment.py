"""
CLI runner for AI Tool Description Enrichment (Step 5).

Usage:
    py -3.13 scripts/run_tool_enrichment.py --limit 10
    py -3.13 scripts/run_tool_enrichment.py --filter verified-only --limit 10
"""

import argparse
import json
import logging
import os
import sys
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_enricher import ToolEnricher
from src.llm.orchestrator import LLMOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_tool_enrichment")


def safe_console_str(text: str) -> str:
    """Sanitize strings for Windows console CP1252 output encoding."""
    if not text:
        return ""
    return str(text).encode("ascii", "replace").decode("ascii")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run LLM description enrichment for verified AI tools."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/output/verified_ai_tools.json",
        help="Input JSON file containing verified AI tools.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output/enriched_ai_tools.json",
        help="Output JSON file for enriched AI tools.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of candidate records to enrich.",
    )
    parser.add_argument(
        "--filter",
        type=str,
        choices=["all", "verified-only"],
        default="all",
        help="Filter candidates: 'all' or 'verified-only'.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Polite delay in seconds between LLM requests.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logger.info("Starting Step 5: AI Tool LLM Description Enrichment")

    if not os.path.exists(args.input):
        logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        records = json.load(f)

    if args.filter == "verified-only":
        records = [r for r in records if r.get("verification_status") in ("verified", "partially_verified")]

    enricher = ToolEnricher(
        orchestrator=LLMOrchestrator(),
        request_delay_sec=args.delay,
    )

    enriched_records = enricher.enrich_records(records, limit=args.limit)

    # Save output
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(enriched_records, f, indent=2, ensure_ascii=False)

    stats = enricher.stats
    provider_str = ", ".join(sorted(stats["providers_used"])) if stats["providers_used"] else "None"
    model_str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    print("\n" + "=" * 70)
    print("STEP 5 - LLM DESCRIPTION ENRICHMENT SUMMARY")
    print("=" * 70)
    print(f"  Records loaded                  : {stats['records_loaded']}")
    print(f"  Records attempted               : {stats['records_attempted']}")
    print(f"  Descriptions generated          : {stats['descriptions_successfully_generated']}")
    print(f"  Failures                        : {stats['failures']}")
    print(f"  Skipped unverified              : {stats['skipped_unverified']}")
    print(f"  Records with missing description: {stats['records_with_missing_descriptions']}")
    print(f"  Provider / Model used           : {provider_str} ({model_str})")
    print(f"  Elapsed execution time          : {stats['elapsed_time_sec']}s")
    print(f"  Output saved to                 : {args.output}")
    print("=" * 70)

    # Print sample descriptions
    print("\nSample Generated Descriptions:")
    for idx, rec in enumerate(enriched_records[:5], 1):
        name = safe_console_str(rec.get("tool_name", "Unknown"))
        status = rec.get("enrichment_status")
        short = safe_console_str(rec.get("short_description", "None"))
        detailed = safe_console_str(rec.get("detailed_overview", "None"))
        print(f"\n  {idx}. [{status.upper()}] {name}")
        print(f"     Short   : {short}")
        print(f"     Overview: {detailed}")

    print("\n")


if __name__ == "__main__":
    main()
