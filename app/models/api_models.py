from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.db_models import EventType, IncidentStatus

class DegradationCheckRequest(BaseModel):
    service_id: int

class DegradationCheckResponse(BaseModel):
    service_id: int
    service_name: str
    is_degraded: bool
    incident_id: Optional[int] = None
    message: str

class ServiceHealthCheckRequest(BaseModel):
    service_names: List[str]
    created_by: str

class ServiceHealthStatus(BaseModel):
    is_healthy: bool
    incident_id: Optional[int] = None

# Dictionary with service_name as key and ServiceHealthStatus as value
ServiceHealthCheckResponse = Dict[str, ServiceHealthStatus]

class PlannedIncidentRequest(BaseModel):
    service_id: int
    event_name: str
    event_description: str
    degradation_start: datetime
    created_by: str
    event_type: EventType = EventType.PLANNED

class UpdateIncidentRequest(BaseModel):
    status: Optional[IncidentStatus] = None
    event_description: Optional[str] = None
    updated_by: str

class IncidentResponse(BaseModel):
    id: int
    service_id: int
    service_name: str
    event_name: str
    event_type: str
    status: str
    created_at: datetime
    degradation_start: datetime
    created_by: str
    event_description: str
    updated_at: datetime
    updated_by: Optional[str] = None

class UserToken(BaseModel):
    user_id: str
    exp: datetime

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: str
    role: str
    exp: datetime

class CommentCreate(BaseModel):
    incident_id: int
    text: str

class CommentUpdate(BaseModel):
    text: str

class CommentResponse(BaseModel):
    id: int
    incident_id: int
    user_id: str
    text: str
    created_at: datetime
    updated_at: Optional[datetime] = None

class HealthStatusNowRequest(BaseModel):
    service_ids: Optional[List[int]] = None

class HealthStatusResponse(BaseModel):
    service_id: int
    service_name: str
    is_healthy: bool
    last_checked: datetime
    status_code: int

class HealthStatusRangeRequest(BaseModel):
    service_ids: Optional[List[int]] = None
    start_time: datetime
    end_time: datetime

class HealthStatusHistoryResponse(BaseModel):
    service_id: int
    service_name: str
    history: List[Dict[str, Any]]  # Timestamp and health status

class IncidentCreate(BaseModel):
    service_id: int
    event_name: str
    event_description: str
    event_type: EventType
    degradation_start: datetime