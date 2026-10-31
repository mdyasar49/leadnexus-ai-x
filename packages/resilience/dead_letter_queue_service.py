"""
LeadNexus AI X - Phase 30: Enterprise Reliability & Resilience
Dead Letter Queue (DLQ) Service: Fault quarantine, error classification, and redrive orchestration.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.resilience import DeadLetterMessage, DLQStatus


class DLQClassifier:
    """Classifies runtime failures into actionable remediation categories."""

    @classmethod
    def classify_error(cls, error_msg: str) -> str:
        err_lower = error_msg.lower()
        if "429" in err_lower or "rate limit" in err_lower or "throttl" in err_lower:
            return "RATE_LIMIT"
        elif "401" in err_lower or "403" in err_lower or "unauthorized" in err_lower or "forbidden" in err_lower or "invalid_token" in err_lower:
            return "UPSTREAM_AUTH_FAILURE"
        elif "schema" in err_lower or "validation" in err_lower or "json" in err_lower or "parse" in err_lower:
            return "SCHEMA_CORRUPTION"
        elif "timeout" in err_lower or "connect" in err_lower or "502" in err_lower or "503" in err_lower or "504" in err_lower or "network" in err_lower:
            return "NETWORK_TRANSIENT"
        return "UNCLASSIFIED_ERROR"


class DeadLetterQueueService:
    """Quarantines failing messages, tracks retry counts, and coordinates redrives."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def quarantine_message(
        self,
        queue_name: str,
        task_id: str,
        payload: Dict[str, Any],
        error_message: str,
        workspace_id: Optional[str] = None,
        retry_count: int = 3,
    ) -> DeadLetterMessage:
        category = DLQClassifier.classify_error(error_message)

        dlq_msg = DeadLetterMessage(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            queue_name=queue_name,
            task_id=task_id,
            payload=payload,
            error_category=category,
            error_message=error_message,
            retry_count=retry_count,
            quarantined_at=datetime.now(timezone.utc),
            status=DLQStatus.QUARANTINED.value,
        )
        self.db.add(dlq_msg)
        self.db.commit()
        self.db.refresh(dlq_msg)
        return dlq_msg

    def redrive_message(self, dlq_id: str) -> Optional[DeadLetterMessage]:
        """Marks a quarantined message as REDRIVEN for worker retry."""
        msg = self.db.query(DeadLetterMessage).filter(DeadLetterMessage.id == dlq_id).first()
        if not msg:
            return None

        msg.status = DLQStatus.REDRIVEN.value
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def discard_message(self, dlq_id: str) -> Optional[DeadLetterMessage]:
        """Discards an unrecoverable corrupted message."""
        msg = self.db.query(DeadLetterMessage).filter(DeadLetterMessage.id == dlq_id).first()
        if not msg:
            return None

        msg.status = DLQStatus.DISCARDED.value
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def list_quarantined(self, queue_name: Optional[str] = None) -> List[DeadLetterMessage]:
        q = self.db.query(DeadLetterMessage).filter(DeadLetterMessage.status == DLQStatus.QUARANTINED.value)
        if queue_name:
            q = q.filter(DeadLetterMessage.queue_name == queue_name)
        return q.all()
