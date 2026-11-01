from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.api.routes.auth import router as auth_router
from app.api.routes.tenants import router as tenants_router
from app.api.routes.campaigns import router as campaigns_router
from app.api.routes.sources import router as sources_router
from app.api.routes.runs import router as runs_router
from app.api.routes.discovery import router as discovery_router
from app.api.routes.browser import router as browser_router
from app.api.routes.operations import router as operations_router
from app.api.routes.costs import router as costs_router
from app.api.routes.ai_intelligence import router as ai_intel_router, intel_router
from app.api.routes.scoring_routes import router as scoring_router
from app.api.routes.icp_routes import router as icp_router
from app.api.routes.research_ai import research_router, ai_tools_router
from app.api.routes.search_routes import router as search_router
from app.api.routes.lead_workspace import router as leads_router
from app.api.routes.export_routes import router as exports_router
from app.api.routes.enrichment_routes import router as enrichment_router
from app.api.routes.contact_intelligence_routes import (
    contacts_router,
    people_router,
    domains_router,
    verification_router
)
from app.api.routes.workflow_routes import (
    workflows_router,
    runs_router as wf_runs_router,
    dlq_router,
    metrics_router as wf_metrics_router
)
from app.api.routes.review_routes import (
    reviews_router,
    conflicts_router
)
from app.api.routes.monitoring_routes import (
    monitoring_router,
    alerts_router,
    watchlists_router,
    notifications_router,
    collaboration_router,
    briefs_router
)
from app.api.routes.analytics_routes import analytics_router
from app.api.routes.decision_intelligence_routes import decision_intel_router
from app.api.routes.knowledge_graph_routes import knowledge_graph_router
from app.api.routes.semantic_ontology_routes import semantic_ontology_router
from app.api.routes.knowledge_retrieval_routes import knowledge_retrieval_router
from app.api.routes.autonomous_research_routes import autonomous_research_router
from app.api.routes.integration_routes import integrations_router
from app.api.routes.developer_platform_routes import router as developer_router
from app.api.routes.governance_routes import router as governance_router
from app.api.routes.resilience_routes import router as resilience_router
from app.api.routes.performance_routes import router as performance_router
from app.api.routes.data_lifecycle_routes import router as lifecycle_router
from app.api.routes.migration_routes import router as migration_router
from app.api.routes.event_routes import router as event_router
from app.api.routes.enterprise_webhook_routes import router as webhook_router
from app.api.routes.digital_twin_routes import router as simulation_router
from app.api.routes.multi_region_routes import router as multi_region_router
from app.api.routes.direct_lead_routes import router as direct_lead_router
from app.api.routes.api_gateway_routes import router as gateway_router
from app.api.routes.identity_routes import router as identity_router
from app.api.routes.data_fabric_routes import router as data_fabric_router
from app.api.routes.ai_platform_routes import router as ai_platform_router
from app.api.routes.agent_routes import router as agent_router
from app.api.routes.document_intelligence_routes import router as document_intelligence_router
from app.api.routes.orchestration_routes import router as orchestration_router
from app.api.routes.telemetry_routes import router as telemetry_router
from app.api.routes.self_healing_routes import router as self_healing_router
from app.api.routes.entity_graph_routes import router as entity_graph_router

# Root router for top-level probes
root_router = APIRouter()
root_router.include_router(health_router)

