from pydantic import BaseModel, ConfigDict
from typing import Generic, TypeVar, Optional, Any
from datetime import datetime
from enum import Enum


T = TypeVar("T")


class BloodType(str, Enum):
    A = "A"
    B = "B"
    AB = "AB"
    O = "O"


class Gender(str, Enum):
    male = "male"
    female = "female"


class HealthStatus(str, Enum):
    qualified = "qualified"
    conditional = "conditional"
    disqualified = "disqualified"


class DonorStatus(str, Enum):
    registered = "registered"
    verified = "verified"
    rejected = "rejected"
    organ_retrieved = "organ_retrieved"
    closed = "closed"


class OrganType(str, Enum):
    heart = "heart"
    liver = "liver"
    kidney = "kidney"
    lung = "lung"
    pancreas = "pancreas"
    cornea = "cornea"


class OrganStatus(str, Enum):
    available = "available"
    locked = "locked"
    allocated = "allocated"
    retrieved = "retrieved"
    in_transit = "in_transit"
    delivered = "delivered"
    transplanted = "transplanted"
    discarded = "discarded"


class UrgencyLevel(str, Enum):
    critical = "critical"
    urgent = "urgent"
    normal = "normal"
    elective = "elective"


class RecipientStatus(str, Enum):
    waiting = "waiting"
    matched = "matched"
    scheduled = "scheduled"
    transplanted = "transplanted"
    deceased = "deceased"
    delisted = "delisted"


class AllocationStatus(str, Enum):
    pending = "pending"
    provincial_approved = "provincial_approved"
    national_approved = "national_approved"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"


class ApprovalLevel(str, Enum):
    pending = "pending"
    provincial = "provincial"
    national = "national"
    final = "final"


class TransportStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    delivered = "delivered"
    failed = "failed"
    emergency = "emergency"


class AlertType(str, Enum):
    temperature = "temperature"
    delay = "delay"
    route_deviation = "route_deviation"
    ischemia_risk = "ischemia_risk"
    vehicle_failure = "vehicle_failure"
    other = "other"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    escalated = "escalated"


class ApprovalActionType(str, Enum):
    approve = "approve"
    reject = "reject"
    escalate = "escalate"


class PreopCheckStatus(str, Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    recheck_recommended = "recheck_recommended"


class SurgeryStatus(str, Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class FollowUpType(str, Enum):
    routine = "routine"
    special = "special"
    emergency = "emergency"


class ConsumableCategory(str, Enum):
    surgical = "surgical"
    preservation = "preservation"
    testing = "testing"
    general = "general"


class ConsumableStatus(str, Enum):
    normal = "normal"
    low = "low"
    critical = "critical"
    replenishing = "replenishing"


class ReplenishmentStatus(str, Enum):
    none = "none"
    pending = "pending"
    approved = "approved"
    procuring = "procuring"
    arrived = "arrived"


class NotificationRecipientType(str, Enum):
    coordinator = "coordinator"
    transplant_center = "transplant_center"
    transport_team = "transport_team"
    regulator = "regulator"


class NotificationTypeEnum(str, Enum):
    donor_registered = "donor_registered"
    allocation_request = "allocation_request"
    transport_alert = "transport_alert"
    approval_progress = "approval_progress"
    followup_alert = "followup_alert"
    inventory_alert = "inventory_alert"
    report_ready = "report_ready"


class Response(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class TimestampsMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime
