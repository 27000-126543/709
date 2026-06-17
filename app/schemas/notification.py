from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class RecipientType(str, Enum):
    coordinator = "coordinator"
    transplant_center = "transplant_center"
    transport_team = "transport_team"
    regulator = "regulator"
    donor = "donor"
    recipient = "recipient"
    doctor = "doctor"
    approver = "approver"
    user = "user"


class NotificationType(str, Enum):
    donor_registered = "donor_registered"
    allocation_request = "allocation_request"
    transport_alert = "transport_alert"
    approval_progress = "approval_progress"
    followup_alert = "followup_alert"
    inventory_alert = "inventory_alert"
    report_ready = "report_ready"
    allocation = "allocation"
    approval = "approval"
    transport = "transport"
    surgery = "surgery"
    followup = "followup"
    alert = "alert"
    system = "system"


class ReferenceType(str, Enum):
    allocation = "allocation"
    approval = "approval"
    transport = "transport"
    surgery = "surgery"
    followup = "followup"
    consumable = "consumable"
    donor = "donor"
    recipient = "recipient"
    organ = "organ"
    report = "report"


class NotificationCreate(BaseModel):
    recipient_type: str
    recipient_id: str
    title: str
    content: str
    notification_type: str
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipient_type: str
    recipient_id: str
    title: str
    content: str
    notification_type: str
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    is_read: bool = False
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[NotificationResponse]
    total: int
    page: int = 1
    size: int = 20
