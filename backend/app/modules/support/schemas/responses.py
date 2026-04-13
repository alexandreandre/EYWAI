from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class TicketStatusHistoryItem(BaseModel):
    id: str
    old_status: Optional[str]
    new_status: str
    changed_by: str
    changed_at: datetime


class TicketResponse(BaseModel):
    id: str
    company_id: str
    user_id: str
    user_role: str
    module: str
    request_type: str
    urgency: str
    description: str
    context: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    status_history: Optional[List[TicketStatusHistoryItem]] = None
