from sqlalchemy import Column, String, Boolean, DateTime, Text, Enum as SAEnum
from datetime import datetime
import uuid

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    recipient_type = Column(
        SAEnum(
            "coordinator",
            "transplant_center",
            "transport_team",
            "regulator",
            name="notification_recipient_type",
        ),
        nullable=False,
    )
    recipient_id = Column(String(36), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    notification_type = Column(
        SAEnum(
            "donor_registered",
            "allocation_request",
            "transport_alert",
            "approval_progress",
            "followup_alert",
            "inventory_alert",
            "report_ready",
            name="notification_type",
        ),
        nullable=False,
    )
    reference_id = Column(String(36), nullable=True)
    reference_type = Column(String(50), nullable=True)
    is_read = Column(Boolean, default=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=datetime.utcnow)
