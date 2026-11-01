"""
LeadNexus AI X — Dead-Letter Webhook Redrive Engine
Phase 35: Batch Re-dispatch, Circuit Inspection & Audited Redrive Jobs
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.webhooks import (
    EnterpriseWebhookEndpoint,
    EnterpriseWebhookDelivery,
    WebhookRedriveJob,
)
from packages.webhooks.delivery_service import WebhookDeliveryService

logger = logging.getLogger("leadnexus.webhooks.redrive")


class WebhookRedriveService:
    """
    Executes controlled redrive of dead-letter or failed webhook deliveries.
    """

    def __init__(self, delivery_service: Optional[WebhookDeliveryService] = None):
        self.delivery_service = delivery_service or WebhookDeliveryService()

    def create_redrive_job(
        self,
        db: Session,
        tenant_id: str,
        initiated_by: str,
        endpoint_id: Optional[str] = None,
        filter_status: str = "DEAD_LETTER",
        max_attempts: int = 50,
    ) -> WebhookRedriveJob:
        """
        Creates and executes a dead-letter redrive batch job.
        """
        now = datetime.now(timezone.utc)
        query = db.query(EnterpriseWebhookDelivery).filter(
            EnterpriseWebhookDelivery.tenant_id == tenant_id,
            EnterpriseWebhookDelivery.status == filter_status,
        )
        if endpoint_id:
            query = query.filter(EnterpriseWebhookDelivery.endpoint_id == endpoint_id)

        eligible_deliveries: List[EnterpriseWebhookDelivery] = query.limit(max_attempts).all()

        job = WebhookRedriveJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            endpoint_id=endpoint_id,
            initiated_by=initiated_by,
            filter_status=filter_status,
            max_attempts=max_attempts,
            total_eligible=len(eligible_deliveries),
            redriven_count=0,
            success_count=0,
            failed_count=0,
            status="RUNNING",
            created_at=now,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Execute redrive synchronously or queue
        for delivery in eligible_deliveries:
            endpoint = db.query(EnterpriseWebhookEndpoint).filter(
                EnterpriseWebhookEndpoint.id == delivery.endpoint_id
            ).first()

            if not endpoint or not endpoint.is_active:
                job.failed_count += 1
                job.redriven_count += 1
                continue

            # Re-dispatch with attempt reset
            new_delivery = self.delivery_service.dispatch(
                db=db,
                endpoint=endpoint,
                event_id=delivery.event_id,
                event_type=delivery.event_type,
                payload=delivery.payload,
                attempt_number=1,
                max_retries=delivery.max_retries,
            )

            job.redriven_count += 1
            if new_delivery.status == "SUCCESS":
                job.success_count += 1
            else:
                job.failed_count += 1

        job.status = "COMPLETED"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job
