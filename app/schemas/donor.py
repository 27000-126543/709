from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.common import (
    BloodType,
    Gender,
    HealthStatus,
    DonorStatus,
)


class DonorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., max_length=100)
    id_number: str = Field(..., max_length=50)
    gender: Gender
    age: int = Field(..., ge=0, le=150)
    blood_type: BloodType
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)
    health_status: HealthStatus = HealthStatus.qualified
    health_check_detail: Optional[str] = None
    family_consent: bool = False
    consent_document_url: Optional[str] = Field(None, max_length=500)
    consent_verified: bool = False
    consent_notes: Optional[str] = None
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    hospital: Optional[str] = Field(None, max_length=200)
    coordinator_id: Optional[str] = Field(None, max_length=36)


class DonorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, max_length=100)
    id_number: Optional[str] = Field(None, max_length=50)
    gender: Optional[Gender] = None
    age: Optional[int] = Field(None, ge=0, le=150)
    blood_type: Optional[BloodType] = None
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)
    health_status: Optional[HealthStatus] = None
    health_check_detail: Optional[str] = None
    family_consent: Optional[bool] = None
    consent_document_url: Optional[str] = Field(None, max_length=500)
    consent_verified: Optional[bool] = None
    consent_notes: Optional[str] = None
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    hospital: Optional[str] = Field(None, max_length=200)
    coordinator_id: Optional[str] = Field(None, max_length=36)
    status: Optional[DonorStatus] = None


class DonorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    id_number: str
    gender: Gender
    age: int
    blood_type: BloodType
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = None
    health_status: HealthStatus
    health_check_detail: Optional[str] = None
    family_consent: bool
    consent_document_url: Optional[str] = None
    consent_verified: bool
    consent_notes: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    hospital: Optional[str] = None
    coordinator_id: Optional[str] = None
    status: DonorStatus
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DonorHealthCheckCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donor_id: str = Field(..., max_length=36)
    health_status: HealthStatus
    health_check_detail: str
    hla_typing: Optional[str] = None
    pra_level: Optional[float] = Field(None, ge=0, le=100)


class DonorConsentVerify(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donor_id: str = Field(..., max_length=36)
    consent_verified: bool
    consent_notes: Optional[str] = None
    consent_document_url: Optional[str] = Field(None, max_length=500)
    family_consent: bool = True


class DonorRejectRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donor_id: str = Field(..., max_length=36)
    rejection_reason: str
