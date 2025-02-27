from sqlmodel import Session, select, and_
from datetime import datetime, timezone, timedelta
import os
from app.models.db_models import (
    Cloud_Services, 
    Health_Status, 
    Incident, 
    Degradation_Events, 
    IncidentStatus,
    EventType
)

# Load configuration from environment variables
HEALTH_CHECK_WINDOW = int(os.getenv("HEALTH_CHECK_WINDOW_MINUTES", "60"))
DEGRADATION_THRESHOLD = float(os.getenv("DEGRADATION_THRESHOLD_PERCENT", "70"))
CONCENTRATED_FAILURES_THRESHOLD = float(os.getenv("CONCENTRATED_FAILURES_THRESHOLD_PERCENT", "90"))

def analyze_health_data(service_id: int, session: Session) -> bool:
    """
    Analyze health status data for a specific service over the specified time window.
    Returns True if the service is degraded, False otherwise.
    """
    # Get the service information
    service = session.exec(select(Cloud_Services).where(Cloud_Services.id == service_id)).first()
    if not service:
        raise ValueError(f"Service with ID {service_id} not found")
        
    # Calculate the start time for the analysis window
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=HEALTH_CHECK_WINDOW)
    
    # Query all health status records for this service in the time window
    query = select(Health_Status).where(
        and_(
            Health_Status.service_id == service_id,
            Health_Status.timestamp >= start_time,
            Health_Status.timestamp <= end_time
        )
    ).order_by(Health_Status.timestamp)
    
    health_records = session.exec(query).all()
    
    # If no health records, can't determine degradation
    if not health_records:
        return False
        
    # Count unhealthy records
    total_records = len(health_records)
    unhealthy_records = sum(1 for record in health_records if not record.is_health)
    failure_percentage = (unhealthy_records / total_records) * 100.0
    
    # Check if failure rate exceeds threshold
    is_degraded = failure_percentage >= DEGRADATION_THRESHOLD
    
    # Check concentrated failures in recent half
    mid_point = len(health_records) // 2
    recent_records = health_records[mid_point:]
    recent_unhealthy = sum(1 for r in recent_records if not r.is_health)
    
    # Check for concentrated recent failures
    if unhealthy_records > 0:
        recent_failure_percentage = (recent_unhealthy / unhealthy_records) * 100.0
        recent_concentrated_failures = recent_failure_percentage >= CONCENTRATED_FAILURES_THRESHOLD
        is_degraded = is_degraded or recent_concentrated_failures
    
    return is_degraded

def handle_degradation_and_incidents(
    service_id: int,
    is_degraded: bool,
    auto_triggered: bool,
    session: Session
) -> dict:
    """Create degradation event and incident if needed."""
    service = session.exec(select(Cloud_Services).where(Cloud_Services.id == service_id)).first()
    if not service:
        raise ValueError(f"Service with ID {service_id} not found")
    
    result = {
        "incident_id": None,
        "message": ""
    }
    
    if not is_degraded:
        result["message"] = f"Service {service.service_name} is not degraded"
        return result
    
    # Check for existing open incident
    open_incident = session.exec(
        select(Incident).where(
            and_(
                Incident.service_id == service_id,
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED])
            )
        )
    ).first()
    
    # Create degradation event
    degradation_event = Degradation_Events(
        service_id=service_id,
        incident_id=open_incident.id if open_incident else None,
        timestamp=datetime.now(timezone.utc),
        time_window_minutes=HEALTH_CHECK_WINDOW,
        auto_triggered=auto_triggered
    )
    session.add(degradation_event)
    session.commit()
    session.refresh(degradation_event)
    
    # If no open incident, create one
    if not open_incident:
        incident = Incident(
            created_by_event=degradation_event.id,
            created_by="auto_run" if auto_triggered else "user",
            service_id=service_id,
            event_name=f"Service Degradation - {service.service_name}",
            event_type=EventType.UNPLANNED,
            event_description=f"Service degradation detected for {service.service_name}"
        )
        session.add(incident)
        session.commit()
        session.refresh(incident)
        
        # Update the degradation event with the new incident ID
        degradation_event.incident_id = incident.id
        session.add(degradation_event)
        session.commit()
        
        result["incident_id"] = incident.id
        result["message"] = f"New incident created for {service.service_name} (ID: {incident.id})"
    else:
        result["incident_id"] = open_incident.id
        result["message"] = f"Added degradation event to existing incident (ID: {open_incident.id}) for {service.service_name}"
    
    return result

def create_planned_incident(
    service_id: int,
    event_name: str,
    event_description: str,
    degradation_start: datetime,
    created_by: str,
    session: Session
) -> Incident:
    """Create a planned incident for upcoming maintenance or known downtime."""
    service = session.exec(select(Cloud_Services).where(Cloud_Services.id == service_id)).first()
    if not service:
        raise ValueError(f"Service with ID {service_id} not found")
    
    incident = Incident(
        created_by=created_by,
        service_id=service_id,
        event_name=event_name,
        event_type=EventType.PLANNED,
        event_description=event_description,
        degradation_start=degradation_start,
        status=IncidentStatus.OPEN
    )
    
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident

def update_incident(
    incident_id: int,
    update_data: dict,
    session: Session
) -> Incident:
    """Update an existing incident with new status or description."""
    incident = session.exec(select(Incident).where(Incident.id == incident_id)).first()
    if not incident:
        raise ValueError(f"Incident with ID {incident_id} not found")
    
    for field, value in update_data.items():
        if value is not None:
            setattr(incident, field, value)
    
    incident.updated_at = datetime.now(timezone.utc)
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident