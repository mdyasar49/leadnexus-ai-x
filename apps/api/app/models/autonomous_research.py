import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


# --- Enums ---

class ResearchMode(str, enum.Enum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
    FORENSIC = "FORENSIC"
    CONTINUOUS = "CONTINUOUS"


class ToolRiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    RESTRICTED = "RESTRICTED"


class RunStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    TERMINATED = "TERMINATED"


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SKIPPED = "SKIPPED"


class StopCondition(str, enum.Enum):
    GOAL_SATISFIED = "GOAL_SATISFIED"
    DEPTH_LIMIT = "DEPTH_LIMIT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    USER_STOP = "USER_STOP"
    ERROR = "ERROR"
    RESEARCH_LIMIT_REACHED = "RESEARCH_LIMIT_REACHED"


class TaskType(str, enum.Enum):
    COMPANY_PROFILING = "COMPANY_PROFILING"
    TECHNOLOGY_DETECTION = "TECHNOLOGY_DETECTION"
    ODOO_VERIFICATION = "ODOO_VERIFICATION"
    INTENT_DISCOVERY = "INTENT_DISCOVERY"
    DECISION_MAKER_SEARCH = "DECISION_MAKER_SEARCH"
    CONTACT_VERIFICATION = "CONTACT_VERIFICATION"
    EVIDENCE_VALIDATION = "EVIDENCE_VALIDATION"
    ENTITY_RESOLUTION = "ENTITY_RESOLUTION"
    DATA_QUALITY_AUDIT = "DATA_QUALITY_AUDIT"
    GAP_REMEDIATION = "GAP_REMEDIATION"


# --- Autonomy Policy Models ---

class AutonomyPolicy(Base):
    __tablename__ = "autonomy_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    risk_level = Column(String(50), default=ToolRiskLevel.LOW.value, nullable=False)
    max_iterations = Column(Integer, default=10, nullable=False)
    max_runtime_seconds = Column(Integer, default=300, nullable=False)
    max_tool_calls = Column(Integer, default=50, nullable=False)
    max_parallel_tasks = Column(Integer, default=5, nullable=False)
    max_cost_budget = Column(Float, default=10.0, nullable=False)
    allowed_tools = Column(JSON, default=list)
    forbidden_tools = Column(JSON, default=list)
    allowed_domains = Column(JSON, default=list)
    blocked_domains = Column(JSON, default=list)
    require_human_approval = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_autonomy_pol_ws_active", "workspace_id", "is_active"),
    )


class AutonomyPolicyVersion(Base):
    __tablename__ = "autonomy_policy_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    policy_id = Column(String(36), ForeignKey("autonomy_policies.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    policy_data = Column(JSON, default=dict)
    changed_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Research Plan Models ---

class ResearchPlan(Base):
    __tablename__ = "research_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    objective = Column(Text, nullable=False)
    mode = Column(String(50), default=ResearchMode.STANDARD.value, nullable=False)
    target_type = Column(String(50), default="COMPANY", nullable=False)
    target_id = Column(String(36), nullable=True, index=True)
    target_name = Column(String(255), nullable=True)
    policy_id = Column(String(36), ForeignKey("autonomy_policies.id"), nullable=True, index=True)
    max_depth = Column(Integer, default=3, nullable=False)
    estimated_cost = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="DRAFT", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchPlanVersion(Base):
    __tablename__ = "research_plan_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(36), ForeignKey("research_plans.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    plan_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchPlanStep(Base):
    __tablename__ = "research_plan_steps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(36), ForeignKey("research_plans.id"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    task_type = Column(String(50), nullable=False)
    agent_name = Column(String(100), nullable=False)
    tool_name = Column(String(100), nullable=True)
    parameters = Column(JSON, default=dict)
    status = Column(String(50), default="PENDING", nullable=False)
    depends_on = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchPlanDependency(Base):
    __tablename__ = "research_plan_dependencies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(36), ForeignKey("research_plans.id"), nullable=False, index=True)
    source_step_id = Column(String(36), nullable=False, index=True)
    target_step_id = Column(String(36), nullable=False, index=True)
    dependency_type = Column(String(50), default="FINISH_TO_START", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Autonomous Research Run & Execution Models ---

class AutonomousResearchRun(Base):
    __tablename__ = "autonomous_research_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("research_plans.id"), nullable=True, index=True)
    objective = Column(Text, nullable=False)
    mode = Column(String(50), default=ResearchMode.STANDARD.value, nullable=False)
    status = Column(String(50), default=RunStatus.PENDING.value, nullable=False)
    current_step_id = Column(String(36), nullable=True)
    current_iteration = Column(Integer, default=0, nullable=False)
    total_iterations = Column(Integer, default=0, nullable=False)
    tool_call_count = Column(Integer, default=0, nullable=False)
    pages_visited = Column(Integer, default=0, nullable=False)
    total_cost = Column(Float, default=0.0, nullable=False)
    error_message = Column(Text, nullable=True)
    stop_condition = Column(String(50), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_auto_run_ws_status", "workspace_id", "status"),
    )


class ResearchRunCheckpoint(Base):
    __tablename__ = "research_run_checkpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    iteration = Column(Integer, nullable=False)
    state_snapshot = Column(JSON, default=dict)
    completed_tasks = Column(JSON, default=list)
    pending_tasks = Column(JSON, default=list)
    discovered_entities = Column(JSON, default=list)
    cost_accrued = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    step_id = Column(String(36), nullable=True, index=True)
    task_type = Column(String(50), nullable=False)
    agent_name = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    status = Column(String(50), default=TaskStatus.PENDING.value, nullable=False)
    input_payload = Column(JSON, default=dict)
    output_payload = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchTaskAttempt(Base):
    __tablename__ = "research_task_attempts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("research_tasks.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    error_details = Column(JSON, default=dict)
    latency_ms = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)


