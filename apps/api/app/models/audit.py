from sqlalchemy import Column, String, Text, JSON
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    organization_id = Column(String(36), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True) # USER_REGISTERED, LOGIN_SUCCESS, etc.
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=True)
    request_id = Column(String(128), nullable=True)
    ip_address = Column(String(50), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    details = Column(JSON, default=dict, nullable=False)
    user_agent = Column(String(500), nullable=True)



