from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timezone
from ldap3 import Server, Connection, ALL
from sqlmodel import Session, select
from app.config.settings import settings
from app.models.db_models import User
from app.utils.database import get_session

security = HTTPBearer()

def create_jwt_token(user_id: str, role: str) -> str:
    """Create a JWT token for a user"""
    expire = datetime.now(timezone.utc) + settings.jwt.expire_delta
    to_encode = {
        "user_id": user_id,
        "role": role,
        "exp": expire
    }
    return jwt.encode(to_encode, settings.jwt.secret_key, algorithm=settings.jwt.algorithm)

def verify_jwt_token(token: str) -> dict:
    """Verify a JWT token and return its payload"""
    try:
        payload = jwt.decode(token, settings.jwt.secret_key, algorithms=[settings.jwt.algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

def get_ldap_connection() -> Connection:
    """Create and return an LDAP connection"""
    server = Server(settings.ldap.server_url, get_info=ALL)
    return Connection(
        server,
        settings.ldap.bind_dn,
        settings.ldap.bind_password,
        auto_bind=True
    )

def get_user_from_ldap(username: str) -> dict:
    """Get user information from LDAP"""
    conn = get_ldap_connection()
    search_filter = settings.ldap.user_search_filter.format(username=username)
    
    conn.search(
        settings.ldap.search_base,
        search_filter,
        attributes=[settings.ldap.role_attribute]
    )
    
    if not conn.entries:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in LDAP"
        )
    
    user_entry = conn.entries[0]
    return {
        "user_id": username,
        "role": getattr(user_entry, settings.ldap.role_attribute).value
    }

def verify_token_and_get_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session)
) -> User:
    """Verify JWT token and return the corresponding user"""
    try:
        payload = verify_jwt_token(credentials.credentials)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
            
        # Check if user exists in database
        user = session.exec(
            select(User).where(User.user_id == user_id)
        ).first()
        
        if not user:
            # If user doesn't exist, try to get from LDAP and create
            ldap_user = get_user_from_ldap(user_id)
            user = User(
                user_id=user_id,
                role=ldap_user["role"]
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        
        return user
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

# Dependency to get current user from token
get_current_user = verify_token_and_get_user

def check_admin_role(user: User = Depends(get_current_user)) -> User:
    """Check if user has admin role"""
    if user.role not in settings.roles.admin_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    return user
