import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.monitoring import (
    EntityNote,
    EntityComment,
    EntityTag,
    IntelligenceBrief,
    EntityChangeEvent,
    Alert
)
from app.models.workspace_ui import Bookmark
from app.models.technology import TechnologyObservation
from app.models.lead import IntentSignal, Company
from app.models.scoring import LeadScore
from packages.monitoring.notification_service import NotificationService


class CollaborationService:
    """
    Manages entity notes, threaded comments with @mentions, tagging,
    bookmarks, unified intelligence timeline, and daily/weekly briefs.
    """

    MENTION_REGEX = re.compile(r"@([a-zA-Z0-9_\-\.]+)")

    def __init__(self, db: Session):
        self.db = db
        self.notification_service = NotificationService(db)

    # 1. Notes
    def create_note(
        self,
        workspace_id: str,
        user_id: str,
        entity_type: str,
        entity_id: str,
        note_text: str,
        author_name: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> EntityNote:
        """Create a persistent research note on an entity."""
        note = EntityNote(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            author_name=author_name,
            note_text=note_text,
            tags=tags or []
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def list_notes(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[EntityNote]:
        """List notes attached to an entity."""
        return self.db.query(EntityNote).filter(
            and_(
                EntityNote.workspace_id == workspace_id,
                EntityNote.entity_type == entity_type,
                EntityNote.entity_id == entity_id
            )
        ).order_by(desc(EntityNote.created_at)).limit(limit).all()

    # 2. Comments & Mentions
    def create_comment(
        self,
        workspace_id: str,
        user_id: str,
        entity_type: str,
        entity_id: str,
        comment_text: str
    ) -> EntityComment:
        """
        Create a comment on an entity, parse @mentions, and dispatch in-app notifications.
        """
        mentioned_handles = self.MENTION_REGEX.findall(comment_text)
        # Unique list of mentions
        unique_mentions = list(dict.fromkeys(mentioned_handles))

        comment = EntityComment(
            workspace_id=workspace_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            comment_text=comment_text,
            mentions=unique_mentions
        )
        self.db.add(comment)
        self.db.commit()
        self.db.refresh(comment)

        # Notify mentioned users
        for mention in unique_mentions:
            self.notification_service.dispatch_notification(
                workspace_id=workspace_id,
                user_id=mention,
                title=f"Mentioned in {entity_type} discussion",
                message=f"You were mentioned by user {user_id}: \"{comment_text[:100]}...\"",
                severity="MEDIUM",
                category="LEAD"
            )

        return comment

    def list_comments(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[EntityComment]:
        """List comments on an entity."""
        return self.db.query(EntityComment).filter(
            and_(
                EntityComment.workspace_id == workspace_id,
                EntityComment.entity_type == entity_type,
                EntityComment.entity_id == entity_id
            )
        ).order_by(desc(EntityComment.created_at)).limit(limit).all()

    # 3. Tags
    def add_tag(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        tag_name: str
    ) -> EntityTag:
        """Tag an entity."""
        clean_tag = tag_name.strip().lower()
        existing = self.db.query(EntityTag).filter(
            and_(
                EntityTag.workspace_id == workspace_id,
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id,
                EntityTag.tag_name == clean_tag
            )
        ).first()
        if existing:
            return existing

        tag = EntityTag(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            tag_name=clean_tag
        )
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag

    def remove_tag(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        tag_name: str
    ) -> bool:
        """Remove a tag from an entity."""
        clean_tag = tag_name.strip().lower()
        tag = self.db.query(EntityTag).filter(
            and_(
                EntityTag.workspace_id == workspace_id,
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id,
                EntityTag.tag_name == clean_tag
            )
        ).first()
        if not tag:
            return False
        self.db.delete(tag)
        self.db.commit()
        return True

    def list_tags(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str
    ) -> List[str]:
        """List tags for an entity."""
        tags = self.db.query(EntityTag).filter(
            and_(
                EntityTag.workspace_id == workspace_id,
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id
            )
        ).all()
        return [t.tag_name for t in tags]

    # 4. Bookmarks
    def toggle_bookmark(
        self,
        workspace_id: str,
        user_id: str,
        entity_type: str,
        entity_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add or remove a bookmark for a user."""
        existing = self.db.query(Bookmark).filter(
            and_(
                Bookmark.workspace_id == workspace_id,
                Bookmark.user_id == user_id,
                Bookmark.entity_type == entity_type,
                Bookmark.entity_id == entity_id
            )
        ).first()

        if existing:
            self.db.delete(existing)
            self.db.commit()
            return {"bookmarked": False, "entity_id": entity_id}
        else:
            bm = Bookmark(
                workspace_id=workspace_id,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                notes=notes
            )
            self.db.add(bm)
            self.db.commit()
            return {"bookmarked": True, "entity_id": entity_id, "bookmark_id": bm.id}

    def list_bookmarks(
        self,
        workspace_id: str,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Bookmark]:
        """List bookmarks for a user."""
        return self.db.query(Bookmark).filter(
            and_(Bookmark.workspace_id == workspace_id, Bookmark.user_id == user_id)
        ).order_by(desc(Bookmark.created_at)).offset(offset).limit(limit).all()

    # 5. Unified Activity Timeline
    def get_unified_timeline(
        self,
        workspace_id: str,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Consolidates change events, alerts, notes, comments, tech observations,
        and intent signals into a unified chronological activity timeline.
        """
        timeline: List[Dict[str, Any]] = []

        # Change events
        changes = self.db.query(EntityChangeEvent).filter(
            and_(
                EntityChangeEvent.workspace_id == workspace_id,
                EntityChangeEvent.entity_type == entity_type,
                EntityChangeEvent.entity_id == entity_id
            )
        ).order_by(desc(EntityChangeEvent.detected_at)).limit(limit).all()

        for c in changes:
            timeline.append({
                "type": "CHANGE_EVENT",
                "id": c.id,
                "timestamp": c.detected_at.isoformat() if c.detected_at else None,
                "title": f"Changed {c.field_name}",
                "description": f"From '{c.old_value}' to '{c.new_value}'",
                "severity": c.significance_level,
                "score": c.significance_score,
                "source": c.source_name,
                "evidence_url": c.source_url
            })

        # Alerts
        alerts = self.db.query(Alert).filter(
            and_(
                Alert.workspace_id == workspace_id,
                Alert.entity_type == entity_type,
                Alert.entity_id == entity_id
            )
        ).order_by(desc(Alert.created_at)).limit(limit).all()

        for a in alerts:
            timeline.append({
                "type": "ALERT",
                "id": a.id,
                "timestamp": a.created_at.isoformat() if a.created_at else None,
                "title": a.title,
                "description": a.message,
                "severity": a.severity,
                "status": a.status,
                "evidence_summary": a.evidence_summary
            })

        # Notes
        notes = self.list_notes(workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id, limit=limit)
        for n in notes:
            timeline.append({
                "type": "NOTE",
                "id": n.id,
                "timestamp": n.created_at.isoformat() if n.created_at else None,
                "title": f"Note by {n.author_name or 'User'}",
                "description": n.note_text,
                "tags": n.tags
            })

        # Comments
        comments = self.list_comments(workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id, limit=limit)
        for cm in comments:
            timeline.append({
                "type": "COMMENT",
                "id": cm.id,
                "timestamp": cm.created_at.isoformat() if cm.created_at else None,
                "title": f"Comment",
                "description": cm.comment_text,
                "mentions": cm.mentions
            })

        # Sort timeline descending by timestamp
        timeline.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return timeline[:limit]

    # 6. Intelligence Brief Generator
    def generate_intelligence_brief(
        self,
        workspace_id: str,
        campaign_id: Optional[str] = None,
        days: int = 1,
        title: Optional[str] = None
    ) -> IntelligenceBrief:
        """
        Compiles an executive summary, top change events, affected leads,
        and recommended actions for the given time window (1 day = daily, 7 days = weekly).
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Query top changes
        changes = self.db.query(EntityChangeEvent).filter(
            and_(
                EntityChangeEvent.workspace_id == workspace_id,
                EntityChangeEvent.detected_at >= since,
                EntityChangeEvent.significance_level.in_(["HIGH", "CRITICAL"])
            )
        ).order_by(desc(EntityChangeEvent.significance_score)).limit(10).all()

        top_changes_payload = [
            {
                "change_id": c.id,
                "entity_type": c.entity_type,
                "entity_id": c.entity_id,
                "field_name": c.field_name,
                "change_class": c.change_class,
                "significance_level": c.significance_level,
                "significance_score": c.significance_score,
                "old_value": c.old_value,
                "new_value": c.new_value,
                "source": c.source_name
            }
            for c in changes
        ]

        # Affected companies
        affected_company_ids = list({c.entity_id for c in changes if c.entity_type == "COMPANY"})
        affected_leads_payload = []

        if affected_company_ids:
            companies = self.db.query(Company).filter(
                and_(Company.workspace_id == workspace_id, Company.id.in_(affected_company_ids))
            ).all()
            for comp in companies:
                affected_leads_payload.append({
                    "company_id": comp.id,
                    "company_name": comp.name,
                    "domain": comp.domain,
                    "lead_status": comp.status,
                    "country": comp.country
                })

        brief_title = title or f"Intelligence Brief ({'Daily' if days == 1 else 'Weekly'}) - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        summary = (
            f"Over the past {days} day(s), {len(changes)} high/critical intelligence changes were detected "
            f"affecting {len(affected_company_ids)} priority target companies. "
            f"Key findings include leadership transitions, technological footprint evolutions, "
            f"and verified high-intent signals."
        )

        brief = IntelligenceBrief(
            workspace_id=workspace_id,
            campaign_id=campaign_id,
            title=brief_title,
            executive_summary=summary,
            top_changes=top_changes_payload,
            affected_leads=affected_leads_payload,
            generated_at=datetime.now(timezone.utc)
        )
        self.db.add(brief)
        self.db.commit()
        self.db.refresh(brief)
        return brief
