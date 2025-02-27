from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from sqlmodel import Session, select, and_
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

# Add the parent directory to sys.path to import the models
sys.path.append(str(Path(__file__).parent.parent))

from Scheduler.model.models import Cloud_Services, Health_Status, Incident, Degradation_Events, IncidentStatus
from Connectivity.database import engine, get_session

app = FastAPI(title="Degradation Service",
              description="A service that checks for service degradation based on health status data")

class DegradationCheckRequest(BaseModel):
    service_id: int
    time_window_minutes: int = 60

class DegradationCheckResponse(BaseModel):
    service_id: int
    service_name: str
    is_degraded: bool
    failure_rate: float
    degradation_event_id: Optional[int] = None
    incident_id: Optional[int] = None
    message: str

def analyze_health_data(service_id: int, time_window_minutes: int = 60, session: Session = None) -> dict:
    """
    Analyze health status data for a specific service over the specified time window.
    
    Returns:
    - Failure rate (percentage of unhealthy statuses)
    - Whether the service is considered degraded
    - Whether recent failures are concentrated (90% of failures in half the window)
    """
    # Use the provided session or create one
    close_session = False
    if session is None:
        session = Session(engine)
        close_session = True
        
    try:
        # Get the service information
        service = session.exec(select(Cloud_Services).where(Cloud_Services.id == service_id)).first()
        if not service:
            raise ValueError(f"Service with ID {service_id} not found")
            
        # Calculate the start time for the analysis window
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=time_window_minutes)
        
        # Query all health status records for this service in the time window
        query = select(Health_Status).where(
            and_(
                Health_Status.service_id == service_id,
                Health_Status.timestamp >= start_time,
                Health_Status.timestamp <= end_time
            )
        ).order_by(Health_Status.timestamp)
        
        health_records = session.exec(query).all()
        
        # If no health records, we can't analyze
        if not health_records:
            return {
                "failure_rate": 0.0,
                "is_degraded": False,
                "recent_concentrated_failures": False,
                "total_records": 0,
                "unhealthy_records": 0
            }
            
        # Count unhealthy records and calculate failure rate
        total_records = len(health_records)
        unhealthy_records = sum(1 for record in health_records if not record.is_health)
        failure_rate = (unhealthy_records / total_records) * 100.0
        
        # Check if failure rate exceeds 70%
        is_degraded = failure_rate >= 70.0
        
        # Check if 90% of failures are in the most recent half of the records
        # Simply split the list in half and take the second half as the recent records
        mid_point = len(health_records) // 2
        recent_records = health_records[mid_point:]  # Second half of the records
        recent_unhealthy = sum(1 for r in recent_records if not r.is_health)
        
        recent_concentrated_failures = False
        if unhealthy_records > 0:  # Avoid division by zero
            recent_failure_percentage = (recent_unhealthy / unhealthy_records) * 100.0
            recent_concentrated_failures = recent_failure_percentage >= 90.0
        
        # If either condition is met, the service is considered degraded
        is_degraded = is_degraded or recent_concentrated_failures
        
        return {
            "failure_rate": failure_rate,
            "is_degraded": is_degraded,
            "recent_concentrated_failures": recent_concentrated_failures,
            "total_records": total_records,
            "unhealthy_records": unhealthy_records
        }
    
    finally:
        if close_session:
            session.close()

