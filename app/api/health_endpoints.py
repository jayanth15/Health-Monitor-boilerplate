from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from app.models.db_models import (
    Cloud_Services,
    Health_Status,
    Incident,
    Comment,
    User,
    EventType
)
from app.models.api_models import (
    HealthStatusNowRequest,
    HealthStatusResponse,
    HealthStatusRangeRequest,
    HealthStatusHistoryResponse,
    IncidentCreate,
    IncidentResponse,
    UpdateIncidentRequest,
    CommentCreate,
    CommentUpdate,
    CommentResponse
)
from app.utils.database import get_session
from app.services.health_service import get_current_health_status, get_health_history
from app.utils.auth import get_current_user, check_admin_role

router = APIRouter()

# Health status check - available to all authenticated users
@router.post("/health_status_now", response_model=List[HealthStatusResponse])
async def get_current_status(
    request: HealthStatusNowRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)  # Only requires authentication, no role check
):
    """Get current health status for specified services or all services"""
    try:
        service_ids = request.service_ids
        # If no service IDs provided, get all active services
        if not service_ids:
            services = session.exec(
                select(Cloud_Services)
                .where(Cloud_Services.is_live == True)
            ).all()
            service_ids = [svc.id for svc in services]

        results = []
        for service_id in service_ids:
            status = get_current_health_status(service_id, session)
            if status:
                results.append(status)

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# All other endpoints require admin role
@router.post("/health_status_range", response_model=List[HealthStatusHistoryResponse])
async def get_status_history(
    request: HealthStatusRangeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Get health status history for specified services in a time range"""
    try:
        service_ids = request.service_ids
        if not service_ids:
            services = session.exec(
                select(Cloud_Services)
                .where(Cloud_Services.is_live == True)
            ).all()
            service_ids = [svc.id for svc in services]

        results = []
        for service_id in service_ids:
            history = get_health_history(
                service_id,
                request.start_time,
                request.end_time,
                session
            )
            if history:
                results.append(history)

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_incident", response_model=IncidentResponse)
async def create_incident(
    request: IncidentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Create a new incident"""
    try:
        service = session.get(Cloud_Services, request.service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")

        incident = Incident(
            service_id=request.service_id,
            event_name=request.event_name,
            event_description=request.event_description,
            event_type=request.event_type,
            degradation_start=request.degradation_start,
            created_by=current_user.user_id,
            created_by_id=current_user.id
        )

        session.add(incident)
        session.commit()
        session.refresh(incident)

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

@router.get("/get_all_incident", response_model=List[IncidentResponse])
async def get_all_incidents(
    service_ids: Optional[List[int]] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Get all incidents for specified services or all services"""
    try:
        query = select(Incident)
        if service_ids:
            query = query.where(Incident.service_id.in_(service_ids))

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

@router.get("/{incident_id}/get", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Get a specific incident by ID"""
    try:
        incident = session.get(Incident, incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

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

@router.patch("/{incident_id}/update", response_model=IncidentResponse)
async def update_incident(
    incident_id: int,
    request: UpdateIncidentRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Update an incident's status or description"""
    try:
        incident = session.get(Incident, incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        if request.status is not None:
            incident.status = request.status
        if request.event_description is not None:
            incident.event_description = request.event_description

        incident.updated_at = datetime.now()
        incident.updated_by = current_user.user_id
        incident.updated_by_id = current_user.id

        session.add(incident)
        session.commit()
        session.refresh(incident)

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

@router.post("/create_comment", response_model=CommentResponse)
async def create_comment(
    request: CommentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Create a new comment on an incident"""
    try:
        incident = session.get(Incident, request.incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        comment = Comment(
            incident_id=request.incident_id,
            user_id=current_user.id,
            text=request.text
        )

        session.add(comment)
        session.commit()
        session.refresh(comment)

        return CommentResponse(
            id=comment.id,
            incident_id=comment.incident_id,
            user_id=current_user.user_id,
            text=comment.text,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_comments/{incident_id}", response_model=List[CommentResponse])
async def get_comments(
    incident_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Get all comments for a specific incident"""
    try:
        comments = session.exec(
            select(Comment)
            .where(Comment.incident_id == incident_id)
            .order_by(Comment.created_at)
        ).all()

        # Get all user IDs in one query
        user_ids = {comment.user_id for comment in comments}
        users = {
            user.id: user.user_id
            for user in session.exec(select(User).where(User.id.in_(user_ids))).all()
        }

        return [
            CommentResponse(
                id=comment.id,
                incident_id=comment.incident_id,
                user_id=users[comment.user_id],
                text=comment.text,
                created_at=comment.created_at,
                updated_at=comment.updated_at
            )
            for comment in comments
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{comment_id}/update", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    request: CommentUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(check_admin_role)  # Requires admin role
):
    """Update a comment"""
    try:
        comment = session.get(Comment, comment_id)
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        # Check if the user is the owner of the comment
        if comment.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this comment")

        comment.text = request.text
        comment.updated_at = datetime.now()

        session.add(comment)
        session.commit()
        session.refresh(comment)

        return CommentResponse(
            id=comment.id,
            incident_id=comment.incident_id,
            user_id=current_user.user_id,
            text=comment.text,
            created_at=comment.created_at,
            updated_at=comment.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))