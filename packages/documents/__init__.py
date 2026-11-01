"""
LeadNexus AI X - Phase 42: Document & Unstructured Data Intelligence Package
Exposes sanitizer, parser, table extractor, entity extractor, and provenance tracker.
"""

from typing import Any, Dict, List, Optional
import uuid

from packages.documents.document_sanitizer import DocumentSanitizer
from packages.documents.document_parser import DocumentParser, ParsedChunk, ParsedTable
from packages.documents.table_extractor import TableExtractor
from packages.documents.entity_extractor import EntityExtractor, ExtractedEntity
from packages.documents.provenance_tracker import DocumentProvenanceTracker


class DocumentIntelligencePipeline:
    """Unified pipeline orchestrating end-to-end processing of unstructured documents."""

    @classmethod
    def process_document(
        cls,
        filename: str,
        content: bytes,
        workspace_id: str,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        doc_id = document_id or str(uuid.uuid4())

        # 1. Security inspection & malware scan
        security_assessment = DocumentSanitizer.inspect(filename, content)
        if not security_assessment["is_safe"]:
            return {
                "document_id": doc_id,
                "workspace_id": workspace_id,
                "filename": filename,
                "status": "REJECTED" if security_assessment["malware_status"] == "REJECTED" else "FLAGGED",
                "security": security_assessment,
                "chunks": [],
                "tables": [],
                "entities": [],
                "citations": [],
            }

        # 2. Layout parsing into chunks and tables
        parse_result = DocumentParser.parse(filename, content)

        # 3. Additional Markdown table extraction if present in text
        all_tables = list(parse_result["tables"])
        for chunk in parse_result["chunks"]:
            md_tables = TableExtractor.extract_from_markdown(chunk["content"])
            for mdt in md_tables:
                all_tables.append({
                    "headers": mdt["headers"],
                    "rows": mdt["rows"],
                    "row_count": mdt["row_count"],
                    "col_count": mdt["col_count"],
                    "page_number": chunk["page_number"],
                    "table_index": len(all_tables),
                    "confidence": mdt["confidence"],
                })

        # 4. Entity extraction across chunks
        extracted_entities: List[Dict[str, Any]] = []
        citations: List[Dict[str, Any]] = []

        for chunk in parse_result["chunks"]:
            chunk_entities = EntityExtractor.extract_from_chunk(
                text=chunk["content"],
                page_number=chunk["page_number"],
                chunk_id=chunk.get("id"),
            )
            for ent in chunk_entities:
                ent_dict = ent.to_dict()
                ent_id = str(uuid.uuid4())
                ent_dict["id"] = ent_id
                extracted_entities.append(ent_dict)

                # 5. Create verifiable citation
                citation = DocumentProvenanceTracker.create_citation(
                    document_id=doc_id,
                    claim_text=f"{ent.entity_type}: {ent.entity_value}",
                    source_snippet=ent.context_snippet,
                    page_number=ent.page_number,
                    entity_id=ent_id,
                    confidence=ent.confidence,
                )
                citations.append(citation)

        return {
            "document_id": doc_id,
            "workspace_id": workspace_id,
            "filename": filename,
            "file_type": parse_result["file_type"],
            "page_count": parse_result["page_count"],
            "ocr_applied": parse_result["ocr_applied"],
            "status": "COMPLETED",
            "security": security_assessment,
            "chunks": parse_result["chunks"],
            "tables": all_tables,
            "entities": extracted_entities,
            "citations": citations,
            "total_tokens": parse_result["total_tokens"],
        }


__all__ = [
    "DocumentSanitizer",
    "DocumentParser",
    "ParsedChunk",
    "ParsedTable",
    "TableExtractor",
    "EntityExtractor",
    "ExtractedEntity",
    "DocumentProvenanceTracker",
    "DocumentIntelligencePipeline",
]
