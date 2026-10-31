from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import LeadScore, EvidenceClaim
from app.models.analytics import (
    AnalyticsSnapshot,
    LeadSnapshot,
    CompanySnapshot,
    ContactSnapshot,
    IntentSnapshot,
    QualitySnapshot,
    ScoreSnapshot
)


class SnapshotEngine:
    """
    Manages periodic (daily, weekly, monthly) and event-based analytics snapshots.
    Preserves full historical time-series data without overwriting prior states.
    """

    def __init__(self, db: Session):
        self.db = db

    def capture_lead_snapshot(self, workspace_id: str, campaign_id: Optional[str] = None) -> LeadSnapshot:
        """Captures point-in-time snapshot of the Lead Intelligence Funnel and scores."""
        query = self.db.query(Company).filter(Company.workspace_id == workspace_id)
        if campaign_id:
            query = query.filter(Company.campaign_id == campaign_id)
        
        companies = query.all()
        total_leads = len(companies)

        # Stage distribution in the Lead Intelligence Funnel
        counts = {
            "DISCOVERED": 0,
            "RESEARCHING": 0,
            "ENRICHING": 0,
            "QUALIFYING": 0,
            "REVIEW_REQUIRED": 0,
            "QUALIFIED": 0,
            "HIGH_PRIORITY": 0,
            "READY": 0,
            "STALE": 0,
            "SUPPRESSED": 0
        }

        total_priority = 0.0
        company_ids = [c.id for c in companies]

        for c in companies:
            st = (c.status or "DISCOVERED").upper()
            if st in counts:
                counts[st] += 1
            elif st in ["NEW", "PENDING"]:
                counts["DISCOVERED"] += 1
            elif st in ["RESEARCHED", "ENRICHED"]:
                counts["QUALIFYING"] += 1
            else:
                counts["DISCOVERED"] += 1

        scores = self.db.query(LeadScore).filter(
            and_(LeadScore.workspace_id == workspace_id, LeadScore.company_id.in_(company_ids))
        ).all() if company_ids else []

        avg_priority = 0.0
        avg_icp = 0.0
        if scores:
            avg_priority = round(sum(s.lead_priority_score for s in scores) / len(scores), 2)
            avg_icp = round(sum(s.icp_fit_score for s in scores) / len(scores), 2)
            # Count high priority (tier P1 or score >= 80)
            counts["HIGH_PRIORITY"] = sum(1 for s in scores if s.lead_priority_score >= 80.0)
            counts["QUALIFIED"] = sum(1 for s in scores if s.lead_priority_score >= 60.0)

        snapshot = LeadSnapshot(
            workspace_id=workspace_id,
            campaign_id=campaign_id,
            snapshot_date=datetime.now(timezone.utc),
            total_leads=total_leads,
            discovered_count=counts["DISCOVERED"],
            researching_count=counts["RESEARCHING"],
            enriching_count=counts["ENRICHING"],
            qualifying_count=counts["QUALIFYING"],
            review_required_count=counts["REVIEW_REQUIRED"],
            qualified_count=counts["QUALIFIED"],
            high_priority_count=counts["HIGH_PRIORITY"],
            ready_count=counts["READY"],
            stale_count=counts["STALE"],
            suppressed_count=counts["SUPPRESSED"],
            average_priority_score=avg_priority,
            average_icp_fit=avg_icp
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def capture_company_snapshots(self, workspace_id: str, limit: int = 100) -> List[CompanySnapshot]:
        """Captures individual company snapshots for historical drift and trend analysis."""
        companies = self.db.query(Company).filter(Company.workspace_id == workspace_id).limit(limit).all()
        snapshots = []
        now = datetime.now(timezone.utc)

        for c in companies:
            # Check contact count
            contact_count = self.db.query(Contact).filter(
                and_(Contact.workspace_id == workspace_id, Contact.company_id == c.id)
            ).count()

            snap = CompanySnapshot(
                workspace_id=workspace_id,
                company_id=c.id,
                snapshot_date=now,
                name=c.name,
                domain=c.domain,
                industry=c.industry,
                country=c.country,
                lead_score=float(c.lead_score or 0.0),
                quality_score=float(getattr(c, "data_quality_score", 75.0) or 75.0),
                status=c.status or "DISCOVERED",
                decision_maker_count=contact_count,
                verified_contact_count=contact_count,
                primary_technologies=[]
            )
            self.db.add(snap)
            snapshots.append(snap)

        self.db.commit()
        return snapshots

    def record_score_snapshot(
        self,
        workspace_id: str,
        company_id: str,
        lead_priority_score: float,
        intent_score: float,
        icp_fit_score: float,
        priority_tier: str
    ) -> ScoreSnapshot:
        """Preserves score change event in the historical time series."""
        snap = ScoreSnapshot(
            workspace_id=workspace_id,
            company_id=company_id,
            snapshot_date=datetime.now(timezone.utc),
            lead_priority_score=lead_priority_score,
            intent_score=intent_score,
            icp_fit_score=icp_fit_score,
            priority_tier=priority_tier
        )
        self.db.add(snap)
        self.db.commit()
        self.db.refresh(snap)
        return snap

    def get_score_history(self, workspace_id: str, company_id: str) -> List[Dict[str, Any]]:
        """Retrieves chronological score evolution for an entity."""
        records = self.db.query(ScoreSnapshot).filter(
            and_(ScoreSnapshot.workspace_id == workspace_id, ScoreSnapshot.company_id == company_id)
        ).order_by(ScoreSnapshot.snapshot_date.asc()).all()

        return [
            {
                "snapshot_date": r.snapshot_date.isoformat(),
                "lead_priority_score": r.lead_priority_score,
                "intent_score": r.intent_score,
                "icp_fit_score": r.icp_fit_score,
                "priority_tier": r.priority_tier
            }
            for r in records
        ]

    def capture_intent_snapshot(self, workspace_id: str, campaign_id: Optional[str] = None) -> List[IntentSnapshot]:
        """Captures intent signal distributions across categories."""
        signals = self.db.query(IntentSignal).filter(IntentSignal.workspace_id == workspace_id).all()
        by_type: Dict[str, List[float]] = {}
        for s in signals:
            itype = getattr(s, "signal_type", None) or getattr(s, "intent_type", None) or "BUYING_INTENT"
            strength_val = float(getattr(s, "signal_strength", None) or getattr(s, "strength", 50.0) or 50.0)
            if itype not in by_type:
                by_type[itype] = []
            by_type[itype].append(strength_val)

        now = datetime.now(timezone.utc)
        snapshots = []
        for itype, strengths in by_type.items():
            snap = IntentSnapshot(
                workspace_id=workspace_id,
                campaign_id=campaign_id,
                snapshot_date=now,
                intent_type=itype,
                total_signals=len(strengths),
                average_strength=round(sum(strengths) / len(strengths), 2) if strengths else 0.0,
                active_companies_count=len(strengths)
            )
            self.db.add(snap)
            snapshots.append(snap)

        self.db.commit()
        return snapshots
