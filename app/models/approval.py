from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from app.database import Base


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    allocation_id = Column(String(36), ForeignKey("allocations.id"), nullable=False)
    approval_level = Column(
        SAEnum("provincial", "national", name="approval_approval_level_enum"),
        nullable=False,
    )
    sequence = Column(Integer, nullable=False, default=1)
    approver_id = Column(String(36), nullable=True)
    approver_name = Column(String(100), nullable=True)
    approver_role = Column(String(100), nullable=True)
    approver_title = Column(String(100), nullable=True)
    department = Column(String(200), nullable=True)
    province = Column(String(50), nullable=True)
    status = Column(
        SAEnum(
            "pending",
            "approved",
            "rejected",
            "escalated",
            "auto_escalated",
            "expired",
            name="approval_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    comment = Column(Text, nullable=True)
    decision_document_url = Column(String(500), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    deadline_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(hours=2))
    timeout_hours = Column(Integer, nullable=False, default=2)
    auto_escalate = Column(Boolean, nullable=False, default=True)
    escalated = Column(Boolean, default=False)
    escalated_at = Column(DateTime, nullable=True)
    escalated_reason = Column(Text, nullable=True)
    escalated_to_id = Column(String(36), nullable=True)
    escalated_to_level = Column(
        SAEnum("provincial", "national", name="escalated_to_level"),
        nullable=True,
    )
    reminder_count = Column(Integer, nullable=False, default=0)
    last_reminder_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    allocation = relationship("Allocation", back_populates="approvals")
    escalation_logs = relationship("ApprovalEscalationLog", back_populates="approval", lazy="selectin", cascade="all, delete-orphan")


class ApprovalEscalationLog(Base):
    __tablename__ = "approval_escalation_logs"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    approval_id = Column(String(36), ForeignKey("approvals.id"), nullable=False)
    escalation_type = Column(
        SAEnum("timeout", "manual", "reminder", "override", name="escalation_type"),
        nullable=False,
    )
    from_level = Column(
        SAEnum("provincial", "national", name="escalation_from_level"),
        nullable=False,
    )
    to_level = Column(
        SAEnum("provincial", "national", name="escalation_to_level"),
        nullable=False,
    )
    from_approver_id = Column(String(36), nullable=True)
    from_approver_name = Column(String(100), nullable=True)
    to_approver_id = Column(String(36), nullable=True)
    to_approver_name = Column(String(100), nullable=True)
    triggered_by = Column(String(36), nullable=True)
    triggered_by_name = Column(String(100), nullable=True)
    is_auto = Column(Boolean, nullable=False, default=False)
    reason = Column(Text, nullable=True)
    previous_deadline = Column(DateTime, nullable=True)
    new_deadline = Column(DateTime, nullable=True)
    escalated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")

    approval = relationship("Approval", back_populates="escalation_logs")
