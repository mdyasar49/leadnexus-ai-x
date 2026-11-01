"""
Agent Registry & Specifications (Phase 41)
Defines specifications, capabilities, tools, and permissions for all 12 specialized enterprise agents.
"""

from typing import Any, Dict, List, Optional
from app.models.multi_agent_platform import AgentTypeEnum


class AgentDefinition:
    def __init__(
        self,
        agent_type: str,
        display_name: str,
        role_description: str,
        capabilities: List[str],
        allowed_tools: List[str],
        max_steps: int = 10,
        sandbox_restricted: bool = True,
    ):
        self.agent_type = agent_type
        self.display_name = display_name
        self.role_description = role_description
        self.capabilities = capabilities
        self.allowed_tools = allowed_tools
        self.max_steps = max_steps
        self.sandbox_restricted = sandbox_restricted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "display_name": self.display_name,
            "role_description": self.role_description,
            "capabilities": self.capabilities,
            "allowed_tools": self.allowed_tools,
            "max_steps": self.max_steps,
            "sandbox_restricted": self.sandbox_restricted,
        }


class AgentRegistry:
    """Central directory containing all 12 approved enterprise specialized agents."""

    _ROSTER: Dict[str, AgentDefinition] = {
        AgentTypeEnum.RESEARCH_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.RESEARCH_AGENT,
            display_name="Research Specialist Agent",
            role_description="Performs broad open-web signal gathering, query formulation, and intelligence synthesis.",
            capabilities=["web_search", "document_scraping", "dossier_synthesis"],
            allowed_tools=["http_fetch", "text_extractor", "summary_engine"],
            max_steps=12,
        ),
        AgentTypeEnum.COMPANY_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.COMPANY_AGENT,
            display_name="Firmographic Company Agent",
            role_description="Resolves canonical company identities, firmographics, revenue bands, and employee counts.",
            capabilities=["domain_resolution", "firmographics_lookup", "industry_classification"],
            allowed_tools=["company_db_lookup", "domain_whois", "entity_resolver"],
            max_steps=8,
        ),
        AgentTypeEnum.PERSON_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.PERSON_AGENT,
            display_name="Decision Maker Profile Agent",
            role_description="Discovers and structures decision-maker profiles, seniority, titles, and professional bios.",
            capabilities=["title_classification", "seniority_mapping", "executive_discovery"],
            allowed_tools=["people_directory", "title_normalizer"],
            max_steps=8,
        ),
        AgentTypeEnum.CONTACT_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.CONTACT_AGENT,
            display_name="Contact Verification Agent",
            role_description="Discovers verified corporate email patterns, corporate phone numbers, and LinkedIn handles.",
            capabilities=["email_pattern_derivation", "smtp_deliverability_check", "phone_formatting"],
            allowed_tools=["email_verifier", "phone_normalizer"],
            max_steps=6,
        ),
        AgentTypeEnum.TECHNOLOGY_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.TECHNOLOGY_AGENT,
            display_name="Technology Stack Detection Agent",
            role_description="Analyzes digital footprints to detect active CRM, ERP, Cloud, and Developer frameworks.",
            capabilities=["technographic_scan", "cloud_provider_detection", "crm_erp_fingerprinting"],
            allowed_tools=["tech_detector", "dns_scanner"],
            max_steps=8,
        ),
        AgentTypeEnum.EVIDENCE_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.EVIDENCE_AGENT,
            display_name="Evidence & Citation Agent",
            role_description="Verifies claims with citations, URL provenance timestamps, and factual grounding checks.",
            capabilities=["citation_verification", "provenance_tracking", "hallucination_detection"],
            allowed_tools=["url_verifier", "claim_checker"],
            max_steps=6,
        ),
        AgentTypeEnum.SCORING_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.SCORING_AGENT,
            display_name="ICP Scoring & Intent Agent",
            role_description="Calculates multi-factor ICP qualification scores, buying readiness, and surge indicators.",
            capabilities=["icp_fit_calculation", "intent_weighting", "propensity_scoring"],
            allowed_tools=["scoring_engine", "icp_rules"],
            max_steps=6,
        ),
        AgentTypeEnum.QUALITY_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.QUALITY_AGENT,
            display_name="Data Quality & Integrity Agent",
            role_description="Validates completeness, RFC schema compliance, null detection, and freshness SLAs.",
            capabilities=["contract_verification", "null_inspection", "freshness_sla_audit"],
            allowed_tools=["data_contract_validator", "quality_evaluator"],
            max_steps=6,
        ),
        AgentTypeEnum.GRAPH_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.GRAPH_AGENT,
            display_name="Semantic Graph Linker Agent",
            role_description="Constructs relational edges connecting Companies, People, Leads, Signals, and Intent.",
            capabilities=["subgraph_traversal", "entity_linking", "relationship_inference"],
            allowed_tools=["graph_edge_builder", "similarity_linker"],
            max_steps=8,
        ),
        AgentTypeEnum.ANALYTICS_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.ANALYTICS_AGENT,
            display_name="Analytics & Telemetry Agent",
            role_description="Aggregates pipeline execution metrics, token utilization, costs, and throughput trends.",
            capabilities=["metric_aggregation", "trend_projection", "cost_auditing"],
            allowed_tools=["metrics_aggregator", "token_counter"],
            max_steps=6,
        ),
        AgentTypeEnum.PLANNING_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.PLANNING_AGENT,
            display_name="Lead Research Supervisor & Planner",
            role_description="Decomposes high-level user research objectives, dispatches sub-tasks, and orchestrates delegations.",
            capabilities=["task_decomposition", "dependency_graphing", "delegation_coordination"],
            allowed_tools=["task_dispatcher", "subtask_scheduler"],
            max_steps=15,
        ),
        AgentTypeEnum.REVIEW_AGENT: AgentDefinition(
            agent_type=AgentTypeEnum.REVIEW_AGENT,
            display_name="Human-in-the-Loop Review Agent",
            role_description="Conducts final compliance checks, verifies user explicit-add constraints, and gates exports.",
            capabilities=["compliance_audit", "export_gatekeeping", "human_review_escalation"],
            allowed_tools=["compliance_evaluator", "export_verifier"],
            max_steps=6,
        ),
    }

    @classmethod
    def get_agent(cls, agent_type: str) -> AgentDefinition:
        if agent_type not in cls._ROSTER:
            raise KeyError(f"Unknown specialized agent: {agent_type}. Allowed: {list(cls._ROSTER.keys())}")
        return cls._ROSTER[agent_type]

    @classmethod
    def list_all(cls) -> List[AgentDefinition]:
        return list(cls._ROSTER.values())

