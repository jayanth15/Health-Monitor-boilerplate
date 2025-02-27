from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import List, Dict
from app.models.db_models import Cloud_Services, Incident
from app.models.api_models import (
    DegradationCheckRequest,
    DegradationCheckResponse,
    PlannedIncidentRequest,
    UpdateIncidentRequest,
    IncidentResponse,
    ServiceHealthCheckRequest,
    ServiceHealthStatus,
    ServiceHealthCheckResponse
)
from app.services.degradation_functions import (
    analyze_health_data,
    handle_degradation_and_incidents,
    create_planned_incident,
    update_incident
)
from app.utils.database import get_session

router = APIRouter()

@router.post("/check-degradation/", response_model=DegradationCheckResponse)
def check_service_degradation(
    request: DegradationCheckRequest,
    session: Session = Depends(get_session)
):
    """Manual endpoint to check if a service is degraded"""
    try:
        # Get the service information first
        service = session.get(Cloud_Services, request.service_id)
        if not service:
            raise HTTPException(status_code=404, detail=f"Service with ID {request.service_id} not found")
        
        # Analyze health data for the service
        is_degraded = analyze_health_data(request.service_id, session)
        
        result = {
            "service_id": request.service_id,
            "service_name": service.service_name,
            "is_degraded": is_degraded,
            "incident_id": None,
            "message": "Service status checked successfully."
        }
        
        if is_degraded:
            incident_result = handle_degradation_and_incidents(
                service_id=request.service_id,
                is_degraded=True,
                auto_triggered=False,
                session=session
            )
            result["incident_id"] = incident_result["incident_id"]
            result["message"] = incident_result["message"]
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auto-check-degradation/{service_id}")
def auto_check_degradation(
    service_id: int,
    session: Session = Depends(get_session)
):
    """Endpoint called automatically when a health check fails"""
    try:
        # Get the service information first
        service = session.get(Cloud_Services, service_id)
        if not service:
            raise HTTPException(status_code=404, detail=f"Service with ID {service_id} not found")
        
        # Analyze health data for the service
        is_degraded = analyze_health_data(service_id, session)
        
        result = {
            "service_id": service_id,
            "service_name": service.service_name,
            "is_degraded": is_degraded,
        }
        
        if is_degraded:
            incident_result = handle_degradation_and_incidents(
                service_id=service_id,
                is_degraded=True,
                auto_triggered=True,
                session=session
            )
            result.update(incident_result)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/incidents/planned", response_model=IncidentResponse)
def create_planned_maintenance(
    request: PlannedIncidentRequest,
    session: Session = Depends(get_session)
):
    """Create a planned incident for upcoming maintenance"""
    try:
        incident = create_planned_incident(
            service_id=request.service_id,
            event_name=request.event_name,
            event_description=request.event_description,
            degradation_start=request.degradation_start,
            created_by=request.created_by,
            session=session
        )
        
        # Get service name for response
        service = session.get(Cloud_Services, request.service_id)
        
        return IncidentResponse(
            id=incident.id,
            service_id=incident.service_id,
            service_name=service.service_name,
            event_name=incident.event_name,
            event_type=incident.event_type,
            status=incident.status,
            created_at=incident.created_at,
            degradation_start=incident.degradation_start,
            created_by=incident.created_by,
            event_description=incident.event_description,
            updated_at=incident.updated_at,
            updated_by=incident.updated_by
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/incidents/{incident_id}", response_model=IncidentResponse)
def update_incident_status(
    incident_id: int,
    request: UpdateIncidentRequest,
    session: Session = Depends(get_session)
):
    """Update an incident's status or description"""
    try:
        update_data = request.dict(exclude_unset=True)
        update_data["updated_by"] = request.updated_by
        
        incident = update_incident(incident_id, update_data, session)
        service = session.get(Cloud_Services, incident.service_id)
        
        return IncidentResponse(
            id=incident.id,
            service_id=incident.service_id,
            service_name=service.service_name,
            event_name=incident.event_name,
            event_type=incident.event_type,
            status=incident.status,
            created_at=incident.created_at,
            degradation_start=incident.degradation_start,
            created_by=incident.created_by,
            event_description=incident.event_description,
            updated_at=incident.updated_at,
            updated_by=incident.updated_by
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/incidents/", response_model=List[IncidentResponse])
def list_incidents(
    service_id: int = None,
    status: str = None,
    session: Session = Depends(get_session)
):
    """List all incidents with optional filtering"""
    try:
        query = select(Incident)
        if service_id:
            query = query.where(Incident.service_id == service_id)
        if status:
            query = query.where(Incident.status == status)
            
        incidents = session.exec(query).all()
        
        # Get all related services in one query
        service_ids = {inc.service_id for inc in incidents}
        services = {
            svc.id: svc.service_name 
            for svc in session.exec(select(Cloud_Services).where(Cloud_Services.id.in_(service_ids))).all()
        }
        
        return [
            IncidentResponse(
                id=inc.id,
                service_id=inc.service_id,
                service_name=services[inc.service_id],
                event_name=inc.event_name,
                event_type=inc.event_type,
                status=inc.status,
                created_at=inc.created_at,
                degradation_start=inc.degradation_start,
                created_by=inc.created_by,
                event_description=inc.event_description,
                updated_at=inc.updated_at,
                updated_by=inc.updated_by
            )
            for inc in incidents
        ]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/check-services/", response_model=ServiceHealthCheckResponse)
def check_services_health(
    request: ServiceHealthCheckRequest,
    session: Session = Depends(get_session)
):
    """Check health status for multiple services by their names"""
    try:
        # Get all requested services
        services = session.exec(
            select(Cloud_Services)
            .where(Cloud_Services.service_name.in_(request.service_names))
        ).all()
        
        # Create a map of found services
        service_map = {service.service_name: service for service in services}
        
        # Initialize response dictionary
        response: ServiceHealthCheckResponse = {}
        
        # Check each requested service
        for service_name in request.service_names:
            if service_name not in service_map:
                # Service not found, mark as unhealthy
                response[service_name] = ServiceHealthStatus(
                    is_healthy=False
                )
                continue
            
            service = service_map[service_name]
            
            # Check if service is degraded
            is_degraded = analyze_health_data(service.id, session)
            
            if not is_degraded:
                # Service is healthy
                response[service_name] = ServiceHealthStatus(
                    is_healthy=True
                )
            else:
                # Service is degraded, handle incident creation
                incident_result = handle_degradation_and_incidents(
                    service_id=service.id,
                    is_degraded=True,
                    auto_triggered=False,
                    session=session
                )
                
                response[service_name] = ServiceHealthStatus(
                    is_healthy=False,
                    incident_id=incident_result["incident_id"]
                )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))