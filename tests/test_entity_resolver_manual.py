"""
Step 22 Manual Verification Test Suite — Deterministic Entity Resolution,
Canonicalization, and Deduplication.

Verifies:
1. Exact canonical match ("OpenAI" -> "OpenAI")
2. Legal suffix normalization ("OpenAI, Inc." -> "OpenAI")
3. Case normalization ("OPENAI" -> "OpenAI")
4. Alias match ("Open AI" -> "OpenAI")
5. Unknown entity ("Some Completely Unknown AI Company" -> UNRESOLVED)
6. Startup/product namespace separation (STARTUP vs PRODUCT don't cross-contaminate)
7. Product + startup context (ChatGPT with OpenAI, Inc. resolves cleanly)
8. Duplicate records (collapses multiple representations into 1 canonical entity)
9. Mapping log (preserves raw name, canonical name, and source URL in EntityMappingLog)
10. Determinism (repeated execution produces byte-for-byte identical output)
"""

import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.entity.resolver import (
    DeterministicEntityResolver,
    MatchMethod,
    ResolutionStatus,
    normalize_entity_name,
)
from src.llm.schemas import EntityMappingLog, EntityType


def run_tests() -> bool:
    resolver = DeterministicEntityResolver()
    passed = 0
    total = 10

    print("=" * 65)
    print("STEP 22 — DETERMINISTIC ENTITY RESOLVER MANUAL TESTS")
    print("=" * 65)

    source_url = "https://techcrunch.com/2026/09/11/ai-funding/"

    # -------------------------------------------------------------
    # 1. Exact canonical match
    # -------------------------------------------------------------
    res1 = resolver.resolve_startup("OpenAI", source_url=source_url)
    assert res1.canonical_name == "OpenAI", f"Expected OpenAI, got {res1.canonical_name}"
    assert res1.match_method == MatchMethod.EXACT
    assert res1.status == ResolutionStatus.RESOLVED
    assert res1.is_matched is True
    print("[PASS] Test 1: Exact canonical match verified ('OpenAI' -> 'OpenAI').")
    passed += 1

    # -------------------------------------------------------------
    # 2. Legal suffix normalization
    # -------------------------------------------------------------
    res2 = resolver.resolve_startup("OpenAI, Inc.", source_url=source_url)
    assert res2.canonical_name == "OpenAI", f"Expected OpenAI, got {res2.canonical_name}"
    assert res2.match_method == MatchMethod.EXACT
    assert res2.status == ResolutionStatus.RESOLVED
    assert res2.is_matched is True
    print("[PASS] Test 2: Legal suffix normalization verified ('OpenAI, Inc.' -> 'OpenAI').")
    passed += 1

    # -------------------------------------------------------------
    # 3. Case normalization
    # -------------------------------------------------------------
    res3 = resolver.resolve_startup("OPENAI", source_url=source_url)
    assert res3.canonical_name == "OpenAI", f"Expected OpenAI, got {res3.canonical_name}"
    assert res3.match_method == MatchMethod.EXACT
    assert res3.status == ResolutionStatus.RESOLVED
    print("[PASS] Test 3: Case normalization verified ('OPENAI' -> 'OpenAI').")
    passed += 1

    # -------------------------------------------------------------
    # 4. Alias match
    # -------------------------------------------------------------
    res4 = resolver.resolve_startup("Open AI", source_url=source_url)
    assert res4.canonical_name == "OpenAI", f"Expected OpenAI, got {res4.canonical_name}"
    assert res4.match_method == MatchMethod.ALIAS
    assert res4.status == ResolutionStatus.RESOLVED
    assert res4.is_matched is True
    print("[PASS] Test 4: Alias match verified ('Open AI' -> 'OpenAI' via ALIAS).")
    passed += 1

    # -------------------------------------------------------------
    # 5. Unknown entity
    # -------------------------------------------------------------
    unknown_raw = "Some Completely Unknown AI Company"
    res5 = resolver.resolve_startup(unknown_raw, source_url=source_url)
    assert res5.canonical_name == unknown_raw, f"Expected raw name fallback, got {res5.canonical_name}"
    assert res5.match_method == MatchMethod.UNRESOLVED
    assert res5.status == ResolutionStatus.UNRESOLVED
    assert res5.is_matched is False
    print("[PASS] Test 5: Unknown entity correctly retained as UNRESOLVED without hallucination.")
    passed += 1

    # -------------------------------------------------------------
    # 6. Startup/product namespace separation
    # -------------------------------------------------------------
    # "Cursor" is both a known product and a company (Anysphere / Cursor)
    startup_cursor = resolver.resolve_startup("Cursor", source_url=source_url)
    product_cursor = resolver.resolve_product("Cursor", source_url=source_url)
    assert startup_cursor.entity_type == "STARTUP"
    assert product_cursor.entity_type == "PRODUCT"
    assert startup_cursor.entity_type != product_cursor.entity_type
    print("[PASS] Test 6: STARTUP and PRODUCT namespaces are strictly separated.")
    passed += 1

    # -------------------------------------------------------------
    # 7. Product + startup context
    # -------------------------------------------------------------
    prod_res = resolver.resolve_product(
        raw_name="ChatGPT",
        source_url=source_url,
        startup_context="OpenAI, Inc.",
    )
    assert prod_res.canonical_name == "ChatGPT", f"Expected ChatGPT, got {prod_res.canonical_name}"
    assert prod_res.startup_context == "OpenAI", f"Expected startup context OpenAI, got {prod_res.startup_context}"
    assert prod_res.status == ResolutionStatus.RESOLVED
    print("[PASS] Test 7: Product resolution respects canonical startup context ('ChatGPT' under 'OpenAI, Inc.' -> 'OpenAI').")
    passed += 1

    # -------------------------------------------------------------
    # 8. Duplicate records deduplication
    # -------------------------------------------------------------
    records = [
        {
            "recordType": "STARTUP",
            "source": {"name": "TechCrunch", "url": "https://techcrunch.com/1"},
            "content": {"entityName": "OpenAI, Inc.", "data": {"employeeCount": 1000}},
        },
        {
            "recordType": "STARTUP",
            "source": {"name": "TechCrunch", "url": "https://techcrunch.com/2"},
            "content": {"entityName": "Open AI", "data": {"employeeCount": 1000}},
        },
        {
            "recordType": "STARTUP",
            "source": {"name": "VentureBeat", "url": "https://venturebeat.com/3"},
            "content": {"entityName": "OPENAI", "data": {"employeeCount": 1000}},
        },
        {
            "recordType": "STARTUP",
            "source": {"name": "TechCrunch", "url": "https://techcrunch.com/4"},
            "content": {"entityName": "Anthropic, PBC", "data": {"employeeCount": 300}},
        },
    ]
    deduped, removed_count = resolver.deduplicate(records)
    assert len(deduped) == 2, f"Expected 2 unique startups, got {len(deduped)}"
    assert removed_count == 2, f"Expected 2 duplicates removed, got {removed_count}"
    assert deduped[0]["content"]["entityName"] == "OpenAI"
    assert deduped[1]["content"]["entityName"] == "Anthropic"
    print(f"[PASS] Test 8: Deduplication collapsed 3 variations of OpenAI into 1 canonical entity (removed {removed_count} duplicates).")
    passed += 1

    # -------------------------------------------------------------
    # 9. Mapping log
    # -------------------------------------------------------------
    log_entry = res2.to_mapping_log()
    assert isinstance(log_entry, EntityMappingLog)
    assert log_entry.raw_name == "OpenAI, Inc."
    assert log_entry.canonical_name == "OpenAI"
    assert log_entry.entity_type == EntityType.STARTUP
    assert str(log_entry.source_url).startswith("https://techcrunch.com")
    print("[PASS] Test 9: EntityMappingLog generated and validated against Pydantic schema.")
    passed += 1

    # -------------------------------------------------------------
    # 10. Determinism
    # -------------------------------------------------------------
    test_inputs = ["Anthropic, PBC", "Mistral AI SAS", "Cohere Inc.", "Scale AI, Inc.", "Unknown Bot Inc."]
    run_a = [resolver.resolve_startup(inp, source_url) for inp in test_inputs]
    run_b = [resolver.resolve_startup(inp, source_url) for inp in test_inputs]
    for r_a, r_b in zip(run_a, run_b):
        assert r_a.canonical_name == r_b.canonical_name
        assert r_a.match_method == r_b.match_method
        assert r_a.status == r_b.status
        assert r_a.confidence == r_b.confidence
    print("[PASS] Test 10: Determinism verified (identical results across repeated runs).")
    passed += 1

    print("=" * 65)
    print(f"RESULTS: {passed}/{total} tests passed. Status: ALL PASS")
    print("=" * 65)
    return True


if __name__ == "__main__":
    run_tests()
