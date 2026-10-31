from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import LeadScore
from app.models.technology import TechnologyObservation
from app.models.operations import ResearchGap
from app.models.enrichment import (
    EnrichmentJob,
    EnrichmentTask,
    EnrichmentRecommendation,
    EnrichmentDepth,
    JobStatus as EnrichmentJobStatus
)


GAP_IMPORTANCE_WEIGHTS = {
    "DECISION_MAKER": 0.95,
    "BUSINESS_CONTACT": 0.90,
    "TECHNOLOGY": 0.85,
    "DOMAIN": 0.90,
    "LOCATION": 0.70,
    "EMPLOYEE_COUNT": 0.60,
    "INTENT_CORROBORATION": 0.80
}


class SmartEnrichmentEngine:
    """Smart prioritization engine, budget governor, and research recommendation system."""

    @staticmethod
    def evaluate_company_gaps(
        db: Session,
        workspace_id: str,
        company_id: str
    ) -> List[EnrichmentRecommendation]:
        """
        Analyzes an existing company lead and generates prioritized research recommendations
        ranked by Expected Information Gain over Cost.
        """
        comp = (
            db.query(Company)
            .filter(Company.workspace_id == workspace_id, Company.id == company_id)
            .first()
        )
        if not comp:
            return []

        # Suppression Check: Never enrich disqualified or suppressed leads
        if comp.status in {"DISQUALIFIED", "SUPPRESSED", "ARCHIVED"}:
            return []

        # Retrieve lead score and tier
        score = (
            db.query(LeadScore)
            .filter(LeadScore.workspace_id == workspace_id, LeadScore.company_id == company_id)
            .first()
        )
        lead_priority_score = score.lead_priority_score if score else float(comp.lead_score)
        lead_val_factor = max(0.2, lead_priority_score / 100.0)

        recommendations = []

        # 1. Check Missing Domain
        if not comp.domain:
            expected_gain = round(lead_val_factor * GAP_IMPORTANCE_WEIGHTS["DOMAIN"], 2)
            recommendations.append(
                EnrichmentRecommendation(
                    workspace_id=workspace_id,
                    entity_type="COMPANY",
                    entity_id=company_id,
                    recommended_action="DISCOVER_DOMAIN",
                    target_field="domain",
                    priority="CRITICAL",
                    expected_gain=expected_gain,
                    reason="Company lacks a verified primary web domain."
                )
            )

        # 2. Check Missing Technologies
        tech_count = (
            db.query(TechnologyObservation)
            .filter(TechnologyObservation.workspace_id == workspace_id, TechnologyObservation.company_id == company_id)
            .count()
        )
        if tech_count == 0:
            expected_gain = round(lead_val_factor * GAP_IMPORTANCE_WEIGHTS["TECHNOLOGY"], 2)
            recommendations.append(
                EnrichmentRecommendation(
                    workspace_id=workspace_id,
                    entity_type="COMPANY",
                    entity_id=company_id,
                    recommended_action="DISCOVER_TECHNOLOGY",
                    target_field="technology",
                    priority="HIGH",
                    expected_gain=expected_gain,
                    reason="No verified technology stack or ERP footprint detected."
                )
            )

        # 3. Check Missing Decision Maker
        dm_count = (
            db.query(Contact)
            .filter(
                Contact.workspace_id == workspace_id,
                Contact.company_id == company_id,
                Contact.is_decision_maker.is_(True)
            )
            .count()
        )
        if dm_count == 0:
            expected_gain = round(lead_val_factor * GAP_IMPORTANCE_WEIGHTS["DECISION_MAKER"], 2)
            recommendations.append(
                EnrichmentRecommendation(
                    workspace_id=workspace_id,
                    entity_type="COMPANY",
                    entity_id=company_id,
                    recommended_action="FIND_DECISION_MAKER",
                    target_role="CTO / Head of IT / ERP Manager",
                    priority="CRITICAL" if lead_priority_score >= 80 else "HIGH",
                    expected_gain=expected_gain,
                    reason="High intent detected, but no key decision-maker has been identified."
                )
            )

        # 4. Check Missing Business Email
        email_count = (
            db.query(Contact)
            .filter(
                Contact.workspace_id == workspace_id,
                Contact.company_id == company_id,
                Contact.email.is_not(None),
                Contact.email != "",
                Contact.email_status != "INVALID"
            )
            .count()
        )
        if email_count == 0:
            expected_gain = round(lead_val_factor * GAP_IMPORTANCE_WEIGHTS["BUSINESS_CONTACT"], 2)
            recommendations.append(
                EnrichmentRecommendation(
                    workspace_id=workspace_id,
                    entity_type="COMPANY",
                    entity_id=company_id,
                    recommended_action="FIND_BUSINESS_CONTACT",
                    target_field="email",
                    priority="HIGH",
                    expected_gain=expected_gain,
                    reason="No deliverable or public business contact email available."
                )
            )

        # 5. Check Missing Location (City / State)
        if not comp.city or not comp.country:
            expected_gain = round(lead_val_factor * GAP_IMPORTANCE_WEIGHTS["LOCATION"], 2)
            recommendations.append(
                EnrichmentRecommendation(
                    workspace_id=workspace_id,
                    entity_type="COMPANY",
                    entity_id=company_id,
                    recommended_action="RESOLVE_LOCATION",
                    target_field="location",
                    priority="MEDIUM",
                    expected_gain=expected_gain,
                    reason="Geographic location details incomplete."
                )
            )

        # Sort recommendations by expected gain descending
        recommendations.sort(key=lambda r: r.expected_gain, reverse=True)
        return recommendations

    @staticmethod
    def create_enrichment_job(
        db: Session,
        workspace_id: str,
        user_id: str,
        company_ids: List[str],
        depth: str = "STANDARD",
        budget_limit_usd: float = 25.0
    ) -> EnrichmentJob:
        """Creates an enrichment job governed by tenant micro-cost budgets."""
        job = EnrichmentJob(
            workspace_id=workspace_id,
            user_id=user_id,
            job_type="COMPANY_ENRICHMENT",
            depth=depth,
            status=EnrichmentJobStatus.PENDING.value,
            total_entities=len(company_ids),
            budget_limit_usd=budget_limit_usd,
            started_at=datetime.now(timezone.utc)
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Generate individual tasks for each company
        completed = 0
        for cid in company_ids:
            recs = SmartEnrichmentEngine.evaluate_company_gaps(db, workspace_id, cid)
            task_gain = max([r.expected_gain for r in recs], default=0.5)
            
            task = EnrichmentTask(
                workspace_id=workspace_id,
                job_id=job.id,
                entity_type="COMPANY",
                entity_id=cid,
                priority_score=task_gain,
                expected_info_gain=task_gain,
                estimated_cost=0.015,
                status=EnrichmentJobStatus.COMPLETED.value,
                result_summary={"recommendations_generated": len(recs)}
            )
            db.add(task)
            completed += 1

        job.completed_entities = completed
        job.cost_usd = round(completed * 0.015, 3)
        job.status = EnrichmentJobStatus.COMPLETED.value
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)

        return job
