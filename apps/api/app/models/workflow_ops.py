from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkflowType(str, Enum):
    RESEARCH_WORKFLOW = "RESEARCH_WORKFLOW"
    ENRICHMENT_WORKFLOW = "ENRICHMENT_WORKFLOW"
    VERIFICATION_WORKFLOW = "VERIFICATION_WORKFLOW"
    QUALIFICATION_WORKFLOW = "QUALIFICATION_WORKFLOW"
    REVIEW_WORKFLOW = "REVIEW_WORKFLOW"
    QUALITY_WORKFLOW = "QUALITY_WORKFLOW"
    CONFLICT_WORKFLOW = "CONFLICT_WORKFLOW"
    STALE_DATA_WORKFLOW = "STALE_DATA_WORKFLOW"
    EXPORT_WORKFLOW = "EXPORT_WORKFLOW"
    SHEET_SYNC_WORKFLOW = "SHEET_SYNC_WORKFLOW"
    CAMPAIGN_WORKFLOW = "CAMPAIGN_WORKFLOW"


class WorkflowVersionStatus(str, Enum):
    DRAFT = "DRAFT"
    TESTING = "TESTING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    RETIRED = "RETIRED"


class ExecutionStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class NodeType(str, Enum):
    TRIGGER = "TRIGGER"
    CONDITION = "CONDITION"
    RESEARCH = "RESEARCH"
    ENRICH = "ENRICH"
    VERIFY = "VERIFY"
    QUALIFY = "QUALIFY"
    SCORE = "SCORE"
    REFRESH = "REFRESH"
    WAIT = "WAIT"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    APPROVAL = "APPROVAL"
    REJECT = "REJECT"
    NOTIFY = "NOTIFY"
    EXPORT = "EXPORT"
    SHEET_SYNC = "SHEET_SYNC"
    CREATE_RESEARCH_GAP = "CREATE_RESEARCH_GAP"
    RESOLVE_CONFLICT = "RESOLVE_CONFLICT"
    END = "END"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    DEFERRED = "DEFERRED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ReviewPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


class ConflictSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FeedbackCategory(str, Enum):
    AI_CORRECT = "AI_CORRECT"
    AI_INCORRECT = "AI_INCORRECT"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    WRONG_ENTITY = "WRONG_ENTITY"
    STALE_DATA = "STALE_DATA"
    WRONG_ROLE = "WRONG_ROLE"
    WRONG_CONTACT = "WRONG_CONTACT"
    DUPLICATE = "DUPLICATE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


class WorkflowDefinition(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_definitions"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    workflow_type = Column(String(50), default="RESEARCH_WORKFLOW", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    current_version_id = Column(String(36), nullable=True)
    tags = Column(JSON, default=list, nullable=False)

    __table_args__ = (
        Index("idx_wf_def_ws_name", "workspace_id", "name"),
    )


class WorkflowVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_versions"

    workspace_id = Column(String(36), nullable=False, index=True)
    workflow_id = Column(String(36), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="DRAFT", nullable=False)  # DRAFT, ACTIVE, PAUSED, RETIRED
    
    definition_payload = Column(JSON, default=dict, nullable=False)  # nodes, edges, config
    validation_status = Column(String(50), default="VALID", nullable=False)
    published_at = Column(DateTime, nullable=True)
    created_by = Column(String(36), nullable=False)


class WorkflowExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_executions"

    workspace_id = Column(String(36), nullable=False, index=True)
    workflow_id = Column(String(36), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_version_id = Column(String(36), nullable=False, index=True)
    
    trigger_type = Column(String(50), default="MANUAL", nullable=False)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    status = Column(String(50), default="RUNNING", nullable=False, index=True)
    
    idempotency_token = Column(String(128), nullable=True, index=True)
    cost_usd = Column(Float, default=0.0, nullable=False)
    budget_limit_usd = Column(Float, default=25.0, nullable=False)
    error_message = Column(Text, nullable=True)
    
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_wf_exec_ws_entity", "workspace_id", "entity_type", "entity_id"),
    )


class WorkflowTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_tasks"

    workspace_id = Column(String(36), nullable=False, index=True)
    execution_id = Column(String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(100), nullable=False)
    node_type = Column(String(50), nullable=False)
    
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    input_payload = Column(JSON, default=dict, nullable=False)
    output_payload = Column(JSON, default=dict, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


class WorkflowTaskAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_task_attempts"

    task_id = Column(String(36), ForeignKey("workflow_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    error_details = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)


# Human-in-the-Loop Review System
class ReviewQueue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_queues"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    queue_type = Column(String(50), default="GENERAL_REVIEW", nullable=False)
    sla_minutes = Column(Integer, default=1440, nullable=False)  # 24 hours
    is_active = Column(Boolean, default=True, nullable=False)


class ReviewItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_items"

    workspace_id = Column(String(36), nullable=False, index=True)
    queue_id = Column(String(36), ForeignKey("review_queues.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type = Column(String(50), default="COMPANY", nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)
    
    priority = Column(String(50), default="NORMAL", nullable=False, index=True)
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    assigned_to_user_id = Column(String(36), nullable=True, index=True)
    
    ai_recommendation = Column(JSON, default=dict, nullable=False)
    decision = Column(String(50), nullable=True)
    decision_by_user_id = Column(String(36), nullable=True)
    decision_reason = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    
    due_at = Column(DateTime, nullable=True)
    research_attempts = Column(Integer, default=0, nullable=False)
    max_research_attempts = Column(Integer, default=3, nullable=False)

    __table_args__ = (
        Index("idx_review_ws_status", "workspace_id", "status"),
    )


class ReviewComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "review_comments"

    workspace_id = Column(String(36), nullable=False, index=True)
    review_item_id = Column(String(36), ForeignKey("review_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False)
    user_name = Column(String(255), nullable=True)
    comment_text = Column(Text, nullable=False)
    comment_type = Column(String(50), default="NOTE", nullable=False)


class HumanFeedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "human_feedbacks"

    workspace_id = Column(String(36), nullable=False, index=True)
    review_item_id = Column(String(36), nullable=True)
    entity_id = Column(String(36), nullable=False, index=True)
    
    category = Column(String(50), default="AI_CORRECT", nullable=False)
    reason = Column(Text, nullable=False)
    feedback_metadata = Column(JSON, default=dict, nullable=False)


class ConflictWorkflow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conflict_workflows"

    workspace_id = Column(String(36), nullable=False, index=True)
    field_conflict_id = Column(String(36), nullable=False, index=True)
    severity = Column(String(50), default="MEDIUM", nullable=False)
    status = Column(String(50), default="UNRESOLVED", nullable=False)
    
    assigned_to_user_id = Column(String(36), nullable=True)
    resolved_value = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class WorkflowDeadLetter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_dead_letters"

    workspace_id = Column(String(36), nullable=False, index=True)
    execution_id = Column(String(36), nullable=False, index=True)
    task_id = Column(String(36), nullable=False, index=True)
    
    error_code = Column(String(100), nullable=False)
    error_payload = Column(JSON, default=dict, nullable=False)
    retryable = Column(Boolean, default=False, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)


class WorkflowMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_metrics"

    workspace_id = Column(String(36), nullable=False, index=True)
    workflow_id = Column(String(36), nullable=False, index=True)
    
    total_executions = Column(Integer, default=0, nullable=False)
    successful_executions = Column(Integer, default=0, nullable=False)
    failed_executions = Column(Integer, default=0, nullable=False)
    avg_duration_ms = Column(Integer, default=0, nullable=False)
    total_cost_usd = Column(Float, default=0.0, nullable=False)
