from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime, timedelta

from app.schemas.common import (
    ApprovalLevel,
    ApprovalStatus,
    ApprovalActionType,
)


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allocation_id: str = Field(..., max_length=36)
    approval_level: ApprovalLevel
    approver_id: str = Field(..., max_length=36)
    approver_name: str = Field(..., max_length=100)
    approver_role: str = Field(..., max_length=100)
    timeout_hours: int = Field(2, gt=0)


class ApprovalAction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_id: str = Field(..., max_length=36)
    action: ApprovalActionType
    comment: Optional[str] = None
    approver_id: str = Field(..., max_length=36)


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    allocation_id: str
    approval_level: ApprovalLevel
    approver_id: str
    approver_name: str
    approver_role: str
    status: ApprovalStatus
    comment: Optional[str] = None
    escalated_at: Optional[datetime] = None
    timeout_at: datetime
    escalated_to_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ApprovalEscalation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_id: str = Field(..., max_length=36)
    escalated_to_id: str = Field(..., max_length=36)
    escalated_to_name: str = Field(..., max_length=100)
    escalated_to_role: str = Field(..., max_length=100)
    reason: str
    additional_timeout_hours: Optional[int] = Field(2, gt=0)
