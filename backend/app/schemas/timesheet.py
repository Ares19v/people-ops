from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.models.timesheet import TimesheetStatus

class ProjectResponse(BaseModel):
    id: str
    name: str
    code: str
    client_name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class TimesheetEntryCreate(BaseModel):
    project_id: str
    task_name: str = Field(..., min_length=2, max_length=200)
    entry_date: date
    hours: float = Field(..., gt=0.0, le=16.0)
    is_billable: bool = True
    notes: Optional[str] = Field(None, max_length=1000)

class TimesheetEntryResponse(BaseModel):
    id: str
    user_id: str
    employee_name: Optional[str] = None
    project_id: str
    project_name: Optional[str] = None
    task_name: str
    entry_date: date
    hours: float
    is_billable: bool
    notes: Optional[str] = None
    status: TimesheetStatus
    approver_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TimesheetDecisionRequest(BaseModel):
    entry_ids: List[str]
    decision: str = Field(..., pattern="^(APPROVE|REJECT)$")
    rejection_reason: Optional[str] = None

class TimesheetReportFilter(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    status: Optional[TimesheetStatus] = None

class TimesheetReportSummary(BaseModel):
    total_hours: float
    billable_hours: float
    non_billable_hours: float
    entry_count: int
    entries: List[TimesheetEntryResponse]
