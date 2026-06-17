from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

from app.schemas.common import (
    TransportStatus,
    AlertType,
)


class TransportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allocation_id: str = Field(..., max_length=36)
    organ_id: str = Field(..., max_length=36)
    retrieval_team_id: Optional[str] = Field(None, max_length=36)
    origin_hospital: str = Field(..., max_length=200)
    destination_hospital: str = Field(..., max_length=200)
    departure_time: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None


class TransportUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    retrieval_team_id: Optional[str] = Field(None, max_length=36)
    status: Optional[TransportStatus] = None
    current_temperature: Optional[float] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    departure_time: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    route_deviation_km: Optional[float] = Field(None, ge=0)
    emergency_plan_activated: Optional[bool] = None
    emergency_plan_detail: Optional[str] = None


class TransportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    allocation_id: str
    organ_id: str
    retrieval_team_id: Optional[str] = None
    origin_hospital: str
    destination_hospital: str
    status: TransportStatus
    current_temperature: Optional[float] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    departure_time: Optional[datetime] = None
    estimated_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    alert_triggered: bool
    alert_type: Optional[str] = None
    alert_detail: Optional[str] = None
    emergency_plan_activated: bool
    emergency_plan_detail: Optional[str] = None
    route_deviation_km: float
    created_at: datetime
    updated_at: datetime


class TransportLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transport_id: str = Field(..., max_length=36)
    current_temperature: Optional[float] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    status: Optional[TransportStatus] = None
    log_time: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None


class TransportAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transport_id: str
    alert_type: AlertType
    alert_detail: str
    alert_time: datetime
    current_temperature: Optional[float] = None
    current_location: Optional[str] = None
    route_deviation_km: Optional[float] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
