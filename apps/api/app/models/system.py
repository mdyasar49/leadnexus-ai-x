from sqlalchemy import Column, String, Text
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

class SystemMetadata(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "system_metadata"

    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)

