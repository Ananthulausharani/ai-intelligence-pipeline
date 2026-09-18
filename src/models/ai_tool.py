"""
AI Tool Data Schema for AI Intelligence Pipeline.

Defines the canonical AITool model using Pydantic v2 validation.
Designed for AI data curation trial:
- Strict typing with source traceability
- List and array representation for multi-valued fields
- Resilient URL and date parsing using existing pipeline conventions
- Strict null policy: optional/unverified fields remain None / blank cells
- Serialization-ready for JSON outputs and Google Sheets batch export
"""

from datetime import datetime, timezone
from typing import Any, ClassVar, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AITool(BaseModel):
    """
    Canonical schema for AI Tools in the AI Intelligence Pipeline.
    Contains 42 structured attributes spanning Identity, Description,
    Product capabilities, Pricing, Quality/Verification, and Pipeline Metadata.
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        validate_assignment=True,
    )

    # -----------------------------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------------------------
    tool_name: str = Field(
        ...,
        description="Official name of the AI tool.",
    )
    company_developer: Optional[str] = Field(
        default=None,
        description="Company, organization, or developer who built the tool.",
    )
    official_website: Optional[HttpUrl] = Field(
        default=None,
        description="Canonical website or landing page URL.",
    )
    logo_url: Optional[HttpUrl] = Field(
        default=None,
        description="Direct URL to official tool logo or icon image.",
    )
    country: Optional[str] = Field(
        default=None,
        description="Country of origin or headquarters.",
    )
    version: Optional[str] = Field(
        default=None,
        description="Current release version or model version.",
    )
    launch_date: Optional[datetime] = Field(
        default=None,
        description="Initial public launch date or release timestamp.",
    )
    current_status: Optional[str] = Field(
        default=None,
        description="Operational status (e.g. 'Active', 'Beta', 'Deprecated').",
    )

    # -----------------------------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------------------------
    short_description: Optional[str] = Field(
        default=None,
        description="Concise one-line summary or tagline.",
    )
    detailed_overview: Optional[str] = Field(
        default=None,
        description="Comprehensive explanation of tool capabilities and architecture.",
    )

    # -----------------------------------------------------------------------
    # PRODUCT
    # -----------------------------------------------------------------------
    primary_task: Optional[str] = Field(
        default=None,
        description="Primary problem domain or task solved (e.g. 'AI Code Editor').",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Taxonomy categories (e.g. ['Developer Tools', 'Code Assistants']).",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Descriptive keywords and search tags.",
    )
    key_features: list[str] = Field(
        default_factory=list,
        description="Key functional features and capabilities.",
    )
    main_use_cases: list[str] = Field(
        default_factory=list,
        description="Primary real-world applications or scenarios.",
    )
    ai_capabilities: list[str] = Field(
        default_factory=list,
        description="Specific AI capabilities (e.g. ['Autonomous Agent', 'Code Generation']).",
    )
    inputs: list[str] = Field(
        default_factory=list,
        description="Supported input modalities (e.g. ['text', 'code', 'image']).",
    )
    outputs: list[str] = Field(
        default_factory=list,
        description="Supported output modalities (e.g. ['code', 'diff', 'text']).",
    )
    supported_platforms: list[str] = Field(
        default_factory=list,
        description="Operating systems, editors, or platforms (e.g. ['macOS', 'VS Code']).",
    )
    integrations: list[str] = Field(
        default_factory=list,
        description="Third-party software and service integrations.",
    )
    api_availability: Optional[Union[bool, str]] = Field(
        default=None,
        description="API availability status or description (e.g. True, False, or 'REST API').",
    )
    open_source_status: Optional[Union[bool, str]] = Field(
        default=None,
        description="Open source status or license (e.g. True, False, 'Open Source', 'Proprietary').",
    )
    signup_requirement: Optional[Union[bool, str]] = Field(
        default=None,
        description="Signup/account requirement (e.g. 'Account Required', 'No Sign-up').",
    )

    # -----------------------------------------------------------------------
    # PRICING
    # -----------------------------------------------------------------------
    pricing_model: Optional[str] = Field(
        default=None,
        description="Pricing tier (e.g. 'Free', 'Freemium', 'Paid', 'Usage-Based').",
    )
    starting_price: Optional[str] = Field(
        default=None,
        description="Entry price point (e.g. '$20/month', 'Free').",
    )
    free_plan: Optional[bool] = Field(
        default=None,
        description="Flag indicating if a perpetual free tier exists.",
    )
    free_trial: Optional[bool] = Field(
        default=None,
        description="Flag indicating if a time-bound free trial is available.",
    )
    important_usage_limits: Optional[str] = Field(
        default=None,
        description="Key usage restrictions, quotas, or rate limits.",
    )

    # -----------------------------------------------------------------------
    # QUALITY / VERIFICATION
    # -----------------------------------------------------------------------
    pros: list[str] = Field(
        default_factory=list,
        description="Key strengths and verified benefits.",
    )
    cons: list[str] = Field(
        default_factory=list,
        description="Known drawbacks or pain points.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Technical limitations and unaddressed edges.",
    )
    ai_orbit_summary: Optional[str] = Field(
        default=None,
        description="Curated evaluation synthesis or analyst summary.",
    )
    usage_adoption_signals: Optional[str] = Field(
        default=None,
        description="Verifiable adoption signals (e.g. GitHub stars, active users).",
    )
    quality_score: Optional[float] = Field(
        default=None,
        description="Comprehensive 0-100 quality score evaluated against AI Tools guideline rubric.",
    )
    quality_score_breakdown: Optional[dict[str, Any]] = Field(
        default=None,
        description="Detailed score breakdown per criterion (Capability, Usefulness, Adoption, Activity, Maturity, Recency, Differentiation, Information Quality).",
    )
    quality_score_rationale: Optional[str] = Field(
        default=None,
        description="Concise justification and evidence-based rationale for the assigned quality score.",
    )
    last_verified_date: Optional[datetime] = Field(
        default=None,
        description="Date when information was last verified.",
    )
    discovery_source: Optional[str] = Field(
        default=None,
        description="Platform or method where tool was discovered.",
    )
    discovery_source_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL of the initial discovery source.",
    )
    verification_source: Optional[str] = Field(
        default=None,
        description="Entity or domain verifying tool metadata.",
    )
    verification_source_url: Optional[HttpUrl] = Field(
        default=None,
        description="URL of the verification source.",
    )

    # -----------------------------------------------------------------------
    # RECORD / PIPELINE METADATA
    # -----------------------------------------------------------------------
    record_id: Optional[str] = Field(
        default=None,
        description="Deterministic unique record identifier (e.g. slug or uuid).",
    )
    entity_type: Literal["tool"] = Field(
        default="tool",
        description="Fixed entity type classification, always defaulted to 'tool'.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC creation timestamp.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC update timestamp.",
    )

    # -----------------------------------------------------------------------
    # SPREADSHEET EXPORT CONFIGURATION
    # -----------------------------------------------------------------------
    SHEET_COLUMNS: ClassVar[list[str]] = [
        # Record / Pipeline Metadata
        "record_id",
        "entity_type",
        "created_at",
        "updated_at",
        # Identity
        "tool_name",
        "company_developer",
        "official_website",
        "logo_url",
        "country",
        "version",
        "launch_date",
        "current_status",
        # Description
        "short_description",
        "detailed_overview",
        # Product
        "primary_task",
        "categories",
        "tags",
        "key_features",
        "main_use_cases",
        "ai_capabilities",
        "inputs",
        "outputs",
        "supported_platforms",
        "integrations",
        "api_availability",
        "open_source_status",
        "signup_requirement",
        # Pricing
        "pricing_model",
        "starting_price",
        "free_plan",
        "free_trial",
        "important_usage_limits",
        # Quality / Verification
        "pros",
        "cons",
        "limitations",
        "ai_orbit_summary",
        "usage_adoption_signals",
        "quality_score",
        "quality_score_breakdown",
        "quality_score_rationale",
        "last_verified_date",
        "discovery_source",
        "discovery_source_url",
        "verification_source",
        "verification_source_url",
    ]

    # -----------------------------------------------------------------------
    # FIELD VALIDATORS & RESILIENCE HOOKS
    # -----------------------------------------------------------------------

    @field_validator("tool_name", mode="before")
    @classmethod
    def _validate_tool_name(cls, v: Any) -> str:
        """Ensure tool_name is a non-empty string."""
        if v is None or not isinstance(v, str) or not v.strip():
            raise ValueError("tool_name must be a non-empty string")
        return v.strip()

    @field_validator(
        "official_website",
        "logo_url",
        "discovery_source_url",
        "verification_source_url",
        mode="before",
    )
    @classmethod
    def _clean_optional_url(cls, v: Any) -> Any:
        """Convert empty or whitespace-only URL strings to None."""
        if v is None:
            return None
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                return None
            return v_stripped
        return v

    @field_validator(
        "launch_date",
        "last_verified_date",
        mode="before",
    )
    @classmethod
    def _clean_optional_date(cls, v: Any) -> Any:
        """
        Normalize date input using existing pipeline date conventions.
        Accepts datetime, date, or ISO-8601 strings. Converts empty strings to None.
        """
        if v is None:
            return None
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                return None
            # Attempt parsing using pipeline's freshness normalizer if available
            try:
                from src.agents.freshness import normalize_datetime
                normalized = normalize_datetime(v_stripped)
                if normalized is not None:
                    return normalized
            except ImportError:
                pass
            # Standard ISO fallback
            try:
                iso_clean = v_stripped[:-1] + "+00:00" if v_stripped.endswith(("Z", "z")) else v_stripped
                return datetime.fromisoformat(iso_clean)
            except (ValueError, TypeError):
                return v_stripped
        return v

    @field_validator(
        "categories",
        "tags",
        "key_features",
        "main_use_cases",
        "ai_capabilities",
        "inputs",
        "outputs",
        "supported_platforms",
        "integrations",
        "pros",
        "cons",
        "limitations",
        mode="before",
    )
    @classmethod
    def _coerce_list_fields(cls, v: Any) -> list[str]:
        """
        Ensure multi-valued fields are always lists of non-empty strings.
        Accepts None (converts to []), comma-separated strings, or iterables.
        """
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if "," in s:
                return [part.strip() for part in s.split(",") if part.strip()]
            return [s]
        if isinstance(v, (list, tuple, set)):
            result = []
            for item in v:
                if item is not None:
                    item_str = str(item).strip()
                    if item_str:
                        result.append(item_str)
            return result
        return [str(v)]

    @field_validator(
        "free_plan",
        "free_trial",
        mode="before",
    )
    @classmethod
    def _clean_optional_bool(cls, v: Any) -> Optional[bool]:
        """Normalize boolean inputs, mapping string representations and empty strings."""
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if not s:
                return None
            if s in ("true", "1", "yes", "y"):
                return True
            if s in ("false", "0", "no", "n"):
                return False
        return v

    @field_validator(
        "api_availability",
        "open_source_status",
        "signup_requirement",
        mode="before",
    )
    @classmethod
    def _clean_optional_union(cls, v: Any) -> Any:
        """Clean string or boolean status fields, converting empty strings to None."""
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            if s.lower() in ("true", "yes"):
                return True
            if s.lower() in ("false", "no"):
                return False
            return s
        return v

    @field_validator(
        "company_developer",
        "country",
        "version",
        "current_status",
        "short_description",
        "detailed_overview",
        "primary_task",
        "pricing_model",
        "important_usage_limits",
        "ai_orbit_summary",
        "usage_adoption_signals",
        "quality_score_rationale",
        "discovery_source",
        "verification_source",
        "record_id",
        mode="before",
    )
    @classmethod
    def _clean_optional_strings(cls, v: Any) -> Optional[str]:
        """Convert empty or whitespace-only strings to None for optional text fields."""
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v)

    @field_validator("quality_score", mode="before")
    @classmethod
    def _clean_optional_float(cls, v: Any) -> Optional[float]:
        """Convert float/int/numeric string to float or None."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                return None
        return None

    @field_validator("quality_score_breakdown", mode="before")
    @classmethod
    def _clean_optional_dict(cls, v: Any) -> Optional[dict[str, Any]]:
        """Clean dictionary or parse JSON string for quality score breakdown."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            try:
                import json
                parsed = json.loads(s)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None

    @field_validator("starting_price", mode="before")
    @classmethod
    def _clean_starting_price(cls, v: Any) -> Optional[str]:
        """Accept numeric or string price representations."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return f"${v:.2f}" if v > 0 else "Free"
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v)

    # -----------------------------------------------------------------------
    # SERIALIZATION & CONVERSION METHODS
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize model into a JSON-compatible dictionary.
        Dates are ISO-formatted, URLs are converted to strings, and enums are resolved.
        """
        return self.model_dump(mode="json")

    @classmethod
    def get_sheet_columns(cls) -> list[str]:
        """Return ordered list of column headers for Google Sheets export."""
        return list(cls.SHEET_COLUMNS)

    def to_sheet_row(self) -> list[Any]:
        """
        Convert this AITool instance into a spreadsheet row matching get_sheet_columns().
        Strict null policy: unstated/null values become empty strings ('').
        Lists are serialized as comma-separated strings (', ').
        Datetimes are serialized as ISO-8601 strings.
        URLs are serialized as strings.
        Booleans are serialized as 'True' / 'False'.
        """
        row: list[Any] = []
        for col in self.SHEET_COLUMNS:
            val = getattr(self, col, None)
            row.append(self._format_cell_value(val))
        return row

    @classmethod
    def from_sheet_row(cls, data: Union[list[Any], dict[str, Any]]) -> "AITool":
        """
        Reconstruct an AITool instance from a spreadsheet row list or dictionary.
        Converts empty string cells to None.
        """
        if isinstance(data, list):
            data = dict(zip(cls.SHEET_COLUMNS, data))
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            if v == "" or v is None:
                cleaned[k] = None
            else:
                cleaned[k] = v
        return cls(**cleaned)

    @staticmethod
    def _format_cell_value(val: Any) -> str:
        """Format individual field value for Google Sheets cell representation."""
        if val is None:
            return ""
        if isinstance(val, bool):
            return "True" if val else "False"
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, datetime):
            return val.isoformat()
        if isinstance(val, list):
            return ", ".join(str(item) for item in val)
        if isinstance(val, dict):
            import json
            return json.dumps(val, ensure_ascii=False)
        return str(val)
