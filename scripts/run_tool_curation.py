"""
AI Tool Final Curation & Quality Selection Runner — Step 6.

Loads enriched AI tool records, performs deterministic deduplication,
calculates 8-criterion quality scores, applies guideline rejection rules,
validates through the final 8-gate grounding validator, and saves:
1. data/output/final_ai_tools.json
2. data/output/tool_curation_report.json

Usage:
    py -3.13 scripts/run_tool_curation.py [--input data/output/enriched_ai_tools.json] [--target 1000]
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
import sys
import time
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tool_deduplicator import ToolDeduplicator
from src.agents.tool_final_validator import ToolFinalValidator
from src.agents.tool_quality_scorer import ToolQualityScorer
from src.models.ai_tool import AITool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_tool_curation")


def safe_console_str(text: Any) -> str:
    """Sanitize strings for Windows console CP1252 output encoding."""
    if text is None:
        return ""
    return str(text).encode("ascii", "replace").decode("ascii")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run final curation, quality scoring, and selection for AI tools."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="data/output/enriched_ai_tools.json",
        help="Path to input enriched AI tools JSON.",
    )
    parser.add_argument(
        "--raw-input",
        type=str,
        default="data/output/raw_ai_tools.json",
        help="Path to raw candidate tools JSON for audit metrics.",
    )
    parser.add_argument(
        "--verified-input",
        type=str,
        default="data/output/verified_ai_tools.json",
        help="Path to verified tools JSON for audit metrics.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/output/final_ai_tools.json",
        help="Path to final curated JSON output.",
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default="data/output/tool_curation_report.json",
        help="Path to final curation audit report JSON.",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=1000,
        help="Maximum target records to curate (Batch 1 limit: 1,000).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=70.0,
        help="Minimum quality score for automatic selection (default: 70.0).",
    )
    parser.add_argument(
        "--reject-score",
        type=float,
        default=60.0,
        help="Threshold below which records are strictly rejected (default: 60.0).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    t0 = time.perf_counter()

    print("\n" + "=" * 70)
    print("STEP 6 - FINAL CURATION, QUALITY SCORING & SELECTION")
    print("=" * 70 + "\n")
    print(f"Target record cap:      {args.target}")
    print(f"Min qualifying score:   {args.min_score}")
    print(f"Hard reject score:      {args.reject_score}")
    print(f"Input file:             {args.input}")
    print(f"Output file:            {args.output}")
    print(f"Report file:            {args.report_output}\n")

    # 1. Load input records
    if not os.path.exists(args.input):
        logger.error("Input file not found: %s", args.input)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        enriched_records = json.load(f)

    raw_count = 0
    if os.path.exists(args.raw_input):
        try:
            with open(args.raw_input, "r", encoding="utf-8") as f:
                raw_count = len(json.load(f))
        except Exception:
            pass

    verified_count = 0
    if os.path.exists(args.verified_input):
        try:
            with open(args.verified_input, "r", encoding="utf-8") as f:
                verified_count = len(json.load(f))
        except Exception:
            pass

    logger.info("Loaded %d enriched candidate records.", len(enriched_records))

    # 2. Deduplicate candidates
    deduplicator = ToolDeduplicator()
    deduped_records = deduplicator.deduplicate(enriched_records)
    duplicates_count = deduplicator.stats["duplicates_merged"]

    # 3. Quality Scoring & Initial Rejection Filtering
    scorer = ToolQualityScorer(
        minimum_qualifying_score=args.min_score,
        reject_threshold=args.reject_score,
    )

    scored_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    rejection_reasons: dict[str, int] = {}
    score_distribution = {
        "Exceptional (90-100)": 0,
        "Excellent (80-89)": 0,
        "Good (70-79)": 0,
        "Average / Skip (60-69)": 0,
        "Reject (<60)": 0,
    }

    for rec in deduped_records:
        score, breakdown, rationale = scorer.score_record(rec)
        rec["quality_score"] = score
        rec["quality_score_breakdown"] = breakdown
        rec["quality_score_rationale"] = rationale

        # Record distribution
        if score >= 90.0:
            score_distribution["Exceptional (90-100)"] += 1
        elif score >= 80.0:
            score_distribution["Excellent (80-89)"] += 1
        elif score >= 70.0:
            score_distribution["Good (70-79)"] += 1
        elif score >= 60.0:
            score_distribution["Average / Skip (60-69)"] += 1
        else:
            score_distribution["Reject (<60)"] += 1

        # Evaluate rejection
        is_rejected, reason = scorer.evaluate_rejection(rec, score)
        if is_rejected:
            rejected_records.append({
                "tool_name": rec.get("tool_name", "Unknown"),
                "score": score,
                "reason": reason,
            })
            reason_key = (reason or "Unknown").split(":")[0]
            rejection_reasons[reason_key] = rejection_reasons.get(reason_key, 0) + 1
        else:
            scored_records.append(rec)

    # 4. Sort internally by quality score descending
    scored_records.sort(key=lambda r: r.get("quality_score", 0.0), reverse=True)

    # 5. Cap at target limit
    candidates_for_validation = scored_records[:args.target]

    # 6. Final Grounding & Cleanliness Validation
    validator = ToolFinalValidator()
    final_qualifying, validation_failures = validator.validate_dataset(candidates_for_validation)

    # 7. Convert to canonical AITool objects for schema conformance
    validated_tools: list[AITool] = []
    for rec in final_qualifying:
        try:
            tool_obj = AITool(**rec)
            validated_tools.append(tool_obj)
        except Exception as exc:
            logger.warning("Record failed AITool validation: %s (%s)", rec.get("tool_name"), exc)
            validation_failures.append({
                "tool_name": rec.get("tool_name", "Unknown"),
                "errors": [f"Schema validation error: {exc}"],
            })

    # 8. Save final curated dataset
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    final_output_dicts = [t.to_dict() for t in validated_tools]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_output_dicts, f, indent=2, ensure_ascii=False)

    elapsed_time = time.perf_counter() - t0

    # 9. Aggregate audit metrics
    missing_official_websites = sum(1 for t in validated_tools if not t.official_website)
    missing_logos = sum(1 for t in validated_tools if not t.logo_url)
    missing_pricing = sum(1 for t in validated_tools if not t.pricing_model and not t.starting_price)
    missing_descriptions = sum(1 for t in validated_tools if not t.short_description or not t.detailed_overview)

    sources_distribution: dict[str, int] = {}
    for t in validated_tools:
        src = t.discovery_source or "Unknown"
        sources_distribution[src] = sources_distribution.get(src, 0) + 1

    curation_report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_time_sec": round(elapsed_time, 2),
        "raw_candidates_discovered": raw_count or len(enriched_records),
        "candidates_after_deduplication": len(deduped_records),
        "candidates_verified": verified_count or len(enriched_records),
        "candidates_enriched": len(enriched_records),
        "candidates_rejected": len(rejected_records),
        "rejection_reasons": rejection_reasons,
        "final_qualifying_count": len(validated_tools),
        "target_cap": args.target,
        "score_distribution": score_distribution,
        "duplicate_count": duplicates_count,
        "missing_official_website_count": missing_official_websites,
        "missing_logo_count": missing_logos,
        "missing_pricing_count": missing_pricing,
        "missing_description_count": missing_descriptions,
        "validation_failures": len(validation_failures),
        "source_distribution": sources_distribution,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.report_output)), exist_ok=True)
    with open(args.report_output, "w", encoding="utf-8") as f:
        json.dump(curation_report, f, indent=2, ensure_ascii=False)

    # 10. Print Summary
    print("\n" + "=" * 70)
    print("CURATION SUMMARY REPORT")
    print("=" * 70)
    print(f"  Raw Candidates Discovered       : {curation_report['raw_candidates_discovered']}")
    print(f"  Candidates After Deduplication  : {curation_report['candidates_after_deduplication']}")
    print(f"  Duplicates Merged               : {duplicates_count}")
    print(f"  Candidates Evaluated            : {len(deduped_records)}")
    print(f"  Candidates Rejected             : {len(rejected_records)}")
    print(f"  Validation Failures             : {len(validation_failures)}")
    print(f"  Final Qualifying Records        : {len(validated_tools)}")
    print(f"  Elapsed Time                    : {elapsed_time:.2f}s")
    print(f"  Final Output JSON               : {args.output}")
    print(f"  Audit Report JSON               : {args.report_output}")
    print("-" * 70)
    print("SCORE DISTRIBUTION:")
    for tier, count in score_distribution.items():
        print(f"  {tier:<24}: {count:>3}")
    print("-" * 70)
    print("REJECTION REASONS BREAKDOWN:")
    for r_reason, count in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  {r_reason:<35}: {count:>3}")
    print("=" * 70 + "\n")

    # Sample Qualifying Records
    if validated_tools:
        print("Qualifying Tools Sample:")
        for idx, t in enumerate(validated_tools[:5], 1):
            name = safe_console_str(t.tool_name)
            site = str(t.official_website or "None")
            score = t.quality_score
            short = safe_console_str(t.short_description or "")[:80]
            print(f"  {idx}. {name:<25} | Score: {score:>4.1f} | Web: {site}")
            print(f"     Description: {short}...")
        print()


if __name__ == "__main__":
    main()
