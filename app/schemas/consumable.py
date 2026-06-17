from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.common import (
    ConsumableCategory,
    ConsumableStatus,
    ReplenishmentStatus,
)


class ConsumableCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., max_length=200)
    category: ConsumableCategory
    stock_quantity: int = Field(0, ge=0)
    safety_stock_level: int = Field(0, ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    unit_price: Optional[float] = Field(None, ge=0)
    supplier: Optional[str] = Field(None, max_length=200)


class ConsumableUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = Field(None, max_length=200)
    category: Optional[ConsumableCategory] = None
    stock_quantity: Optional[int] = Field(None, ge=0)
    safety_stock_level: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=50)
    unit_price: Optional[float] = Field(None, ge=0)
    supplier: Optional[str] = Field(None, max_length=200)
    status: Optional[ConsumableStatus] = None
    replenishment_status: Optional[ReplenishmentStatus] = None
    outbound_quota_locked: Optional[int] = Field(None, ge=0)


class ConsumableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: ConsumableCategory
    stock_quantity: int
    safety_stock_level: int
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    supplier: Optional[str] = None
    status: ConsumableStatus
    replenishment_request_id: Optional[str] = None
    replenishment_status: Optional[ReplenishmentStatus] = None
    outbound_quota_locked: int
    created_at: datetime
    updated_at: datetime


class ReplenishmentRequestCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consumable_id: str = Field(..., max_length=36)
    requested_quantity: int = Field(..., gt=0)
    reason: str
    requested_by: str = Field(..., max_length=36)
    expected_arrival_date: Optional[datetime] = None


class ReplenishmentRequestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Optional[ReplenishmentStatus] = None
    approved_quantity: Optional[int] = Field(None, gt=0)
    approver_id: Optional[str] = Field(None, max_length=36)
    approval_notes: Optional[str] = None
    actual_arrival_date: Optional[datetime] = None
    actual_quantity: Optional[int] = Field(None, gt=0)


class OutboundQuotaCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consumable_id: str = Field(..., max_length=36)
    allocation_id: Optional[str] = Field(None, max_length=36)
    surgery_id: Optional[str] = Field(None, max_length=36)
    requested_quantity: int = Field(..., gt=0)
    purpose: str
    requested_by: str = Field(..., max_length=36)
