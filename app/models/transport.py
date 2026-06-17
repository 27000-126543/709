from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Transport(Base):
    __tablename__ = "transports"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    allocation_id = Column(String(36), ForeignKey("allocations.id"), nullable=False)
    organ_id = Column(String(36), ForeignKey("organs.id"), nullable=False)
    retrieval_task_id = Column(String(36), ForeignKey("retrieval_tasks.id"), nullable=True)
    transport_team_id = Column(String(36), ForeignKey("transport_teams.id"), nullable=True)
    transport_code = Column(String(50), nullable=True, unique=True)
    transport_mode = Column(
        SAEnum("ground", "air", "train", "mixed", name="transport_mode"),
        nullable=True,
    )
    origin_hospital = Column(String(200), nullable=False)
    origin_lat = Column(Float, nullable=True)
    origin_lng = Column(Float, nullable=True)
    origin_province = Column(String(50), nullable=True)
    origin_city = Column(String(50), nullable=True)
    destination_hospital = Column(String(200), nullable=False)
    destination_lat = Column(Float, nullable=True)
    destination_lng = Column(Float, nullable=True)
    destination_province = Column(String(50), nullable=True)
    destination_city = Column(String(50), nullable=True)
    estimated_distance_km = Column(Float, nullable=True)
    estimated_duration_min = Column(Integer, nullable=True)
    status = Column(
        SAEnum(
            "pending",
            "assigned",
            "in_progress",
            "delivered",
            "failed",
            "emergency",
            "cancelled",
            name="transport_status_enum",
        ),
        nullable=False,
        default="pending",
    )
    current_temperature = Column(Float, nullable=True)
    temperature_min = Column(Float, nullable=True)
    temperature_max = Column(Float, nullable=True)
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    departure_time = Column(DateTime, nullable=True)
    estimated_arrival = Column(DateTime, nullable=True)
    actual_arrival = Column(DateTime, nullable=True)
    received_by = Column(String(100), nullable=True)
    received_at = Column(DateTime, nullable=True)
    alert_triggered = Column(Boolean, default=False)
    alert_type = Column(String(100), nullable=True)
    alert_detail = Column(Text, nullable=True)
    emergency_plan_activated = Column(Boolean, default=False)
    emergency_plan_detail = Column(Text, nullable=True)
    emergency_plan_activated_at = Column(DateTime, nullable=True)
    route_deviation_km = Column(Float, default=0)
    delay_minutes = Column(Integer, default=0)
    delay_reason = Column(Text, nullable=True)
    container_id = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    allocation = relationship("Allocation", back_populates="transports")
    organ = relationship("Organ", back_populates="transports")
    retrieval_task = relationship("RetrievalTask", lazy="selectin")
    transport_team = relationship("TransportTeam", back_populates="transports")
    logs = relationship("TransportLog", back_populates="transport", lazy="selectin", cascade="all, delete-orphan")
    alerts = relationship("TransportAlert", back_populates="transport", lazy="selectin", cascade="all, delete-orphan")


class TransportLog(Base):
    __tablename__ = "transport_logs"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    transport_id = Column(String(36), ForeignKey("transports.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    event_type = Column(
        SAEnum(
            "status_change",
            "location_update",
            "temperature_update",
            "checkpoint",
            "note",
            "handover",
            name="transport_event_type",
        ),
        nullable=False,
    )
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    location_address = Column(String(500), nullable=True)
    temperature = Column(Float, nullable=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    checkpoint_name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    recorded_by = Column(String(100), nullable=True)
    recorded_by_id = Column(String(36), nullable=True)
    photo_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")

    transport = relationship("Transport", back_populates="logs")


class TransportAlert(Base):
    __tablename__ = "transport_alerts"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    transport_id = Column(String(36), ForeignKey("transports.id"), nullable=False)
    alert_code = Column(String(50), nullable=True)
    alert_type = Column(
        SAEnum(
            "temperature_high",
            "temperature_low",
            "delay_risk",
            "route_deviation",
            "device_offline",
            "container_opened",
            "other",
            name="transport_alert_type",
        ),
        nullable=False,
    )
    severity = Column(
        SAEnum("low", "medium", "high", "critical", name="alert_severity"),
        nullable=False,
        default="medium",
    )
    title = Column(String(200), nullable=False)
    detail = Column(Text, nullable=True)
    value_current = Column(String(100), nullable=True)
    value_threshold = Column(String(100), nullable=True)
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_by_id = Column(String(36), nullable=True)
    ack_note = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_note = Column(Text, nullable=True)
    emergency_action_taken = Column(Boolean, default=False)
    emergency_action_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transport = relationship("Transport", back_populates="alerts")
