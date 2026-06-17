from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Donor(Base):
    __tablename__ = "donors"

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
    health_status = Column(
        SAEnum("qualified", "conditional", "disqualified", name="donor_health_status"),
        nullable=True,
        default="qualified",
    )
    health_check_detail = Column(Text, nullable=True)
    family_consent = Column(Boolean, default=False)
    consent_document_url = Column(String(500), nullable=True)
    consent_verified = Column(Boolean, default=False)
    consent_notes = Column(Text, nullable=True)
    hospital = Column(String(200), nullable=True)
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    address_detail = Column(String(500), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_name = Column(String(100), nullable=True)
    coordinator_id = Column(String(36), ForeignKey("coordinators.id"), nullable=True)
    status = Column(
        SAEnum(
            "registered",
            "verified",
            "rejected",
            "organ_retrieved",
            "closed",
            name="donor_status",
        ),
        nullable=False,
        default="registered",
    )
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    consents = relationship("DonorConsent", back_populates="donor", lazy="selectin", cascade="all, delete-orphan")
    health_checks = relationship("DonorHealthCheck", back_populates="donor", lazy="selectin", cascade="all, delete-orphan")
    organs = relationship("Organ", back_populates="donor", lazy="selectin", cascade="all, delete-orphan")
    coordinator = relationship("Coordinator", back_populates="donors")


class DonorConsent(Base):
    __tablename__ = "donor_consents"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    donor_id = Column(String(36), ForeignKey("donors.id"), nullable=False)
    family_consent_given = Column(Boolean, default=False)
    consent_document_url = Column(String(500), nullable=True)
    consent_verified = Column(Boolean, default=False)
    consent_notes = Column(Text, nullable=True)
    consent_date = Column(DateTime, nullable=True)
    witness_name = Column(String(100), nullable=True)
    witness_contact = Column(String(20), nullable=True)
    relationship_to_donor = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    donor = relationship("Donor", back_populates="consents")


class DonorHealthCheck(Base):
    __tablename__ = "donor_health_checks"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    donor_id = Column(String(36), ForeignKey("donors.id"), nullable=False)
    check_date = Column(DateTime, nullable=False)
    overall_status = Column(
        SAEnum("qualified", "conditional", "disqualified", name="health_overall_status"),
        nullable=False,
        default="qualified",
    )
    hiv = Column(Boolean, nullable=False, default=False)
    hepatitis_b = Column(Boolean, nullable=False, default=False)
    hepatitis_c = Column(Boolean, nullable=False, default=False)
    syphilis = Column(Boolean, nullable=False, default=False)
    tbb = Column(Boolean, nullable=False, default=False)
    heart_function = Column(String(200), nullable=True)
    liver_function = Column(String(200), nullable=True)
    kidney_function = Column(String(200), nullable=True)
    lung_function = Column(String(200), nullable=True)
    other_infectious = Column(Text, nullable=True)
    additional_notes = Column(Text, nullable=True)
    checked_by = Column(String(100), nullable=True)
    report_document_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    donor = relationship("Donor", back_populates="health_checks")