# --- Tool Registry & Execution Models ---

class ResearchTool(Base):
    __tablename__ = "research_tools"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(50), nullable=False)
    risk_level = Column(String(50), default=ToolRiskLevel.LOW.value, nullable=False)
    description = Column(Text, nullable=True)
    parameters_schema = Column(JSON, default=dict)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchToolExecution(Base):
    __tablename__ = "research_tool_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("research_tasks.id"), nullable=True, index=True)
    tool_name = Column(String(100), nullable=False)
    risk_level = Column(String(50), nullable=False)
    input_parameters = Column(JSON, default=dict)
    output_result = Column(JSON, default=dict)
    is_success = Column(Boolean, default=True, nullable=False)
    latency_ms = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Agent Models ---

class ResearchAgent(Base):
    __tablename__ = "research_agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, unique=True)
    role_description = Column(Text, nullable=False)
    default_tools = Column(JSON, default=list)
    max_iterations = Column(Integer, default=5, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchAgentVersion(Base):
    __tablename__ = "research_agent_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), ForeignKey("research_agents.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    config_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchAgentExecution(Base):
    __tablename__ = "research_agent_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    status = Column(String(50), default="RUNNING", nullable=False)
    iterations_used = Column(Integer, default=0, nullable=False)
    findings_produced = Column(Integer, default=0, nullable=False)
    execution_summary = Column(JSON, default=dict)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)


# --- Findings & Evidence Models ---

class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    task_id = Column(String(36), ForeignKey("research_tasks.id"), nullable=True, index=True)
    agent_name = Column(String(100), nullable=False)
    finding_type = Column(String(50), nullable=False)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=True)
    entity_name = Column(String(255), nullable=True)
    confidence_score = Column(Float, default=0.5, nullable=False)
    evidence_snippet = Column(Text, nullable=True)
    raw_data = Column(JSON, default=dict)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchFindingEvidence(Base):
    __tablename__ = "research_finding_evidences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id = Column(String(36), ForeignKey("research_findings.id"), nullable=False, index=True)
    source_url = Column(String(1024), nullable=False)
    source_domain = Column(String(255), nullable=False)
    source_type = Column(String(50), default="PUBLIC_WEB", nullable=False)
    excerpt = Column(Text, nullable=True)
    corroborated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Gaps & Decisions Models ---

