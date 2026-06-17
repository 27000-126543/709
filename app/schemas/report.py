from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any, List, Dict
from datetime import date, datetime
from enum import Enum


class ReportType(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    custom = "custom"


class ExportFormat(str, Enum):
    excel = "excel"
    pdf = "pdf"
    csv = "csv"


class DailyReportStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    new_donor_count: int = 0
    donor_approved_count: int = 0
    new_organ_count: int = 0
    organ_available_count: int = 0
    new_recipient_count: int = 0
    waiting_list_count: int = 0
    allocation_request_count: int = 0
    allocation_approved_count: int = 0
    transplant_count: int = 0
    transport_count: int = 0
    transport_on_time_count: int = 0
    transport_alert_count: int = 0
    followup_count: int = 0
    followup_alert_count: int = 0
    consumable_low_stock_count: int = 0
    approval_pending_count: int = 0


class DailyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_date: date
    report_type: ReportType = ReportType.daily
    generated_at: datetime
    province: Optional[str] = None
    transplant_center_id: Optional[str] = None
    stats: DailyReportStats
    organ_distribution: Optional[dict[str, int]] = None
    urgency_distribution: Optional[dict[str, int]] = None
    notes: Optional[str] = None


class ReportExportRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_type: ReportType
    start_date: date
    end_date: date
    export_format: ExportFormat = ExportFormat.excel
    province: Optional[str] = Field(None, max_length=50)
    transplant_center_id: Optional[str] = Field(None, max_length=36)
    include_charts: bool = True
    include_raw_data: bool = False
    requested_by: str = Field(..., max_length=36)


class ReportQuery(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_type: ReportType = ReportType.daily
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    province: Optional[str] = Field(None, max_length=50)
    transplant_center_id: Optional[str] = Field(None, max_length=36)


class ReportData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    province: Optional[str] = None
    transplant_center_id: Optional[str] = None
    transplant_center_name: Optional[str] = None
    donation_count: int = 0
    allocation_success_rate: float = 0.0
    transport_on_time_rate: float = 0.0
    recipient_survival_rate: float = 0.0
    consumable_consumption: Optional[Dict[str, Any]] = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_date: date
    generated_at: datetime
    data: List[ReportData]
