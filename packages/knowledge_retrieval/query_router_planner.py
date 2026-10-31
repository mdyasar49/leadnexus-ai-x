import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.lead import Company, Contact, IntentSignal
from app.models.semantic_ontology import Concept
from app.models.knowledge_retrieval import (
    AIQuery,
    AIQueryPlan,
    QueryType,
    RetrievalMode,
)


class QueryRouterAndPlanner:
    """
    Intelligent Query Router & Planner:
    - Analyzes natural language user/internal queries
    - Classifies query type (Entity lookup, Evidence lookup, Tech, Intent, Comparison, Research, etc.)
    - Detects target entities, canonical ontology concepts, and temporal constraints
    - Validates and compiles a bounded AIQueryPlan
    """

    QUERY_TYPE_PATTERNS = [
        (re.compile(r"\b(?:why|how)\s+(?:is|did)\s+.*(?:high priority|score|tier)\b", re.I), QueryType.SCORE_QUERY.value),
        (re.compile(r"\b(?:evidence|proves?|source|proof|show evidence)\b", re.I), QueryType.EVIDENCE_LOOKUP.value),
        (re.compile(r"\b(?:compare|comparison|versus|vs\.?)\b", re.I), QueryType.ENTITY_COMPARISON.value),
        (re.compile(r"\b(?:what changed|recently|last\s+(?:week|month|30\s+days)|historically)\b", re.I), QueryType.CHANGE_QUERY.value),
        (re.compile(r"\b(?:who|decision maker|cto|ceo|contact|people|team)\b", re.I), QueryType.DECISION_MAKER_QUERY.value),
        (re.compile(r"\b(?:intent|looking for|seeking|planning|buying|migration intent)\b", re.I), QueryType.INTENT_QUERY.value),
        (re.compile(r"\b(?:odoo|sap|tech|technology|stack|erp|version)\b", re.I), QueryType.TECHNOLOGY_QUERY.value),
        (re.compile(r"\b(?:similar|lookalike|alike)\b", re.I), QueryType.RECOMMENDATION_QUERY.value),
        (re.compile(r"\b(?:research|investigate|missing|gap|what next)\b", re.I), QueryType.RESEARCH_QUERY.value),
        (re.compile(r"\b(?:analytics|metric|trend|forecast|rate)\b", re.I), QueryType.ANALYTICS_QUERY.value),
    ]

    TEMPORAL_PATTERNS = [
        (re.compile(r"\blast\s+7\s+days\b|\blast\s+week\b", re.I), 7),
        (re.compile(r"\blast\s+30\s+days\b|\blast\s+month\b|\brecently\b", re.I), 30),
        (re.compile(r"\blast\s+90\s+days\b|\blast\s+quarter\b", re.I), 90),
        (re.compile(r"\blast\s+year\b|\blast\s+365\s+days\b", re.I), 365),
    ]

    def __init__(self, db: Session):
        self.db = db

    def route_query_type(self, raw_query: str) -> str:
        """Classifies the primary intent of the natural language query."""
        for pattern, q_type in self.QUERY_TYPE_PATTERNS:
            if pattern.search(raw_query):
                return q_type
        return QueryType.GENERAL_PLATFORM_QUERY.value

    def detect_entities(self, workspace_id: str, raw_query: str) -> List[Dict[str, Any]]:
        """Identifies target companies or contacts mentioned in the query."""
        entities = []
        # Check against companies in workspace
        companies = self.db.query(Company).filter(Company.workspace_id == workspace_id).all()
        q_lower = raw_query.lower()
        for comp in companies:
            if comp.name.lower() in q_lower or (comp.domain and comp.domain.lower() in q_lower):
                entities.append({
                    "entity_type": "COMPANY",
                    "entity_id": comp.id,
                    "name": comp.name,
                    "domain": comp.domain
                })

        return entities

    def detect_concepts(self, workspace_id: str, raw_query: str) -> List[Dict[str, Any]]:
        """Identifies canonical ontology concepts (e.g. ODOO, RETAIL, CTO)."""
        concepts = []
        q_lower = raw_query.lower()
        canonical_candidates = self.db.query(Concept).filter(Concept.workspace_id == workspace_id).all()
        for c in canonical_candidates:
            if c.canonical_name.lower() in q_lower or c.display_name.lower() in q_lower:
                concepts.append({
                    "concept_id": c.id,
                    "canonical_name": c.canonical_name,
                    "ontology_type": c.ontology_type
                })
        return concepts

    def detect_temporal_constraint(self, raw_query: str) -> Optional[Dict[str, Any]]:
        """Extracts recency time window constraints."""
        for pattern, days in self.TEMPORAL_PATTERNS:
            if pattern.search(raw_query):
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                return {
                    "days": days,
                    "cutoff_iso": cutoff.isoformat(),
                    "constraint_type": "RECENT_WINDOW"
                }
        return None

    def plan_query(
        self,
        workspace_id: str,
        user_id: str,
        raw_query: str,
        conversation_id: Optional[str] = None
    ) -> Tuple[AIQuery, AIQueryPlan]:
        """
        Creates an immutable AIQuery record and structured, validated AIQueryPlan.
        """
        clean_q = re.sub(r"\s+", " ", raw_query.strip())
        q_type = self.route_query_type(clean_q)
        entities = self.detect_entities(workspace_id, clean_q)
        concepts = self.detect_concepts(workspace_id, clean_q)
        temporal = self.detect_temporal_constraint(clean_q)

        # Determine retrieval modes to activate
        modes = [RetrievalMode.EXACT.value, RetrievalMode.KEYWORD.value, RetrievalMode.SEMANTIC.value]
        if q_type in (QueryType.EVIDENCE_LOOKUP.value, QueryType.SCORE_QUERY.value):
            modes.append(RetrievalMode.EVIDENCE.value)
        if q_type in (QueryType.RELATIONSHIP_QUERY.value, QueryType.TECHNOLOGY_QUERY.value, QueryType.RECOMMENDATION_QUERY.value):
            modes.append(RetrievalMode.GRAPH.value)
        if temporal or q_type == QueryType.CHANGE_QUERY.value:
            modes.append(RetrievalMode.TEMPORAL.value)

        # Build plan steps
        steps = [
            {"step": 1, "action": "RETRIEVE_CANDIDATES", "modes": modes},
            {"step": 2, "action": "APPLY_TENANT_AND_PERMISSION_FILTER", "workspace_id": workspace_id},
            {"step": 3, "action": "MULTI_SIGNAL_RANKING_AND_DEDUPLICATION"},
            {"step": 4, "action": "CONTEXT_ASSEMBLY_AND_BUDGETING"},
            {"step": 5, "action": "GROUNDED_RESPONSE_AND_CITATION_SYNTHESIS"}
        ]

        # Persist AIQuery
        ai_query = AIQuery(
            workspace_id=workspace_id,
            user_id=user_id,
            conversation_id=conversation_id,
            raw_query=clean_q,
            normalized_query=clean_q.lower(),
            query_type=q_type,
            retrieval_mode=RetrievalMode.HYBRID.value
        )
        self.db.add(ai_query)
        self.db.commit()
        self.db.refresh(ai_query)

        # Persist AIQueryPlan
        plan = AIQueryPlan(
            query_id=ai_query.id,
            query_type=q_type,
            target_entities=entities,
            target_concepts=concepts,
            retrieval_modes=modes,
            temporal_constraints=temporal or {},
            minimum_confidence=0.70,
            max_evidence_items=12,
            plan_steps=steps,
            is_validated=True
        )
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)

        return ai_query, plan

