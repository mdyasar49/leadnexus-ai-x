"""
Multi-Agent AI Platform Package (Phase 41)
Orchestration, Inter-Agent Messaging, Memory, Arbitration & Bounded Execution for 12 Specialized Agents
"""

from packages.agents.agent_registry import AgentRegistry, AgentDefinition
from packages.agents.agent_runtime import AutonomousAgent, AgentExecutionResult, BoundedExecutionExceededError
from packages.agents.agent_bus import InterAgentMessageBus
from packages.agents.arbitration_engine import AgentArbitrator, ArbitrationConflict
from packages.agents.specialized_agents import (
    ResearchAgent,
    CompanyAgent,
    PersonAgent,
    ContactAgent,
    TechnologyAgent,
    EvidenceAgent,
    ScoringAgent,
    QualityAgent,
    GraphAgent,
    AnalyticsAgent,
    PlanningAgent,
    ReviewAgent,
    get_specialized_agent,
)

__all__ = [
    "AgentRegistry",
    "AgentDefinition",
    "AutonomousAgent",
    "AgentExecutionResult",
    "BoundedExecutionExceededError",
    "InterAgentMessageBus",
    "AgentArbitrator",
    "ArbitrationConflict",
    "ResearchAgent",
    "CompanyAgent",
    "PersonAgent",
    "ContactAgent",
    "TechnologyAgent",
    "EvidenceAgent",
    "ScoringAgent",
    "QualityAgent",
    "GraphAgent",
    "AnalyticsAgent",
    "PlanningAgent",
    "ReviewAgent",
    "get_specialized_agent",
]

