from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Consumable(Base):
    __tablename__ = "consumables"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    sku = Column(String(100), nullable=True, unique=True)
    name = Column(String(200), nullable=False)
    generic_name = Column(String(200), nullable=True)
    category = Column(
        SAEnum(
            "surgical",
            "preservation",
            "testing",
            "immunosuppressant",
            "antibiotic",
            "anesthesia",
            "consumable_general",
            "equipment",
            "other",
            name="consumable_category_enum",
        ),
        nullable=False,
    )
    subcategory = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    manufacturer = Column(String(200), nullable=True)
    supplier = Column(String(200), nullable=True)
    unit = Column(String(50), nullable=False)
    unit_price = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True, default="CNY")
    stock_quantity = Column(Integer, nullable=False, default=0)
    safety_stock_level = Column(Integer, nullable=False, default=0)
    reorder_point = Column(Integer, nullable=True)
    reorder_quantity = Column(Integer, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    batch_number = Column(String(100), nullable=True)
    location_rack = Column(String(100), nullable=True)
    location_bin = Column(String(100), nullable=True)
    storage_condition = Column(String(200), nullable=True)
    temperature_min = Column(Float, nullable=True)
    temperature_max = Column(Float, nullable=True)
    requires_refrigeration = Column(Boolean, default=False)
    controlled_substance = Column(Boolean, default=False)
    status = Column(
        SAEnum(
            "in_stock",
            "low_stock",
            "out_of_stock",
            "critical",
            "replenishing",
            "discontinued",
            "expired",
            name="consumable_status_enum",
        ),
        nullable=False,
        default="in_stock",
    )
    image_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transplant_center = relationship("TransplantCenter", back_populates="consumables")
    transactions = relationship("ConsumableTransaction", back_populates="consumable", lazy="selectin", cascade="all, delete-orphan")
    replenishment_requests = relationship("ReplenishmentRequest", back_populates="consumable", lazy="selectin")
    outbound_quotas = relationship("OutboundQuota", back_populates="consumable", lazy="selectin", cascade="all, delete-orphan")


class ConsumableTransaction(Base):
    __tablename__ = "consumable_transactions"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    consumable_id = Column(String(36), ForeignKey("consumables.id"), nullable=False)
    transaction_code = Column(String(100), nullable=True, unique=True)
    transaction_type = Column(
        SAEnum(
            "inbound",
            "outbound",
            "adjustment",
            "transfer_in",
            "transfer_out",
            "return",
            "disposal",
            "expired_removal",
            name="consumable_transaction_type",
        ),
        nullable=False,
    )
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)
    stock_before = Column(Integer, nullable=True)
    stock_after = Column(Integer, nullable=True)
    reference_id = Column(String(36), nullable=True)
    reference_type = Column(String(100), nullable=True)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=True)
    allocation_id = Column(String(36), ForeignKey("allocations.id"), nullable=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    department = Column(String(200), nullable=True)
    recipient = Column(String(200), nullable=True)
    recipient_id = Column(String(36), nullable=True)
    batch_number = Column(String(100), nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=True)
    performed_by_id = Column(String(36), nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_by_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    transaction_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")

    consumable = relationship("Consumable", back_populates="transactions")
    surgery = relationship("Surgery", lazy="selectin")
    allocation = relationship("Allocation", lazy="selectin")
    transplant_center = relationship("TransplantCenter", lazy="selectin")


class ReplenishmentRequest(Base):
    __tablename__ = "replenishment_requests"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    consumable_id = Column(String(36), ForeignKey("consumables.id"), nullable=False)
    request_code = Column(String(100), nullable=True, unique=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    requested_quantity = Column(Integer, nullable=False)
    current_stock = Column(Integer, nullable=True)
    safety_stock = Column(Integer, nullable=True)
    urgency_level = Column(
        SAEnum("routine", "urgent", "emergency", name="replenishment_urgency"),
        nullable=False,
        default="routine",
    )
    expected_delivery_date = Column(DateTime, nullable=True)
    supplier = Column(String(200), nullable=True)
    supplier_contact = Column(String(100), nullable=True)
    estimated_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True, default="CNY")
    status = Column(
        SAEnum(
            "draft",
            "submitted",
            "under_review",
            "approved",
            "rejected",
            "ordered",
            "shipped",
            "received",
            "cancelled",
            "partially_received",
            name="replenishment_status_enum",
        ),
        nullable=False,
        default="draft",
    )
    requested_by = Column(String(100), nullable=True)
    requested_by_id = Column(String(36), nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_by_id = Column(String(36), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)
    approved_by_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_by = Column(String(100), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    order_date = Column(DateTime, nullable=True)
    tracking_number = Column(String(100), nullable=True)
    shipping_method = Column(String(100), nullable=True)
    shipped_date = Column(DateTime, nullable=True)
    received_date = Column(DateTime, nullable=True)
    received_quantity = Column(Integer, nullable=True, default=0)
    received_by = Column(String(100), nullable=True)
    quality_check_passed = Column(Boolean, default=True)
    quality_issues = Column(Text, nullable=True)
    invoice_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    consumable = relationship("Consumable", back_populates="replenishment_requests")
    transplant_center = relationship("TransplantCenter", back_populates="replenishment_requests")


class OutboundQuota(Base):
    __tablename__ = "outbound_quotas"

    id = Column(String(36), primary_key=True, default=lambda: uuid.uuid4().hex)
    consumable_id = Column(String(36), ForeignKey("consumables.id"), nullable=False)
    quota_code = Column(String(100), nullable=True, unique=True)
    transplant_center_id = Column(String(36), ForeignKey("transplant_centers.id"), nullable=True)
    department = Column(String(200), nullable=True)
    period_type = Column(
        SAEnum("daily", "weekly", "monthly", "quarterly", "yearly", "per_surgery", name="quota_period"),
        nullable=False,
    )
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    allocation_id = Column(String(36), ForeignKey("allocations.id"), nullable=True)
    surgery_id = Column(String(36), ForeignKey("surgeries.id"), nullable=True)
    allocated_quantity = Column(Integer, nullable=False)
    used_quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, nullable=False, default=0)
    available_quantity = Column(Integer, nullable=False)
    locked = Column(Boolean, default=False)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(36), nullable=True)
    lock_reason = Column(Text, nullable=True)
    allocation_basis = Column(Text, nullable=True)
    approval_required = Column(Boolean, default=True)
    approved_by = Column(String(100), nullable=True)
    approved_by_id = Column(String(36), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_by_id = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(
        SAEnum("active", "exhausted", "expired", "revoked", "completed", name="outbound_quota_status"),
        nullable=False,
        default="active",
    )
    created_at = Column(DateTime, default=datetime.utcnow, server_default="now()")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    consumable = relationship("Consumable", back_populates="outbound_quotas")
    transplant_center = relationship("TransplantCenter", lazy="selectin")
    allocation = relationship("Allocation", lazy="selectin")
    surgery = relationship("Surgery", lazy="selectin")
