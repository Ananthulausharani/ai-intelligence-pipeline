"""
Research Paper Harvest Runner (Step 27A).

Harvests >= 1,100 unique verified AI research papers directly from arXiv public API,
performs deterministic deduplication, enriches with Hugging Face GitHub metadata,
and saves validated records to data/output/research_papers.json and
data/output/research_harvest_report.json.
"""

import asyncio
import logging
import os
import sys
import time

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.agents.agent3_research import ResearchPaperAgent, save_harvest_results

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_research_harvest")


async def main() -> None:
    print("\n" + "=" * 60)
    print("STEP 27A — VERIFIED RESEARCH PAPER HARVESTING")
    print("=" * 60 + "\n")

    agent = ResearchPaperAgent()
    target = 1100
    batch_size = 200

    print(f"Target unique papers : {target}")
    print(f"arXiv batch size     : {batch_size}")
    print("Primary source       : arXiv Public Atom API (export.arxiv.org)")
    print("AI/ML categories     : cs.AI, cs.LG, cs.CL, cs.CV, cs.RO, cs.NE, stat.ML")
    print("Enrichment source    : Hugging Face Papers API (verified repo/stars)")
    print("Zero-fabrication rule: STRICTLY ENFORCED\n")

    papers, report = await agent.harvest_papers_async(
        target=target,
        batch_size=batch_size,
        inter_batch_delay=2.5,
        enrich_github=True,
        max_enrichment_concurrency=10,
    )

    save_harvest_results(papers, report)

    print("\n" + "=" * 60)
    print("RESEARCH HARVEST SUMMARY")
    print("=" * 60)
    print(f"Target                  : {report['target']}")
    print(f"Verified unique papers  : {report['verified_unique_papers']}")
    print(f"Raw records received    : {report['raw_records_received']}")
    print(f"Duplicates removed      : {report['duplicates_removed']}")
    print(f"Rejected records        : {report['rejected_records']}")
    print(f"Papers with GitHub      : {report['papers_with_github']}")
    print(f"Papers without GitHub   : {report['papers_without_github']}")
    print(f"Papers with stars       : {report['papers_with_stars']}")
    print(f"Enrichment success rate : {report['github_enrichment_success_rate'] * 100:.1f}%")
    print(f"Source traceability     : {report['source_traceability_rate'] * 100:.1f}%")
    print(f"Paper URL coverage      : {report['paper_url_coverage'] * 100:.1f}%")
    print(f"Fabricated records      : {report['fabricated_records']}")
    print(f"Batches requested       : {report['batches_requested']}")
    print(f"Execution duration      : {report['execution_duration_seconds']}s")
    print(f"Status                  : {report['status']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
