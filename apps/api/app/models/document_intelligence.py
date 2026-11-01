"""
LeadNexus AI X - Phase 42: Document & Unstructured Data Intelligence Models
Provides enterprise persistence for document ingestion, multi-format layout parsing,
structured table extraction, named entity extraction, and evidence provenance tracking.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentRecord(Base):
    """Represents an ingested unstructured or structured enterprise document."""
    __tablename__ = "document_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False, index=True)  # PDF, DOCX, XLSX, CSV, HTML, TXT, JSON, XML, IMAGE
    file_size_bytes = Column(Integer, default=0)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    status = Column(String(32), default="PENDING", index=True)  # PENDING, PARSING, COMPLETED, FAILED, FLAGGED
    page_count = Column(Integer, default=1)
    malware_status = Column(String(32), default="CLEAN")  # CLEAN, SUSPICIOUS, REJECTED
    ocr_applied = Column(Boolean, default=False)
    quality_score = Column(Float, default=1.0)
    metadata_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    tables = relationship("DocumentTable", back_populates="document", cascade="all, delete-orphan")
    entities = relationship("DocumentExtractedEntity", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
            "file_hash": self.file_hash,
            "status": self.status,
            "page_count": self.page_count,
            "malware_status": self.malware_status,
            "ocr_applied": self.ocr_applied,
            "quality_score": self.quality_score,
            "metadata_payload": self.metadata_payload or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentChunk(Base):
    """Semantic layout chunk representing a section, paragraph, or OCR block."""
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("document_records.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, default=1)
    chunk_index = Column(Integer, default=0)
    chunk_type = Column(String(32), default="PARAGRAPH")  # PARAGRAPH, HEADING, TABLE, LIST, METADATA
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    bounding_box = Column(JSON, default=dict)  # {x0, y0, x1, y1}
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentRecord", back_populates="chunks")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "chunk_type": self.chunk_type,
            "content": self.content,
            "token_count": self.token_count,
            "bounding_box": self.bounding_box or {},
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentTable(Base):
    """Extracted structured table from documents (XLSX, CSV, PDF/HTML tables)."""
    __tablename__ = "document_tables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("document_records.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, default=1)
    table_index = Column(Integer, default=0)
    headers = Column(JSON, default=list)  # list of str header names
    rows = Column(JSON, default=list)  # list of dicts/lists
    row_count = Column(Integer, default=0)
    col_count = Column(Integer, default=0)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentRecord", back_populates="tables")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "table_index": self.table_index,
            "headers": self.headers or [],
            "rows": self.rows or [],
            "row_count": self.row_count,
            "col_count": self.col_count,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentExtractedEntity(Base):
    """Structured entity extracted from document chunks or tables."""
    __tablename__ = "document_extracted_entities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("document_records.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(36), nullable=True, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # COMPANY, PERSON, EMAIL, PHONE, TITLE, TECH, FINANCIAL
    entity_value = Column(String(255), nullable=False)
    normalized_value = Column(String(255), nullable=False)
    confidence = Column(Float, default=0.9)
    context_snippet = Column(Text, nullable=True)
    page_number = Column(Integer, default=1)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    document = relationship("DocumentRecord", back_populates="entities")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "entity_type": self.entity_type,
            "entity_value": self.entity_value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "context_snippet": self.context_snippet,
            "page_number": self.page_number,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentProvenanceRecord(Base):
    """Grounding and provenance citation connecting extracted insights to raw source tokens."""
    __tablename__ = "document_provenance_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), nullable=False, index=True)
    entity_id = Column(String(36), nullable=True, index=True)
    claim_text = Column(Text, nullable=False)
    source_citation = Column(String(512), nullable=False)
    page_number = Column(Integer, default=1)
    sha256_proof = Column(String(64), nullable=False)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "entity_id": self.entity_id,
            "claim_text": self.claim_text,
            "source_citation": self.source_citation,
            "page_number": self.page_number,
            "sha256_proof": self.sha256_proof,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
