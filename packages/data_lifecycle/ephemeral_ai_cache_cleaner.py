"""
LeadNexus AI X - Phase 32: Enterprise Data Lifecycle & AI Memory Hygiene
Ephemeral AI Cache Cleaner: Vector buffer purging, transient LLM turn cleanup, and memory minimization.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.knowledge_retrieval import AIConversationMessage, RAGDocumentChunk


class EphemeralAICacheCleaner:
    """Purges transient conversation turns and temporary RAG chunk embeddings past TTL."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def purge_stale_conversation_turns(self, ttl_days: int = 14) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        stale_messages = self.db.query(AIConversationMessage).filter(
            AIConversationMessage.created_at < cutoff
        ).all()

        purged_count = len(stale_messages)
        for msg in stale_messages:
            self.db.delete(msg)

        if purged_count > 0:
            self.db.commit()

        return purged_count

    def purge_transient_rag_chunks(self, ttl_days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        stale_chunks = self.db.query(RAGDocumentChunk).filter(
            RAGDocumentChunk.created_at < cutoff
        ).all()

        purged_count = len(stale_chunks)
        for chunk in stale_chunks:
            self.db.delete(chunk)

        if purged_count > 0:
            self.db.commit()

        return purged_count
