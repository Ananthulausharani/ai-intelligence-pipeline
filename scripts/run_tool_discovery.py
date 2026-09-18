"""
Manual execution runner for AI Tool discovery extraction (Step 3).

Discovers candidate AI tools from approved public directories (TAAFT, Creati.ai).
Saves raw candidates to data/output/raw_ai_tools.json.

Usage:
    python scripts/run_tool_discovery.py [--limit 30] [--output data/output/raw_ai_tools.json]
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_harvester import ToolHarvester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_tool_discovery")


async def main():
    parser = argparse.ArgumentParser(description="Discover candidate AI tools from approved directories.")
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Maximum number of unique candidate AI tools to discover (default: 30, safe small limit).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output/raw_ai_tools.json",
        help="Path to output JSON file (default: data/output/raw_ai_tools.json).",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("STEP 3 - AI TOOL CANDIDATE DISCOVERY")
    print("=" * 70 + "\n")
    print(f"Target unique candidate limit: {args.limit}")
    print(f"Output destination:            {args.output}\n")

    harvester = ToolHarvester()
    t0 = time.perf_counter()
    candidates = await harvester.discover_and_save(limit=args.limit, output_file=args.output)
    elapsed = time.perf_counter() - t0

    report = harvester.report

    # Print Source Breakdown
    print("\n" + "-" * 70)
    print("DISCOVERY SOURCE BREAKDOWN")
    print("-" * 70)
    for src in report.get("sources", []):
        name = src.get("source_name", "Unknown")
        status = src.get("status", "UNKNOWN")
        discovered = src.get("candidates_discovered", 0)
        pages = src.get("pages_attempted", 0)
        fails = src.get("failed_requests", 0)
        errors = src.get("errors", [])
        err_note = f" (Errors: {errors[0]})" if errors else ""
        print(f"  [{status}] {name:<26}: {discovered:>3} discovered | {pages} pages | {fails} failed{err_note}")

    # Print Summary Table
    print("\n" + "=" * 70)
    print("DISCOVERY SUMMARY")
    print("=" * 70)
    print(f"  Total raw candidates discovered : {report.get('total_discovered', 0)}")
    print(f"  Duplicates removed (merged)    : {report.get('duplicates_removed', 0)}")
    print(f"  HTTP / network failures        : {report.get('total_failures', 0)}")
    print(f"  Final unique candidates saved   : {report.get('final_candidate_count', 0)}")
    print(f"  Elapsed execution time          : {elapsed:.2f}s")
    print(f"  Saved JSON output               : {args.output}")
    print("=" * 70 + "\n")

    # Sample candidates preview
    if candidates:
        print("Sample Candidates Discovered:")
        for idx, c in enumerate(candidates[:5], 1):
            name = (c.get("tool_name") or "N/A").encode("ascii", "replace").decode("ascii")
            dev = (c.get("company_developer") or "Independent / Unstated").encode("ascii", "replace").decode("ascii")
            src_name = c.get("discovery_source", "N/A")
            refs = len(c.get("discovery_references", []))
            print(f"  {idx}. {name} (by {dev}) - Source: {src_name} ({refs} ref(s))")
        print()


if __name__ == "__main__":
    asyncio.run(main())
