from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class FollowUpRecord(Base):
    __tablename__ = "follow_up_records"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=False)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    record_code = Column(String(50), nullable=True, unique=True)
    followup_date = Column(DateTime, nullable=False)
    scheduled_date = Column(DateTime, nullable=True)
    actual_date = Column(DateTime, nullable=True)
    visit_type = Column(
        SAEnum(
            "in_person",
            "telemedicine",
            "phone",
            "home_visit",
            "hospital_admission",
            "emergency",
            name="visit_type",
        ),
        nullable=False,
        default="in_person",
    )
    followup_type = Column(
        SAEnum(
            "one_week",
            "one_month",
            "three_months",
            "six_months",
            "one_year",
            "annual",
            "bi_annual",
            "as_needed",
            "special",
            "emergency",
            name="followup_type_enum",
        ),
        nullable=False,
        default="one_month",
    )
    followup_visit_number = Column(Integer, nullable=True)
    days_post_transplant = Column(Integer, nullable=True)
    patient_weight_kg = Column(Float, nullable=True)
    patient_bp_systolic = Column(Integer, nullable=True)
    patient_bp_diastolic = Column(Integer, nullable=True)
    heart_rate = Column(Integer, nullable=True)
    temperature = Column(Float, nullable=True)
    organ_function_indicator = Column(String(200), nullable=True)
    organ_function_value = Column(Float, nullable=True)
    organ_function_unit = Column(String(50), nullable=True)
    organ_function_status = Column(
        SAEnum("normal", "mild_abnormal", "moderate_abnormal", "severe_abnormal", name="organ_function_status"),
        nullable=True,
    )
    lab_data = Column(Text, nullable=True)
    imaging_data = Column(Text, nullable=True)
    biopsy_data = Column(Text, nullable=True)
    data = Column(Text, nullable=True)
    immunosuppressant_dosage = Column(Text, nullable=True)
    drug_levels = Column(Text, nullable=True)
    adverse_events = Column(Text, nullable=True)
    complications = Column(Text, nullable=True)
    abnormal_flags = Column(Text, nullable=True)
    overall_status = Column(
        SAEnum("excellent", "good", "fair", "poor", "critical", name="followup_overall_status"),
        nullable=True,
    )
    alert_triggered = Column(Boolean, default=False)
    alert_details = Column(Text, nullable=True)
    referral_required = Column(Boolean, default=False)
    referral_details = Column(Text, nullable=True)
    readmission_required = Column(Boolean, default=False)
    readmission_details = Column(Text, nullable=True)
    next_scheduled_date = Column(DateTime, nullable=True)
    next_followup_type = Column(String(100), nullable=True)
    doctor_id = Column(String(36), nullable=True)
    doctor_name = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    patient_report = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recipient = relationship("Recipient", back_populates="followups")
    surgery = relationship("Surgery", back_populates="followups")
    transplant_center = relationship("TransplantCenter", lazy="selectin")
    alerts = relationship("FollowUpAlert", back_populates="record", lazy="selectin", cascade="all, delete-orphan")


class FollowUpAlert(Base):
    __tablename__ = "follow_up_alerts"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    record_id = Column(String(36), ForeignKey("follow_up_records.id"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("recipients.id"), nullable=False)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=True)
    alert_code = Column(String(50), nullable=True)
    alert_type = Column(
        SAEnum(
            "lab_abnormal",
            "organ_dysfunction",
            "rejection_suspected",
            "drug_toxicity",
            "infection",
            "missed_followup",
            "non_compliance",
            "adverse_event",
            "complication",
            "other",
            name="followup_alert_type",
        ),
        nullable=False,
    )
    severity = Column(
        SAEnum("low", "medium", "high", "critical", name="followup_alert_severity"),
        nullable=False,
        default="medium",
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    affected_parameter = Column(String(200), nullable=True)
    current_value = Column(String(100), nullable=True)
    normal_range = Column(String(100), nullable=True)
    unit = Column(String(50), nullable=True)
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_by_id = Column(String(36), nullable=True)
    ack_note = Column(Text, nullable=True)
    intervention_required = Column(Boolean, default=False)
    intervention_done = Column(Boolean, default=False)
    intervention_detail = Column(Text, nullable=True)
    intervention_date = Column(DateTime, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_note = Column(Text, nullable=True)
    patient_notified = Column(Boolean, default=False)
    patient_notified_at = Column(DateTime, nullable=True)
    escalation_required = Column(Boolean, default=False)
    escalated_to = Column(String(100), nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    record = relationship("FollowUpRecord", back_populates="alerts")
    recipient = relationship("Recipient", lazy="selectin")
    surgery = relationship("Surgery", lazy="selectin")


FollowUp = FollowUpRecord
