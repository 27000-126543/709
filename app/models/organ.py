from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class OrganType:
    HEART = "heart"
    LIVER = "liver"
    KIDNEY_LEFT = "kidney_left"
    KIDNEY_RIGHT = "kidney_right"
    LUNG_LEFT = "lung_left"
    LUNG_RIGHT = "lung_right"
    PANCREAS = "pancreas"
    SMALL_INTESTINE = "small_intestine"
    CORNEA = "cornea"


class Organ(Base):
    __tablename__ = "organs"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    donor_id = Column(String(36), ForeignKey("donors.id"), nullable=False)
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
            name="organ_type_enum",
        ),
        nullable=False,
    )
    blood_type = Column(String(10), nullable=False)
    hla_a = Column(String(50), nullable=True)
    hla_b = Column(String(50), nullable=True)
    hla_c = Column(String(50), nullable=True)
    hla_drb1 = Column(String(50), nullable=True)
    hla_dqb1 = Column(String(50), nullable=True)
    pra_level = Column(Float, nullable=True)
    viability_assessment = Column(String(200), nullable=True)
    viability_score = Column(Float, nullable=True)
    weight_grams = Column(Float, nullable=True)
    cold_ischemia_max_hours = Column(Float, nullable=True)
    warm_ischemia_minutes = Column(Float, nullable=True)
    match_locked = Column(Boolean, nullable=False, default=False)
    match_locked_at = Column(DateTime, nullable=True)
    matched_recipient_id = Column(String(36), nullable=True)
    retrieval_team_id = Column(String(36), ForeignKey("transport_teams.id"), nullable=True)
    retrieval_time = Column(DateTime, nullable=True)
    preserved_until = Column(DateTime, nullable=True)
    temperature_requirement = Column(String(100), nullable=True)
    preservation_solution = Column(String(100), nullable=True)
    status = Column(
        SAEnum(
            "available",
            "allocated",
            "retrieved",
            "in_transit",
            "delivered",
            "transplanted",
            "discarded",
            name="organ_status_enum",
        ),
        nullable=False,
        default="available",
    )
    discard_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    donor = relationship("Donor", back_populates="organs")
    match_results = relationship("MatchResult", back_populates="organ", lazy="selectin", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="organ", lazy="selectin")
    transports = relationship("Transport", back_populates="organ", lazy="selectin")
    retrieval_team = relationship("TransportTeam", back_populates="assigned_organs")
