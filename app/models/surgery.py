from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Surgery(Base):
    __tablename__ = "surgeries"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    allocation_id = Column(String(36), ForeignKey("allocations.id"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=False)
    organ_id = Column(String(36), ForeignKey("organs.id"), nullable=False)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    surgery_code = Column(String(50), nullable=True, unique=True)
    surgeon_id = Column(String(36), nullable=True)
    surgeon_name = Column(String(100), nullable=True)
    anesthesiologist = Column(String(100), nullable=True)
    operating_room = Column(String(100), nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    surgery_date = Column(DateTime, nullable=True)
    surgery_start_time = Column(DateTime, nullable=True)
    surgery_end_time = Column(DateTime, nullable=True)
    warm_ischemia_minutes = Column(Float, nullable=True)
    total_duration_minutes = Column(Integer, nullable=True)
    anesthesia_type = Column(String(100), nullable=True)
    surgical_approach = Column(String(200), nullable=True)
    intraoperative_notes = Column(Text, nullable=True)
    complications = Column(Text, nullable=True)
    blood_loss_ml = Column(Float, nullable=True)
    transfusion_required = Column(Boolean, default=False)
    transfusion_details = Column(Text, nullable=True)
    surgery_status = Column(
        SAEnum(
            "scheduled",
            "preparing",
            "in_progress",
            "completed",
            "failed",
            "cancelled",
            name="surgery_status_enum",
        ),
        nullable=False,
        default="scheduled",
    )
    outcome = Column(
        SAEnum("successful", "partial", "failed", "pending", name="surgery_outcome"),
        nullable=True,
    )
    failure_reason = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    cancelled_by = Column(String(100), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    patient_transferred_to_icu = Column(Boolean, default=False)
    icu_admission_date = Column(DateTime, nullable=True)
    discharge_date = Column(DateTime, nullable=True)
    postop_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    allocation = relationship("Allocation", back_populates="surgeries")
    recipient = relationship("Recipient", back_populates="surgeries")
    organ = relationship("Organ", lazy="selectin")
    transplant_center = relationship("TransplantCenter", lazy="selectin")
    preop_checks = relationship("PreOpCheck", back_populates="surgery", lazy="selectin", cascade="all, delete-orphan")
    immunosuppressant_plans = relationship("ImmunosuppressantPlan", back_populates="surgery", lazy="selectin", cascade="all, delete-orphan")
    drug_monitorings = relationship("DrugMonitoring", back_populates="surgery", lazy="selectin", cascade="all, delete-orphan")
    rejection_alerts = relationship("RejectionAlert", back_populates="surgery", lazy="selectin", cascade="all, delete-orphan")
    followups = relationship("FollowUpRecord", back_populates="surgery", lazy="selectin")


class PreOpCheck(Base):
    __tablename__ = "pre_op_checks"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=False)
    check_type = Column(
        SAEnum(
            "blood",
            "cardiac",
            "pulmonary",
            "renal",
            "hepatic",
            "infectious",
            "imaging",
            "other",
            name="preop_check_type",
        ),
        nullable=False,
    )
    check_name = Column(String(200), nullable=False)
    performed_at = Column(DateTime, nullable=True)
    result = Column(Text, nullable=True)
    result_value = Column(String(200), nullable=True)
    reference_range = Column(String(200), nullable=True)
    unit = Column(String(50), nullable=True)
    status = Column(
        SAEnum(
            "pending",
            "passed",
            "failed",
            "abnormal",
            "recheck_required",
            name="preop_check_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    abnormal_flags = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    requires_recheck = Column(Boolean, default=False)
    recheck_date = Column(DateTime, nullable=True)
    recheck_result = Column(Text, nullable=True)
    checked_by = Column(String(100), nullable=True)
    report_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    surgery = relationship("Surgery", back_populates="preop_checks")


class ImmunosuppressantPlan(Base):
    __tablename__ = "immunosuppressant_plans"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=True)
    phase = Column(
        SAEnum("induction", "maintenance", "rejection_treatment", "tapering", name="immuno_phase"),
        nullable=False,
    )
    drug_name = Column(String(200), nullable=False)
    drug_generic_name = Column(String(200), nullable=True)
    drug_class = Column(String(100), nullable=True)
    dose = Column(Float, nullable=False)
    dose_unit = Column(String(50), nullable=False)
    route = Column(String(50), nullable=True)
    frequency = Column(String(100), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    duration_days = Column(Integer, nullable=True)
    prescribing_doctor = Column(String(100), nullable=True)
    prescribing_doctor_id = Column(String(36), nullable=True)
    approved = Column(Boolean, default=False)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    adjustment_history = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    surgery = relationship("Surgery", back_populates="immunosuppressant_plans")
    recipient = relationship("Recipient", lazy="selectin")
    drug_monitorings = relationship("DrugMonitoring", back_populates="plan", lazy="selectin")


class DrugMonitoring(Base):
    __tablename__ = "drug_monitorings"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=False)
    plan_id = Column(String(36), ForeignKey("immunosuppressant_plans.id"), nullable=True)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=True)
    drug_name = Column(String(200), nullable=False)
    test_date = Column(DateTime, nullable=False)
    concentration_level = Column(Float, nullable=True)
    concentration_unit = Column(String(50), nullable=True)
    target_min = Column(Float, nullable=True)
    target_max = Column(Float, nullable=True)
    level = Column(
        SAEnum("subtherapeutic", "therapeutic", "supratherapeutic", "toxic", name="drug_level"),
        nullable=True,
    )
    dose_given = Column(Float, nullable=True)
    dose_unit = Column(String(50), nullable=True)
    last_dose_time = Column(DateTime, nullable=True)
    sample_type = Column(String(100), nullable=True)
    test_method = Column(String(100), nullable=True)
    lab_name = Column(String(200), nullable=True)
    result_note = Column(Text, nullable=True)
    dose_advised = Column(Text, nullable=True)
    adjustment_made = Column(Boolean, default=False)
    adjustment_detail = Column(Text, nullable=True)
    adjusted_by = Column(String(100), nullable=True)
    adjusted_at = Column(DateTime, nullable=True)
    abnormal = Column(Boolean, default=False)
    alert_triggered = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    surgery = relationship("Surgery", back_populates="drug_monitorings")
    plan = relationship("ImmunosuppressantPlan", back_populates="drug_monitorings")
    recipient = relationship("Recipient", lazy="selectin")


class RejectionAlert(Base):
    __tablename__ = "rejection_alerts"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=True)
    alert_code = Column(String(50), nullable=True)
    rejection_type = Column(
        SAEnum(
            "hyperacute",
            "accelerated",
            "acute_cellular",
            "acute_antibody_mediated",
            "chronic",
            "suspicious",
            name="rejection_type",
        ),
        nullable=False,
    )
    severity = Column(
        SAEnum("mild", "moderate", "severe", "critical", name="rejection_severity"),
        nullable=False,
        default="moderate",
    )
    suspected_date = Column(DateTime, nullable=False)
    confirmed_date = Column(DateTime, nullable=True)
    confirmed = Column(Boolean, default=False)
    biopsy_done = Column(Boolean, default=False)
    biopsy_result = Column(Text, nullable=True)
    biopsy_report_url = Column(String(500), nullable=True)
    symptoms = Column(Text, nullable=True)
    lab_findings = Column(Text, nullable=True)
    imaging_findings = Column(Text, nullable=True)
    banff_grade = Column(String(50), nullable=True)
    treatment_given = Column(Text, nullable=True)
    treatment_response = Column(
        SAEnum("excellent", "good", "partial", "poor", "none", "pending", name="treatment_response"),
        nullable=True,
    )
    current_status = Column(
        SAEnum("investigating", "treated", "resolving", "resolved", "progressing", "chronic", name="rejection_status"),
        nullable=False,
        default="investigating",
    )
    outcome = Column(Text, nullable=True)
    reported_by = Column(String(100), nullable=True)
    reported_by_id = Column(String(36), nullable=True)
    attending_physician = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    surgery = relationship("Surgery", back_populates="rejection_alerts")
    recipient = relationship("Recipient", lazy="selectin")
