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
from sqlalchemy import and_, or_, text
from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, SessionLocal, get_sync_db
from app.models.tenant import Workspace, Organization
from app.models.user import User
from app.models.lead import Company, Contact, IntentSignal
from app.models.semantic_ontology import Concept
from app.models.knowledge_graph import KnowledgeEntity, KnowledgeRelationship
from app.models.knowledge_retrieval import (
    AIQuery,
    AIQueryPlan,
    AIQueryExecution,
    AICitation,
    AIClaim,
    AIAnswerValidation,
    AIResearchSession,
    AIBudget,
    AIFeedback,
    AIEvaluation,
    QueryType,
    RetrievalMode,
    AnswerState,
    PredictionLabel,
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.knowledge_retrieval.query_router_planner import QueryRouterAndPlanner
from packages.knowledge_retrieval.hybrid_retriever import HybridRetriever
from packages.knowledge_retrieval.retrieval_ranking_engine import RetrievalRankingEngine
from packages.knowledge_retrieval.grounded_response_engine import GroundedResponseEngine
from packages.knowledge_retrieval.claim_validation_engine import ClaimValidationEngine
from packages.knowledge_retrieval.research_assistant_engine import ResearchAssistantEngine
from packages.knowledge_retrieval.ai_cost_and_model_router import AICostAndModelRouter
from packages.knowledge_retrieval.evaluation_and_feedback_service import EvaluationAndFeedbackService


class TestPhase25KnowledgeRetrieval(unittest.TestCase):
    """
    Test suite covering Phase 25:
    Enterprise AI Knowledge Retrieval, RAG, Context Intelligence & Grounded Research Assistant
    """

    @classmethod
    def setUpClass(cls):
        tables_to_recreate = [
            "ai_feedbacks", "ai_evaluations", "ai_model_routes", "ai_models", "ai_budgets",
            "ai_research_tool_calls", "ai_research_steps", "ai_research_sessions",
            "ai_conversation_messages", "ai_conversations", "ai_answer_validations",
            "ai_claim_evidence", "ai_claims", "ai_citations", "retrieval_results",
            "retrieval_queries", "rag_embeddings", "rag_document_chunks", "rag_documents",
            "ai_query_executions", "ai_query_plans", "ai_queries"
        ]
        with sync_engine.connect() as conn:
            for t in tables_to_recreate:
                conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
            conn.commit()

        Base.metadata.create_all(bind=sync_engine)
        cls.db = SessionLocal()

        cls.org_id = f"test-org-{uuid.uuid4()}"
        cls.ws_id = f"test-ws-{uuid.uuid4()}"
        cls.user_id = f"test-user-{uuid.uuid4()}"

        cls.user = User(
            id=cls.user_id,
            email=f"rag_architect_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="secret_hash_pwd",
            first_name="RAG",
            last_name="Architect",
            is_active=True,
            is_superuser=True
        )
        cls.db.add(cls.user)

        cls.ws = Workspace(
            id=cls.ws_id,
            organization_id=cls.org_id,
            name="RAG Test Workspace",
            slug=f"rag-ws-{uuid.uuid4().hex[:6]}",
            is_active=True
        )
        cls.db.add(cls.ws)

        # Seed Companies
        cls.comp_1 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Apex Retail Sydney",
            normalized_name="apex retail sydney",
            domain="apexretail.com.au",
            country="Australia",
            industry="Retail",
            lead_score=92,
            status="QUALIFIED"
        )
        cls.comp_2 = Company(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            name="Pacific Mining Brisbane",
            normalized_name="pacific mining brisbane",
            domain="pacificmining.com.au",
            country="Australia",
            industry="Mining",
            lead_score=68,
            status="DISCOVERED"
        )
        cls.db.add(cls.comp_1)
        cls.db.add(cls.comp_2)

        # Seed Contacts
        cls.contact_1 = Contact(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_1.id,
            full_name="Elena Rostova",
            email="elena@apexretail.com.au",
            source_url="https://apexretail.com.au/team/elena",
            job_title="Chief Technology Officer",
            email_status="VERIFIED",
            is_decision_maker=True,
            confidence_score=0.96
        )
        cls.db.add(cls.contact_1)

        # Seed Intent Signals
        cls.sig_1 = IntentSignal(
            id=str(uuid.uuid4()),
            workspace_id=cls.ws_id,
            company_id=cls.comp_1.id,
            source_name="Official RFP",
            signal_type="PARTNER_SEARCH",
            detected_keyword="Odoo 17 Implementation",
            source_url="https://apexretail.com.au/rfp/odoo-erp",
            evidence_snippet="Apex Retail Sydney is actively seeking an Odoo implementation partner for inventory migration.",
            signal_strength=0.95
        )
        cls.db.add(cls.sig_1)
        cls.db.commit()

        # FastAPI test client overrides
        app.dependency_overrides[get_sync_db] = lambda: cls.db
        app.dependency_overrides[get_active_workspace] = lambda: cls.ws
        app.dependency_overrides[get_current_user] = lambda: cls.user
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.db.close()

    # --- 1. Query Router & Plan Generation ---

    def test_01_query_routing_and_plan_generation(self):
        planner = QueryRouterAndPlanner(self.db)
        raw_q = "Why is Apex Retail Sydney a high priority lead in the last 30 days?"
        ai_query, plan = planner.plan_query(self.ws_id, self.user_id, raw_q)

        self.assertIsNotNone(ai_query.id)
        self.assertEqual(plan.query_type, QueryType.SCORE_QUERY.value)
        self.assertTrue(len(plan.target_entities) > 0)
        self.assertEqual(plan.target_entities[0]["name"], "Apex Retail Sydney")
        self.assertIsNotNone(plan.temporal_constraints)
        self.assertEqual(plan.temporal_constraints.get("days"), 30)

    # --- 2. Hybrid Retrieval Across Multi-Modalities ---

    def test_02_hybrid_retrieval_across_modes(self):
        retriever = HybridRetriever(self.db)
        candidates = retriever.retrieve(
            workspace_id=self.ws_id,
            raw_query="Apex Retail Sydney Odoo 17 implementation",
            target_entity_ids=[self.comp_1.id]
        )
        self.assertGreater(len(candidates), 0)
        types = {c["entity_type"] for c in candidates}
        self.assertIn("COMPANY", types)
        self.assertIn("INTENT_SIGNAL", types)

    # --- 3. Retrieval Ranking & Source Independence Deduplication ---

    def test_03_retrieval_ranking_and_source_independence_deduplication(self):
        ranker = RetrievalRankingEngine()
        candidates = [
            {
                "item_id": "c1", "snippet": "Apex Retail adopts Odoo ERP.",
                "source_url": "https://itnews.com.au/articles/apex-odoo",
                "semantic_score": 0.9, "keyword_score": 0.8, "exact_score": 0.5,
                "freshness_score": 1.0, "source_reliability": 0.9
            },
            # Second item from the SAME domain (syndicated clone)
            {
                "item_id": "c2", "snippet": "Apex Retail adopts Odoo ERP summary.",
                "source_url": "https://itnews.com.au/syndicated/apex-odoo-summary",
                "semantic_score": 0.9, "keyword_score": 0.8, "exact_score": 0.5,
                "freshness_score": 1.0, "source_reliability": 0.9
            }
        ]
        ranked = ranker.rank_and_deduplicate(candidates, max_items=5)
        self.assertEqual(len(ranked), 2)
        # Invariant: First independent item ranks higher than subsequent clone on same domain
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])
        self.assertEqual(ranked[1]["source_independence_score"], round(1.0 / (2 ** 0.5), 2))

    # --- 4. Grounded Response Generation with Verifiable Citations ---

    def test_04_grounded_response_generation_with_citations(self):
        responder = GroundedResponseEngine(self.db)
        retrieved_context = [
            {
                "item_id": "sig-1", "title": "Apex RFP", "snippet": "Apex Retail is seeking an Odoo partner.",
                "source_url": "https://apexretail.com.au/rfp", "final_score": 0.95
            }
        ]
        query_id = str(uuid.uuid4())
        execution = responder.synthesize_response(
            query_id=query_id,
            user_query="Why is Apex Retail high priority?",
            ranked_context=retrieved_context,
            detected_entity_name="Apex Retail Sydney"
        )
        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.answer_state, AnswerState.GROUNDED.value)
        self.assertIn("Apex Retail is seeking an Odoo partner", execution.response_text)

        # Check citations
        citations = self.db.query(AICitation).filter(AICitation.execution_id == execution.id).all()
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].citation_number, 1)

    # --- 5. Conflict Detection & Recency Reasoning ---

    def test_05_conflict_detection_and_recency_handling(self):
        responder = GroundedResponseEngine(self.db)
        conflicting_context = [
            {"item_id": "c1", "title": "Old Wiki", "snippet": "Apex Retail operates on Odoo 17.", "source_url": "https://wiki.org"},
            {"item_id": "c2", "title": "Recent Job", "snippet": "Apex Retail hiring lead for Odoo 18 upgrade.", "source_url": "https://jobs.org"}
        ]
        query_id = str(uuid.uuid4())
        execution = responder.synthesize_response(
            query_id=query_id,
            user_query="Which Odoo version is used?",
            ranked_context=conflicting_context,
            detected_entity_name="Apex Retail"
        )
        self.assertTrue(execution.has_conflicts)
        self.assertEqual(execution.answer_state, AnswerState.CONFLICTING_EVIDENCE.value)
        self.assertIn("Conflicting evidence detected", execution.response_text)

    # --- 6. Insufficient Evidence Response ---

    def test_06_insufficient_evidence_response(self):
        responder = GroundedResponseEngine(self.db)
        query_id = str(uuid.uuid4())
        execution = responder.synthesize_response(
            query_id=query_id,
            user_query="Does NonExistentCompany plan to buy Salesforce next quarter?",
            ranked_context=[]
        )
        self.assertEqual(execution.answer_state, AnswerState.INSUFFICIENT_EVIDENCE.value)
        self.assertIn("insufficient public evidence", execution.response_text.lower())
        self.assertEqual(execution.confidence_score, 0.0)

    # --- 7. Prediction Separation Labeling ---

    def test_07_prediction_separation_labeling(self):
        responder = GroundedResponseEngine(self.db)
        retrieved_context = [
            {"item_id": "s1", "title": "Signal", "snippet": "Observed ERP job post.", "source_url": "https://apex.com.au"}
        ]
        query_id = str(uuid.uuid4())
        execution = responder.synthesize_response(
            query_id=query_id,
            user_query="Status check",
            ranked_context=retrieved_context
        )
        # Invariants: Explicit labels distinguish observation from prediction
        self.assertIn("[OBSERVED", execution.response_text)
        self.assertIn("[PREDICTED]", execution.response_text)
        self.assertIn("[RECOMMENDED]", execution.response_text)

    # --- 8. Claim Extraction & Groundedness Validation ---

    def test_08_claim_extraction_and_groundedness_validation(self):
        validator = ClaimValidationEngine(self.db)
        retrieved_evidence = [
            {"item_id": "e1", "snippet": "Apex Retail Sydney is actively seeking an Odoo implementation partner."}
        ]
        response_text = (
            "Apex Retail Sydney is actively seeking an Odoo implementation partner.\n"
            "[PREDICTED] Procurement probability remains elevated next quarter.\n"
            "An ungrounded claim that they bought 500 laptops yesterday."
        )
        val = validator.extract_and_validate_claims(
            execution_id=str(uuid.uuid4()),
            response_text=response_text,
            retrieved_evidence=retrieved_evidence
        )
        self.assertGreater(val.total_claims, 0)
        self.assertGreaterEqual(val.supported_claims, 1)

    # --- 9. Research Assistant Tool Allowlisting ---

    def test_09_research_assistant_tool_allowlisting(self):
        assistant = ResearchAssistantEngine(self.db)
        session = assistant.start_research_session(
            workspace_id=self.ws_id,
            user_id=self.user_id,
            target_entity_id=self.comp_1.id,
            objective="Investigate Odoo 17 footprint"
        )
        self.assertEqual(session.current_status, "ACTIVE")

        # Step tool call: Allowed tool
        res_allowed = assistant.execute_tool_call(
            step_id=str(uuid.uuid4()),
            tool_name="retrieve_evidence",
            parameters={"entity_id": self.comp_1.id}
        )
        self.assertEqual(res_allowed["status"], "SUCCESS")

        # Step tool call: Forbidden tool -> PermissionError
        with self.assertRaises(PermissionError):
            assistant.execute_tool_call(
                step_id=str(uuid.uuid4()),
                tool_name="raw_sql",
                parameters={"query": "DROP TABLE companies"}
            )

    # --- 10. Lead 360 AI Summary ---

    def test_10_lead_360_ai_summary(self):
        assistant = ResearchAssistantEngine(self.db)
        summary = assistant.generate_lead_360_summary(self.ws_id, self.comp_1.id)
        self.assertEqual(summary["company_name"], "Apex Retail Sydney")
        self.assertEqual(summary["lead_priority_tier"], "P1_HIGH")
        self.assertTrue(len(summary["decision_makers"]) > 0)
        self.assertEqual(summary["decision_makers"][0]["name"], "Elena Rostova")
        self.assertIn("Odoo 17 Implementation", summary["why_this_lead_matters"] + summary["why_now"] + str(summary["observed_intent"]))

    # --- 11. Company Comparison Matrix ---

    def test_11_company_comparison(self):
        assistant = ResearchAssistantEngine(self.db)
        comp = assistant.compare_companies(self.ws_id, self.comp_1.id, self.comp_2.id)
        self.assertIn("Apex Retail Sydney vs. Pacific Mining Brisbane", comp["comparison_target"])
        self.assertEqual(comp["metrics"]["lead_score"]["company_a"], 92)
        self.assertEqual(comp["metrics"]["lead_score"]["company_b"], 68)

    # --- 12. AI Cost Tracking & Budget Governance ---

    def test_12_ai_cost_and_budget_throttling(self):
        cost_router = AICostAndModelRouter(self.db)
        # Normal update
        allowed = cost_router.check_and_update_budget(self.ws_id, tokens_used=1000, estimated_cost_usd=0.01)
        self.assertTrue(allowed)

        # Trigger budget limit
        budget = self.db.query(AIBudget).filter(AIBudget.workspace_id == self.ws_id).first()
        budget.current_month_spent_usd = 300.0  # Exceeds 250.0 limit
        self.db.commit()

        throttled = cost_router.check_and_update_budget(self.ws_id, tokens_used=500)
        self.assertFalse(throttled)

        # Reset budget for downstream tests
        budget.current_month_spent_usd = 10.0
        budget.is_throttled = False
        self.db.commit()

    # --- 13. Model Routing by Task Tier ---

    def test_13_model_routing_by_task_tier(self):
        cost_router = AICostAndModelRouter(self.db)
        route = cost_router.route_task_model(self.ws_id, task_type="SUMMARIZATION")
        self.assertIsNotNone(route["model_name"])
        self.assertEqual(route["prompt_version"], "v1.0")

    # --- 14. Human Feedback & Evaluation ---

    def test_14_human_feedback_and_grounding_evaluation(self):
        service = EvaluationAndFeedbackService(self.db)
        fb = service.submit_feedback(
            workspace_id=self.ws_id,
            execution_id=str(uuid.uuid4()),
            user_id=self.user_id,
            rating="HELPFUL",
            feedback_text="Strong evidence citations verified."
        )
        self.assertEqual(fb.rating, "HELPFUL")

        evaluation = service.run_workspace_evaluation(self.ws_id)
        self.assertGreaterEqual(evaluation.average_groundedness, 0.0)

    # --- 15. REST API Endpoints Integration ---

    def test_15_api_endpoints_integration(self):
        # 1. POST /api/v1/ai/query/plan
        resp_plan = self.client.post("/api/v1/ai/query/plan", json={
            "query": "Why is Apex Retail Sydney a high priority lead?"
        })
        self.assertEqual(resp_plan.status_code, 200)
        self.assertEqual(resp_plan.json()["query_type"], QueryType.SCORE_QUERY.value)

        # 2. POST /api/v1/ai/query
        resp_query = self.client.post("/api/v1/ai/query", json={
            "query": "Why is Apex Retail Sydney a high priority lead?"
        })
        self.assertEqual(resp_query.status_code, 200)
        self.assertEqual(resp_query.json()["answer_state"], AnswerState.GROUNDED.value)
        self.assertGreaterEqual(len(resp_query.json()["citations"]), 1)

        # 3. GET /api/v1/ai/lead/{id}/summary
        resp_sum = self.client.get(f"/api/v1/ai/lead/{self.comp_1.id}/summary")
        self.assertEqual(resp_sum.status_code, 200)
        self.assertEqual(resp_sum.json()["company_name"], "Apex Retail Sydney")

        # 4. POST /api/v1/ai/compare
        resp_comp = self.client.post("/api/v1/ai/compare", json={
            "company_id_a": self.comp_1.id,
            "company_id_b": self.comp_2.id
        })
        self.assertEqual(resp_comp.status_code, 200)

        # 5. GET /api/v1/ai/evaluations
        resp_eval = self.client.get("/api/v1/ai/evaluations")
        self.assertEqual(resp_eval.status_code, 200)
        self.assertIn("average_groundedness", resp_eval.json())

