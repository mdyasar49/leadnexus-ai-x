from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TechnologyCategory(str, Enum):
    ERP = "ERP"
    CRM = "CRM"
    ECOMMERCE = "ECOMMERCE"
    CLOUD_HOSTING = "CLOUD_HOSTING"
    FRONTEND_FRAMEWORK = "FRONTEND_FRAMEWORK"
    BACKEND_FRAMEWORK = "BACKEND_FRAMEWORK"
    DATABASE = "DATABASE"
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    ANALYTICS = "ANALYTICS"


class OdooSignalType(str, Enum):
    USES_ODOO = "USES_ODOO"
    IMPLEMENTS_ODOO = "IMPLEMENTS_ODOO"
    SUPPORTS_ODOO = "SUPPORTS_ODOO"
    PARTNER_ECOSYSTEM = "PARTNER_ECOSYSTEM"
    ODOO_DEVELOPER_HIRING = "ODOO_DEVELOPER_HIRING"
    ODOO_MIGRATION = "ODOO_MIGRATION"
    ODOO_UPGRADE = "ODOO_UPGRADE"
    ODOO_INTEGRATION = "ODOO_INTEGRATION"
    ODOO_CUSTOMIZATION = "ODOO_CUSTOMIZATION"
    ODOO_SUPPORT = "ODOO_SUPPORT"
    ODOO_TROUBLESHOOTING = "ODOO_TROUBLESHOOTING"
    ODOO_CONTRIBUTION = "ODOO_CONTRIBUTION"


class TechnologyObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "technology_observations"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    
    technology = Column(String(100), nullable=False, index=True)
    category = Column(String(50), default="ERP", nullable=False)
    version = Column(String(50), nullable=True)
    source_url = Column(String(1000), nullable=False)
    evidence_text = Column(Text, nullable=False)
    evidence_hash = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, default=1.0, nullable=False)
    detection_method = Column(String(100), default="HTML_SIGNATURE", nullable=False)
    
    first_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_tech_ws_comp_tech", "workspace_id", "company_id", "technology"),
    )


class OdooSignalObservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "odoo_signal_observations"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    
    signal_type = Column(String(50), default="USES_ODOO", nullable=False, index=True)
    detected_version = Column(String(50), nullable=True)  # e.g., "Odoo 17", "Odoo 18"
    source_url = Column(String(1000), nullable=False)
    evidence_text = Column(Text, nullable=False)
    evidence_hash = Column(String(64), nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    
    is_verified = Column(Boolean, default=False, nullable=False)
    meta_attributes = Column(JSON, default=dict, nullable=False)