def handle_degradation_and_incidents(
    service_id: int, 
    failure_rate: float,
    is_degraded: bool, 
    time_window_minutes: int,
    auto_triggered: bool,
    session: Session
) -> dict:
    """
    Create degradation event and incident if needed.
    Return the IDs of any created entities and a message.
    """
    # Get the service information
    service = session.exec(select(Cloud_Services).where(Cloud_Services.id == service_id)).first()
    if not service:
        raise ValueError(f"Service with ID {service_id} not found")
    
    result = {
        "degradation_event_id": None,
        "incident_id": None,
        "message": ""
    }
    
    if not is_degraded:
        result["message"] = f"Service {service.service_name} is not degraded (failure rate: {failure_rate:.2f}%)"
        return result
    
    # Create a degradation event
    # First, check if there's an open incident for this service
    open_incident = session.exec(
        select(Incident).where(
            and_(
                Incident.service_id == service_id,
                Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED])
            )
        )
    ).first()
    
    # Create the degradation event
    degradation_event = Degradation_Events(
        service_id=service_id,
        incident_id=open_incident.id if open_incident else None,
        timestamp=datetime.now(timezone.utc),
        failure_rate=failure_rate,
        time_window_minutes=time_window_minutes,
        auto_triggered=auto_triggered
    )
    session.add(degradation_event)
    session.commit()
    session.refresh(degradation_event)
    
    result["degradation_event_id"] = degradation_event.id
    
    # If no open incident, create one
    if not open_incident:
        incident = Incident(
            service_id=service_id,
            start_time=datetime.now(timezone.utc),
            status=IncidentStatus.OPEN,
            description=f"Automated incident created due to service degradation. Failure rate: {failure_rate:.2f}%"
        )
        session.add(incident)
        session.commit()
        session.refresh(incident)
        
        # Update the degradation event with the new incident ID
        degradation_event.incident_id = incident.id
        session.add(degradation_event)
        session.commit()
        
        result["incident_id"] = incident.id
        result["message"] = f"New incident created for {service.service_name} (ID: {incident.id}). Failure rate: {failure_rate:.2f}%"
    else:
        result["incident_id"] = open_incident.id
        result["message"] = f"Added degradation event to existing incident (ID: {open_incident.id}) for {service.service_name}. Failure rate: {failure_rate:.2f}%"
    
    return result

@app.post("/check-degradation/", response_model=DegradationCheckResponse)
def check_service_degradation(
    request: DegradationCheckRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Manual endpoint to check if a service is degraded based on recent health status data
    """
    try:
        # Analyze health data for the service
        analysis = analyze_health_data(request.service_id, request.time_window_minutes, session)
        
        # Get the service information
        service = session.exec(select(Cloud_Services).where(Cloud_Services.id == request.service_id)).first()
        if not service:
            raise HTTPException(status_code=404, detail=f"Service with ID {request.service_id} not found")
        
        # If degraded, handle creating degradation event and incident
        result = {
            "service_id": request.service_id,
            "service_name": service.service_name,
            "is_degraded": analysis["is_degraded"],
            "failure_rate": analysis["failure_rate"],
            "degradation_event_id": None,
            "incident_id": None,
            "message": f"Analysis complete. Failure rate: {analysis['failure_rate']:.2f}%."
        }
        
        if analysis["is_degraded"]:
            # Handle degradation and incidents
            incident_result = handle_degradation_and_incidents(
                service_id=request.service_id,
                failure_rate=analysis["failure_rate"],
                is_degraded=True,
                time_window_minutes=request.time_window_minutes,
                auto_triggered=False,  # Manual trigger from API
                session=session
            )
            
            result["degradation_event_id"] = incident_result["degradation_event_id"]
            result["incident_id"] = incident_result["incident_id"]
            result["message"] = incident_result["message"]
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking service degradation: {str(e)}")

@app.post("/auto-check-degradation/{service_id}")
def auto_check_degradation(
    service_id: int,
    session: Session = Depends(get_session)
):
    """
    Endpoint called automatically when a health check fails
    Analyzes recent health data and creates degradation events/incidents if needed
    """
    try:
        # Analyze health data for the service (using default 60 minute window)
        analysis = analyze_health_data(service_id, 60, session)
        
        # Get the service information
        service = session.exec(select(Cloud_Services).where(Cloud_Services.id == service_id)).first()
        if not service:
            raise HTTPException(status_code=404, detail=f"Service with ID {service_id} not found")
        
        result = {
            "service_id": service_id,
            "service_name": service.service_name,
            "is_degraded": analysis["is_degraded"],
            "failure_rate": analysis["failure_rate"],
        }
        
        if analysis["is_degraded"]:
            # Handle degradation and incidents
            incident_result = handle_degradation_and_incidents(
                service_id=service_id,
                failure_rate=analysis["failure_rate"],
                is_degraded=True,
                time_window_minutes=60,
                auto_triggered=True,  # Automatic trigger
                session=session
            )
            
            result["degradation_event_id"] = incident_result["degradation_event_id"]
            result["incident_id"] = incident_result["incident_id"]
            result["message"] = incident_result["message"]
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in automatic degradation check: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)