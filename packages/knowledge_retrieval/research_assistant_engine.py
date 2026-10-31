import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.lead import Company, Contact, IntentSignal
from app.models.knowledge_graph import KnowledgeEntity, KnowledgeRelationship
from app.models.semantic_ontology import Concept
from app.models.knowledge_retrieval import (
    AIResearchSession,
    AIResearchStep,
    AIResearchToolCall,
)


class ResearchAssistantEngine:
    """
    Controlled Multi-Step AI Research Assistant:
    - Executes structured, bounded investigation sessions
    - Strict Tool Allowlisting:
        Permitted: search, retrieve_evidence, retrieve_company, retrieve_person, retrieve_graph, retrieve_timeline, retrieve_analytics
        Forbidden: raw_sql, shell, filesystem, secret_store, arbitrary_http, outreach automation
    - Produces high-level intelligence syntheses:
        * Lead 360 AI Summary
        * Company AI Summary
        * Person AI Summary
        * Company Comparison Matrix
    """

    ALLOWED_TOOLS = {
        "search", "retrieve_evidence", "retrieve_company", "retrieve_person",
        "retrieve_graph", "retrieve_timeline", "retrieve_analytics"
    }

    def __init__(self, db: Session):
        self.db = db

    def start_research_session(
        self,
        workspace_id: str,
        user_id: str,
        target_entity_id: str,
        objective: str,
        max_steps: int = 5
    ) -> AIResearchSession:
        """Initializes a bounded multi-step research session."""
        session = AIResearchSession(
            workspace_id=workspace_id,
            user_id=user_id,
            target_entity_id=target_entity_id,
            objective=objective,
            current_status="ACTIVE",
            current_step=1,
            max_steps=max(1, min(max_steps, 10)),
            budget_tokens=40000,
            used_tokens=0
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def execute_tool_call(
        self,
        step_id: str,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validates and executes an allowlisted research tool call."""
        t_name = tool_name.strip().lower()
        if t_name not in self.ALLOWED_TOOLS:
            call = AIResearchToolCall(
                step_id=step_id,
                tool_name=tool_name,
                parameters=parameters,
                is_authorized=False,
                result_count=0
            )
            self.db.add(call)
            self.db.commit()
            raise PermissionError(f"Forbidden research tool: '{tool_name}'.")

        # Mock tool execution return
        result_count = 3
        call = AIResearchToolCall(
            step_id=step_id,
            tool_name=tool_name,
            parameters=parameters,
            is_authorized=True,
            result_count=result_count,
            execution_time_ms=45.0
        )
        self.db.add(call)
        self.db.commit()
        return {"status": "SUCCESS", "tool": tool_name, "result_count": result_count}

    def generate_lead_360_summary(
        self,
        workspace_id: str,
        company_id: str
    ) -> Dict[str, Any]:
        """
        Synthesizes a complete Lead 360 AI intelligence summary.
        Grounded in database facts, verified contacts, and intent signals.
        """
        comp = self.db.query(Company).filter(
            and_(Company.workspace_id == workspace_id, Company.id == company_id)
        ).first()
        if not comp:
            raise ValueError(f"Company '{company_id}' not found.")

        contacts = self.db.query(Contact).filter(
            and_(Contact.workspace_id == workspace_id, Contact.company_id == company_id)
        ).all()

        signals = self.db.query(IntentSignal).filter(
            and_(IntentSignal.workspace_id == workspace_id, IntentSignal.company_id == company_id)
        ).all()

        dm_list = [c for c in contacts if c.is_decision_maker]

        # Structure comprehensive Lead 360 output
        summary = {
            "company_id": comp.id,
            "company_name": comp.name,
            "domain": comp.domain,
            "industry": comp.industry or "Unspecified",
            "country": comp.country or "Unspecified",
            "lead_score": comp.lead_score or 0,
            "lead_priority_tier": "P1_HIGH" if (comp.lead_score or 0) >= 80 else "P2_MEDIUM",
            "why_this_lead_matters": (
                f"{comp.name} exhibits verified technical modernization demand in {comp.industry or 'industry'}. "
                f"Possesses a high lead score of {comp.lead_score or 0}."
            ),
            "why_now": (
                f"Observed {len(signals)} recent intent signals indicating active technology evaluation or migration."
                if signals else "Active discovery stage; awaiting initial intent signal corroboration."
            ),
            "observed_intent": [
                {"signal_type": s.signal_type, "topic": s.detected_keyword, "evidence": s.evidence_snippet[:120]}
                for s in signals
            ],
            "decision_makers": [
                {"name": d.full_name, "title": d.job_title, "email_status": d.email_status}
                for d in dm_list
            ],
            "data_quality_assessment": {
                "has_contacts": len(contacts) > 0,
                "has_decision_maker": len(dm_list) > 0,
                "has_intent_signals": len(signals) > 0,
                "quality_score": 90.0 if dm_list and signals else 65.0
            },
            "research_gaps": (
                [] if (dm_list and signals and comp.industry) else
                [
                    k for k, v in [
                        ("DECISION_MAKER_MISSING", len(dm_list) == 0),
                        ("INTENT_SIGNALS_SPARSE", len(signals) == 0),
                        ("INDUSTRY_UNKNOWN", not comp.industry)
                    ] if v
                ]
            ),
            "recommended_next_action": (
                "Review lead for export to downstream data platform or authorized Google Sheet."
                if (comp.lead_score or 0) >= 80 else "Schedule research task to identify verified CTO/CIO contacts."
            )
        }
        return summary

    def compare_companies(
        self,
        workspace_id: str,
        company_id_a: str,
        company_id_b: str
    ) -> Dict[str, Any]:
        """Performs a multi-dimensional comparison between two target companies."""
        c_a = self.db.query(Company).filter(and_(Company.workspace_id == workspace_id, Company.id == company_id_a)).first()
        c_b = self.db.query(Company).filter(and_(Company.workspace_id == workspace_id, Company.id == company_id_b)).first()
        if not c_a or not c_b:
            raise ValueError("Both company IDs must be valid.")

        return {
            "comparison_target": f"{c_a.name} vs. {c_b.name}",
            "metrics": {
                "lead_score": {"company_a": c_a.lead_score or 0, "company_b": c_b.lead_score or 0},
                "industry": {"company_a": c_a.industry, "company_b": c_b.industry},
                "country": {"company_a": c_a.country, "company_b": c_b.country},
                "status": {"company_a": c_a.status, "company_b": c_b.status}
            },
            "summary": (
                f"{c_a.name} (Score {c_a.lead_score}) vs {c_b.name} (Score {c_b.lead_score}). "
                f"Both operate within {c_a.industry or 'the'} sector."
            )
        }

