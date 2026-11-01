"""
LeadNexus AI X - Phase 43: Autonomous Orchestration & Long-Running Mission Engine Models
Provides persistent state, DAG execution tracking, multi-step checkpointing,
and human-in-the-loop governance for durable autonomous missions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class MissionRecord(Base):
    """Represents a long-running, multi-step autonomous research mission."""
    __tablename__ = "mission_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    goal = Column(Text, nullable=False)
    status = Column(String(32), default="CREATED", index=True)  # CREATED, RUNNING, PAUSED, AWAITING_HUMAN_REVIEW, COMPLETED, FAILED, CANCELLED
    priority = Column(String(16), default="NORMAL", index=True)  # LOW, NORMAL, HIGH, CRITICAL
    total_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)
    failed_steps = Column(Integer, default=0)
    current_checkpoint_id = Column(String(36), nullable=True)
    configuration = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    steps = relationship("MissionStepRecord", back_populates="mission", cascade="all, delete-orphan")
    checkpoints = relationship("MissionCheckpoint", back_populates="mission", cascade="all, delete-orphan")
    reviews = relationship("MissionHumanReviewItem", back_populates="mission", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "goal": self.goal,
            "status": self.status,
            "priority": self.priority,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "current_checkpoint_id": self.current_checkpoint_id,
            "configuration": self.configuration or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MissionStepRecord(Base):
    """Individual task node in a mission DAG."""
    __tablename__ = "mission_step_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("mission_records.id", ondelete="CASCADE"), nullable=False, index=True)
    step_name = Column(String(255), nullable=False)
    agent_type = Column(String(64), nullable=False)  # ResearchAgent, CompanyAgent, ReviewAgent, etc.
    status = Column(String(32), default="PENDING", index=True)  # PENDING, READY, RUNNING, COMPLETED, FAILED, BLOCKED, AWAITING_REVIEW
    dependencies = Column(JSON, default=list)  # list of prerequisite step IDs
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    input_payload = Column(JSON, default=dict)
    output_payload = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    mission = relationship("MissionRecord", back_populates="steps")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "step_name": self.step_name,
            "agent_type": self.agent_type,
            "status": self.status,
            "dependencies": self.dependencies or [],
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "input_payload": self.input_payload or {},
            "output_payload": self.output_payload or {},
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MissionCheckpoint(Base):
    """Durable state snapshot enabling recovery, rollback, and resume."""
    __tablename__ = "mission_checkpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("mission_records.id", ondelete="CASCADE"), nullable=False, index=True)
    checkpoint_number = Column(Integer, default=1)
    state_snapshot = Column(JSON, nullable=False)
    reason = Column(String(64), default="PERIODIC_AUTOSAVE")  # STEP_COMPLETION, PAUSE_REQUESTED, PERIODIC_AUTOSAVE, CRASH_RECOVERY
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    mission = relationship("MissionRecord", back_populates="checkpoints")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "checkpoint_number": self.checkpoint_number,
            "state_snapshot": self.state_snapshot or {},
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MissionHumanReviewItem(Base):
    """Human-in-the-loop review item for mission decision verification."""
    __tablename__ = "mission_human_review_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mission_id = Column(String(36), ForeignKey("mission_records.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), nullable=False, index=True)
    review_title = Column(String(255), nullable=False)
    candidate_data = Column(JSON, default=dict)
    decision = Column(String(32), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED, MODIFIED
    reviewer_notes = Column(Text, nullable=True)
    decided_by = Column(String(255), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    mission = relationship("MissionRecord", back_populates="reviews")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "step_id": self.step_id,
            "review_title": self.review_title,
            "candidate_data": self.candidate_data or {},
            "decision": self.decision,
            "reviewer_notes": self.reviewer_notes,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

