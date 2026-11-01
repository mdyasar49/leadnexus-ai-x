"""
LeadNexus AI X - Phase 47: Real-Time Streaming Intelligence & Signal Stream API Routes
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_sync_db
from app.models.signal_stream import (
    LiveSignalRecord,
    StreamSubscriptionRecord,
    SignalAnomalyAlert,
    PublishSignalRequest,
    LiveSignalResponse,
    CreateSubscriptionRequest,
    SubscriptionResponse,
    AnomalyAlertResponse,
    StreamStatsResponse,
    SignalType,
)
from packages.streaming.stream_hub import SignalStreamHub

router = APIRouter(prefix="/stream", tags=["Real-Time Streaming Intelligence"])

# Shared runtime SignalStreamHub singleton
_shared_stream_hub = SignalStreamHub(
    buffer_capacity=1000,
    dedup_window_seconds=60.0,
    spike_window_seconds=300.0,
    spike_threshold=3,
)


def _seed_initial_stream_signals():
    """Populates realistic initial signals into the stream buffer."""
    if _shared_stream_hub.buffer.total_appended > 0:
        return

    signals = [
        {
            "signal_type": "TECH_ADOPTION",
            "company_name": "Atlassian Corp",
            "topic": "signals.technology",
            "payload": {"technology": "React 19", "country": "Australia", "category": "Frontend"},
            "confidence": 0.98,
            "source": "GITHUB_REPO_ANALYZER",
        },
        {
            "signal_type": "HIRING_SURGE",
            "company_name": "Canva Inc",
            "topic": "signals.hiring",
            "payload": {"role": "Senior AI Systems Engineer", "headcount": 15, "city": "Sydney"},
            "confidence": 0.96,
            "source": "JOB_BOARD_STREAM",
        },
        {
            "signal_type": "BUYING_INTENT",
            "company_name": "Odoo Australia Pty Ltd",
            "topic": "signals.intent",
            "payload": {"technology": "Enterprise ERP", "stage": "EVALUATING", "country": "Australia"},
            "confidence": 0.95,
            "source": "WEB_INTENT_RADAR",
        },
        {
            "signal_type": "LEADERSHIP_CHANGE",
            "company_name": "Nexus Cloud Solutions",
            "topic": "signals.leadership",
            "payload": {"executive": "Sarah Jenkins", "title": "Chief Technology Officer"},
            "confidence": 0.99,
            "source": "EXECUTIVE_RADAR",
        },
    ]

    for s in signals:
        _shared_stream_hub.publish(s)


# Seed initial streaming signals
_seed_initial_stream_signals()


@router.post("/signals/publish", status_code=status.HTTP_201_CREATED)
def publish_live_signal(
    payload: PublishSignalRequest,
    db: Session = Depends(get_sync_db),
):
    """Publishes a live business intelligence signal into the streaming hub and database."""
    signal_id = f"sig_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    # Persist in DB
    record = LiveSignalRecord(
        id=signal_id,
        signal_type=payload.signal_type.value,
        company_name=payload.company_name,
        entity_key=payload.entity_key or f"company:{payload.company_name.lower().replace(' ', '-')}",
        topic=payload.topic,
        payload=payload.payload,
        confidence=payload.confidence,
        source=payload.source,
        timestamp=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Publish to runtime stream hub
    hub_result = _shared_stream_hub.publish({
        "id": record.id,
        "signal_type": record.signal_type,
        "company_name": record.company_name,
        "entity_key": record.entity_key,
        "topic": record.topic,
        "payload": record.payload,
        "confidence": record.confidence,
        "source": record.source,
        "timestamp": record.timestamp.isoformat(),
    })

    # If anomaly detected, record in DB as well
    if hub_result.get("anomaly_detected") and hub_result.get("anomaly"):
        anom = hub_result["anomaly"]
        anom_record = SignalAnomalyAlert(
            id=anom["id"],
            company_name=anom["company_name"],
            signal_count=anom["signal_count"],
            window_seconds=anom["window_seconds"],
            severity=anom["severity"],
            description=anom["description"],
            timestamp=now,
        )
        db.add(anom_record)
        db.commit()

    return {
        "status": hub_result["status"],
        "signal_id": record.id,
        "topic": record.topic,
        "dispatched_subscribers": hub_result.get("dispatched_subscribers", 0),
        "anomaly_detected": hub_result.get("anomaly_detected", False),
    }


@router.get("/signals/recent", response_model=List[LiveSignalResponse])
def get_recent_stream_signals(
    topic: Optional[str] = Query(None, description="Topic filter (e.g. signals.technology)"),
    company: Optional[str] = Query(None, description="Company filter"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(25, ge=1, le=100),
):
    """Retrieves recent real-time signals from the backpressure ring buffer."""
    criteria: Dict[str, Any] = {}
    if company:
        criteria["company"] = company
    if min_confidence:
        criteria["min_confidence"] = min_confidence

    signals = _shared_stream_hub.get_recent_signals(
        topic=topic,
        filter_criteria=criteria,
        limit=limit,
    )

    formatted = []
    for s in signals:
        ts = s.get("timestamp")
        if isinstance(ts, str):
            try:
                parsed_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                parsed_ts = datetime.now(timezone.utc)
        else:
            parsed_ts = datetime.now(timezone.utc)

        formatted.append(
            LiveSignalResponse(
                id=s.get("id", f"sig_{uuid.uuid4().hex[:8]}"),
                signal_type=s.get("signal_type", "UNKNOWN"),
                company_name=s.get("company_name", "Unknown"),
                entity_key=s.get("entity_key"),
                topic=s.get("topic", "signals.general"),
                payload=s.get("payload", {}),
                confidence=s.get("confidence", 0.95),
                source=s.get("source", "LIVE_STREAM"),
                timestamp=parsed_ts,
            )
        )
    return formatted


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_stream_subscription(
    payload: CreateSubscriptionRequest,
    db: Session = Depends(get_sync_db),
):
    """Creates a real-time stream subscription with specific topic and filter criteria."""
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    record = StreamSubscriptionRecord(
        id=sub_id,
        user_id=payload.user_id,
        topic=payload.topic,
        filter_criteria=payload.filter_criteria,
        is_active=True,
        created_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    _shared_stream_hub.subscribe(
        topic=payload.topic,
        filter_criteria=payload.filter_criteria,
        subscription_id=record.id,
    )

    return SubscriptionResponse(
        id=record.id,
        topic=record.topic,
        filter_criteria=record.filter_criteria,
        is_active=record.is_active,
        created_at=record.created_at,
    )


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
def list_stream_subscriptions(
    db: Session = Depends(get_sync_db),
):
    """Lists all active streaming subscriptions."""
    records = db.query(StreamSubscriptionRecord).filter(StreamSubscriptionRecord.is_active == True).all()
    return [
        SubscriptionResponse(
            id=r.id,
            topic=r.topic,
            filter_criteria=r.filter_criteria,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.delete("/subscriptions/{subscription_id}")
def delete_stream_subscription(
    subscription_id: str,
    db: Session = Depends(get_sync_db),
):
    """Cancels and removes a stream subscription."""
    _shared_stream_hub.unsubscribe(subscription_id)
    record = db.query(StreamSubscriptionRecord).filter(StreamSubscriptionRecord.id == subscription_id).first()
    if record:
        record.is_active = False
        db.commit()
    return {"status": "SUCCESS", "message": f"Subscription {subscription_id} unsubscribed"}


@router.get("/anomalies", response_model=List[AnomalyAlertResponse])
def get_stream_anomalies(
    limit: int = Query(20, ge=1, le=50),
):
    """Returns recently detected buying intent surges and hiring anomaly alerts."""
    anomalies = _shared_stream_hub.aggregator.get_recent_anomalies(limit=limit)
    res = []
    for a in anomalies:
        ts = a.get("timestamp")
        parsed_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")) if isinstance(ts, str) else datetime.now(timezone.utc)
        res.append(
            AnomalyAlertResponse(
                id=a["id"],
                company_name=a["company_name"],
                signal_count=a["signal_count"],
                window_seconds=a["window_seconds"],
                severity=a["severity"],
                description=a["description"],
                timestamp=parsed_ts,
            )
        )
    return res


@router.get("/stats", response_model=StreamStatsResponse)
def get_stream_stats():
    """Returns streaming throughput, active topics, and backpressure buffer health."""
    stats = _shared_stream_hub.get_stats()
    return StreamStatsResponse(**stats)


@router.post("/simulate-surge")
def simulate_signal_surge(
    company_name: str = Query("Odoo Australia Pty Ltd"),
    surge_count: int = Query(4, ge=2, le=10),
    db: Session = Depends(get_sync_db),
):
    """Generates a burst of signals to verify real-time spike and anomaly detection."""
    results = []
    for i in range(surge_count):
        req = PublishSignalRequest(
            signal_type=SignalType.BUYING_INTENT,
            company_name=company_name,
            topic="signals.intent.surge",
            payload={"burst_index": i + 1, "intent_score": 92 + i, "country": "Australia"},
            confidence=0.97,
            source="SURGE_SIMULATOR",
        )
        res = publish_live_signal(req, db=db)
        results.append(res)

    return {
        "status": "SURGE_SIMULATED",
        "company_name": company_name,
        "signals_emitted": surge_count,
        "results": results,
    }
