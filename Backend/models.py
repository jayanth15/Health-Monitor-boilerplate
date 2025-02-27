from sqlmodel import Field, SQLModel, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum as PyEnum


class Cloud_Services(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_name: str
    endpoint: str
    is_live: bool = True
    
    # Relationship with Health_Status
    health_statuses: List["Health_Status"] = Relationship(back_populates="cloud_service")
    
    # Additional relationships
    degradation_events: List["Degradation_Events"] = Relationship(back_populates="cloud_service")
    incidents: List["Incident"] = Relationship(back_populates="cloud_service")


class Health_Status(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: int = Field(foreign_key="cloud_services.id")
    is_health: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status_code: int
    
    # Relationship with Cloud_Services
    cloud_service: Cloud_Services = Relationship(back_populates="health_statuses")


class IncidentStatus(str, PyEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: int = Field(foreign_key="cloud_services.id")
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    status: str = Field(default=IncidentStatus.OPEN)
    description: str
    
    # Relationship with Cloud_Services
    cloud_service: Cloud_Services = Relationship(back_populates="incidents")
    # Relationship with Degradation_Events
    degradation_events: List["Degradation_Events"] = Relationship(back_populates="incident")


class Degradation_Events(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: int = Field(foreign_key="cloud_services.id")
    incident_id: Optional[int] = Field(default=None, foreign_key="incident.id")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    failure_rate: float  # Percentage of failures in the time window
    time_window_minutes: int  # The time window analyzed (e.g., 60 minutes)
    auto_triggered: bool  # Whether triggered automatically or manually
    
    # Relationship with Cloud_Services
    cloud_service: Cloud_Services = Relationship(back_populates="degradation_events")
    # Relationship with Incident
    incident: Optional[Incident] = Relationship(back_populates="degradation_events")