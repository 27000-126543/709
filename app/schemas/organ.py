from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.common import (
    BloodType,
    OrganType,
    OrganStatus,
)


class OrganCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donor_id: str = Field(..., max_length=36)
    organ_type: OrganType
    blood_type: BloodType
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)
    retrieval_time: Optional[datetime] = None
    preserved_until: Optional[datetime] = None
    temperature_requirement: Optional[str] = Field(None, max_length=100)
    max_ischemia_hours: Optional[float] = Field(None, gt=0)


class OrganUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donor_id: Optional[str] = Field(None, max_length=36)
    organ_type: Optional[OrganType] = None
    blood_type: Optional[BloodType] = None
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[OrganStatus] = None
    retrieval_time: Optional[datetime] = None
    preserved_until: Optional[datetime] = None
    temperature_requirement: Optional[str] = Field(None, max_length=100)
    max_ischemia_hours: Optional[float] = Field(None, gt=0)


class OrganResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    donor_id: str
    organ_type: OrganType
    blood_type: BloodType
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = None
    status: OrganStatus
    retrieval_time: Optional[datetime] = None
    preserved_until: Optional[datetime] = None
    temperature_requirement: Optional[str] = None
    max_ischemia_hours: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class OrganLockRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organ_id: str = Field(..., max_length=36)
    reason: Optional[str] = None
    locked_by: str = Field(..., max_length=36)
