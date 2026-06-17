from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    report_date = Column(DateTime, nullable=False, unique=True)
    report_code = Column(String(100), nullable=True, unique=True)
    province = Column(String(50), nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String(100), nullable=True)
    generated_by_id = Column(String(36), nullable=True)
    status = Column(
        SAEnum("draft", "reviewed", "approved", "published", "archived", name="report_status"),
        nullable=False,
        default="draft",
    )
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    donor_registered_count = Column(Integer, nullable=False, default=0)
    donor_verified_count = Column(Integer, nullable=False, default=0)
    donor_rejected_count = Column(Integer, nullable=False, default=0)
    donor_organ_retrieved_count = Column(Integer, nullable=False, default=0)
    total_organs_retrieved = Column(Integer, nullable=False, default=0)
    organs_heart = Column(Integer, nullable=False, default=0)
    organs_liver = Column(Integer, nullable=False, default=0)
    organs_kidney_left = Column(Integer, nullable=False, default=0)
    organs_kidney_right = Column(Integer, nullable=False, default=0)
    organs_lung_left = Column(Integer, nullable=False, default=0)
    organs_lung_right = Column(Integer, nullable=False, default=0)
    organs_pancreas = Column(Integer, nullable=False, default=0)
    organs_small_intestine = Column(Integer, nullable=False, default=0)
    organs_cornea = Column(Integer, nullable=False, default=0)
    organs_discarded = Column(Integer, nullable=False, default=0)
    organs_discard_rate = Column(Float, nullable=True)
    match_runs_count = Column(Integer, nullable=False, default=0)
    match_candidates_generated = Column(Integer, nullable=False, default=0)
    allocation_requests_count = Column(Integer, nullable=False, default=0)
    allocation_provincial_approved = Column(Integer, nullable=False, default=0)
    allocation_national_approved = Column(Integer, nullable=False, default=0)
    allocation_rejected = Column(Integer, nullable=False, default=0)
    allocation_completed = Column(Integer, nullable=False, default=0)
    allocation_success_rate = Column(Float, nullable=True)
    approval_pending_provincial = Column(Integer, nullable=False, default=0)
    approval_pending_national = Column(Integer, nullable=False, default=0)
    approval_timeout_escalated = Column(Integer, nullable=False, default=0)
    approval_avg_time_minutes = Column(Float, nullable=True)
    transport_total = Column(Integer, nullable=False, default=0)
    transport_in_progress = Column(Integer, nullable=False, default=0)
    transport_completed = Column(Integer, nullable=False, default=0)
    transport_failed = Column(Integer, nullable=False, default=0)
    transport_ontime_count = Column(Integer, nullable=False, default=0)
    transport_on_time_rate = Column(Float, nullable=True)
    transport_alerts_count = Column(Integer, nullable=False, default=0)
    transport_emergency_activated = Column(Integer, nullable=False, default=0)
    transport_avg_duration_minutes = Column(Float, nullable=True)
    surgeries_scheduled = Column(Integer, nullable=False, default=0)
    surgeries_completed = Column(Integer, nullable=False, default=0)
    surgeries_failed = Column(Integer, nullable=False, default=0)
    surgeries_success_rate = Column(Float, nullable=True)
    surgeries_avg_duration_minutes = Column(Float, nullable=True)
    recipients_postop_icu = Column(Integer, nullable=False, default=0)
    recipients_discharged = Column(Integer, nullable=False, default=0)
    recipient_survival_30d = Column(Integer, nullable=True)
    recipient_survival_30d_rate = Column(Float, nullable=True)
    recipient_survival_90d = Column(Integer, nullable=True)
    recipient_survival_90d_rate = Column(Float, nullable=True)
    recipient_survival_1y = Column(Integer, nullable=True)
    recipient_survival_1y_rate = Column(Float, nullable=True)
    rejection_reports_count = Column(Integer, nullable=False, default=0)
    rejection_acute = Column(Integer, nullable=False, default=0)
    rejection_chronic = Column(Integer, nullable=False, default=0)
    followups_scheduled = Column(Integer, nullable=False, default=0)
    followups_completed = Column(Integer, nullable=False, default=0)
    followups_missed = Column(Integer, nullable=False, default=0)
    followup_alerts_count = Column(Integer, nullable=False, default=0)
    consumables_total_value = Column(Float, nullable=True)
    consumables_used_count = Column(Integer, nullable=False, default=0)
    consumables_low_stock_alerts = Column(Integer, nullable=False, default=0)
    consumables_out_of_stock = Column(Integer, nullable=False, default=0)
    replenishment_requests = Column(Integer, nullable=False, default=0)
    replenishment_approved = Column(Integer, nullable=False, default=0)
    waiting_list_total = Column(Integer, nullable=False, default=0)
    waiting_list_new = Column(Integer, nullable=False, default=0)
    waiting_list_removed = Column(Integer, nullable=False, default=0)
    waiting_list_avg_days = Column(Float, nullable=True)
    summary_highlights = Column(Text, nullable=True)
    issues_and_concerns = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transplant_center = relationship("TransplantCenter", back_populates="daily_reports")
    records = relationship("ReportRecord", back_populates="daily_report", lazy="selectin", cascade="all, delete-orphan")


class ReportRecord(Base):
    __tablename__ = "report_records"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    daily_report_id = Column(String(36), ForeignKey("daily_reports.id"), nullable=False)
    report_type = Column(
        SAEnum(
            "donor_summary",
            "organ_summary",
            "matching_summary",
            "allocation_summary",
            "approval_summary",
            "transport_summary",
            "surgery_summary",
            "survival_summary",
            "rejection_summary",
            "followup_summary",
            "consumable_summary",
            "waiting_list_summary",
            "custom",
            name="report_record_type",
        ),
        nullable=False,
    )
    title = Column(String(500), nullable=False)
    metric_name = Column(String(200), nullable=True)
    metric_value = Column(Float, nullable=True)
    metric_unit = Column(String(50), nullable=True)
    comparison_period = Column(String(100), nullable=True)
    previous_value = Column(Float, nullable=True)
    change_percentage = Column(Float, nullable=True)
    trend = Column(
        SAEnum("up", "down", "flat", "improving", "worsening", name="metric_trend"),
        nullable=True,
    )
    rank = Column(Integer, nullable=True)
    province = Column(String(50), nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    organ_type = Column(String(50), nullable=True)
    demographic_segment = Column(String(200), nullable=True)
    data_json = Column(Text, nullable=True)
    chart_type = Column(String(50), nullable=True)
    chart_config = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    interpretation = Column(Text, nullable=True)
    action_required = Column(Boolean, default=False)
    action_items = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")

    daily_report = relationship("DailyReport", back_populates="records")
    transplant_center = relationship("TransplantCenter", lazy="selectin")
