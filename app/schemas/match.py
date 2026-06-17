from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any
from datetime import datetime

from app.schemas.common import (
    OrganType,
    UrgencyLevel,
    BloodType,
)


class MatchRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organ_id: str = Field(..., max_length=36)
    donor_id: str = Field(..., max_length=36)
    organ_type: OrganType
    blood_type: BloodType
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)
    urgency_filter: Optional[UrgencyLevel] = None
    max_results: int = Field(10, ge=1, le=100)


class MatchResultItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_id: str
    recipient_name: str
    matching_score: float = Field(..., ge=0, le=100)
    blood_type_match: bool
    hla_match_count: int
    pra_compatible: bool
    urgency_level: UrgencyLevel
    waiting_days: int
    rank: int = Field(..., ge=1)
    matching_detail: Optional[str] = None


class MatchResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organ_id: str
    donor_id: str
    organ_type: OrganType
    total_candidates: int
    matched_at: datetime
    results: list[MatchResultItem]


class MatchingResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_id: str
    matching_score: float
    matching_detail: Optional[Any] = None
    rank: int
