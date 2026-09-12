"""
Canonical data schemas for the AI Intelligence Pipeline.
All records use Pydantic v2 for validation.
"""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------

class Source(BaseModel):
    name: str
    url: HttpUrl


# ---------------------------------------------------------------------------
# 1. Startup
# ---------------------------------------------------------------------------

class StartupData(BaseModel):
    employeeCount: Optional[int] = None
    website: Optional[HttpUrl] = None
    company_url: Optional[HttpUrl] = None
    industries: Optional[list[str]] = None
    description: Optional[str] = None


class StartupContent(BaseModel):
    entityName: str
    data: StartupData = Field(default_factory=StartupData)


class Startup(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    recordType: Literal["STARTUP"] = "STARTUP"
    source: Source
    content: StartupContent
    collectedAt: datetime


# ---------------------------------------------------------------------------
# 2. Product
# ---------------------------------------------------------------------------

class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"


class ProductContent(BaseModel):
    productName: str
    startupName: Optional[str] = None
    pricingModel: Optional[PricingModel] = None
    product_url: Optional[HttpUrl] = None


class Product(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    recordType: Literal["PRODUCT"] = "PRODUCT"
    source: Source
    content: ProductContent
    collectedAt: datetime


# ---------------------------------------------------------------------------
# 3. Research Paper
# ---------------------------------------------------------------------------

class ResearchPaperContent(BaseModel):
    title: str
    authors: list[str]
    paper_url: HttpUrl
    github_url: Optional[HttpUrl] = None
    github_stars: Optional[int] = None  # only set when github_url is present
    published_date: datetime


class ResearchPaper(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    recordType: Literal["RESEARCH_PAPER"] = "RESEARCH_PAPER"
    source: Optional[Source] = None
    content: ResearchPaperContent
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    paper_url: Optional[HttpUrl] = None
    github_url: Optional[HttpUrl] = None
    github_stars: Optional[int] = None
    published_date: Optional[datetime] = None
    collectedAt: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 4. Job
# ---------------------------------------------------------------------------

class JobContent(BaseModel):
    company: str
    date: datetime
    is_remote: bool
    role_family: str


class Job(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    recordType: Literal["JOB"] = "JOB"
    content: JobContent


# ---------------------------------------------------------------------------
# 5. News
# ---------------------------------------------------------------------------

class NewsContent(BaseModel):
    title: str
    text: str
    published_date: datetime


class News(BaseModel):
    schemaVersion: Literal["1.0"] = "1.0"
    recordType: Literal["NEWS"] = "NEWS"
    source: Source
    content: NewsContent
    collectedAt: datetime


# ---------------------------------------------------------------------------
# 6. Entity Mapping Log
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    STARTUP = "STARTUP"
    PRODUCT = "PRODUCT"


class EntityMappingLog(BaseModel):
    raw_name: str
    canonical_name: str
    entity_type: EntityType
    source_url: HttpUrl
