import os
import sys
import unittest
import uuid
from datetime import datetime, timezone, timedelta

# Ensure project paths are in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from fastapi.testclient import TestClient
from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, SessionLocal, get_sync_db
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.lead import Company, Contact
from app.models.scoring import LeadScore
from app.models.workspace_ui import SavedSearch, Bookmark
from app.models.monitoring import (
    MonitorRule,
    MonitorCheckpoint,
    EntityChangeEvent,
    Alert,
    AlertFingerprint,
    AlertFeedback,
    Watchlist as MonWatchlist,
    WatchlistItem as MonWatchlistItem,
    Notification,
    NotificationPreference,
    EntityNote,
    EntityComment,
    EntityTag,
    IntelligenceBrief,
    ChangeClass,
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


class TestPhase20Monitoring(unittest.TestCase):
    """Test suite covering Phase 20 Enterprise Continuous Monitoring, Intelligent Alerts, Watchlists & Collaboration."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"
        cls.user_2_id = f"test-user-2-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"monitoring_lead_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Monitoring",
            last_name="Architect",
            is_active=True,
            is_superuser=True
        )
        cls.user_2 = User(
            id=cls.user_2_id,
            email=f"analyst_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="Intelligence",
            last_name="Analyst",
            is_active=True,
            is_superuser=False
        )
        cls.db.add(cls.user)
        cls.db.add(cls.user_2)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="Monitoring Intelligence Workspace",
            slug=f"mon-ws-{uuid.uuid4().hex[:6]}"
        )
        cls.db.add(cls.ws)
        cls.db.commit()

        # Seed test company
        cls.comp = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Apex Dynamics Australia",
            normalized_name="apex dynamics australia",
            domain="apexdynamics.com.au",
            country="Australia",
            industry="Mining & Resources",
            lead_score=85,
            status="RESEARCHED"
        )
        cls.db.add(cls.comp)

        # Seed LeadScore
        cls.score = LeadScore(
            id=str(uuid.uuid4()),
            company_id=cls.comp.id,
            workspace_id=cls.ws_id,
            lead_priority_score=88.5,
            priority_tier="P1_HIGH",
            intent_score=85.0,
            icp_fit_score=92.0
        )
        cls.db.add(cls.score)
        cls.db.commit()

        # TestClient override dependencies
        def override_get_active_workspace():
            return cls.ws

        def override_get_current_user():
            return cls.user

        def override_get_sync_db():
            yield cls.db

        app.dependency_overrides[get_active_workspace] = override_get_active_workspace
        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_sync_db] = override_get_sync_db

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.db.close()

    def test_change_significance_noise_detection(self):
        """Verify noise patterns (e.g. copyright updates, session tokens) are classified as NOISE."""
        engine = ChangeSignificanceEngine(self.db)
        
        # Test copyright update
        chg_class, score, level = engine.classify_change(
            field_name="footer_text",
            old_value="Copyright 2023 Acme Corp. All rights reserved.",
            new_value="Copyright 2024 Acme Corp. All rights reserved.",
            entity_id=self.comp.id
        )
        self.assertEqual(chg_class, ChangeClass.NOISE.value)
        self.assertEqual(level, SignificanceLevel.INFO.value)
        self.assertLessEqual(score, 10.0)

    def test_change_significance_classification_and_scoring(self):
        """Verify high-impact changes (leadership, tech, intent) receive appropriate classifications and scores."""
        engine = ChangeSignificanceEngine(self.db)

        # 1. Leadership change
        chg_class, score, level = engine.classify_change(
            field_name="ceo_name",
            old_value="John Smith",
            new_value="Sarah Connor",
            entity_id=self.comp.id
        )
        self.assertEqual(chg_class, ChangeClass.LEADERSHIP_CHANGE.value)
        self.assertIn(level, [SignificanceLevel.HIGH.value, SignificanceLevel.CRITICAL.value])
        self.assertGreater(score, 80.0)

        # 2. Technology change
        chg_class, score, level = engine.classify_change(
            field_name="technologies",
            old_value="Legacy ERP",
            new_value="Odoo Enterprise 17",
            entity_id=self.comp.id
        )
        self.assertEqual(chg_class, ChangeClass.TECHNOLOGY_CHANGE.value)
        self.assertGreaterEqual(score, 70.0)

        # 3. Contact change
        chg_class, score, level = engine.classify_change(
            field_name="decision_maker_email",
            old_value="old.contact@apexdynamics.com.au",
            new_value="new.cto@apexdynamics.com.au",
            entity_id=self.comp.id
        )
        self.assertEqual(chg_class, ChangeClass.CONTACT_CHANGE.value)
        self.assertGreaterEqual(score, 65.0)

    def test_record_change_event(self):
        """Verify recording of change events with full provenance and evidence citations."""
        engine = ChangeSignificanceEngine(self.db)
        event = engine.record_change_event(
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp.id,
            field_name="erp_system",
            old_value="SAP R/3",
            new_value="Odoo ERP",
            source_name="Company Careers Page",
            source_url="https://apexdynamics.com.au/careers/odoo-specialist",
            evidence_snippet="We are migrating our core operations to Odoo 17 ERP."
        )
        self.assertIsNotNone(event.id)
        self.assertEqual(event.change_class, ChangeClass.TECHNOLOGY_CHANGE.value)
        self.assertGreater(event.significance_score, 70.0)
        self.assertEqual(event.evidence_snippet, "We are migrating our core operations to Odoo 17 ERP.")

    def test_alert_engine_fingerprint_deduplication(self):
        """Verify day-bucketed fingerprinting collapses duplicate collector alerts into one with multi-source evidence."""
        alert_engine = AlertEngine(self.db)

        # First alert from Website collector
        alert_1, is_new_1 = alert_engine.create_or_corroborate_alert(
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp.id,
            field_name="erp_migration",
            change_class=ChangeClass.TECHNOLOGY_CHANGE.value,
            title="Odoo Migration Detected",
            message="Company is migrating from SAP to Odoo.",
            evidence="Careers page mentions Odoo Lead Architect role.",
            severity=SignificanceLevel.HIGH.value
        )
        self.assertTrue(is_new_1)
        self.assertEqual(alert_1.status, AlertStatus.OPEN.value)

        # Second alert from GitHub collector on same day
        alert_2, is_new_2 = alert_engine.create_or_corroborate_alert(
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp.id,
            field_name="erp_migration",
            change_class=ChangeClass.TECHNOLOGY_CHANGE.value,
            title="Odoo Migration Detected",
            message="Company is migrating from SAP to Odoo.",
            evidence="GitHub repo apex-odoo-connect commit detected.",
            severity=SignificanceLevel.HIGH.value
        )
        self.assertFalse(is_new_2)
        self.assertEqual(alert_1.id, alert_2.id)  # Same deduplicated alert

        # Verify occurrence count incremented in fingerprint record
        fp = self.db.query(AlertFingerprint).filter(AlertFingerprint.alert_id == alert_1.id).first()
        self.assertGreaterEqual(fp.occurrence_count, 2)
        self.assertIn("GitHub repo apex-odoo-connect", alert_2.evidence_summary)

    def test_alert_lifecycle(self):
        """Verify acknowledge, snooze, resolve, dismiss, and feedback operations."""
        alert_engine = AlertEngine(self.db)
        alert, _ = alert_engine.create_or_corroborate_alert(
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp.id,
            field_name="funding_round",
            change_class=ChangeClass.BUSINESS_CHANGE.value,
            title="Series B Funding Announced",
            message="Company raised $25M Series B.",
            evidence="Australian Financial Review article",
            severity=SignificanceLevel.HIGH.value
        )

        # 1. Acknowledge
        ack_alert = alert_engine.acknowledge_alert(self.ws_id, alert.id, self.user_id)
        self.assertEqual(ack_alert.status, AlertStatus.ACKNOWLEDGED.value)
        self.assertIsNotNone(ack_alert.acknowledged_at)

        # 2. Snooze
        snoozed_alert = alert_engine.snooze_alert(self.ws_id, alert.id, duration_hours=48)
        self.assertEqual(snoozed_alert.status, AlertStatus.SNOOZED.value)
        self.assertIsNotNone(snoozed_alert.snoozed_until)

        # 3. Resolve
        res_alert = alert_engine.resolve_alert(self.ws_id, alert.id)
        self.assertEqual(res_alert.status, AlertStatus.RESOLVED.value)
        self.assertIsNotNone(res_alert.resolved_at)

        # 4. Feedback
        fb = alert_engine.record_feedback(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            alert_id=alert.id,
            feedback_type="USEFUL",
            notes="Crucial intent timing for outreach planning"
        )
        self.assertEqual(fb.feedback_type, "USEFUL")

    def test_watchlist_management_and_items(self):
        """Verify watchlist creation, item association, and priority tracking."""
        wl_service = WatchlistService(self.db)

        # Create Watchlist
        wl = wl_service.create_watchlist(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            name="Tier 1 High-Priority Australian Mining Leads",
            watchlist_type=WatchlistType.ENTITY_WATCHLIST.value
        )
        self.assertIsNotNone(wl.id)

        # Add item
        item = wl_service.add_item_to_watchlist(
            workspace_id=self.ws_id,
            watchlist_id=wl.id,
            entity_id=self.comp.id,
            priority="HIGH",
            notes="Active ERP RFP underway"
        )
        self.assertEqual(item.priority, "HIGH")

        # List items
        items = wl_service.list_watchlist_items(self.ws_id, wl.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].entity_id, self.comp.id)

        # Entity watch summary
        summary = wl_service.get_entity_watch_summary(self.ws_id, self.comp.id)
        self.assertTrue(summary["is_watched"])
        self.assertGreaterEqual(summary["watchlist_count"], 1)

        # Remove item
        removed = wl_service.remove_item_from_watchlist(self.ws_id, wl.id, self.comp.id)
        self.assertTrue(removed)

    def test_saved_search_watchlist_evaluation(self):
        """Verify periodic evaluation of saved searches matching new companies into watchlists."""
        wl_service = WatchlistService(self.db)

        # Create SavedSearch matching our seeded company
        saved_search = SavedSearch(
            id=str(uuid.uuid4()),
            workspace_id=self.ws_id,
            user_id=self.user_id,
            name="Mining Australia Search",
            query="Mining",
            filters={"industry": "Mining", "country": "Australia"}
        )
        self.db.add(saved_search)
        self.db.commit()

        # Create a search watchlist
        wl = wl_service.create_watchlist(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            name="Continuous Mining Match Watchlist",
            watchlist_type=WatchlistType.SEARCH_WATCHLIST.value
        )

        # Evaluate
        eval_res = wl_service.evaluate_saved_search_watchlist(
            workspace_id=self.ws_id,
            saved_search_id=saved_search.id,
            watchlist_id=wl.id
        )
        self.assertGreaterEqual(eval_res["new_matches_count"], 1)
        self.assertIn(self.comp.id, eval_res["new_match_ids"])

        # Check that the item is now present in the watchlist
        items = wl_service.list_watchlist_items(self.ws_id, wl.id)
        self.assertEqual(len(items), 1)

    def test_notification_preferences_and_quiet_hours(self):
        """Verify quiet hours and severity thresholds filter dispatched notifications."""
        notif_service = NotificationService(self.db)

        # Set preference with HIGH minimum severity and quiet hours
        pref = notif_service.update_preference(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            category="LEAD",
            min_severity="HIGH",
            channel="IN_APP",
            quiet_hours_start="22:00",
            quiet_hours_end="07:00"
        )
        self.assertEqual(pref.min_severity, "HIGH")

        # Low-severity notification should be suppressed
        n_low = notif_service.dispatch_notification(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            title="Minor text change",
            message="Website copyright year updated",
            severity="LOW",
            category="LEAD"
        )
        self.assertIsNone(n_low)

        # High-severity force-dispatch should succeed
        n_high = notif_service.dispatch_notification(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            title="CEO Resignation",
            message="CEO has announced resignation effective immediately.",
            severity="HIGH",
            category="LEAD",
            force_dispatch=True
        )
        self.assertIsNotNone(n_high)
        self.assertEqual(n_high.title, "CEO Resignation")

    def test_notification_dispatch_and_digest(self):
        """Verify notification read tracking and daily digest generation."""
        notif_service = NotificationService(self.db)

        # Dispatch 2 notifications
        n1 = notif_service.dispatch_notification(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            title="High Intent Detected",
            message="Apex Dynamics viewed pricing 4 times",
            severity="HIGH",
            force_dispatch=True
        )
        n2 = notif_service.dispatch_notification(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            title="New Tech Footprint",
            message="Odoo CRM detected",
            severity="HIGH",
            force_dispatch=True
        )

        # Digest should group pending notifications
        digest = notif_service.generate_digest(self.ws_id, self.user_id, frequency="DAILY")
        self.assertGreaterEqual(digest["total_pending_count"], 2)
        self.assertIn("LEAD", digest["category_groups"])

        # Mark one read
        read_success = notif_service.mark_as_read(self.ws_id, self.user_id, n1.id)
        self.assertTrue(read_success)

        # Mark all read
        cleared_count = notif_service.mark_all_as_read(self.ws_id, self.user_id)
        self.assertGreaterEqual(cleared_count, 1)

    def test_collaboration_notes_comments_mentions_tags_bookmarks(self):
        """Verify notes, comments with @mentions triggering notifications, tags, and bookmarks."""
        collab_service = CollaborationService(self.db)

        # 1. Notes
        note = collab_service.create_note(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            entity_type="COMPANY",
            entity_id=self.comp.id,
            note_text="Confirmed via LinkedIn that Odoo migration begins in Q1.",
            tags=["erp", "odoo", "q1-target"]
        )
        self.assertIsNotNone(note.id)
        notes = collab_service.list_notes(self.ws_id, "COMPANY", self.comp.id)
        self.assertGreaterEqual(len(notes), 1)

        # 2. Comments with @mentions
        comment = collab_service.create_comment(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            entity_type="COMPANY",
            entity_id=self.comp.id,
            comment_text=f"Please review @{self.user_2_id} before the executive briefing."
        )
        self.assertIn(self.user_2_id, comment.mentions)

        # Check that mentioned user received an in-app notification
        user2_notifs = NotificationService(self.db).list_notifications(self.ws_id, self.user_2_id)
        self.assertGreaterEqual(len(user2_notifs), 1)
        self.assertIn("Mentioned in COMPANY discussion", user2_notifs[0].title)

        # 3. Tags
        tag = collab_service.add_tag(self.ws_id, "COMPANY", self.comp.id, "High-Value-Target")
        self.assertEqual(tag.tag_name, "high-value-target")
        tags = collab_service.list_tags(self.ws_id, "COMPANY", self.comp.id)
        self.assertIn("high-value-target", tags)

        collab_service.remove_tag(self.ws_id, "COMPANY", self.comp.id, "High-Value-Target")
        tags_after = collab_service.list_tags(self.ws_id, "COMPANY", self.comp.id)
        self.assertNotIn("high-value-target", tags_after)

        # 4. Bookmarks
        bm_res = collab_service.toggle_bookmark(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            entity_type="COMPANY",
            entity_id=self.comp.id,
            notes="Key target for Odoo modernization"
        )
        self.assertTrue(bm_res["bookmarked"])

        bms = collab_service.list_bookmarks(self.ws_id, self.user_id)
        self.assertEqual(len(bms), 1)

    def test_unified_activity_timeline_and_intelligence_brief(self):
        """Verify unified chronological intelligence timeline and intelligence brief generation."""
        collab_service = CollaborationService(self.db)

        # Unified Timeline
        timeline = collab_service.get_unified_timeline(
            workspace_id=self.ws_id,
            entity_type="COMPANY",
            entity_id=self.comp.id
        )
        self.assertIsInstance(timeline, list)
        self.assertGreater(len(timeline), 0)
        types_in_timeline = {t["type"] for t in timeline}
        self.assertTrue(types_in_timeline.intersection({"CHANGE_EVENT", "ALERT", "NOTE", "COMMENT"}))

        # Generate Intelligence Brief
        brief = collab_service.generate_intelligence_brief(
            workspace_id=self.ws_id,
            days=7,
            title="Weekly Strategic Brief - Mining & Resources"
        )
        self.assertIsNotNone(brief.id)
        self.assertIn("Weekly Strategic Brief", brief.title)
        self.assertIsInstance(brief.top_changes, list)
        self.assertIsInstance(brief.affected_leads, list)

    def test_fastapi_monitoring_and_collaboration_routes(self):
        """Verify REST API endpoints for monitoring, alerts, watchlists, notifications, and collaboration."""
        # 1. Monitoring health
        resp = self.client.get("/api/v1/monitoring/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("health_status", data)
        self.assertIn("health_score", data)

        # 2. Create and list monitor rules
        resp = self.client.post("/api/v1/monitoring/rules", json={
            "name": "Odoo Careers Monitor Rule",
            "target_type": "COMPANY",
            "target_id": self.comp.id,
            "frequency": "DAILY",
            "conditions": {"field": "careers", "contains": "odoo"}
        })
        self.assertEqual(resp.status_code, 201)
        rule_id = resp.json()["id"]

        resp = self.client.get("/api/v1/monitoring/rules")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()), 1)

        # 3. List change events
        resp = self.client.get("/api/v1/monitoring/changes")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

        # 4. List alerts
        resp = self.client.get("/api/v1/alerts")
        self.assertEqual(resp.status_code, 200)
        alerts = resp.json()
        self.assertIsInstance(alerts, list)
        if len(alerts) > 0:
            first_alert_id = alerts[0]["id"]
            # Acknowledge
            ack_resp = self.client.post(f"/api/v1/alerts/{first_alert_id}/acknowledge")
            self.assertEqual(ack_resp.status_code, 200)
            # Feedback
            fb_resp = self.client.post(f"/api/v1/alerts/{first_alert_id}/feedback", json={
                "feedback_type": "USEFUL",
                "notes": "Verified via careers portal"
            })
            self.assertEqual(fb_resp.status_code, 200)

        # 5. Create and list watchlists
        wl_resp = self.client.post("/api/v1/watchlists", json={
            "name": "Australian Tech Stack Watchlist",
            "watchlist_type": "TECHNOLOGY_WATCHLIST"
        })
        self.assertEqual(wl_resp.status_code, 201)
        wl_id = wl_resp.json()["id"]

        item_resp = self.client.post(f"/api/v1/watchlists/{wl_id}/items", json={
            "entity_id": self.comp.id,
            "priority": "HIGH",
            "notes": "Watching for ERP rollout announcements"
        })
        self.assertEqual(item_resp.status_code, 201)

        # 6. Notifications preferences & list
        pref_resp = self.client.get("/api/v1/notifications/preferences")
        self.assertEqual(pref_resp.status_code, 200)

        notif_list_resp = self.client.get("/api/v1/notifications")
        self.assertEqual(notif_list_resp.status_code, 200)

        digest_resp = self.client.get("/api/v1/notifications/digest")
        self.assertEqual(digest_resp.status_code, 200)
        self.assertIn("category_groups", digest_resp.json())

        # 7. Collaboration timeline & briefs
        timeline_resp = self.client.get(f"/api/v1/collaboration/timeline?entity_id={self.comp.id}&entity_type=COMPANY")
        self.assertEqual(timeline_resp.status_code, 200)
        self.assertIsInstance(timeline_resp.json(), list)

        brief_resp = self.client.post("/api/v1/briefs/generate", json={
            "days": 1,
            "title": "Daily Executive Lead Intelligence Brief"
        })
        self.assertEqual(brief_resp.status_code, 201)
        self.assertIn("executive_summary", brief_resp.json())


if __name__ == "__main__":
    unittest.main()
