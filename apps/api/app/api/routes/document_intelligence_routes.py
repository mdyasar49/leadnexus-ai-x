"""
LeadNexus AI X - Phase 42: Document & Unstructured Data Intelligence Routes
Provides endpoints for document ingestion, security scanning, multi-format parsing,
table structure extraction, named entity extraction, and evidence provenance citations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user
from app.models.document_intelligence import (
    DocumentRecord,
    DocumentChunk,
    DocumentTable,
    DocumentExtractedEntity,
    DocumentProvenanceRecord,
)
from packages.documents import (
    DocumentSanitizer,
    DocumentParser,
    TableExtractor,
    EntityExtractor,
    DocumentProvenanceTracker,
    DocumentIntelligencePipeline,
)

router = APIRouter(prefix="/documents", tags=["Document & Unstructured Data Intelligence"])


# Pydantic Schemas
class IngestDocumentRequest(BaseModel):
    filename: str = Field(..., description="Original filename with extension (e.g. leads.csv, pitch.pdf)")
    content_text: Optional[str] = Field(None, description="Raw text or decoded payload")
    file_type: Optional[str] = Field(None, description="Optional override format (CSV, JSON, HTML, XML, TXT, PDF)")


class ParseTextRequest(BaseModel):
    text: str = Field(..., description="Raw text or markdown snippet to parse directly")
    extract_tables: bool = True
    extract_entities: bool = True


@router.get("/health")
def get_documents_health():
    """Health check for document intelligence subsystems."""
    return {
        "status": "HEALTHY",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "HTML", "TXT", "JSON", "XML"],
        "ocr_engine": "ACTIVE_SIMULATED",
        "security_scanner": "ACTIVE",
        "entity_extractor": "ACTIVE",
    }


@router.post("/upload")
def upload_and_process_document(
    request: IngestDocumentRequest,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """
    Ingests, scans for security threats, parses, extracts tables and entities,
    and stores records with full grounding provenance.
    """
    content_bytes = (request.content_text or "").encode("utf-8")
    doc_id = str(uuid.uuid4())

    # Run the comprehensive pipeline
    result = DocumentIntelligencePipeline.process_document(
        filename=request.filename,
        content=content_bytes,
        workspace_id=workspace.id,
        document_id=doc_id,
    )

    # Persist DocumentRecord
    doc_record = DocumentRecord(
        id=doc_id,
        workspace_id=workspace.id,
        filename=request.filename,
        file_type=result.get("file_type", "TXT"),
        file_size_bytes=len(content_bytes),
        file_hash=result["security"]["file_hash"],
        status=result["status"],
        page_count=result.get("page_count", 1),
        malware_status=result["security"]["malware_status"],
        ocr_applied=result.get("ocr_applied", False),
        quality_score=result["security"]["quality_score"],
        metadata_payload={
            "threats_found": result["security"]["threats_found"],
            "total_tokens": result.get("total_tokens", 0),
        },
    )
    db.add(doc_record)
    db.flush()

    if result["status"] == "COMPLETED":
        # Save chunks
        for c in result.get("chunks", []):
            db.add(
                DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    page_number=c.get("page_number", 1),
                    chunk_index=c.get("chunk_index", 0),
                    chunk_type=c.get("chunk_type", "PARAGRAPH"),
                    content=c.get("content", ""),
                    token_count=c.get("token_count", 0),
                    bounding_box=c.get("bounding_box", {}),
                    confidence=c.get("confidence", 1.0),
                )
            )

        # Save tables
        for t in result.get("tables", []):
            db.add(
                DocumentTable(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    page_number=t.get("page_number", 1),
                    table_index=t.get("table_index", 0),
                    headers=t.get("headers", []),
                    rows=t.get("rows", []),
                    row_count=t.get("row_count", 0),
                    col_count=t.get("col_count", 0),
                    confidence=t.get("confidence", 1.0),
                )
            )

        # Save entities
        for e in result.get("entities", []):
            db.add(
                DocumentExtractedEntity(
                    id=e.get("id", str(uuid.uuid4())),
                    document_id=doc_id,
                    chunk_id=e.get("chunk_id"),
                    entity_type=e.get("entity_type", "COMPANY"),
                    entity_value=e.get("entity_value", ""),
                    normalized_value=e.get("normalized_value", ""),
                    confidence=e.get("confidence", 0.9),
                    context_snippet=e.get("context_snippet"),
                    page_number=e.get("page_number", 1),
                )
            )

        # Save citations
        for cit in result.get("citations", []):
            db.add(
                DocumentProvenanceRecord(
                    id=cit.get("id", str(uuid.uuid4())),
                    document_id=doc_id,
                    entity_id=cit.get("entity_id"),
                    claim_text=cit.get("claim_text", ""),
                    source_citation=cit.get("source_citation", ""),
                    page_number=cit.get("page_number", 1),
                    sha256_proof=cit.get("sha256_proof", ""),
                    confidence=cit.get("confidence", 1.0),
                )
            )

    db.commit()
    db.refresh(doc_record)

    return {
        "document": doc_record.to_dict(),
        "summary": {
            "chunks_count": len(result.get("chunks", [])),
            "tables_count": len(result.get("tables", [])),
            "entities_count": len(result.get("entities", [])),
            "citations_count": len(result.get("citations", [])),
        },
    }


@router.get("")
def list_documents(
    file_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Lists ingested documents within the current workspace."""
    query = db.query(DocumentRecord).filter(DocumentRecord.workspace_id == workspace.id)
    if file_type:
        query = query.filter(DocumentRecord.file_type == file_type.upper())
    if status_filter:
        query = query.filter(DocumentRecord.status == status_filter.upper())
    
    docs = query.order_by(DocumentRecord.created_at.desc()).limit(100).all()
    return {"documents": [d.to_dict() for d in docs], "count": len(docs)}


