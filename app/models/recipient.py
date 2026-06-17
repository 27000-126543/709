from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=False)
    age = Column(Integer, nullable=False)
    id_number = Column(String(50), nullable=False, unique=True)
    blood_type = Column(String(10), nullable=False)
    hla_a = Column(String(50), nullable=True)
    hla_b = Column(String(50), nullable=True)
    hla_c = Column(String(50), nullable=True)
    hla_drb1 = Column(String(50), nullable=True)
    hla_dqb1 = Column(String(50), nullable=True)
    hla_typing = Column(Text, nullable=True)
    pra_level = Column(Float, nullable=True)
    pra_antibodies = Column(Text, nullable=True)
    organ_type_needed = Column(
        SAEnum(
            "heart",
            "liver",
            "kidney_left",
            "kidney_right",
            "lung_left",
            "lung_right",
            "pancreas",
            "small_intestine",
            "cornea",
            name="organ_type_needed",
        ),
        nullable=False,
    )
    urgency_level = Column(
        SAEnum("emergency", "priority", "routine", name="urgency_level_new"),
        nullable=False,
        default="routine",
    )
    meld_score = Column(Float, nullable=True)
    waiting_since = Column(DateTime, nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    hospital = Column(String(200), nullable=True)
    doctor_in_charge = Column(String(100), nullable=True)
    doctor_id = Column(String(36), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    status = Column(
        SAEnum(
            "waiting",
            "matched",
            "scheduled",
            "transplanted",
            "deceased",
            "delisted",
            name="recipient_status",
        ),
        nullable=False,
        default="waiting",
    )
    delist_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    waiting_list_entries = relationship("WaitingList", back_populates="recipient", lazy="selectin", cascade="all, delete-orphan")
    match_results = relationship("MatchResult", back_populates="recipient", lazy="selectin", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="recipient", lazy="selectin")
    followups = relationship("FollowUpRecord", back_populates="recipient", lazy="selectin")
    surgeries = relationship("Surgery", back_populates="recipient", lazy="selectin")
    transplant_center = relationship("TransplantCenter", back_populates="recipients")


class WaitingList(Base):
    __tablename__ = "waiting_lists"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=False)
    organ_type = Column(
        SAEnum(
            "heart",
            "liver",
            "kidney_left",
            "kidney_right",
            "lung_left",
            "lung_right",
            "pancreas",
            "small_intestine",
            "cornea",
            name="waiting_organ_type",
        ),
        nullable=False,
    )
    list_date = Column(DateTime, nullable=False)
    urgency_level = Column(
        SAEnum("emergency", "priority", "routine", name="waiting_urgency_level"),
        nullable=False,
        default="routine",
    )
    meld_score = Column(Float, nullable=True)
    waiting_days = Column(Integer, nullable=False, default=0)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    province = Column(String(50), nullable=True)
    priority_rank = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    removed_date = Column(DateTime, nullable=True)
    removal_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recipient = relationship("Recipient", back_populates="waiting_list_entries")
    transplant_center = relationship("TransplantCenter", back_populates="waiting_lists")
