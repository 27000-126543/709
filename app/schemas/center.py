from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Optional
from datetime import datetime

from app.schemas.common import (
    NotificationRecipientType,
    NotificationTypeEnum,
)


class TransplantCenterCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., max_length=200)
    code: str = Field(..., max_length=50)
    province: str = Field(..., max_length=50)
    city: str = Field(..., max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    director: Optional[str] = Field(None, max_length=100)
    director_phone: Optional[str] = Field(None, max_length=50)
    organ_types_available: Optional[list[str]] = None
    license_number: Optional[str] = Field(None, max_length=100)
    status: str = "active"


class TransplantCenterUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    director: Optional[str] = Field(None, max_length=100)
    director_phone: Optional[str] = Field(None, max_length=50)
    organ_types_available: Optional[list[str]] = None
    license_number: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None


class TransplantCenterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str
    province: str
    city: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    director: Optional[str] = None
    director_phone: Optional[str] = None
    organ_types_available: Optional[list[str]] = None
    license_number: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class CoordinatorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., max_length=100)
    id_number: str = Field(..., max_length=50)
    phone: str = Field(..., max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    age: Optional[int] = Field(None, ge=0, le=150)
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    hospital: Optional[str] = Field(None, max_length=200)
    role: str = Field("coordinator", max_length=100)
    certification_number: Optional[str] = Field(None, max_length=100)
    status: str = "active"


class CoordinatorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, max_length=100)
    id_number: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    age: Optional[int] = Field(None, ge=0, le=150)
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    province: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=50)
    hospital: Optional[str] = Field(None, max_length=200)
    role: Optional[str] = Field(None, max_length=100)
    certification_number: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None


class CoordinatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    id_number: str
    phone: str
    email: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    transplant_center_id: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    hospital: Optional[str] = None
    role: str
    certification_number: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class NotificationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_type: NotificationRecipientType
    recipient_id: str = Field(..., max_length=36)
    title: str = Field(..., max_length=200)
    content: str
    notification_type: NotificationTypeEnum
    reference_id: Optional[str] = Field(None, max_length=36)
    reference_type: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field("normal", max_length=20)
    sent_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipient_type: NotificationRecipientType
    recipient_id: str
    title: str
    content: str
    notification_type: NotificationTypeEnum
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    is_read: bool
    sent_at: datetime
    created_at: datetime
