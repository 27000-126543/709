from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    organ_id = Column(String(36), ForeignKey("organs.id"), nullable=False)
    donor_id = Column(String(36), ForeignKey("donors.id"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=False)
    total_score = Column(Float, nullable=False)
    blood_type_score = Column(Float, nullable=True)
    hla_score = Column(Float, nullable=True)
    pra_score = Column(Float, nullable=True)
    geography_score = Column(Float, nullable=True)
    urgency_score = Column(Float, nullable=True)
    waiting_time_score = Column(Float, nullable=True)
    age_score = Column(Float, nullable=True)
    other_score = Column(Float, nullable=True)
    rank = Column(Integer, nullable=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(36), nullable=True)
    match_status = Column(
        SAEnum("candidate", "shortlisted", "selected", "rejected", "expired", name="match_status"),
        nullable=False,
        default="candidate",
    )
    rejection_reason = Column(Text, nullable=True)
    run_id = Column(String(36), nullable=True)
    run_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organ = relationship("Organ", back_populates="match_results")
    recipient = relationship("Recipient", back_populates="match_results")
    donor = relationship("Donor", lazy="selectin")
    details = relationship("MatchDetail", back_populates="match_result", lazy="selectin", cascade="all, delete-orphan")


class MatchDetail(Base):
    __tablename__ = "match_details"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    match_result_id = Column(String(36), ForeignKey("match_results.id"), nullable=False)
    dimension = Column(String(50), nullable=False)
    sub_dimension = Column(String(100), nullable=True)
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    raw_value = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")

    match_result = relationship("MatchResult", back_populates="details")
