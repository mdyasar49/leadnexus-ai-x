from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.monitoring import (
    Watchlist as MonWatchlist,
    WatchlistItem as MonWatchlistItem,
    WatchlistType,
    EntityChangeEvent,
    ChangeClass,
    SignificanceLevel
)
from app.models.lead import Company, Contact
from app.models.scoring import LeadScore
from app.models.workspace_ui import SavedSearch


class WatchlistService:
    """
    Manages multi-entity watchlists and continuous saved-search evaluation.
    Supports ENTITY_WATCHLIST, SEARCH_WATCHLIST, CAMPAIGN_WATCHLIST, TECHNOLOGY_WATCHLIST, and SIGNAL_WATCHLIST.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_watchlist(
        self,
        workspace_id: str,
        user_id: str,
        name: str,
        watchlist_type: str = WatchlistType.ENTITY_WATCHLIST.value,
        is_active: bool = True
    ) -> MonWatchlist:
        """Create a new user or workspace watchlist."""
        watchlist = MonWatchlist(
            workspace_id=workspace_id,
            user_id=user_id,
            name=name,
            watchlist_type=watchlist_type,
            is_active=is_active
        )
        self.db.add(watchlist)
        self.db.commit()
        self.db.refresh(watchlist)
        return watchlist

    def list_watchlists(
        self,
        workspace_id: str,
        user_id: Optional[str] = None,
        watchlist_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[MonWatchlist]:
        """List watchlists for workspace / user."""
        query = self.db.query(MonWatchlist).filter(MonWatchlist.workspace_id == workspace_id)
        if user_id:
            query = query.filter(MonWatchlist.user_id == user_id)
        if watchlist_type:
            query = query.filter(MonWatchlist.watchlist_type == watchlist_type)
        return query.order_by(desc(MonWatchlist.created_at)).offset(offset).limit(limit).all()

    def get_watchlist(self, workspace_id: str, watchlist_id: str) -> Optional[MonWatchlist]:
        """Get a specific watchlist by ID."""
        return self.db.query(MonWatchlist).filter(
            and_(MonWatchlist.workspace_id == workspace_id, MonWatchlist.id == watchlist_id)
        ).first()

    def add_item_to_watchlist(
        self,
        workspace_id: str,
        watchlist_id: str,
        entity_id: str,
        priority: str = "NORMAL",
        notes: Optional[str] = None
    ) -> MonWatchlistItem:
        """Add an entity to a watchlist."""
        existing = self.db.query(MonWatchlistItem).filter(
            and_(
                MonWatchlistItem.workspace_id == workspace_id,
                MonWatchlistItem.watchlist_id == watchlist_id,
                MonWatchlistItem.entity_id == entity_id
            )
        ).first()
        if existing:
            existing.priority = priority
            if notes:
                existing.notes = notes
            self.db.commit()
            self.db.refresh(existing)
            return existing

        item = MonWatchlistItem(
            workspace_id=workspace_id,
            watchlist_id=watchlist_id,
            entity_id=entity_id,
            priority=priority,
            notes=notes,
            last_checked=datetime.now(timezone.utc)
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def remove_item_from_watchlist(
        self,
        workspace_id: str,
        watchlist_id: str,
        entity_id: str
    ) -> bool:
        """Remove an item from a watchlist."""
        item = self.db.query(MonWatchlistItem).filter(
            and_(
                MonWatchlistItem.workspace_id == workspace_id,
                MonWatchlistItem.watchlist_id == watchlist_id,
                MonWatchlistItem.entity_id == entity_id
            )
        ).first()
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def list_watchlist_items(
        self,
        workspace_id: str,
        watchlist_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[MonWatchlistItem]:
        """List items inside a watchlist."""
        return self.db.query(MonWatchlistItem).filter(
            and_(
                MonWatchlistItem.workspace_id == workspace_id,
                MonWatchlistItem.watchlist_id == watchlist_id
            )
        ).order_by(desc(MonWatchlistItem.created_at)).offset(offset).limit(limit).all()

    def evaluate_saved_search_watchlist(
        self,
        workspace_id: str,
        saved_search_id: str,
        watchlist_id: str
    ) -> Dict[str, Any]:
        """
        Periodically evaluate a saved search against leads/companies.
        Identifies:
        - NEW_MATCH: companies newly matching criteria
        - MATCH_REMOVED: companies no longer matching
        - SCORE_CHANGED: companies with significant score shifts
        """
        saved_search = self.db.query(SavedSearch).filter(
            and_(SavedSearch.workspace_id == workspace_id, SavedSearch.id == saved_search_id)
        ).first()
        if not saved_search:
            return {"error": "Saved search not found", "new_matches": [], "removed_matches": []}

        filters = saved_search.filters or {}
        min_score = filters.get("min_score", 0.0)
        industry = filters.get("industry")
        country = filters.get("country")

        query = self.db.query(Company).filter(Company.workspace_id == workspace_id)
        if industry:
            query = query.filter(Company.industry.ilike(f"%{industry}%"))
        if country:
            query = query.filter(Company.country.ilike(f"%{country}%"))
        
        current_matching = query.all()
        current_matching_ids = {c.id for c in current_matching}

        # Items currently in this watchlist
        existing_items = self.db.query(MonWatchlistItem).filter(
            and_(
                MonWatchlistItem.workspace_id == workspace_id,
                MonWatchlistItem.watchlist_id == watchlist_id
            )
        ).all()
        existing_entity_ids = {item.entity_id for item in existing_items}

        new_ids = current_matching_ids - existing_entity_ids
        removed_ids = existing_entity_ids - current_matching_ids

        # Add new matches to watchlist
        added_count = 0
        for nid in new_ids:
            self.add_item_to_watchlist(
                workspace_id=workspace_id,
                watchlist_id=watchlist_id,
                entity_id=nid,
                priority="HIGH",
                notes=f"Auto-added from Saved Search '{saved_search.name}' match"
            )
            added_count += 1

        # Update last_checked for all evaluated items
        now = datetime.now(timezone.utc)
        for item in existing_items:
            item.last_checked = now
        self.db.commit()

        return {
            "saved_search_id": saved_search_id,
            "watchlist_id": watchlist_id,
            "new_matches_count": added_count,
            "removed_matches_count": len(removed_ids),
            "new_match_ids": list(new_ids),
            "removed_match_ids": list(removed_ids)
        }

    def get_entity_watch_summary(
        self,
        workspace_id: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """Summary of all watchlists monitoring this entity."""
        items = self.db.query(MonWatchlistItem).filter(
            and_(
                MonWatchlistItem.workspace_id == workspace_id,
                MonWatchlistItem.entity_id == entity_id
            )
        ).all()

        watchlist_ids = [it.watchlist_id for it in items]
        watchlists = self.db.query(MonWatchlist).filter(
            MonWatchlist.id.in_(watchlist_ids)
        ).all() if watchlist_ids else []

        return {
            "entity_id": entity_id,
            "is_watched": len(items) > 0,
            "watchlist_count": len(items),
            "watchlists": [
                {
                    "watchlist_id": w.id,
                    "name": w.name,
                    "type": w.watchlist_type,
                    "priority": next((it.priority for it in items if it.watchlist_id == w.id), "NORMAL")
                }
                for w in watchlists
            ]
        }
