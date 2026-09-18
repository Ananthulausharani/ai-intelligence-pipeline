"""
AI Tool Quality Scoring Agent — Step 6.

Implements the authoritative 8-criterion scoring framework from the AI Tools guideline:
1. Capability (25%)
2. Usefulness (20%)
3. Adoption (15%)
4. Activity (15%)
5. Maturity (10%)
6. Recency (5%)
7. Differentiation (5%)
8. Information Quality / Verifiability (5%)
Total = 100 points.

Strict Anti-Hallucination & Conservative Evidence Rules:
- No invented evidence to inflate scores.
- Score only on evidence present in verified/enriched records.
- Prefer official-source evidence over directory listings.
- Missing evidence scores conservatively.
- Do not assume adoption, maturity, recency, or activity without explicit proof.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Optional, Union
from urllib.parse import urlparse

from src.models.ai_tool import AITool

logger = logging.getLogger(__name__)

# Canonical Criteria Weights (Sum = 100)
WEIGHTS = {
    "capability": 25.0,
    "usefulness": 20.0,
    "adoption": 15.0,
    "activity": 15.0,
    "maturity": 10.0,
    "recency": 5.0,
    "differentiation": 5.0,
    "information_quality": 5.0,
}

# Guideline Threshold Categories
THRESHOLDS = {
    "EXCEPTIONAL": (90.0, 100.0),
    "EXCELLENT": (80.0, 89.99),
    "GOOD": (70.0, 79.99),
    "AVERAGE_SKIP": (60.0, 69.99),
    "REJECT": (0.0, 59.99),
}


class ToolQualityScorer:
    """
    Evaluates AI Tool records against the 8-criterion quality rubric.
    Produces deterministic numeric scores, breakdowns, and evidence-grounded rationales.
    """

    def __init__(self, minimum_qualifying_score: float = 70.0, reject_threshold: float = 60.0):
        self.minimum_qualifying_score = minimum_qualifying_score
        self.reject_threshold = reject_threshold

    def score_record(
        self, record: Union[dict[str, Any], AITool]
    ) -> tuple[float, dict[str, float], str]:
        """
        Calculate the 100-point quality score, breakdown, and rationale for an AI tool.

        Returns:
            (quality_score, quality_score_breakdown, quality_score_rationale)
        """
        data = record.to_dict() if isinstance(record, AITool) else record

        cap_score, cap_reasons = self._score_capability(data)
        use_score, use_reasons = self._score_usefulness(data)
        ado_score, ado_reasons = self._score_adoption(data)
        act_score, act_reasons = self._score_activity(data)
        mat_score, mat_reasons = self._score_maturity(data)
        rec_score, rec_reasons = self._score_recency(data)
        dif_score, dif_reasons = self._score_differentiation(data)
        inf_score, inf_reasons = self._score_information_quality(data)

        breakdown = {
            "capability": round(cap_score, 1),
            "usefulness": round(use_score, 1),
            "adoption": round(ado_score, 1),
            "activity": round(act_score, 1),
            "maturity": round(mat_score, 1),
            "recency": round(rec_score, 1),
            "differentiation": round(dif_score, 1),
            "information_quality": round(inf_score, 1),
        }

        total_score = round(sum(breakdown.values()), 1)
        # Bounded between 0.0 and 100.0
        total_score = max(0.0, min(100.0, total_score))

        # Build concise rationale
        all_reasons = [
            r for r in [
                cap_reasons, use_reasons, ado_reasons, act_reasons,
                mat_reasons, rec_reasons, dif_reasons, inf_reasons
            ] if r
        ]
        tier = self.classify_tier(total_score)
        rationale = f"Tier: {tier} ({total_score}/100). " + " | ".join(all_reasons)

        return total_score, breakdown, rationale

    def classify_tier(self, score: float) -> str:
        """Map score to guideline curation classification."""
        if score >= 90.0:
            return "Exceptional"
        if score >= 80.0:
            return "Excellent"
        if score >= 70.0:
            return "Good"
        if score >= 60.0:
            return "Average / Skip"
        return "Reject"

    def evaluate_rejection(
        self, record: Union[dict[str, Any], AITool], score: float
    ) -> tuple[bool, Optional[str]]:
        """
        Apply guideline rejection criteria:
        - Dead / shut-down / deprecated status
        - Inaccessible or unverified
        - Directory URL as official website
        - Missing mandatory identity or descriptions
        - Score below rejection threshold (< 60)
        - Marginal 60-69 score candidate check
        """
        data = record.to_dict() if isinstance(record, AITool) else record

        # 1. Dead or shut-down tools
        status = str(data.get("current_status") or "").lower()
        if status in ("dead", "shut down", "deprecated", "inactive", "closed"):
            return True, f"Tool status is inactive/deprecated: '{status}'"

        # 2. Inaccessible or unverified
        v_status = str(data.get("verification_status") or "").lower()
        if v_status in ("unverified", "failed"):
            return True, f"Verification failed or unverified: '{v_status}'"

        # 3. Missing official website
        website = data.get("official_website")
        if not website or not str(website).strip():
            return True, "Missing canonical official website"

        # Directory URL as official website
        host = urlparse(str(website)).netloc.lower()
        if any(d in host for d in ("theresanaiforthat.com", "creati.ai", "producthunt.com")):
            return True, "Directory URL cannot serve as official product website"

        # 4. Missing mandatory descriptions
        if not data.get("short_description"):
            return True, "Missing short_description"
        if not data.get("detailed_overview"):
            return True, "Missing detailed_overview"

        # 5. Low quality score
        if score < self.reject_threshold:
            return True, f"Quality score {score:.1f} below threshold ({self.reject_threshold})"

        # 6. Marginal 60-69 score candidate check
        if 60.0 <= score < self.minimum_qualifying_score:
            # Documented qualifying justification: verified live service with complete identity and pricing
            has_qualifying_justification = bool(
                data.get("api_availability")
                or data.get("open_source_status")
                or (
                    v_status == "verified"
                    and str(data.get("current_status") or "").lower() == "active"
                    and data.get("logo_url")
                    and (data.get("pricing_model") or data.get("free_plan") is not None)
                    and (len(data.get("inputs") or []) > 0 or len(data.get("outputs") or []) > 0)
                )
            )
            if not has_qualifying_justification:
                return True, f"Score {score:.1f} in 60-69 range without distinctive qualifying justification"

        return False, None

    # -----------------------------------------------------------------------
    # Individual Criterion Scorers
    # -----------------------------------------------------------------------

    def _score_capability(self, data: dict[str, Any]) -> tuple[float, str]:
        """Capability (Weight: 25). Evaluates concrete tasks, modalities, platforms, API."""
        score = 0.0
        details = []

        # Primary task defined (up to 6 pts)
        task = data.get("primary_task")
        if task and len(str(task).strip()) > 2:
            score += 6.0
            details.append(f"Task: {task}")

        # Inputs and outputs modalities (up to 8 pts)
        inputs = data.get("inputs") or []
        outputs = data.get("outputs") or []
        in_pts = min(4.0, len(inputs) * 2.0)
        out_pts = min(4.0, len(outputs) * 2.0)
        if in_pts > 0:
            score += in_pts
        if out_pts > 0:
            score += out_pts
        if inputs or outputs:
            details.append(f"Modalities ({len(inputs)} in, {len(outputs)} out)")

        # Supported platforms (up to 4 pts)
        platforms = data.get("supported_platforms") or []
        if platforms:
            score += min(4.0, len(platforms) * 2.0)
            details.append(f"Platforms ({len(platforms)})")

        # Features & AI capabilities (up to 4 pts)
        caps = data.get("ai_capabilities") or []
        feats = data.get("key_features") or []
        if caps or feats:
            score += min(4.0, (len(caps) + len(feats)) * 1.0)

        # API availability (up to 3 pts)
        api = data.get("api_availability")
        if api is True or (isinstance(api, str) and api.lower() in ("true", "rest api", "graphql", "api available")):
            score += 3.0
            details.append("API verified")

        score = min(WEIGHTS["capability"], score)
        return score, f"Capability: {score:.1f}/25 ({', '.join(details) if details else 'minimal'})"

    def _score_usefulness(self, data: dict[str, Any]) -> tuple[float, str]:
        """Usefulness (Weight: 20). Evaluates workflow problem solving and practical utility."""
        score = 0.0
        details = []

        # Domain utility based on categories/task
        cats = [c.lower() for c in data.get("categories") or []]
        task = str(data.get("primary_task") or "").lower()
        high_utility_keywords = (
            "developer", "coding", "productivity", "automation", "research",
            "data", "design", "writing", "agent", "prompt", "image", "audio",
            "video", "api", "assistant", "summary", "summarizer", "translation",
            "math", "ocr", "document"
        )
        if any(kw in task or any(kw in c for c in cats) for kw in high_utility_keywords):
            score += 10.0
            details.append("High workflow utility domain")
        elif cats or task:
            score += 6.0
            details.append("General utility domain")

        # Clear description of problem solved (up to 6 pts)
        overview = data.get("detailed_overview") or ""
        short_desc = data.get("short_description") or ""
        if len(overview) > 60 and len(short_desc) > 20:
            score += 6.0
            details.append("Documented problem solving")
        elif short_desc:
            score += 3.0

        # Concrete use cases (up to 4 pts)
        use_cases = data.get("main_use_cases") or []
        if use_cases:
            score += min(4.0, len(use_cases) * 2.0)
            details.append(f"{len(use_cases)} use cases")
        elif len(data.get("inputs") or []) > 0 and len(data.get("outputs") or []) > 0:
            # Concrete input/output provides practical workflow utility
            score += 2.0

        score = min(WEIGHTS["usefulness"], score)
        return score, f"Usefulness: {score:.1f}/20 ({', '.join(details) if details else 'unclear utility'})"

    def _score_adoption(self, data: dict[str, Any]) -> tuple[float, str]:
        """Adoption (Weight: 15). Evaluates verifiable adoption signals. Conservative by default."""
        score = 0.0
        details = []

        # Verifiable adoption signals field
        signals = data.get("usage_adoption_signals")
        if signals and len(str(signals).strip()) > 5:
            # Explicit adoption signal present
            sig_text = str(signals).lower()
            if any(k in sig_text for k in ("stars", "users", "downloads", "customers", "ranked")):
                score += 12.0
                details.append(f"Verified signals: {signals}")
            else:
                score += 6.0
                details.append("Signals recorded")

        # Active verified service baseline
        v_status = str(data.get("verification_status") or "").lower()
        if v_status == "verified" and str(data.get("current_status") or "").lower() == "active":
            score += 2.0
            details.append("Active live service")

        # Multi-directory presence (corroborating discovery references)
        refs = data.get("discovery_references") or []
        distinct_sources = {r.get("source") for r in refs if r.get("source")}
        if len(distinct_sources) >= 2:
            score += 3.0
            details.append(f"Multi-directory presence ({len(distinct_sources)} sources)")
        elif distinct_sources:
            score += 1.0  # Conservative baseline for single directory listing

        score = min(WEIGHTS["adoption"], score)
        return score, f"Adoption: {score:.1f}/15 ({', '.join(details) if details else 'no verified adoption proof'})"

    def _score_activity(self, data: dict[str, Any]) -> tuple[float, str]:
        """Activity (Weight: 15). Evaluates availability and operational status."""
        score = 0.0
        details = []

        status = str(data.get("current_status") or "").strip().lower()
        if status == "active":
            score = 15.0
            details.append("Active verified status")
        elif status == "beta":
            score = 10.0
            details.append("Beta release with active access")
        elif status == "pre-launch":
            score = 4.0
            details.append("Pre-launch status")
        elif status in ("dead", "deprecated", "shut down", "inactive"):
            score = 0.0
            details.append(f"Inactive status: {status}")
        else:
            # Unstated status, conservative fallback if verification succeeded
            v_status = str(data.get("verification_status") or "").lower()
            if v_status == "verified":
                score = 5.0
                details.append("Verified live website (status unstated)")
            else:
                score = 1.0
                details.append("Unconfirmed operational status")

        score = min(WEIGHTS["activity"], score)
        return score, f"Activity: {score:.1f}/15 ({', '.join(details)})"

    def _score_maturity(self, data: dict[str, Any]) -> tuple[float, str]:
        """Maturity (Weight: 10). Evaluates backing, versioning, commercial viability."""
        score = 0.0
        details = []

        # Verified company / developer
        dev = data.get("company_developer")
        if dev and len(str(dev).strip()) > 1:
            score += 4.0
            details.append(f"Developer: {dev}")

        # Dedicated custom domain
        website = data.get("official_website")
        if website:
            parsed = urlparse(str(website))
            if parsed.netloc and not any(d in parsed.netloc for d in ("vercel.app", "pages.dev", "github.io")):
                score += 1.0
                details.append("Dedicated domain")

        # Version number
        ver = data.get("version")
        if ver and len(str(ver).strip()) > 0:
            score += 2.0
            details.append(f"Version: {ver}")

        # Clear pricing tier / commercial presence
        pricing = data.get("pricing_model")
        if pricing and pricing.lower() in ("free", "freemium", "paid", "usage-based", "subscription"):
            score += 3.0
            details.append(f"Pricing: {pricing}")

        score = min(WEIGHTS["maturity"], score)
        return score, f"Maturity: {score:.1f}/10 ({', '.join(details) if details else 'early/unstated'})"

    def _score_recency(self, data: dict[str, Any]) -> tuple[float, str]:
        """Recency (Weight: 5). Evaluates release date or recent verification."""
        score = 0.0
        details = []

        # Launch date
        launch = data.get("launch_date")
        if launch:
            try:
                dt = datetime.fromisoformat(str(launch).replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_days = (now - dt).days
                if age_days <= 365:
                    score = 5.0
                    details.append(f"Launched within 1 year ({dt.year})")
                elif age_days <= 730:
                    score = 4.0
                    details.append(f"Launched within 2 years ({dt.year})")
                else:
                    score = 2.0
                    details.append(f"Established launch ({dt.year})")
            except Exception:
                score = 1.0

        # Fallback to recent verification date
        if score == 0.0:
            verified_date = data.get("last_verified_date")
            if verified_date:
                score = 3.0
                details.append("Verified in current curation cycle")

        score = min(WEIGHTS["recency"], score)
        return score, f"Recency: {score:.1f}/5 ({', '.join(details) if details else 'no date evidence'})"

    def _score_differentiation(self, data: dict[str, Any]) -> tuple[float, str]:
        """Differentiation (Weight: 5). Evaluates specialized functionality vs generic wrapper."""
        score = 0.0
        details = []

        inputs = data.get("inputs") or []
        outputs = data.get("outputs") or []
        platforms = data.get("supported_platforms") or []
        api = data.get("api_availability")

        # Multi-modal / cross-modal capability
        if len(inputs) >= 2 or len(outputs) >= 2:
            score += 2.0
            details.append("Multi-modal pipeline")

        # Multi-platform or IDE integration
        if len(platforms) >= 2:
            score += 1.5
            details.append("Cross-platform support")

        # API or programmable interface
        if api:
            score += 1.5
            details.append("Programmable API")

        if score == 0.0:
            score = 1.0
            details.append("Standard utility")

        score = min(WEIGHTS["differentiation"], score)
        return score, f"Differentiation: {score:.1f}/5 ({', '.join(details)})"

    def _score_information_quality(self, data: dict[str, Any]) -> tuple[float, str]:
        """Information Quality / Verifiability (Weight: 5). Evaluates ground truth verifiability."""
        score = 0.0
        details = []

        # Verified official website
        v_status = str(data.get("verification_status") or "").lower()
        website = data.get("official_website")
        if v_status == "verified" and website:
            score += 2.0
            details.append("Official website verified")
        elif website:
            score += 1.0

        # Verified logo
        logo = data.get("logo_url")
        if logo and str(logo).startswith("http"):
            score += 1.0
            details.append("Official logo verified")

        # Verified pricing
        if data.get("pricing_model"):
            score += 1.0
            details.append("Pricing model verified")

        # Complete descriptions
        if data.get("short_description") and data.get("detailed_overview"):
            score += 1.0
            details.append("Descriptions verified")

        score = min(WEIGHTS["information_quality"], score)
        return score, f"Info Quality: {score:.1f}/5 ({', '.join(details)})"
