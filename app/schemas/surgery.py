from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any
from datetime import datetime, date

from app.schemas.common import (
    PreopCheckStatus,
    SurgeryStatus,
)


class SurgeryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allocation_id: str = Field(..., max_length=36)
    recipient_id: str = Field(..., max_length=36)
    organ_id: str = Field(..., max_length=36)
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    surgeon_id: Optional[str] = Field(None, max_length=36)
    surgery_date: Optional[datetime] = None


class SurgeryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transplant_center_id: Optional[str] = Field(None, max_length=36)
    surgeon_id: Optional[str] = Field(None, max_length=36)
    preop_data: Optional[str] = None
    preop_check_status: Optional[PreopCheckStatus] = None
    preop_recheck_notes: Optional[str] = None
    surgery_date: Optional[datetime] = None
    surgery_status: Optional[SurgeryStatus] = None
    immunosuppressant_plan: Optional[str] = None
    blood_concentration_data: Optional[str] = None
    rejection_monitoring_reminders: Optional[str] = None


class SurgeryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    allocation_id: str
    recipient_id: str
    organ_id: str
    transplant_center_id: Optional[str] = None
    surgeon_id: Optional[str] = None
    preop_data: Optional[str] = None
    preop_check_status: PreopCheckStatus
    preop_recheck_notes: Optional[str] = None
    surgery_date: Optional[datetime] = None
    surgery_status: SurgeryStatus
    immunosuppressant_plan: Optional[str] = None
    blood_concentration_data: Optional[str] = None
    rejection_monitoring_reminders: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PreOpCheckCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    surgery_id: str = Field(..., max_length=36)
    preop_data: str
    check_items: Optional[dict[str, Any]] = None


class PreOpCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    surgery_id: str
    preop_check_status: PreopCheckStatus
    preop_data: Optional[str] = None
    preop_recheck_notes: Optional[str] = None
    checked_at: datetime
    checker_id: Optional[str] = None
    checker_name: Optional[str] = None


class ImmunosuppressantPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    surgery_id: str = Field(..., max_length=36)
    drug_name: str = Field(..., max_length=200)
    dosage: str = Field(..., max_length=100)
    frequency: str = Field(..., max_length=100)
    start_date: date
    end_date: Optional[date] = None
    notes: Optional[str] = None


class DrugMonitoringCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    surgery_id: str = Field(..., max_length=36)
    drug_name: str = Field(..., max_length=200)
    blood_concentration: float = Field(..., gt=0)
    target_concentration_min: Optional[float] = None
    target_concentration_max: Optional[float] = None
    measurement_date: datetime
    dosage_adjustment: Optional[str] = None
    notes: Optional[str] = None
