import os
from datetime import timedelta
from pydantic import BaseSettings, Field

class LdapSettings(BaseSettings):
    """LDAP connection settings"""
    server_url: str = Field(default="ldap://ldap.example.com:389", env="LDAP_SERVER_URL")
    search_base: str = Field(default="dc=example,dc=com", env="LDAP_SEARCH_BASE")
    bind_dn: str = Field(default="cn=admin,dc=example,dc=com", env="LDAP_BIND_DN")
    bind_password: str = Field(default="admin_password", env="LDAP_BIND_PASSWORD")
    user_search_filter: str = Field(default="(uid={username})", env="LDAP_USER_SEARCH_FILTER")
    user_id_attribute: str = Field(default="uid", env="LDAP_USER_ID_ATTRIBUTE")
    role_attribute: str = Field(default="employeeType", env="LDAP_ROLE_ATTRIBUTE")
    
class JWTSettings(BaseSettings):
    """JWT token settings"""
    secret_key: str = Field(default="your-secret-key-here", env="JWT_SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="JWT_EXPIRE_MINUTES")
    
    @property
    def expire_delta(self) -> timedelta:
        return timedelta(minutes=self.access_token_expire_minutes)

class RoleSettings(BaseSettings):
    """Role-based access control settings"""
    admin_roles: list = Field(default=["admin", "superuser"], env="ADMIN_ROLES")
    user_roles: list = Field(default=["user", "viewer"], env="USER_ROLES")

class Settings(BaseSettings):
    """Application settings"""
    app_name: str = Field(default="Health Checker", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    ldap: LdapSettings = LdapSettings()
    jwt: JWTSettings = JWTSettings()
    roles: RoleSettings = RoleSettings()
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"

# Create a global settings instance
settings = Settings()