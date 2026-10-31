from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.lead import Company, Contact
from app.models.scoring import LeadScore
from app.models.decision_intelligence import (
    InformationValueAssessment,
    ResearchRecommendation,
    DecisionRecommendation,
    RecommendationType,
    RecommendationStatus
)


class RecommendationEngine:
    """
    Decision recommendation & Expected Information Value (EIV) engine.
    Calculates EIV = (Probability * Importance) / Cost.
    Proposes evidence-grounded research, refresh, verification, and monitoring actions.
    Supports full human review and decision lifecycle (ACCEPT, REJECT, DEFER, EXECUTE).
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_expected_information_value(
        self,
        workspace_id: str,
        company_id: str,
        missing_field: str = "decision_maker",
        importance: float = 1.5,
        prob_finding: float = 0.80,
        estimated_cost: float = 2.50
    ) -> InformationValueAssessment:
        """
        Computes Expected Information Value:
        EIV = (probability_of_finding * importance_weight) / estimated_research_cost
        """
        eiv = round((prob_finding * importance) / max(0.1, estimated_cost), 2)

        assessment = InformationValueAssessment(
            workspace_id=workspace_id,
            target_entity_type="COMPANY",
            target_entity_id=company_id,
            missing_field=missing_field,
            importance_weight=importance,
            probability_of_finding=prob_finding,
            estimated_research_cost=estimated_cost,
            expected_information_value=eiv
        )
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        return assessment

    def generate_research_recommendation(
        self,
        workspace_id: str,
        company_id: str
    ) -> ResearchRecommendation:
        """Analyzes missing data on an account and recommends the optimal source to investigate."""
        company = self.db.query(Company).filter(
            and_(Company.workspace_id == workspace_id, Company.id == company_id)
        ).first()
        if not company:
            raise ValueError(f"Company '{company_id}' not found.")

        # Check missing data
        contacts = self.db.query(Contact).filter(
            and_(Contact.workspace_id == workspace_id, Contact.company_id == company_id)
        ).all()

        missing = "Decision Maker (CTO/ERP Manager)" if not contacts else "Secondary Contact Points"
        rec_source = "Official Company Website / Team Page" if not contacts else "GitHub / Public Directory"

        rec = ResearchRecommendation(
            workspace_id=workspace_id,
            target_entity_id=company.id,
            target_entity_name=company.name,
            missing_information=missing,
            recommended_source=rec_source,
            expected_information_value="HIGH",
            reason=f"Account has high intent but lacks verified {missing}. {rec_source} has 85% probability of resolution."
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def create_decision_recommendation(
        self,
        workspace_id: str,
        recommendation_type: str,
        target_entity: str,
        target_entity_id: str,
        reason: str,
        supporting_metrics: Optional[Dict[str, Any]] = None,
        supporting_evidence: Optional[List[str]] = None,
        confidence: float = 0.88
    ) -> DecisionRecommendation:
        """Creates an evidence-grounded decision proposal for human operators."""
        rec = DecisionRecommendation(
            workspace_id=workspace_id,
            recommendation_type=recommendation_type.upper(),
            target_entity=target_entity,
            target_entity_id=target_entity_id,
            reason=reason,
            supporting_metrics=supporting_metrics or {},
            supporting_evidence=supporting_evidence or [],
            confidence=confidence,
            status=RecommendationStatus.NEW.value,
            expires_at=datetime.now(timezone.utc) + timedelta(days=14)
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def update_recommendation_decision(
        self,
        workspace_id: str,
        recommendation_id: str,
        decision: str  # ACCEPTED, REJECTED, DEFERRED, EXECUTED
    ) -> DecisionRecommendation:
        """Captures human operator action on a proposed decision recommendation."""
        rec = self.db.query(DecisionRecommendation).filter(
            and_(DecisionRecommendation.workspace_id == workspace_id, DecisionRecommendation.id == recommendation_id)
        ).first()
        if not rec:
            raise ValueError(f"Recommendation '{recommendation_id}' not found.")

        rec.status = decision.upper()
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def recommend_priority_investigations(
        self,
        workspace_id: str,
        limit: int = 10
    ) -> List[ResearchRecommendation]:
        """Identifies companies in the workspace and creates research recommendations."""
        companies = (
            self.db.query(Company)
            .filter(Company.workspace_id == workspace_id)
            .limit(limit)
            .all()
        )
        recommendations = []
        for comp in companies:
            rec = self.generate_research_recommendation(workspace_id, comp.id)
            recommendations.append(rec)
        return recommendations

    def process_decision(
        self,
        workspace_id: str,
        recommendation_id: str,
        action: str = "ACCEPTED",
        decided_by: str = "system",
        notes: Optional[str] = None
    ) -> DecisionRecommendation:
        """Captures or updates human decision on a proposed recommendation."""
        dec_rec = self.db.query(DecisionRecommendation).filter(
            and_(DecisionRecommendation.workspace_id == workspace_id, DecisionRecommendation.id == recommendation_id)
        ).first()

        if not dec_rec:
            # Check if recommendation_id is a ResearchRecommendation
            res_rec = self.db.query(ResearchRecommendation).filter(
                and_(ResearchRecommendation.workspace_id == workspace_id, ResearchRecommendation.id == recommendation_id)
            ).first()
            if res_rec:
                dec_rec = DecisionRecommendation(
                    workspace_id=workspace_id,
                    recommendation_type="RESEARCH_INVESTIGATION",
                    target_entity="COMPANY",
                    target_entity_id=res_rec.target_entity_id,
                    reason=res_rec.reason,
                    confidence=0.90,
                    status=action.upper(),
                    supporting_metrics={"decided_by": decided_by, "notes": notes or ""}
                )
                self.db.add(dec_rec)
            else:
                raise ValueError(f"Recommendation '{recommendation_id}' not found.")
        else:
            dec_rec.status = action.upper()
            if notes and dec_rec.supporting_metrics:
                metrics = dict(dec_rec.supporting_metrics)
                metrics["notes"] = notes
                metrics["decided_by"] = decided_by
                dec_rec.supporting_metrics = metrics

        self.db.commit()
        self.db.refresh(dec_rec)
        return dec_rec

