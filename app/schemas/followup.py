from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any, Union
from datetime import datetime
import json

from app.schemas.common import (
    FollowUpType,
)


class FollowUpCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_id: str = Field(..., max_length=36)
    surgery_id: Optional[str] = Field(None, max_length=36)
    followup_date: datetime
    followup_type: FollowUpType = FollowUpType.routine
    data: Optional[Union[str, dict[str, Any]]] = None
    abnormal_flags: Optional[str] = None
    doctor_id: Optional[str] = Field(None, max_length=36)
    notes: Optional[str] = None


class FollowUpUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    followup_date: Optional[datetime] = None
    followup_type: Optional[FollowUpType] = None
    data: Optional[str] = None
    abnormal_flags: Optional[str] = None
    alert_triggered: Optional[bool] = None
    alert_details: Optional[str] = None
    doctor_id: Optional[str] = Field(None, max_length=36)
    notes: Optional[str] = None


class FollowUpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipient_id: str
    surgery_id: Optional[str] = None
    followup_date: datetime
    followup_type: FollowUpType
    data: Optional[str] = None
    abnormal_flags: Optional[str] = None
    alert_triggered: bool
    alert_details: Optional[str] = None
    doctor_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FollowUpRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recipient_id: str = Field(..., max_length=36)
    surgery_id: Optional[str] = Field(None, max_length=36)
    followup_date: datetime
    followup_type: FollowUpType = FollowUpType.routine
    visit_type: Optional[str] = None
    vital_signs: Optional[dict[str, Any]] = None
    lab_results: Optional[dict[str, Any]] = None
    imaging_results: Optional[dict[str, Any]] = None
    biopsy_results: Optional[dict[str, Any]] = None
    medication_adherence: Optional[bool] = None
    adverse_events: Optional[list[str]] = None
    doctor_assessment: Optional[str] = None
    next_followup_date: Optional[datetime] = None
    notes: Optional[str] = None
    doctor_id: Optional[str] = Field(None, max_length=36)


class FollowUpAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    followup_id: str
    recipient_id: str
    recipient_name: str
    alert_type: str
    alert_detail: str
    alert_time: datetime
    abnormal_items: Optional[list[str]] = None
    severity: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
