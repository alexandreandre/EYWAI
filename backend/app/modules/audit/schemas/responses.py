from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    id: str
    company_id: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime = Field(..., description="Horodatage serveur")
