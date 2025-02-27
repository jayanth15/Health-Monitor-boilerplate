from sqlmodel import Session, select, and_
from datetime import datetime
from typing import Optional, Dict, Any, List
from app.models.db_models import Cloud_Services, Health_Status
from app.models.api_models import HealthStatusResponse, HealthStatusHistoryResponse

def get_current_health_status(service_id: int, session: Session) -> Optional[HealthStatusResponse]:
    """Get the most recent health status for a service"""
    service = session.get(Cloud_Services, service_id)
    if not service:
        return None
    
    # Get the most recent health status
    latest_status = session.exec(
        select(Health_Status)
        .where(Health_Status.service_id == service_id)
        .order_by(Health_Status.timestamp.desc())
        .limit(1)
    ).first()
    
    if not latest_status:
        return None
    
    return HealthStatusResponse(
        service_id=service_id,
        service_name=service.service_name,
        is_healthy=latest_status.is_health,
        last_checked=latest_status.timestamp,
        status_code=latest_status.status_code
    )

def get_health_history(
    service_id: int,
    start_time: datetime,
    end_time: datetime,
    session: Session
) -> Optional[HealthStatusHistoryResponse]:
    """Get health status history for a service in the specified time range"""
    service = session.get(Cloud_Services, service_id)
    if not service:
        return None
    
    # Get all health status records in the time range
    status_records = session.exec(
        select(Health_Status)
        .where(
            and_(
                Health_Status.service_id == service_id,
                Health_Status.timestamp >= start_time,
                Health_Status.timestamp <= end_time
            )
        )
        .order_by(Health_Status.timestamp)
    ).all()
    
    if not status_records:
        return None
    
    # Convert records to history format
    history = [
        {
            "timestamp": record.timestamp,
            "is_healthy": record.is_health,
            "status_code": record.status_code
        }
        for record in status_records
    ]
    
    return HealthStatusHistoryResponse(
        service_id=service_id,
        service_name=service.service_name,
        history=history
    )