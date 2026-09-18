from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from app.models.leave import LeaveType, LeaveStatus

class LeaveBalanceItem(BaseModel):
    leave_type: LeaveType
    total_allocated: float
    used_days: float
    pending_days: float
    carry_forwarded: float
    available_balance: float

class LeaveBalanceSummary(BaseModel):
    user_id: str
    year: int
    balances: List[LeaveBalanceItem]

class LeaveApplyRequest(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=3, max_length=500)

class LeaveDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVE|REJECT)$")
    comments: Optional[str] = None

class LeaveApplicationResponse(BaseModel):
    id: str
    user_id: str
    employee_name: Optional[str] = None
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    reason: str
    status: LeaveStatus
    approver_id: Optional[str] = None
    approver_name: Optional[str] = None
    approver_comments: Optional[str] = None
    applied_at: datetime
    decided_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