class ResearchGap(Base):
    __tablename__ = "autonomous_research_gaps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_name = Column(String(255), nullable=True)
    missing_attribute = Column(String(100), nullable=False)
    priority = Column(String(50), default="MEDIUM", nullable=False)
    status = Column(String(50), default="IDENTIFIED", nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchGapAttempt(Base):
    __tablename__ = "research_gap_attempts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    gap_id = Column(String(36), ForeignKey("autonomous_research_gaps.id"), nullable=False, index=True)
    task_id = Column(String(36), nullable=True)
    strategy_used = Column(String(100), nullable=False)
    outcome = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchDecision(Base):
    __tablename__ = "research_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    decision_type = Column(String(100), nullable=False)
    context = Column(JSON, default=dict)
    rationale = Column(Text, nullable=False)
    chosen_action = Column(String(255), nullable=False)
    confidence_score = Column(Float, default=0.5, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchDecisionEvidence(Base):
    __tablename__ = "research_decision_evidences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(String(36), ForeignKey("research_decisions.id"), nullable=False, index=True)
    finding_id = Column(String(36), ForeignKey("research_findings.id"), nullable=False, index=True)
    weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Conflicts, Budgets & Dead Letter Queue Models ---

class AgentConflict(Base):
    __tablename__ = "agent_conflicts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    agent_a = Column(String(100), nullable=False)
    agent_b = Column(String(100), nullable=False)
    conflict_type = Column(String(100), nullable=False)
    entity_name = Column(String(255), nullable=True)
    claim_a = Column(JSON, default=dict)
    claim_b = Column(JSON, default=dict)
    resolution_status = Column(String(50), default="OPEN", nullable=False)
    resolution_details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchBudget(Base):
    __tablename__ = "research_budgets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=True, index=True)
    max_tokens = Column(Integer, default=100000, nullable=False)
    max_pages = Column(Integer, default=25, nullable=False)
    max_tool_calls = Column(Integer, default=50, nullable=False)
    max_runtime_seconds = Column(Integer, default=300, nullable=False)
    max_cost_usd = Column(Float, default=10.0, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    pages_used = Column(Integer, default=0, nullable=False)
    tool_calls_used = Column(Integer, default=0, nullable=False)
    runtime_seconds_used = Column(Integer, default=0, nullable=False)
    cost_usd_used = Column(Float, default=0.0, nullable=False)
    is_exceeded = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchCostEvent(Base):
    __tablename__ = "autonomous_cost_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    units_consumed = Column(Integer, default=1, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchDeadLetter(Base):
    __tablename__ = "research_dead_letters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    task_id = Column(String(36), nullable=True, index=True)
    failure_reason = Column(Text, nullable=False)
    payload = Column(JSON, default=dict)
    stack_trace = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    resolution_status = Column(String(50), default="PENDING", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchEscalation(Base):
    __tablename__ = "research_escalations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    task_id = Column(String(36), nullable=True, index=True)
    escalation_type = Column(String(100), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(50), default="OPEN", nullable=False)
    reviewer_id = Column(String(36), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = Column(DateTime, nullable=True)


# --- Reports, Scores & Simulations ---

class ResearchReport(Base):
    __tablename__ = "research_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    findings_summary = Column(JSON, default=dict)
    completeness_score = Column(Float, default=0.0, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    gaps_unresolved = Column(JSON, default=list)
    report_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchReportVersion(Base):
    __tablename__ = "research_report_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(String(36), ForeignKey("research_reports.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    content_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchCompleteness(Base):
    __tablename__ = "research_completeness_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_name = Column(String(255), nullable=True)
    completeness_pct = Column(Float, default=0.0, nullable=False)
    missing_fields = Column(JSON, default=list)
    score_breakdown = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchConfidence(Base):
    __tablename__ = "research_confidence_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    overall_confidence = Column(Float, default=0.0, nullable=False)
    corroboration_ratio = Column(Float, default=0.0, nullable=False)
    source_diversity_score = Column(Float, default=0.0, nullable=False)
    conflicting_signals_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ResearchSimulation(Base):
    __tablename__ = "research_simulations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("research_plans.id"), nullable=False, index=True)
    estimated_duration_sec = Column(Integer, default=60, nullable=False)
    estimated_tool_calls = Column(Integer, default=10, nullable=False)
    estimated_cost_usd = Column(Float, default=0.5, nullable=False)
    risk_assessment = Column(JSON, default=dict)
    potential_bottlenecks = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# --- Autonomy Events & Auditing ---

class AutonomyEvent(Base):
    __tablename__ = "autonomy_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(36), ForeignKey("autonomous_research_runs.id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AutonomyAuditEvent(Base):
    __tablename__ = "autonomy_audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    actor_id = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(String(36), nullable=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
