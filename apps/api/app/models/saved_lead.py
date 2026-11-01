"""
LeadNexus AI X — Saved Leads Model
Phase 10: PostgreSQL/SQLite Persistence for User-Saved Leads
Only leads explicitly added by the user are stored here and exported.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.db.base import Base


class SavedLead(Base):
    """
    Persisted record of an explicitly added lead.
    Temporary search results must never be stored here.
    """
    __tablename__ = "saved_leads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    
    source_name = Column(String(100), nullable=True)
    source_url = Column(String(1000), nullable=True)
    evidence = Column(Text, nullable=True)
    search_keyword = Column(String(255), nullable=True)
    saved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    company = relationship("Company")
    contact = relationship("Contact")

    __table_args__ = (
        Index("idx_saved_lead_company_contact", "company_id", "contact_id"),
        UniqueConstraint("company_id", "contact_id", name="uq_saved_lead_company_contact"),
    )

