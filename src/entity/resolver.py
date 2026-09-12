"""
Phase IV: Deterministic Entity Resolution, Canonicalization, and Deduplication.

Enforces deterministic entity resolution without LLMs or embedding similarity:
RAW ENTITY
    ↓
NORMALIZATION
    ↓
DETERMINISTIC MATCHING (Canonical exact → Alias exact)
    ↓
CANONICAL ENTITY
    ↓
ENTITY MAPPING LOG
    ↓
DEDUPLICATION
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Optional
import unicodedata

from pydantic import HttpUrl

from src.entity.seed_data import SEED_STARTUPS
from src.llm.schemas import EntityMappingLog, EntityType


# ---------------------------------------------------------------------------
# Entity Normalization
# ---------------------------------------------------------------------------

COMMON_LEGAL_SUFFIXES = [
    "incorporated", "corporation", "limited", "gmbh", "p.b.c.", "pbc",
    "b.v.", "bv", "s.a.s.", "sas", "l.l.c.", "llc", "corp.", "corp",
    "ltd.", "ltd", "inc.", "inc", "co.", "co"
]


def normalize_entity_name(name: str) -> str:
    """
    Deterministically normalize an entity name for comparison.

    Rules:
    - Unicode normalization (NFKD)
    - Lowercase conversion
    - Normalize common separators (-, _, /) to spaces
    - Remove punctuation
    - Safely remove trailing legal suffixes (Inc, LLC, Ltd, etc.)
    - Collapse repeated whitespace and strip ends
    - Never remove meaningful words or fabricate information
    """
    if not name or not isinstance(name, str):
        return ""

    # 1. Unicode normalization
    text = unicodedata.normalize("NFKD", name)

    # 2. Lowercase and trim
    text = text.lower().strip()

    # 3. Replace common separators with spaces
    text = re.sub(r"[\-_/]+", " ", text)

    # 4. Filter unwanted symbols while keeping alphanumeric, spaces, and punctuation for suffix check
    text = re.sub(r"[^\w\s.,]", "", text)

    # 5. Remove trailing legal suffixes
    words = text.replace(",", " ").split()
    if len(words) > 1 and words[-1].rstrip(".") in [s.rstrip(".") for s in COMMON_LEGAL_SUFFIXES]:
        words = words[:-1]

    # 6. Reassemble and strip punctuation
    cleaned = " ".join(words).strip()
    cleaned = re.sub(r"[.,;:]+", "", cleaned).strip()

    # 7. Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned


# ---------------------------------------------------------------------------
# Match Methods & Result Container
# ---------------------------------------------------------------------------

class MatchMethod(str, Enum):
    EXACT = "EXACT"
    ALIAS = "ALIAS"
    UNRESOLVED = "UNRESOLVED"


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


@dataclass
class ResolutionResult:
    raw_name: str
    canonical_name: str
    entity_type: str
    source_url: str
    match_method: MatchMethod
    status: ResolutionStatus
    confidence: float
    is_matched: bool
    startup_context: Optional[str] = None

    def to_mapping_log(self) -> EntityMappingLog:
        """Export as canonical Pydantic EntityMappingLog."""
        # Validate entity type against schema Enum
        etype = EntityType.STARTUP if self.entity_type.upper() == "STARTUP" else EntityType.PRODUCT
        valid_url = self.source_url if self.source_url.startswith("http") else "https://unknown.source"
        return EntityMappingLog(
            raw_name=self.raw_name,
            canonical_name=self.canonical_name,
            entity_type=etype,
            source_url=HttpUrl(valid_url),
        )


# ---------------------------------------------------------------------------
# Deterministic Entity Resolver Class
# ---------------------------------------------------------------------------

class DeterministicEntityResolver:
    """
    Deterministic, explainable entity resolver.
    Operates strictly on exact canonical names and explicit aliases.
    Separates STARTUP and PRODUCT namespaces.
    """

    def __init__(self, seed_startups: Optional[list[dict[str, Any]]] = None) -> None:
        self.seed_startups = seed_startups if seed_startups is not None else SEED_STARTUPS

        # Lookup structures
        self._startup_canonical_map: dict[str, str] = {}
        self._startup_alias_map: dict[str, str] = {}
        self._product_catalog: dict[tuple[str, str], str] = {}  # (norm_startup, norm_prod) -> canonical_prod
        self._product_to_startups: dict[str, list[tuple[str, str]]] = {}  # norm_prod -> [(canon_startup, canon_prod)]

        # Mapping history
        self.mapping_logs: list[ResolutionResult] = []

        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build deterministic in-memory lookup indexes from seed data."""
        for entry in self.seed_startups:
            canon = entry["canonical_name"]
            norm_canon = normalize_entity_name(canon)
            self._startup_canonical_map[norm_canon] = canon

            # Map aliases
            for alias in entry.get("aliases", []):
                norm_alias = normalize_entity_name(alias)
                if norm_alias and norm_alias != norm_canon:
                    self._startup_alias_map[norm_alias] = canon

            # Map products
            for prod in entry.get("products", []):
                norm_prod = normalize_entity_name(prod)
                if norm_prod:
                    self._product_catalog[(norm_canon, norm_prod)] = prod
                    if norm_prod not in self._product_to_startups:
                        self._product_to_startups[norm_prod] = []
                    self._product_to_startups[norm_prod].append((canon, prod))

    @property
    def seed_count(self) -> int:
        """Return the number of seed startup entities loaded."""
        return len(self.seed_startups)

    def resolve_startup(self, raw_name: str, source_url: str = "") -> ResolutionResult:
        """
        Resolve a startup or company entity name.
        Priority:
        1. Exact normalized canonical match
        2. Exact normalized alias match
        3. Unresolved (retains raw name as canonical fallback)
        """
        raw_clean = (raw_name or "").strip()
        norm = normalize_entity_name(raw_clean)

        if not norm:
            res = ResolutionResult(
                raw_name=raw_clean,
                canonical_name="",
                entity_type="STARTUP",
                source_url=source_url,
                match_method=MatchMethod.UNRESOLVED,
                status=ResolutionStatus.UNRESOLVED,
                confidence=0.0,
                is_matched=False,
            )
            self.mapping_logs.append(res)
            return res

        # 1. Exact normalized canonical match
        if norm in self._startup_canonical_map:
            canon = self._startup_canonical_map[norm]
            res = ResolutionResult(
                raw_name=raw_clean,
                canonical_name=canon,
                entity_type="STARTUP",
                source_url=source_url,
                match_method=MatchMethod.EXACT,
                status=ResolutionStatus.RESOLVED,
                confidence=1.0,
                is_matched=True,
            )
            self.mapping_logs.append(res)
            return res

        # 2. Exact normalized alias match
        if norm in self._startup_alias_map:
            canon = self._startup_alias_map[norm]
            res = ResolutionResult(
                raw_name=raw_clean,
                canonical_name=canon,
                entity_type="STARTUP",
                source_url=source_url,
                match_method=MatchMethod.ALIAS,
                status=ResolutionStatus.RESOLVED,
                confidence=1.0,
                is_matched=True,
            )
            self.mapping_logs.append(res)
            return res

        # 3. Unresolved
        res = ResolutionResult(
            raw_name=raw_clean,
            canonical_name=raw_clean,  # preserve original name
            entity_type="STARTUP",
            source_url=source_url,
            match_method=MatchMethod.UNRESOLVED,
            status=ResolutionStatus.UNRESOLVED,
            confidence=0.0,
            is_matched=False,
        )
        self.mapping_logs.append(res)
        return res

    def resolve_product(
        self,
        raw_name: str,
        source_url: str = "",
        startup_context: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Resolve a product entity name, respecting startup context where available.
        Ensures PRODUCT and STARTUP namespaces remain separate.
        """
        raw_clean = (raw_name or "").strip()
        norm_prod = normalize_entity_name(raw_clean)

        resolved_startup = None
        if startup_context:
            startup_res = self.resolve_startup(startup_context, source_url=source_url)
            resolved_startup = startup_res.canonical_name if startup_res.is_matched else startup_context

        if not norm_prod:
            res = ResolutionResult(
                raw_name=raw_clean,
                canonical_name="",
                entity_type="PRODUCT",
                source_url=source_url,
                match_method=MatchMethod.UNRESOLVED,
                status=ResolutionStatus.UNRESOLVED,
                confidence=0.0,
                is_matched=False,
                startup_context=resolved_startup,
            )
            self.mapping_logs.append(res)
            return res

        # If startup context is known, check catalog for that specific startup
        if resolved_startup:
            norm_startup = normalize_entity_name(resolved_startup)
            key = (norm_startup, norm_prod)
            if key in self._product_catalog:
                canon_prod = self._product_catalog[key]
                res = ResolutionResult(
                    raw_name=raw_clean,
                    canonical_name=canon_prod,
                    entity_type="PRODUCT",
                    source_url=source_url,
                    match_method=MatchMethod.EXACT,
                    status=ResolutionStatus.RESOLVED,
                    confidence=1.0,
                    is_matched=True,
                    startup_context=resolved_startup,
                )
                self.mapping_logs.append(res)
                return res

        # If startup context is not supplied, check if product is uniquely known in seed catalog
        if not resolved_startup and norm_prod in self._product_to_startups:
            candidates = self._product_to_startups[norm_prod]
            if len(candidates) == 1:
                canon_startup, canon_prod = candidates[0]
                res = ResolutionResult(
                    raw_name=raw_clean,
                    canonical_name=canon_prod,
                    entity_type="PRODUCT",
                    source_url=source_url,
                    match_method=MatchMethod.EXACT,
                    status=ResolutionStatus.RESOLVED,
                    confidence=1.0,
                    is_matched=True,
                    startup_context=canon_startup,
                )
                self.mapping_logs.append(res)
                return res

        # Unresolved product (preserve raw name, do not invent identity)
        res = ResolutionResult(
            raw_name=raw_clean,
            canonical_name=raw_clean,
            entity_type="PRODUCT",
            source_url=source_url,
            match_method=MatchMethod.UNRESOLVED,
            status=ResolutionStatus.UNRESOLVED,
            confidence=0.0,
            is_matched=False,
            startup_context=resolved_startup,
        )
        self.mapping_logs.append(res)
        return res

    def resolve(
        self,
        raw_name: str,
        entity_type: str,
        source_url: str,
        startup_context: Optional[str] = None,
    ) -> ResolutionResult:
        """
        Unified dispatch interface for deterministic entity resolution.
        """
        etype = entity_type.upper().strip()
        if etype == "STARTUP":
            return self.resolve_startup(raw_name, source_url=source_url)
        elif etype == "PRODUCT":
            return self.resolve_product(raw_name, source_url=source_url, startup_context=startup_context)
        else:
            # Fallback for unsupported or generic entity types
            res = ResolutionResult(
                raw_name=raw_name,
                canonical_name=raw_name,
                entity_type=etype,
                source_url=source_url,
                match_method=MatchMethod.UNRESOLVED,
                status=ResolutionStatus.UNRESOLVED,
                confidence=0.0,
                is_matched=False,
                startup_context=startup_context,
            )
            self.mapping_logs.append(res)
            return res

    def deduplicate(self, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        """
        Deterministically deduplicate records while preserving source traceability.

        Rules:
        - STARTUP: dedup key based on (entity_type, normalized canonical entity name)
        - PRODUCT: dedup key based on (entity_type, normalized product name, normalized canonical startup name)
        - NEWS / JOB: dedup key tied to record_type and item_url (preserves article/job identity)
        """
        seen_keys: set[tuple] = set()
        deduped: list[dict[str, Any]] = []
        duplicates_removed = 0

        for rec in records:
            rtype = str(rec.get("recordType", "")).upper()
            content = rec.get("content", {})
            source = rec.get("source", {})
            item_url = content.get("url") or source.get("url") or ""

            if rtype == "STARTUP":
                raw_name = content.get("entityName") or ""
                res = self.resolve_startup(raw_name, source_url=item_url)
                # Update canonical entity name while preserving raw name
                content["rawEntityName"] = raw_name
                content["entityName"] = res.canonical_name
                dedup_key = ("STARTUP", normalize_entity_name(res.canonical_name))

            elif rtype == "PRODUCT":
                raw_prod = content.get("productName") or content.get("title") or ""
                raw_startup = content.get("startupName") or ""
                res = self.resolve_product(raw_prod, source_url=item_url, startup_context=raw_startup)
                content["rawProductName"] = raw_prod
                content["productName"] = res.canonical_name
                content["startupName"] = res.startup_context or raw_startup
                dedup_key = (
                    "PRODUCT",
                    normalize_entity_name(res.canonical_name),
                    normalize_entity_name(res.startup_context or raw_startup),
                )

            elif rtype in {"NEWS", "JOB"}:
                # Keep article/job identity tied to source/item URLs
                norm_item_url = (item_url or "").rstrip("/")
                dedup_key = (rtype, norm_item_url)

            else:
                # Generic fallback
                dedup_key = (rtype, item_url)

            if dedup_key in seen_keys:
                duplicates_removed += 1
                continue

            seen_keys.add(dedup_key)
            deduped.append(rec)

        return deduped, duplicates_removed
