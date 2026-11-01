"""
Enterprise Event Envelope Definition & Validation.
Follows CloudEvents and LeadNexus strict event envelope specification:
event_id, event_type, event_version, tenant_id, aggregate_type, aggregate_id,
occurred_at, source_service, correlation_id, causation_id, schema_version, payload, checksum.
"""

import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    event_version: str = "1.0.0"
    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_service: str = "leadnexus-core"
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: Optional[str] = None
    schema_version: str = "1.0.0"
    payload: Dict[str, Any] = Field(default_factory=dict)
    checksum: Optional[str] = None

    def model_post_init(self, __context):
        if not self.checksum:
            self.checksum = self.calculate_checksum()

    def calculate_checksum(self) -> str:
        """Calculates deterministic SHA-256 checksum of payload."""
        payload_bytes = json.dumps(self.payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    def verify_checksum(self) -> bool:
        """Verifies payload integrity against checksum."""
        return self.checksum == self.calculate_checksum()
