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


class EventType(str, PyEnum):
    PLANNED = "PLANNED"
    UNPLANNED = "UN-PLANNED"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)  # LDAP user ID
    token: Optional[str] = None
    expiry_date: Optional[datetime] = None
    role: str  # Role from LDAP
    
    # Relationship with comments
    comments: List["Comment"] = Relationship(back_populates="user")
    # Relationship with incidents
    incidents_updated: List["Incident"] = Relationship(back_populates="updated_by_user",
                                                      sa_relationship_kwargs={"foreign_keys": "[Incident.updated_by_id]"})
    incidents_created: List["Incident"] = Relationship(back_populates="created_by_user",
                                                     sa_relationship_kwargs={"foreign_keys": "[Incident.created_by_id]"})


class Comment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incident.id")
    user_id: int = Field(foreign_key="user.id")
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Relationships
    incident: "Incident" = Relationship(back_populates="comments")
    user: User = Relationship(back_populates="comments")


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_by_event: Optional[int] = Field(default=None, foreign_key="degradation_events.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_by: str  # For backward compatibility, can be "auto_run" or user identifier
    service_id: int = Field(foreign_key="cloud_services.id")
    status: str = Field(default=IncidentStatus.OPEN)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_name: str
    event_type: str = Field(default=EventType.UNPLANNED)
    degradation_start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    updated_by: Optional[str] = None  # For backward compatibility
    event_description: str
    
    # Relationships
    cloud_service: Cloud_Services = Relationship(back_populates="incidents")
    degradation_events: List["Degradation_Events"] = Relationship(back_populates="incident")
    comments: List[Comment] = Relationship(back_populates="incident")
    created_by_user: Optional[User] = Relationship(back_populates="incidents_created",
                                                 sa_relationship_kwargs={"foreign_keys": "[Incident.created_by_id]"})
    updated_by_user: Optional[User] = Relationship(back_populates="incidents_updated",
                                                 sa_relationship_kwargs={"foreign_keys": "[Incident.updated_by_id]"})


class Degradation_Events(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: int = Field(foreign_key="cloud_services.id")
    incident_id: Optional[int] = Field(default=None, foreign_key="incident.id")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    time_window_minutes: int  # The time window analyzed (e.g., 60 minutes)
    auto_triggered: bool  # Whether triggered automatically or manually
    
    # Relationship with Cloud_Services
    cloud_service: Cloud_Services = Relationship(back_populates="degradation_events")
    # Relationship with Incident
    incident: Optional[Incident] = Relationship(back_populates="degradation_events")