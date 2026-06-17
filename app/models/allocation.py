from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Allocation(Base):
    __tablename__ = "allocations"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    organ_id = Column(String(36), ForeignKey("organs.id"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=False)
    donor_id = Column(String(36), ForeignKey("donors.id"), nullable=False)
    match_result_id = Column(String(36), ForeignKey("match_results.id"), nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    requested_by = Column(String(36), nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow)
    matching_score = Column(Float, nullable=True)
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    center_verified = Column(Boolean, nullable=False, default=False)
    center_verified_at = Column(DateTime, nullable=True)
    center_verifier = Column(String(100), nullable=True)
    center_verification_notes = Column(Text, nullable=True)
    status = Column(
        SAEnum(
            "pending",
            "provincial_approved",
            "national_approved",
            "rejected",
            "cancelled",
            "in_transit",
            "completed",
            name="allocation_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    current_approval_level = Column(
        SAEnum("pending", "provincial", "national", "final", "rejected", name="approval_level_enum"),
        nullable=False,
        default="pending",
    )
    rejection_reason = Column(Text, nullable=True)
    rejection_by = Column(String(36), nullable=True)
    rejection_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    cancelled_by = Column(String(36), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organ = relationship("Organ", back_populates="allocations")
    recipient = relationship("Recipient", back_populates="allocations")
    donor = relationship("Donor", lazy="selectin")
    match_result = relationship("MatchResult", lazy="selectin")
    transplant_center = relationship("TransplantCenter", back_populates="allocations")
    transports = relationship("Transport", back_populates="allocation", lazy="selectin")
    approvals = relationship("Approval", back_populates="allocation", lazy="selectin")
    surgeries = relationship("Surgery", back_populates="allocation", lazy="selectin")
    retrieval_tasks = relationship("RetrievalTask", back_populates="allocation", lazy="selectin")


class RetrievalTeam(Base):
    __tablename__ = "retrieval_teams"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    team_name = Column(String(200), nullable=False)
    team_code = Column(String(50), nullable=True, unique=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    leader_name = Column(String(100), nullable=False)
    leader_contact = Column(String(20), nullable=False)
    leader_id = Column(String(36), nullable=True)
    members = Column(Text, nullable=True)
    specialization = Column(String(200), nullable=True)
    status = Column(
        SAEnum("available", "on_duty", "resting", "disabled", name="retrieval_team_status"),
        nullable=False,
        default="available",
    )
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    current_location_lat = Column(Float, nullable=True)
    current_location_lng = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transplant_center = relationship("TransplantCenter", back_populates="retrieval_teams")
    tasks = relationship("RetrievalTask", back_populates="team", lazy="selectin")


class RetrievalTask(Base):
    __tablename__ = "retrieval_tasks"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    allocation_id = Column(String(36), ForeignKey("allocations.id"), nullable=False)
    retrieval_team_id = Column(String(36), ForeignKey("retrieval_teams.id"), nullable=False)
    organ_id = Column(String(36), ForeignKey("organs.id"), nullable=False)
    task_code = Column(String(50), nullable=True, unique=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    departed_at = Column(DateTime, nullable=True)
    arrived_at_hospital = Column(DateTime, nullable=True)
    retrieval_started_at = Column(DateTime, nullable=True)
    retrieval_completed_at = Column(DateTime, nullable=True)
    organ_handover_at = Column(DateTime, nullable=True)
    returned_at = Column(DateTime, nullable=True)
    status = Column(
        SAEnum(
            "assigned",
            "accepted",
            "departed",
            "arrived_hospital",
            "retrieving",
            "retrieval_done",
            "handover_done",
            "completed",
            "failed",
            "cancelled",
            name="retrieval_task_status",
        ),
        nullable=False,
        default="assigned",
    )
    origin_hospital = Column(String(200), nullable=True)
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    allocation = relationship("Allocation", back_populates="retrieval_tasks")
    team = relationship("RetrievalTeam", back_populates="tasks")
    organ = relationship("Organ", lazy="selectin")
