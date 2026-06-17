from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.common import (
    AllocationStatus,
    ApprovalLevel,
    OrganType,
)


class AllocationRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organ_id: str = Field(..., max_length=36)
    recipient_id: str = Field(..., max_length=36)
    donor_id: str = Field(..., max_length=36)
    matching_score: Optional[float] = Field(None, ge=0, le=100)
    matching_detail: Optional[str] = None
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    province: Optional[str] = Field(None, max_length=50)


class AllocationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    matching_score: Optional[float] = Field(None, ge=0, le=100)
    matching_detail: Optional[str] = None
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    province: Optional[str] = Field(None, max_length=50)
    status: Optional[AllocationStatus] = None
    current_approval_level: Optional[ApprovalLevel] = None


class AllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organ_id: str
    recipient_id: str
    donor_id: str
    matching_score: Optional[float] = None
    matching_detail: Optional[str] = None
    transplant_center_id: Optional[str] = None
    province: Optional[str] = None
    status: AllocationStatus
    current_approval_level: ApprovalLevel
    created_at: datetime
    updated_at: datetime


class RetrievalTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allocation_id: str
    organ_id: str
    organ_type: OrganType
    donor_id: str
    donor_name: str
    recipient_id: str
    recipient_name: str
    origin_hospital: str
    destination_hospital: str
    retrieval_team_id: Optional[str] = None
    retrieval_deadline: datetime
    status: str
    created_at: datetime
