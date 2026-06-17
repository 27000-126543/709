from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class TransplantCenter(Base):
    __tablename__ = "transplant_centers"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    center_code = Column(String(50), nullable=True, unique=True)
    name = Column(String(300), nullable=False)
    short_name = Column(String(100), nullable=True)
    type = Column(
        SAEnum(
            "general_hospital",
            "specialized_hospital",
            "university_hospital",
            "provincial_center",
            "national_center",
            name="center_type",
        ),
        nullable=True,
    )
    level = Column(
        SAEnum("primary", "secondary", "tertiary", "national", "provincial", "regional", name="center_level"),
        nullable=True,
    )
    license_number = Column(String(100), nullable=True)
    license_expiry = Column(DateTime, nullable=True)
    accredited = Column(Boolean, nullable=False, default=False)
    accreditation_date = Column(DateTime, nullable=True)
    accreditation_expiry = Column(DateTime, nullable=True)
    accreditation_body = Column(String(200), nullable=True)
    organ_transplant_approved = Column(Boolean, nullable=False, default=False)
    approved_organ_types = Column(Text, nullable=True)
    transplant_capacity_annual = Column(Integer, nullable=True)
    icu_beds = Column(Integer, nullable=True)
    operating_rooms = Column(Integer, nullable=True)
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    district = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    postal_code = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    contact_person = Column(String(100), nullable=True)
    contact_title = Column(String(100), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(200), nullable=True)
    emergency_phone = Column(String(20), nullable=True)
    hotline = Column(String(20), nullable=True)
    website = Column(String(300), nullable=True)
    director_name = Column(String(100), nullable=True)
    director_title = Column(String(100), nullable=True)
    director_phone = Column(String(20), nullable=True)
    transplant_team_leader = Column(String(100), nullable=True)
    transplant_team_size = Column(Integer, nullable=True)
    certification_status = Column(
        SAEnum("active", "pending_renewal", "suspended", "revoked", "expired", name="center_certification"),
        nullable=False,
        default="active",
    )
    last_audit_date = Column(DateTime, nullable=True)
    next_audit_date = Column(DateTime, nullable=True)
    audit_findings = Column(Text, nullable=True)
    quality_rating = Column(Integer, nullable=True)
    transplant_success_rate = Column(Float, nullable=True)
    total_transplants = Column(Integer, nullable=True)
    one_year_survival_rate = Column(Float, nullable=True)
    five_year_survival_rate = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(
        SAEnum("active", "inactive", "under_review", "suspended", name="center_status"),
        nullable=False,
        default="active",
    )
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recipients = relationship("Recipient", back_populates="transplant_center", lazy="selectin")
    waiting_lists = relationship("WaitingList", back_populates="transplant_center", lazy="selectin")
    allocations = relationship("Allocation", back_populates="transplant_center", lazy="selectin")
    consumables = relationship("Consumable", back_populates="transplant_center", lazy="selectin")
    replenishment_requests = relationship("ReplenishmentRequest", back_populates="transplant_center", lazy="selectin")
    coordinators = relationship("Coordinator", back_populates="transplant_center", lazy="selectin", cascade="all, delete-orphan")
    retrieval_teams = relationship("RetrievalTeam", back_populates="transplant_center", lazy="selectin")
    transport_teams = relationship("TransportTeam", back_populates="transplant_center", lazy="selectin")
    daily_reports = relationship("DailyReport", back_populates="transplant_center", lazy="selectin")
    user_notifications = relationship("UserNotification", back_populates="transplant_center", lazy="selectin")