# Versioned API v1 Router
api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(direct_lead_router)
api_v1_router.include_router(system_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(tenants_router)
api_v1_router.include_router(campaigns_router)
api_v1_router.include_router(sources_router)
api_v1_router.include_router(runs_router)
api_v1_router.include_router(discovery_router)
api_v1_router.include_router(browser_router)
api_v1_router.include_router(operations_router)
api_v1_router.include_router(costs_router)
api_v1_router.include_router(ai_intel_router)
api_v1_router.include_router(intel_router)
api_v1_router.include_router(scoring_router)
api_v1_router.include_router(icp_router)
api_v1_router.include_router(research_router)
api_v1_router.include_router(ai_tools_router)
api_v1_router.include_router(search_router)
api_v1_router.include_router(leads_router)
api_v1_router.include_router(exports_router)
api_v1_router.include_router(enrichment_router)
api_v1_router.include_router(contacts_router)
api_v1_router.include_router(people_router)
api_v1_router.include_router(domains_router)
api_v1_router.include_router(verification_router)
api_v1_router.include_router(workflows_router)
api_v1_router.include_router(wf_runs_router)
api_v1_router.include_router(dlq_router)
api_v1_router.include_router(wf_metrics_router)
api_v1_router.include_router(reviews_router)
api_v1_router.include_router(conflicts_router)
api_v1_router.include_router(monitoring_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(watchlists_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(collaboration_router)
api_v1_router.include_router(briefs_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(decision_intel_router)
api_v1_router.include_router(knowledge_graph_router)
api_v1_router.include_router(semantic_ontology_router)
api_v1_router.include_router(knowledge_retrieval_router)
api_v1_router.include_router(autonomous_research_router)
api_v1_router.include_router(integrations_router)
api_v1_router.include_router(developer_router)
api_v1_router.include_router(governance_router)
api_v1_router.include_router(resilience_router)
api_v1_router.include_router(performance_router)
api_v1_router.include_router(lifecycle_router)
api_v1_router.include_router(migration_router)
api_v1_router.include_router(event_router)
api_v1_router.include_router(webhook_router)
api_v1_router.include_router(simulation_router)
api_v1_router.include_router(multi_region_router)
api_v1_router.include_router(gateway_router)
api_v1_router.include_router(identity_router)
api_v1_router.include_router(data_fabric_router)
api_v1_router.include_router(ai_platform_router)
api_v1_router.include_router(agent_router)
api_v1_router.include_router(document_intelligence_router)
api_v1_router.include_router(orchestration_router)
api_v1_router.include_router(telemetry_router)
api_v1_router.include_router(self_healing_router)
api_v1_router.include_router(entity_graph_router)

# Direct /api router for universal compatibility
api_direct_router = APIRouter(prefix="/api")
api_direct_router.include_router(direct_lead_router)
api_direct_router.include_router(discovery_router)
api_direct_router.include_router(sources_router)
api_direct_router.include_router(runs_router)
api_direct_router.include_router(browser_router)
api_direct_router.include_router(operations_router)
api_direct_router.include_router(costs_router)
api_direct_router.include_router(ai_intel_router)
api_direct_router.include_router(intel_router)
api_direct_router.include_router(scoring_router)
api_direct_router.include_router(icp_router)
api_direct_router.include_router(research_router)
api_direct_router.include_router(ai_tools_router)
api_direct_router.include_router(search_router)
api_direct_router.include_router(leads_router)
api_direct_router.include_router(exports_router)
api_direct_router.include_router(enrichment_router)
api_direct_router.include_router(contacts_router)
api_direct_router.include_router(people_router)
api_direct_router.include_router(domains_router)
api_direct_router.include_router(verification_router)
api_direct_router.include_router(workflows_router)
api_direct_router.include_router(wf_runs_router)
api_direct_router.include_router(dlq_router)
api_direct_router.include_router(wf_metrics_router)
api_direct_router.include_router(reviews_router)
api_direct_router.include_router(conflicts_router)
api_direct_router.include_router(monitoring_router)
api_direct_router.include_router(alerts_router)
api_direct_router.include_router(watchlists_router)
api_direct_router.include_router(notifications_router)
api_direct_router.include_router(collaboration_router)
api_direct_router.include_router(briefs_router)
api_direct_router.include_router(analytics_router)
api_direct_router.include_router(decision_intel_router)
api_direct_router.include_router(knowledge_graph_router)
api_direct_router.include_router(semantic_ontology_router)
api_direct_router.include_router(knowledge_retrieval_router)
api_direct_router.include_router(autonomous_research_router)
api_direct_router.include_router(integrations_router)
api_direct_router.include_router(developer_router)
api_direct_router.include_router(governance_router)
api_direct_router.include_router(resilience_router)
api_direct_router.include_router(performance_router)
api_direct_router.include_router(lifecycle_router)
api_direct_router.include_router(migration_router)
api_direct_router.include_router(event_router)
api_direct_router.include_router(webhook_router)
api_direct_router.include_router(simulation_router)
api_direct_router.include_router(multi_region_router)
api_direct_router.include_router(gateway_router)
api_direct_router.include_router(identity_router)
api_direct_router.include_router(data_fabric_router)
api_direct_router.include_router(ai_platform_router)
api_direct_router.include_router(agent_router)
api_direct_router.include_router(document_intelligence_router)
api_direct_router.include_router(orchestration_router)
api_direct_router.include_router(telemetry_router)
api_direct_router.include_router(self_healing_router)
api_direct_router.include_router(entity_graph_router)
