from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.common import (
    BloodType,
    Gender,
    OrganType,
    UrgencyLevel,
    RecipientStatus,
)


class RecipientCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., max_length=100)
    id_number: str = Field(..., max_length=50)
    gender: Gender
    age: int = Field(..., ge=0, le=150)
    blood_type: BloodType
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)
    pra_antibodies: Optional[str] = None
    organ_type_needed: OrganType
    urgency_level: UrgencyLevel = UrgencyLevel.routine
    waiting_since: Optional[datetime] = None
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    hospital: Optional[str] = Field(None, max_length=200)
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    doctor_id: Optional[str] = Field(None, max_length=36)


class RecipientUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, max_length=100)
    id_number: Optional[str] = Field(None, max_length=50)
    gender: Optional[Gender] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    blood_type: Optional[BloodType] = None
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)
    pra_antibodies: Optional[str] = None
    organ_type_needed: Optional[OrganType] = None
    urgency_level: Optional[UrgencyLevel] = None
    waiting_since: Optional[datetime] = None
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    hospital: Optional[str] = Field(None, max_length=200)
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    doctor_id: Optional[str] = Field(None, max_length=36)
    status: Optional[RecipientStatus] = None


class RecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    id_number: str
    gender: Gender
    age: int
    blood_type: BloodType
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = None
    pra_antibodies: Optional[str] = None
    organ_type_needed: OrganType
    urgency_level: UrgencyLevel
    waiting_since: Optional[datetime] = None
    province: Optional[str] = None
    city: Optional[str] = None
    hospital: Optional[str] = None
    transplant_center_id: Optional[str] = None
    doctor_id: Optional[str] = None
    status: RecipientStatus
    matching_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class WaitingListAdd(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_id: str = Field(..., max_length=36)
    organ_type_needed: OrganType
    urgency_level: UrgencyLevel = UrgencyLevel.routine
    waiting_since: datetime = Field(default_factory=datetime.utcnow)
