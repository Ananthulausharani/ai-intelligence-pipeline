"""
Manual execution runner for AI Tool website verification and factual enrichment (Step 4).

Loads raw candidates from data/output/raw_ai_tools.json, resolves official websites,
verifies authenticity, extracts factual metadata and logos, and outputs verified records
to data/output/verified_ai_tools.json.

Usage:
    python scripts/run_tool_verification.py [--limit 10] [--input data/output/raw_ai_tools.json] [--output data/output/verified_ai_tools.json]
"""

import argparse
import json
import logging
import os
import sys
import time

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_verifier import ToolVerifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_tool_verification")


def main():
    parser = argparse.ArgumentParser(description="Verify candidate AI tools and enrich from official websites.")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of candidates to verify (default: 10, safe small test).",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/output/raw_ai_tools.json",
        help="Path to raw candidates JSON file (default: data/output/raw_ai_tools.json).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output/verified_ai_tools.json",
        help="Path to output verified JSON file (default: data/output/verified_ai_tools.json).",
    )
    parser.add_argument(
        "--filter",
        choices=["all", "with-external-url", "directory-only"],
        default="all",
        help="Filter candidate subset: 'all' (default), 'with-external-url', or 'directory-only'.",
    )
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("STEP 4 - OFFICIAL WEBSITE VERIFICATION & FACTUAL ENRICHMENT")
    print("=" * 70 + "\n")
    print(f"Candidate verification limit: {args.limit}")
    print(f"Candidate filter mode:        {args.filter}")
    print(f"Input file:                   {args.input}")
    print(f"Output destination:           {args.output}\n")

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        raw_candidates = json.load(f)

    if args.filter == "with-external-url":
        filtered_candidates = [c for c in raw_candidates if c.get("raw_metadata", {}).get("external_product_url")]
    elif args.filter == "directory-only":
        filtered_candidates = [c for c in raw_candidates if not c.get("raw_metadata", {}).get("external_product_url")]
    else:
        filtered_candidates = raw_candidates

    verifier = ToolVerifier(timeout_sec=12.0, request_delay_sec=0.5)
    t0 = time.perf_counter()
    verified_records = verifier.verify_candidates(filtered_candidates, limit=args.limit)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(verified_records, f, indent=2, ensure_ascii=False)

    elapsed = time.perf_counter() - t0

    stats = verifier.stats

    # Print Summary Table
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"  Candidates loaded             : {stats['candidates_loaded']}")
    print(f"  Candidates attempted          : {stats['candidates_attempted']}")
    print(f"  Verified                      : {stats['verified']}")
    print(f"  Partially verified            : {stats['partially_verified']}")
    print(f"  Unverified                    : {stats['unverified']}")
    print(f"  Failed                        : {stats['failed']}")
    print(f"  Official websites resolved    : {stats['official_websites_resolved']}")
    print(f"  Logos resolved                : {stats['logos_resolved']}")
    print(f"  HTTP / network failures       : {stats['network_failures']}")
    print(f"  Elapsed execution time        : {elapsed:.2f}s")
    print(f"  Output saved to               : {args.output}")
    print("=" * 70 + "\n")

    # Sample preview
    if verified_records:
        print("Verified Records Sample:")
        for idx, rec in enumerate(verified_records[:5], 1):
            name = (rec.get("tool_name") or "N/A").encode("ascii", "replace").decode("ascii")
            status = rec.get("verification_status", "unknown")
            web = rec.get("official_website") or "None"
            logo = "Yes" if rec.get("logo_url") else "No"
            pricing = rec.get("pricing_model") or "None"
            inputs = ", ".join(rec.get("inputs") or []) or "None"
            outputs = ", ".join(rec.get("outputs") or []) or "None"
            print(f"  {idx}. [{status.upper()}] {name}")
            print(f"     Website: {web}")
            print(f"     Logo: {logo} | Pricing: {pricing}")
            print(f"     Inputs: {inputs} | Outputs: {outputs}")
        print()


if __name__ == "__main__":
    main()
