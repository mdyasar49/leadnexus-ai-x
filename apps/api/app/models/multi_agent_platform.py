"""
Multi-Agent AI Platform Models (Phase 41)
Supports the 12 specialized agents: ResearchAgent, CompanyAgent, PersonAgent, ContactAgent,
TechnologyAgent, EvidenceAgent, ScoringAgent, QualityAgent, GraphAgent, AnalyticsAgent,
PlanningAgent, ReviewAgent, with memory, bus, arbitration, and bounded task executions.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class AgentTypeEnum:
    RESEARCH_AGENT = "ResearchAgent"
    COMPANY_AGENT = "CompanyAgent"
    PERSON_AGENT = "PersonAgent"
    CONTACT_AGENT = "ContactAgent"
    TECHNOLOGY_AGENT = "TechnologyAgent"
    EVIDENCE_AGENT = "EvidenceAgent"
    SCORING_AGENT = "ScoringAgent"
    QUALITY_AGENT = "QualityAgent"
    GRAPH_AGENT = "GraphAgent"
    ANALYTICS_AGENT = "AnalyticsAgent"
    PLANNING_AGENT = "PlanningAgent"
    REVIEW_AGENT = "ReviewAgent"

    ALL_AGENTS = [
        RESEARCH_AGENT,
        COMPANY_AGENT,
        PERSON_AGENT,
        CONTACT_AGENT,
        TECHNOLOGY_AGENT,
        EVIDENCE_AGENT,
        SCORING_AGENT,
        QUALITY_AGENT,
        GRAPH_AGENT,
        ANALYTICS_AGENT,
        PLANNING_AGENT,
        REVIEW_AGENT,
    ]


class AgentStatus:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ARBITRATION = "ARBITRATION"


class AgentTaskPriority:
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ArbitrationStrategy:
    SUPERVISOR_CONSENSUS = "SUPERVISOR_CONSENSUS"
    CONFIDENCE_WEIGHTED = "CONFIDENCE_WEIGHTED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class AgentTaskRecord(Base):
    """Execution unit assigned to one or more specialized agents with bounded steps and token budget."""

    __tablename__ = "agent_task_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    parent_task_id = Column(String(36), nullable=True, index=True)
    assigned_agent = Column(String(32), nullable=False, index=True)  # AgentTypeEnum
    status = Column(String(16), default=AgentStatus.IDLE, nullable=False)
    priority = Column(String(16), default=AgentTaskPriority.NORMAL, nullable=False)
    goal_description = Column(Text, nullable=False)
    input_context = Column(JSON, default=dict, nullable=False)
    output_result = Column(JSON, default=dict, nullable=False)
    max_steps = Column(Integer, default=10, nullable=False)
    current_steps = Column(Integer, default=0, nullable=False)
    token_budget = Column(Integer, default=16384, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)


class AgentMemoryEntry(Base):
    """Scoped memory entry for agent state persistence and cross-agent context sharing."""

    __tablename__ = "agent_memory_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    agent_type = Column(String(32), nullable=False, index=True)
    memory_scope = Column(String(16), default="TASK", nullable=False)  # EPHEMERAL, TASK, WORKSPACE
    memory_key = Column(String(128), nullable=False, index=True)
    memory_value = Column(JSON, default=dict, nullable=False)
    ttl_seconds = Column(Integer, default=86400, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AgentMessageBusRecord(Base):
    """Inter-agent communications, queries, delegations, and broadcast events."""

    __tablename__ = "agent_message_bus_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), nullable=True, index=True)
    sender_agent = Column(String(32), nullable=False, index=True)
    recipient_agent = Column(String(32), nullable=False, index=True)  # AgentTypeEnum or BROADCAST
    message_type = Column(String(32), default="QUERY", nullable=False)  # QUERY, RESPONSE, DELEGATION, DISPUTE, HEARTBEAT
    payload = Column(JSON, default=dict, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AgentArbitrationRecord(Base):
    """Conflict resolution ledger when two agents disagree on fact, score, or classification."""

    __tablename__ = "agent_arbitration_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), nullable=False, index=True)
    disputing_agents = Column(JSON, default=list, nullable=False)  # ["CompanyAgent", "ResearchAgent"]
    conflict_summary = Column(Text, nullable=False)
    proposed_outcomes = Column(JSON, default=dict, nullable=False)
    arbitrator_decision = Column(JSON, default=dict, nullable=False)
    resolution_strategy = Column(String(32), default=ArbitrationStrategy.SUPERVISOR_CONSENSUS, nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AgentEvaluationMetric(Base):
    """Performance, reliability, latency, and cost benchmark metrics per specialized agent."""

    __tablename__ = "agent_evaluation_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_type = Column(String(32), nullable=False, index=True)
    total_tasks_completed = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=100.0, nullable=False)
    avg_latency_ms = Column(Float, default=0.0, nullable=False)
    avg_tokens_per_task = Column(Float, default=0.0, nullable=False)
    hallucination_score = Column(Float, default=0.0, nullable=False)  # 0.0 = perfect, lower is better
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
