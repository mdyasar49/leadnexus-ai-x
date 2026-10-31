"""
LeadNexus AI X - Phase 32: Enterprise Data Lifecycle, Archival, Retention & Backup Governance Models
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class StorageTier(str, enum.Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    ARCHIVED = "ARCHIVED"
    PURGED = "PURGED"


class ArchiveStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RESTORED = "RESTORED"
    PURGED = "PURGED"


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)  # "AUDIT_LOG", "BROWSER_SNAPSHOT", "RAW_SIGNAL", "CONTACT"
    retention_days = Column(Integer, default=90, nullable=False)
    target_tier = Column(String(50), default=StorageTier.ARCHIVED.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ArchivePackage(Base):
    __tablename__ = "archive_packages"

    id = Column(String(100), primary_key=True)  # e.g. "pkg_leads_2026_q2_01"
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    package_name = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)
    records_count = Column(Integer, default=0, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False)
    storage_uri = Column(String(500), nullable=False)
    size_bytes = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default=ArchiveStatus.ACTIVE.value, nullable=False)
    manifest = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ArchiveTombstone(Base):
    __tablename__ = "archive_tombstones"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    archive_package_id = Column(String(100), ForeignKey("archive_packages.id"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)
    original_entity_id = Column(String(255), nullable=False, index=True)
    archived_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class LifecycleTransitionEvent(Base):
    __tablename__ = "lifecycle_transition_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(255), nullable=False, index=True)
    from_tier = Column(String(50), nullable=False)
    to_tier = Column(String(50), nullable=False)
    reason = Column(String(255), nullable=False)
    transitioned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
