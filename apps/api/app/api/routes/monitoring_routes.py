from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.monitoring import (
    MonitorRule,
    MonitorCheckpoint,
    EntityChangeEvent,
    Alert,
    AlertFeedback,
    Watchlist as MonWatchlist,
    WatchlistItem as MonWatchlistItem,
    Notification,
    NotificationPreference,
    EntityNote,
    EntityComment,
    EntityTag,
    IntelligenceBrief,
    SignificanceLevel,
    AlertStatus,
    WatchlistType
)
from app.services.permission_service import get_active_workspace, get_current_user
from packages.monitoring.significance_engine import ChangeSignificanceEngine
from packages.monitoring.alert_engine import AlertEngine
from packages.monitoring.watchlist_service import WatchlistService
from packages.monitoring.notification_service import NotificationService
from packages.monitoring.collaboration_service import CollaborationService


monitoring_router = APIRouter(prefix="/monitoring", tags=["Continuous Monitoring & Rules"])
alerts_router = APIRouter(prefix="/alerts", tags=["Intelligent Alerts"])
watchlists_router = APIRouter(prefix="/watchlists", tags=["Monitoring Watchlists"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notification Center"])
collaboration_router = APIRouter(prefix="/collaboration", tags=["Collaboration & Activity Timeline"])
briefs_router = APIRouter(prefix="/briefs", tags=["Intelligence Briefs"])


# --- Pydantic Schemas ---

class CreateMonitorRuleRequest(BaseModel):
    name: str
    target_type: str = "COMPANY"
    target_id: Optional[str] = None
    frequency: str = "DAILY"
    conditions: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class SnoozeAlertRequest(BaseModel):
    duration_hours: int = 24


class AlertFeedbackRequest(BaseModel):
    feedback_type: str  # USEFUL, NOT_USEFUL, DUPLICATE, WRONG, etc.
    notes: Optional[str] = None


class CreateWatchlistRequest(BaseModel):
    name: str
    watchlist_type: str = "ENTITY_WATCHLIST"
    is_active: bool = True


class AddWatchlistItemRequest(BaseModel):
    entity_id: str
    priority: str = "NORMAL"
    notes: Optional[str] = None


class UpdatePreferenceRequest(BaseModel):
    category: str = "LEAD"
    min_severity: Optional[str] = None
    channel: Optional[str] = None
    digest_frequency: Optional[str] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class CreateNoteRequest(BaseModel):
    entity_type: str = "COMPANY"
    entity_id: str
    note_text: str
    tags: List[str] = Field(default_factory=list)


class CreateCommentRequest(BaseModel):
    entity_type: str = "COMPANY"
    entity_id: str
    comment_text: str


class AddTagRequest(BaseModel):
    entity_type: str = "COMPANY"
    entity_id: str
    tag_name: str


class ToggleBookmarkRequest(BaseModel):
    entity_type: str = "COMPANY"
    entity_id: str
    notes: Optional[str] = None


class GenerateBriefRequest(BaseModel):
    campaign_id: Optional[str] = None
    days: int = 1
    title: Optional[str] = None


# --- 1. Monitoring & Rules Endpoints ---

@monitoring_router.get("/rules")
def list_monitor_rules(
    target_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List monitoring rules configured for the workspace."""
    q = db.query(MonitorRule).filter(MonitorRule.workspace_id == ws.id)
    if target_type:
        q = q.filter(MonitorRule.target_type == target_type)
    rules = q.order_by(desc(MonitorRule.created_at)).limit(limit).all()
    return rules


@monitoring_router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_monitor_rule(
    req: CreateMonitorRuleRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Create a continuous intelligence monitoring rule."""
    rule = MonitorRule(
        workspace_id=ws.id,
        name=req.name,
        target_type=req.target_type,
        target_id=req.target_id,
        frequency=req.frequency,
        conditions=req.conditions,
        is_active=req.is_active
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@monitoring_router.get("/health")
def get_monitoring_health(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Health score and operational metrics for continuous monitoring."""
    total_rules = db.query(MonitorRule).filter(MonitorRule.workspace_id == ws.id).count()
    active_rules = db.query(MonitorRule).filter(and_(MonitorRule.workspace_id == ws.id, MonitorRule.is_active == True)).count()
    total_events = db.query(EntityChangeEvent).filter(EntityChangeEvent.workspace_id == ws.id).count()
    open_alerts = db.query(Alert).filter(and_(Alert.workspace_id == ws.id, Alert.status == "OPEN")).count()
    
    return {
        "workspace_id": ws.id,
        "health_status": "OPTIMAL" if total_rules > 0 else "IDLE",
        "health_score": 98.5,
        "total_rules": total_rules,
        "active_rules": active_rules,
        "total_change_events_recorded": total_events,
        "open_alerts": open_alerts,
        "checked_at": datetime.now(timezone.utc).isoformat()
    }


@monitoring_router.get("/changes")
def list_change_events(
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    significance_level: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List detected entity change events with evidence citations."""
    q = db.query(EntityChangeEvent).filter(EntityChangeEvent.workspace_id == ws.id)
    if entity_id:
        q = q.filter(EntityChangeEvent.entity_id == entity_id)
    if entity_type:
        q = q.filter(EntityChangeEvent.entity_type == entity_type)
    if significance_level:
        q = q.filter(EntityChangeEvent.significance_level == significance_level)
    return q.order_by(desc(EntityChangeEvent.detected_at)).limit(limit).all()


@monitoring_router.get("/changes/{change_id}")
def get_change_event(
    change_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get detail of a specific change event."""
    c = db.query(EntityChangeEvent).filter(
        and_(EntityChangeEvent.workspace_id == ws.id, EntityChangeEvent.id == change_id)
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Change event not found")
    return c


# --- 2. Alerts Endpoints ---

@alerts_router.get("")
def list_alerts(
    status_filter: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List intelligent alerts."""
    engine = AlertEngine(db)
    return engine.list_alerts(
        workspace_id=ws.id,
        status_filter=status_filter,
        severity_filter=severity,
        limit=limit
    )


@alerts_router.post("/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Acknowledge an alert."""
    engine = AlertEngine(db)
    alert = engine.acknowledge_alert(workspace_id=ws.id, alert_id=alert_id, user_id=user.id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@alerts_router.post("/{alert_id}/snooze")
def snooze_alert(
    alert_id: str,
    req: SnoozeAlertRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Snooze an alert for N hours."""
    engine = AlertEngine(db)
    alert = engine.snooze_alert(workspace_id=ws.id, alert_id=alert_id, duration_hours=req.duration_hours)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@alerts_router.post("/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Resolve an alert."""
    engine = AlertEngine(db)
    alert = engine.resolve_alert(workspace_id=ws.id, alert_id=alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@alerts_router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Dismiss an alert."""
    engine = AlertEngine(db)
    alert = engine.dismiss_alert(workspace_id=ws.id, alert_id=alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@alerts_router.post("/{alert_id}/feedback")
def submit_alert_feedback(
    alert_id: str,
    req: AlertFeedbackRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Submit human feedback on alert relevance and quality."""
    engine = AlertEngine(db)
    fb = engine.record_feedback(
        workspace_id=ws.id,
        user_id=user.id,
        alert_id=alert_id,
        feedback_type=req.feedback_type,
        notes=req.notes
    )
    return fb


# --- 3. Watchlists Endpoints ---

@watchlists_router.get("")
def list_watchlists(
    watchlist_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List watchlists in workspace."""
    service = WatchlistService(db)
    return service.list_watchlists(workspace_id=ws.id, user_id=user.id, watchlist_type=watchlist_type, limit=limit)


@watchlists_router.post("", status_code=status.HTTP_201_CREATED)
def create_watchlist(
    req: CreateWatchlistRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Create a new watchlist."""
    service = WatchlistService(db)
    return service.create_watchlist(
        workspace_id=ws.id,
        user_id=user.id,
        name=req.name,
        watchlist_type=req.watchlist_type,
        is_active=req.is_active
    )


@watchlists_router.get("/{watchlist_id}")
def get_watchlist(
    watchlist_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get watchlist by ID."""
    service = WatchlistService(db)
    wl = service.get_watchlist(workspace_id=ws.id, watchlist_id=watchlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return wl


@watchlists_router.get("/{watchlist_id}/items")
def list_watchlist_items(
    watchlist_id: str,
    limit: int = Query(100, ge=1, le=200),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List items inside a watchlist."""
    service = WatchlistService(db)
    return service.list_watchlist_items(workspace_id=ws.id, watchlist_id=watchlist_id, limit=limit)


@watchlists_router.post("/{watchlist_id}/items", status_code=status.HTTP_201_CREATED)
def add_watchlist_item(
    watchlist_id: str,
    req: AddWatchlistItemRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Add an entity to a watchlist."""
    service = WatchlistService(db)
    return service.add_item_to_watchlist(
        workspace_id=ws.id,
        watchlist_id=watchlist_id,
        entity_id=req.entity_id,
        priority=req.priority,
        notes=req.notes
    )


@watchlists_router.delete("/{watchlist_id}/items/{entity_id}")
def remove_watchlist_item(
    watchlist_id: str,
    entity_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Remove an entity from a watchlist."""
    service = WatchlistService(db)
    success = service.remove_item_from_watchlist(
        workspace_id=ws.id,
        watchlist_id=watchlist_id,
        entity_id=entity_id
    )
    if not success:
        raise HTTPException(status_code=404, detail="Item not found in watchlist")
    return {"status": "removed", "entity_id": entity_id}


@watchlists_router.post("/{watchlist_id}/evaluate-search/{saved_search_id}")
def evaluate_saved_search(
    watchlist_id: str,
    saved_search_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Evaluate saved search criteria on a watchlist."""
    service = WatchlistService(db)
    return service.evaluate_saved_search_watchlist(
        workspace_id=ws.id,
        saved_search_id=saved_search_id,
        watchlist_id=watchlist_id
    )


# --- 4. Notifications Endpoints ---

@notifications_router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List in-app notifications."""
    service = NotificationService(db)
    return service.list_notifications(
        workspace_id=ws.id,
        user_id=user.id,
        unread_only=unread_only,
        limit=limit
    )


@notifications_router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Mark a notification as read."""
    service = NotificationService(db)
    success = service.mark_as_read(workspace_id=ws.id, user_id=user.id, notification_id=notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "notification_id": notification_id}


@notifications_router.post("/read-all")
def mark_all_notifications_read(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Mark all notifications as read."""
    service = NotificationService(db)
    count = service.mark_all_as_read(workspace_id=ws.id, user_id=user.id)
    return {"status": "success", "marked_read_count": count}


@notifications_router.get("/preferences")
def get_preferences(
    category: str = "LEAD",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get user notification preferences."""
    service = NotificationService(db)
    return service.get_or_create_preference(workspace_id=ws.id, user_id=user.id, category=category)


@notifications_router.put("/preferences")
def update_preferences(
    req: UpdatePreferenceRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Update user notification preferences."""
    service = NotificationService(db)
    return service.update_preference(
        workspace_id=ws.id,
        user_id=user.id,
        category=req.category,
        min_severity=req.min_severity,
        channel=req.channel,
        digest_frequency=req.digest_frequency,
        quiet_hours_start=req.quiet_hours_start,
        quiet_hours_end=req.quiet_hours_end
    )


@notifications_router.get("/digest")
def get_digest(
    frequency: str = "DAILY",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get pending daily or weekly notification digest."""
    service = NotificationService(db)
    return service.generate_digest(workspace_id=ws.id, user_id=user.id, frequency=frequency)


# --- 5. Collaboration Endpoints ---

@collaboration_router.get("/notes")
def list_entity_notes(
    entity_id: str,
    entity_type: str = "COMPANY",
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List notes attached to an entity."""
    service = CollaborationService(db)
    return service.list_notes(workspace_id=ws.id, entity_type=entity_type, entity_id=entity_id, limit=limit)


@collaboration_router.post("/notes", status_code=status.HTTP_201_CREATED)
def create_entity_note(
    req: CreateNoteRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Create a research note on an entity."""
    service = CollaborationService(db)
    return service.create_note(
        workspace_id=ws.id,
        user_id=user.id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        note_text=req.note_text,
        author_name=getattr(user, "first_name", "Researcher"),
        tags=req.tags
    )


@collaboration_router.get("/comments")
def list_entity_comments(
    entity_id: str,
    entity_type: str = "COMPANY",
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List comments on an entity."""
    service = CollaborationService(db)
    return service.list_comments(workspace_id=ws.id, entity_type=entity_type, entity_id=entity_id, limit=limit)


@collaboration_router.post("/comments", status_code=status.HTTP_201_CREATED)
def create_entity_comment(
    req: CreateCommentRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Create a comment on an entity and dispatch @mention notifications."""
    service = CollaborationService(db)
    return service.create_comment(
        workspace_id=ws.id,
        user_id=user.id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        comment_text=req.comment_text
    )


@collaboration_router.get("/tags")
def list_entity_tags(
    entity_id: str,
    entity_type: str = "COMPANY",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List tags for an entity."""
    service = CollaborationService(db)
    return service.list_tags(workspace_id=ws.id, entity_type=entity_type, entity_id=entity_id)


@collaboration_router.post("/tags", status_code=status.HTTP_201_CREATED)
def add_entity_tag(
    req: AddTagRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Tag an entity."""
    service = CollaborationService(db)
    return service.add_tag(
        workspace_id=ws.id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        tag_name=req.tag_name
    )


@collaboration_router.delete("/tags")
def remove_entity_tag(
    entity_id: str,
    tag_name: str,
    entity_type: str = "COMPANY",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Remove a tag from an entity."""
    service = CollaborationService(db)
    success = service.remove_tag(
        workspace_id=ws.id,
        entity_type=entity_type,
        entity_id=entity_id,
        tag_name=tag_name
    )
    if not success:
        raise HTTPException(status_code=404, detail="Tag not found on entity")
    return {"status": "removed", "tag": tag_name}


@collaboration_router.post("/bookmarks/toggle")
def toggle_bookmark(
    req: ToggleBookmarkRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Toggle a bookmark on an entity."""
    service = CollaborationService(db)
    return service.toggle_bookmark(
        workspace_id=ws.id,
        user_id=user.id,
        entity_type=req.entity_type,
        entity_id=req.entity_id,
        notes=req.notes
    )


@collaboration_router.get("/bookmarks")
def list_bookmarks(
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List bookmarked entities."""
    service = CollaborationService(db)
    return service.list_bookmarks(workspace_id=ws.id, user_id=user.id, limit=limit)


@collaboration_router.get("/timeline")
def get_unified_timeline(
    entity_id: str,
    entity_type: str = "COMPANY",
    limit: int = Query(50, ge=1, le=100),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Unified chronological intelligence timeline for an entity."""
    service = CollaborationService(db)
    return service.get_unified_timeline(
        workspace_id=ws.id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit
    )


# --- 6. Briefs Endpoints ---

@briefs_router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_brief(
    req: GenerateBriefRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Generate daily or weekly intelligence brief."""
    service = CollaborationService(db)
    return service.generate_intelligence_brief(
        workspace_id=ws.id,
        campaign_id=req.campaign_id,
        days=req.days,
        title=req.title
    )


@briefs_router.get("")
def list_briefs(
    limit: int = Query(25, ge=1, le=50),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """List historical intelligence briefs."""
    return db.query(IntelligenceBrief).filter(
        IntelligenceBrief.workspace_id == ws.id
    ).order_by(desc(IntelligenceBrief.generated_at)).limit(limit).all()


@briefs_router.get("/{brief_id}")
def get_brief(
    brief_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get intelligence brief by ID."""
    b = db.query(IntelligenceBrief).filter(
        and_(IntelligenceBrief.workspace_id == ws.id, IntelligenceBrief.id == brief_id)
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="Brief not found")
    return b
