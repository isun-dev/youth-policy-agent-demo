from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EligibilityStatus(str, Enum):
    ELIGIBLE_LIKELY = "eligible_likely"
    NEED_MORE_INFO = "need_more_info"
    NOT_ELIGIBLE_LIKELY = "not_eligible_likely"


class IntentCategory(str, Enum):
    ALL = "all"
    EMPLOYMENT = "employment"
    HOUSING = "housing"
    SAVINGS = "savings"
    EDUCATION = "education"
    BUSINESS = "business"


class UserIntent(BaseModel):
    category: IntentCategory = IntentCategory.ALL
    target_policy_keyword: Optional[str] = None
    confidence: float = 0.0
    source: str = "rule"


class UserProfile(BaseModel):
    age: Optional[int] = None
    region: Optional[str] = None
    employment_status: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Policy(BaseModel):
    id: str
    name: str
    region: list[str] = Field(default_factory=list)
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    employment_status: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    description: str = ""
    benefit: str = ""
    apply_url: str = ""
    source_url: str = ""
    last_checked: str = ""


class EligibilityResult(BaseModel):
    policy: Policy
    status: EligibilityStatus
    matched_conditions: list[str] = Field(default_factory=list)
    failed_conditions: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