@router.get("/{document_id}")
def get_document_details(
    document_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves document record details with counts of chunks, tables, and entities."""
    doc = db.query(DocumentRecord).filter(
        DocumentRecord.id == document_id,
        DocumentRecord.workspace_id == workspace.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
    table_count = db.query(DocumentTable).filter(DocumentTable.document_id == document_id).count()
    entity_count = db.query(DocumentExtractedEntity).filter(DocumentExtractedEntity.document_id == document_id).count()

    res = doc.to_dict()
    res["chunk_count"] = chunk_count
    res["table_count"] = table_count
    res["entity_count"] = entity_count
    return res


@router.get("/{document_id}/chunks")
def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves semantic layout chunks for a document."""
    doc = db.query(DocumentRecord).filter(
        DocumentRecord.id == document_id,
        DocumentRecord.workspace_id == workspace.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.page_number, DocumentChunk.chunk_index).all()

    return {"document_id": document_id, "chunks": [c.to_dict() for c in chunks], "count": len(chunks)}


@router.get("/{document_id}/tables")
def get_document_tables(
    document_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves extracted structured tables for a document."""
    doc = db.query(DocumentRecord).filter(
        DocumentRecord.id == document_id,
        DocumentRecord.workspace_id == workspace.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    tables = db.query(DocumentTable).filter(
        DocumentTable.document_id == document_id
    ).order_by(DocumentTable.table_index).all()

    return {"document_id": document_id, "tables": [t.to_dict() for t in tables], "count": len(tables)}


@router.get("/{document_id}/entities")
def get_document_entities(
    document_id: str,
    entity_type: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves extracted entities with optional entity_type filter."""
    doc = db.query(DocumentRecord).filter(
        DocumentRecord.id == document_id,
        DocumentRecord.workspace_id == workspace.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    query = db.query(DocumentExtractedEntity).filter(DocumentExtractedEntity.document_id == document_id)
    if entity_type:
        query = query.filter(DocumentExtractedEntity.entity_type == entity_type.upper())

    entities = query.order_by(DocumentExtractedEntity.created_at.asc()).all()
    return {"document_id": document_id, "entities": [e.to_dict() for e in entities], "count": len(entities)}


@router.get("/{document_id}/provenance")
def get_document_provenance(
    document_id: str,
    db: Session = Depends(get_sync_db),
    workspace: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
):
    """Retrieves provenance citations and cryptographic grounding proofs."""
    doc = db.query(DocumentRecord).filter(
        DocumentRecord.id == document_id,
        DocumentRecord.workspace_id == workspace.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    provenance = db.query(DocumentProvenanceRecord).filter(
        DocumentProvenanceRecord.document_id == document_id
    ).all()

    return {"document_id": document_id, "citations": [p.to_dict() for p in provenance], "count": len(provenance)}


@router.post("/parse-text")
def parse_direct_text(
    request: ParseTextRequest,
    user: User = Depends(get_current_user),
):
    """Parses immediate text or markdown snippet without saving a file."""
    parse_result = DocumentParser.parse("snippet.txt", request.text.encode("utf-8"))
    tables = list(parse_result["tables"])
    if request.extract_tables:
        for chunk in parse_result["chunks"]:
            tables.extend(TableExtractor.extract_from_markdown(chunk["content"]))

    entities = []
    if request.extract_entities:
        for chunk in parse_result["chunks"]:
            entities.extend([e.to_dict() for e in EntityExtractor.extract_from_chunk(chunk["content"])])

    return {
        "chunks": parse_result["chunks"],
        "tables": tables,
        "entities": entities,
        "total_tokens": parse_result["total_tokens"],
    }

