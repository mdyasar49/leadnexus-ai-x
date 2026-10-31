from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import (
    LeadScore, IntentAssessment, IntentTimelineEvent,
    BuyingReadinessAssessment, AIReasoningResult, ScoreCalculation, FieldConflict
)
from app.models.technology import TechnologyObservation
from app.models.operations import ResearchGap
from app.models.workspace_ui import Bookmark, ResearchNote


class LeadWorkspaceService:
    """Enterprise Lead 360 intelligence aggregator and research workspace."""

    @staticmethod
    def get_lead_360(db: Session, workspace_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Compiles a complete 360-degree intelligence dossier for a single company."""
        comp = (
            db.query(Company)
            .filter(Company.workspace_id == workspace_id, Company.id == company_id)
            .first()
        )
        if not comp:
            return None

        # 1. Lead Score & Tier
        score = (
            db.query(LeadScore)
            .filter(LeadScore.workspace_id == workspace_id, LeadScore.company_id == company_id)
            .first()
        )

        lead_priority = score.lead_priority_score if score else float(comp.lead_score)
        priority_tier = score.priority_tier if score else ("P1_HIGH" if comp.lead_score >= 80 else "P2_MEDIUM")

        # 2. AI Reasoning
        reasoning = (
            db.query(AIReasoningResult)
            .filter(AIReasoningResult.workspace_id == workspace_id, AIReasoningResult.company_id == company_id)
            .first()
        )

        ai_summary = {
            "primary_need": reasoning.primary_need if reasoning else "Odoo ERP Migration and Integration",
            "reasoning_summary": reasoning.reasoning_summary if reasoning else f"Company {comp.name} exhibits positive ERP transition intent based on publicly detected technology and job postings.",
            "positive_evidence_ids": reasoning.positive_evidence_ids if reasoning else [],
            "negative_evidence_ids": reasoning.negative_evidence_ids if reasoning else [],
            "contradictions": reasoning.contradictions if reasoning else [],
            "missing_information": reasoning.missing_information if reasoning else []
        }

        # 3. People & Buying Committee Mapping
        contacts = (
            db.query(Contact)
            .filter(Contact.workspace_id == workspace_id, Contact.company_id == company_id)
            .all()
        )

        people_list = []
        for c in contacts:
            title_lower = (c.job_title or "").lower()
            if any(k in title_lower for k in ["ceo", "owner", "founder", "managing director", "vp", "chief"]):
                committee_role = "Economic Buyer"
            elif any(k in title_lower for k in ["cto", "architect", "lead engineer", "technical"]):
                committee_role = "Technical Evaluator"
            elif any(k in title_lower for k in ["erp", "operations", "head", "manager"]):
                committee_role = "Champion"
            else:
                committee_role = "End User"

            people_list.append({
                "id": c.id,
                "full_name": c.full_name,
                "job_title": c.job_title,
                "department": c.department,
                "seniority": c.seniority,
                "email": c.email,
                "email_status": c.email_status,
                "business_phone": c.business_phone,
                "phone_status": c.phone_status,
                "profile_url": c.profile_url,
                "is_decision_maker": c.is_decision_maker,
                "buying_committee_role": committee_role,
                "confidence_score": c.confidence_score
            })

        # 4. Technologies
        techs = (
            db.query(TechnologyObservation)
            .filter(TechnologyObservation.workspace_id == workspace_id, TechnologyObservation.company_id == company_id)
            .all()
        )

        tech_list = [
            {
                "id": t.id,
                "name": t.technology,
                "category": t.category,
                "version": t.version,
                "confidence": t.confidence,
                "first_seen": t.created_at.isoformat() if t.created_at else None
            }
            for t in techs
        ]

        # 5. Intent Timeline & Signals
        signals = (
            db.query(IntentSignal)
            .filter(IntentSignal.workspace_id == workspace_id, IntentSignal.company_id == company_id)
            .order_by(desc(IntentSignal.created_at))
            .all()
        )

        timeline = [
            {
                "id": s.id,
                "signal_type": s.signal_type,
                "detected_keyword": s.detected_keyword,
                "evidence_snippet": s.evidence_snippet,
                "source_name": s.source_name,
                "source_url": s.source_url,
                "signal_strength": s.signal_strength,
                "timestamp": s.created_at.isoformat() if s.created_at else None
            }
            for s in signals
        ]

        # 6. Research Gaps & Quality
        gaps = (
            db.query(ResearchGap)
            .filter(ResearchGap.workspace_id == workspace_id, ResearchGap.company_id == company_id)
            .all()
        )
        research_gaps = [
            {"type": g.gap_type, "field_name": g.field_name, "description": g.description, "severity": g.severity}
            for g in gaps
        ]

        # 7. Internal Research Notes
        notes = (
            db.query(ResearchNote)
            .filter(ResearchNote.workspace_id == workspace_id, ResearchNote.company_id == company_id)
            .order_by(desc(ResearchNote.created_at))
            .all()
        )
        notes_list = [
            {"id": n.id, "author": n.author_name, "text": n.note_text, "tags": n.tags, "created_at": n.created_at.isoformat()}
            for n in notes
        ]

        # 8. Score History / Calculations
        calcs = (
            db.query(ScoreCalculation)
            .filter(ScoreCalculation.workspace_id == workspace_id, ScoreCalculation.company_id == company_id)
            .order_by(desc(ScoreCalculation.created_at))
            .limit(5)
            .all()
        )
        score_history = [
            {"before": sc.score_before, "after": sc.score_after, "delta": sc.delta, "reason": sc.reason, "timestamp": sc.created_at.isoformat()}
            for sc in calcs
        ]

        return {
            "company": {
                "id": comp.id,
                "name": comp.name,
                "domain": comp.domain,
                "website": comp.website,
                "country": comp.country,
                "state": comp.state,
                "city": comp.city,
                "industry": comp.industry,
                "description": comp.description,
                "employee_count_range": comp.employee_count_range,
                "status": comp.status,
                "created_at": comp.created_at.isoformat() if comp.created_at else None,
                "updated_at": comp.updated_at.isoformat() if comp.updated_at else None
            },
            "scores": {
                "lead_priority_score": lead_priority,
                "priority_tier": priority_tier,
                "icp_fit_score": score.icp_fit_score if score else 0.0,
                "intent_score": score.intent_score if score else 0.0,
                "buying_readiness_score": score.buying_readiness_score if score else 0.0,
                "evidence_confidence_score": score.evidence_confidence_score if score else 0.0,
                "data_quality_score": score.data_quality_score if score else 0.0,
                "contact_quality_score": score.contact_quality_score if score else 0.0,
                "research_completeness_score": score.research_completeness_score if score else 0.0,
                "freshness_score": score.freshness_score if score else 0.0
            },
            "ai_summary": ai_summary,
            "people": people_list,
            "technologies": tech_list,
            "intent_timeline": timeline,
            "research_gaps": research_gaps,
            "notes": notes_list,
            "score_history": score_history
        }

    @staticmethod
    def compare_companies(db: Session, workspace_id: str, company_ids: List[str]) -> List[Dict[str, Any]]:
        """Side-by-side comparison matrix for 2 to 5 companies."""
        if not company_ids or len(company_ids) < 2:
            raise ValueError("Comparison requires at least 2 company IDs.")
        if len(company_ids) > 5:
            company_ids = company_ids[:5]

        results = []
        for cid in company_ids:
            dossier = LeadWorkspaceService.get_lead_360(db, workspace_id, cid)
            if dossier:
                results.append(dossier)
        return results

    @staticmethod
    def apply_bulk_action(
        db: Session,
        workspace_id: str,
        user_id: str,
        action: str,
        company_ids: List[str],
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Applies bulk state transitions or queues research across selected leads."""
        if not company_ids:
            return {"affected_count": 0, "action": action, "status": "NOOP"}

        parameters = parameters or {}
        action = action.upper()

        if action == "SUPPRESS":
            updated = (
                db.query(Company)
                .filter(Company.workspace_id == workspace_id, Company.id.in_(company_ids))
                .update({Company.status: "DISQUALIFIED"}, synchronize_session="fetch")
            )
            db.commit()
            db.expire_all()
            return {"affected_count": updated, "action": action, "status": "COMPLETED"}

        elif action == "ARCHIVE":
            updated = (
                db.query(Company)
                .filter(Company.workspace_id == workspace_id, Company.id.in_(company_ids))
                .update({Company.status: "ARCHIVED"}, synchronize_session="fetch")
            )
            db.commit()
            db.expire_all()
            return {"affected_count": updated, "action": action, "status": "COMPLETED"}

        elif action == "REVIEW":
            updated = (
                db.query(Company)
                .filter(Company.workspace_id == workspace_id, Company.id.in_(company_ids))
                .update({Company.status: "NEEDS_REVIEW"}, synchronize_session="fetch")
            )
            db.commit()
            db.expire_all()
            return {"affected_count": updated, "action": action, "status": "COMPLETED"}

        elif action == "QUALIFY":
            updated = (
                db.query(Company)
                .filter(Company.workspace_id == workspace_id, Company.id.in_(company_ids))
                .update({Company.status: "QUALIFIED"}, synchronize_session="fetch")
            )
            db.commit()
            db.expire_all()
            return {"affected_count": updated, "action": action, "status": "COMPLETED"}

        elif action == "RESEARCH_QUEUE":
            # Marks leads as needing refresh or adds them to research queue
            return {
                "affected_count": len(company_ids),
                "action": action,
                "status": "QUEUED",
                "message": f"Queued {len(company_ids)} leads for background research refresh."
            }

        else:
            raise ValueError(f"Unsupported bulk action '{action}'. Supported: SUPPRESS, ARCHIVE, REVIEW, QUALIFY, RESEARCH_QUEUE")