class Coordinator(Base):
    __tablename__ = "coordinators"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    employee_id = Column(String(50), nullable=True, unique=True)
    username = Column(String(100), nullable=True, unique=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=True)
    title = Column(String(100), nullable=True)
    specialty = Column(String(200), nullable=True)
    license_number = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    mobile = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
    wechat_id = Column(String(100), nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)
    department = Column(String(200), nullable=True)
    role = Column(
        SAEnum(
            "donor_coordinator",
            "recipient_coordinator",
            "allocation_coordinator",
            "transport_coordinator",
            "surgery_coordinator",
            "followup_coordinator",
            "administrator",
            "super_coordinator",
            name="coordinator_role",
        ),
        nullable=False,
        default="donor_coordinator",
    )
    permissions = Column(Text, nullable=True)
    certified = Column(Boolean, nullable=False, default=False)
    certification_date = Column(DateTime, nullable=True)
    certification_expiry = Column(DateTime, nullable=True)
    training_hours = Column(Float, nullable=True)
    years_of_experience = Column(Float, nullable=True)
    total_donors_handled = Column(Integer, nullable=True)
    total_recipients_handled = Column(Integer, nullable=True)
    success_rate = Column(Float, nullable=True)
    on_duty = Column(Boolean, nullable=False, default=True)
    duty_status = Column(
        SAEnum("on_duty", "off_duty", "leave", "busy", "available", name="coordinator_duty"),
        nullable=False,
        default="available",
    )
    current_location_lat = Column(Float, nullable=True)
    current_location_lng = Column(String(200), nullable=True)
    last_checkin = Column(DateTime, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    status = Column(
        SAEnum("active", "inactive", "suspended", "terminated", name="coordinator_status"),
        nullable=False,
        default="active",
    )
    hire_date = Column(DateTime, nullable=True)
    termination_date = Column(DateTime, nullable=True)
    termination_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transplant_center = relationship("TransplantCenter", back_populates="coordinators")
    donors = relationship("Donor", back_populates="coordinator", lazy="selectin")
    notifications = relationship("UserNotification", back_populates="coordinator", lazy="selectin")


class Regulator(Base):
    __tablename__ = "regulators"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    employee_id = Column(String(50), nullable=True, unique=True)
    username = Column(String(100), nullable=True, unique=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=True)
    title = Column(String(100), nullable=True)
    department = Column(String(200), nullable=True)
    organization = Column(String(300), nullable=True)
    level = Column(
        SAEnum("national", "provincial", "municipal", "district", name="regulator_level"),
        nullable=False,
        default="provincial",
    )
    jurisdiction_province = Column(String(50), nullable=True)
    jurisdiction_cities = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    mobile = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
    office_address = Column(String(500), nullable=True)
    role = Column(
        SAEnum(
            "provincial_approver",
            "national_approver",
            "auditor",
            "inspector",
            "policy_maker",
            "administrator",
            "super_admin",
            name="regulator_role",
        ),
        nullable=False,
        default="provincial_approver",
    )
    permissions = Column(Text, nullable=True)
    approval_limit = Column(
        SAEnum("provincial_only", "national_only", "all", "none", name="approval_limit"),
        nullable=True,
    )
    max_concurrent_approvals = Column(Integer, nullable=True)
    current_pending_approvals = Column(Integer, nullable=True)
    approved_count = Column(Integer, nullable=True)
    rejected_count = Column(Integer, nullable=True)
    avg_approval_time_minutes = Column(Float, nullable=True)
    escalation_count = Column(Integer, nullable=True)
    certified = Column(Boolean, nullable=False, default=False)
    certification_date = Column(DateTime, nullable=True)
    on_duty = Column(Boolean, nullable=False, default=True)
    duty_status = Column(
        SAEnum("on_duty", "off_duty", "leave", "busy", "available", name="regulator_duty"),
        nullable=False,
        default="available",
    )
    substitute_approver_id = Column(String(36), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    status = Column(
        SAEnum("active", "inactive", "suspended", "terminated", name="regulator_status"),
        nullable=False,
        default="active",
    )
    hire_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TransportTeam(Base):
    __tablename__ = "transport_teams"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    team_code = Column(String(50), nullable=True, unique=True)
    team_name = Column(String(200), nullable=False)
    type = Column(
        SAEnum("ground", "air", "train", "mixed", "dedicated", name="transport_team_type"),
        nullable=False,
        default="ground",
    )
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    base_province = Column(String(50), nullable=True)
    base_city = Column(String(50), nullable=True)
    base_address = Column(String(500), nullable=True)
    base_lat = Column(Float, nullable=True)
    base_lng = Column(Float, nullable=True)
    coverage_area = Column(Text, nullable=True)
    leader_name = Column(String(100), nullable=False)
    leader_phone = Column(String(20), nullable=False)
    leader_id = Column(String(36), nullable=True)
    deputy_leader_name = Column(String(100), nullable=True)
    deputy_leader_phone = Column(String(20), nullable=True)
    contact_email = Column(String(200), nullable=True)
    emergency_contact = Column(String(20), nullable=True)
    members = Column(Text, nullable=True)
    total_members = Column(Integer, nullable=True)
    drivers_count = Column(Integer, nullable=True)
    medical_staff_count = Column(Integer, nullable=True)
    logistics_staff_count = Column(Integer, nullable=True)
    vehicles = Column(Text, nullable=True)
    vehicle_count = Column(Integer, nullable=True)
    equipment = Column(Text, nullable=True)
    specialized_equipment = Column(Text, nullable=True)
    has_cold_chain = Column(Boolean, nullable=False, default=True)
    cold_chain_capacity = Column(String(100), nullable=True)
    max_distance_km = Column(Float, nullable=True)
    avg_response_time_minutes = Column(Float, nullable=True)
    avg_trip_duration_minutes = Column(Float, nullable=True)
    total_trips = Column(Integer, nullable=True)
    successful_trips = Column(Integer, nullable=True)
    on_time_rate = Column(Float, nullable=True)
    safety_rating = Column(Float, nullable=True)
    certified = Column(Boolean, nullable=False, default=False)
    certification_date = Column(DateTime, nullable=True)
    certification_expiry = Column(DateTime, nullable=True)
    insurance_valid_until = Column(DateTime, nullable=True)
    status = Column(
        SAEnum("available", "on_duty", "resting", "maintenance", "disabled", name="transport_team_status"),
        nullable=False,
        default="available",
    )
    current_location_lat = Column(Float, nullable=True)
    current_location_lng = Column(Float, nullable=True)
    current_location_address = Column(String(500), nullable=True)
    last_updated_location = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transplant_center = relationship("TransplantCenter", back_populates="transport_teams")
    assigned_organs = relationship("Organ", back_populates="retrieval_team", lazy="selectin")
    transports = relationship("Transport", back_populates="transport_team", lazy="selectin")


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    notification_code = Column(String(100), nullable=True, unique=True)
    recipient_type = Column(
        SAEnum(
            "coordinator",
            "transplant_center",
            "transport_team",
            "regulator",
            "surgeon",
            "admin",
            "all_staff",
            name="notification_recipient_type_enum",
        ),
        nullable=False,
    )
    recipient_id = Column(String(36), nullable=True)
    coordinator_id = Column(String(36), ForeignKey("coordinators.id"), nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    transport_team_id = Column(String(36), ForeignKey("transport_teams.id"), nullable=True)
    regulator_id = Column(String(36), ForeignKey("regulators.id"), nullable=True)
    channel = Column(
        SAEnum("in_app", "sms", "email", "wechat", "push", "phone", "all", name="notification_channel"),
        nullable=False,
        default="in_app",
    )
    notification_type = Column(
        SAEnum(
            "donor_registered",
            "donor_verified",
            "donor_rejected",
            "allocation_request",
            "allocation_approved",
            "allocation_rejected",
            "allocation_escalated",
            "approval_pending",
            "approval_urgent",
            "approval_timeout_approaching",
            "transport_started",
            "transport_alert",
            "transport_delivered",
            "transport_emergency",
            "surgery_scheduled",
            "surgery_completed",
            "rejection_suspected",
            "followup_due",
            "followup_alert",
            "inventory_low",
            "inventory_critical",
            "replenishment_approved",
            "report_ready",
            "system_announcement",
            "custom",
            name="notification_type_enum",
        ),
        nullable=False,
    )
    priority = Column(
        SAEnum("low", "normal", "high", "urgent", "critical", name="notification_priority"),
        nullable=False,
        default="normal",
    )
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    short_summary = Column(String(300), nullable=True)
    reference_id = Column(String(36), nullable=True)
    reference_type = Column(String(50), nullable=True)
    reference_url = Column(String(500), nullable=True)
    action_required = Column(Boolean, default=False)
    action_type = Column(String(100), nullable=True)
    action_url = Column(String(500), nullable=True)
    action_deadline = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    sent_status = Column(
        SAEnum("pending", "queued", "sending", "sent", "delivered", "failed", "cancelled", name="notification_sent_status"),
        nullable=False,
        default="pending",
    )
    failed_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_retry_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    ack_note = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_expired = Column(Boolean, default=False)
    created_by = Column(String(100), nullable=True)
    created_by_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    coordinator = relationship("Coordinator", back_populates="notifications")
    transplant_center = relationship("TransplantCenter", back_populates="user_notifications")
    transport_team = relationship("TransportTeam", lazy="selectin")
    regulator = relationship("Regulator", lazy="selectin")
