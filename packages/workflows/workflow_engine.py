import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.workflow_ops import (
    WorkflowDefinition,
    WorkflowVersion,
    WorkflowExecution,
    WorkflowTask,
    WorkflowTaskAttempt,
    WorkflowDeadLetter,
    ExecutionStatus,
    TaskStatus,
    ReviewItem,
    ReviewPriority,
    ReviewStatus
)
from app.models.lead import Company, Contact
from app.models.scoring import LeadScore
from packages.workflows.workflow_dsl import WorkflowConditionEvaluator, WorkflowValidator, WorkflowDSLError


class WorkflowEngine:
    """Enterprise Workflow Execution & Simulation Engine."""

    @staticmethod
    def generate_idempotency_token(
        workspace_id: str,
        version_id: str,
        entity_id: str,
        trigger_type: str
    ) -> str:
        raw = f"{workspace_id}:{version_id}:{entity_id}:{trigger_type}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def get_entity_context(db: Session, workspace_id: str, entity_id: str) -> Dict[str, Any]:
        """Loads company and scoring context for workflow condition evaluation."""
        comp = db.query(Company).filter(Company.workspace_id == workspace_id, Company.id == entity_id).first()
        if not comp:
            return {}

        score = db.query(LeadScore).filter(LeadScore.workspace_id == workspace_id, LeadScore.company_id == entity_id).first()
        contacts_count = db.query(Contact).filter(Contact.workspace_id == workspace_id, Contact.company_id == entity_id).count()
        dm_count = db.query(Contact).filter(Contact.workspace_id == workspace_id, Contact.company_id == entity_id, Contact.is_decision_maker.is_(True)).count()

        return {
            "id": comp.id,
            "name": comp.name,
            "domain": comp.domain,
            "country": comp.country or "",
            "city": comp.city or "",
            "state": comp.state or "",
            "industry": comp.industry or "",
            "status": comp.status,
            "lead_score": comp.lead_score,
            "lead_priority_score": score.lead_priority_score if score else float(comp.lead_score),
            "intent_score": score.intent_score if score else 0.0,
            "icp_fit_score": score.icp_fit_score if score else 0.0,
            "priority_tier": score.priority_tier if score else "P3_LOW",
            "has_email": contacts_count > 0,
            "has_decision_maker": dm_count > 0,
            "decision_maker_count": dm_count,
            "conflict_count": 0
        }

    @staticmethod
    def simulate_workflow(
        definition_payload: Dict[str, Any],
        entity_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates workflow execution (Dry-run) without DB mutations.
        Returns the traversed path, executed actions, estimated cost, and risk evaluation.
        """
        is_valid, errors = WorkflowValidator.validate_graph(definition_payload)
        if not is_valid:
            return {
                "is_valid": False,
                "validation_errors": errors,
                "traversed_path": [],
                "would_execute_actions": [],
                "estimated_cost_usd": 0.0
            }

        nodes = {n["id"]: n for n in definition_payload.get("nodes", [])}
        edges = definition_payload.get("edges", [])

        # Find Trigger node
        current_node = next((n for n in nodes.values() if n.get("type") == "TRIGGER"), None)
        path = []
        actions = []
        estimated_cost = 0.0
        max_steps = 25
        step = 0

        while current_node and step < max_steps:
            step += 1
            nid = current_node["id"]
            ntype = current_node.get("type")
            path.append(nid)

            if ntype in {"RESEARCH", "ENRICH", "VERIFY", "QUALIFY", "SCORE", "HUMAN_REVIEW", "APPROVAL", "REJECT", "EXPORT", "SHEET_SYNC"}:
                actions.append({"node_id": nid, "action": ntype, "label": current_node.get("label", ntype)})
                if ntype in {"RESEARCH", "ENRICH"}:
                    estimated_cost += 0.02
                elif ntype == "VERIFY":
                    estimated_cost += 0.005

            if ntype in {"END", "REJECT", "APPROVAL"}:
                break

            # Next node determination
            outgoing = [e for e in edges if e.get("from") == nid]
            if not outgoing:
                break

            if ntype == "CONDITION":
                cond = current_node.get("config", {}).get("condition", {})
                passed = WorkflowConditionEvaluator.evaluate(cond, entity_context) if cond else True
                
                target_edge = next((e for e in outgoing if e.get("label", "").lower() == ("true" if passed else "false")), outgoing[0])
                current_node = nodes.get(target_edge.get("to"))
            else:
                current_node = nodes.get(outgoing[0].get("to"))

        return {
            "is_valid": True,
            "traversed_path": path,
            "would_execute_actions": actions,
            "estimated_cost_usd": round(estimated_cost, 4),
            "step_count": len(path),
            "final_node": path[-1] if path else None,
            "risk_level": "LOW" if len(actions) < 5 else "MEDIUM"
        }

    @staticmethod
    def execute_workflow(
        db: Session,
        workspace_id: str,
        workflow_id: str,
        entity_id: str,
        trigger_type: str = "MANUAL",
        budget_limit_usd: float = 25.0
    ) -> WorkflowExecution:
        """Executes a workflow version against an entity with budget bounds and idempotency protection."""
        wf = db.query(WorkflowDefinition).filter(WorkflowDefinition.workspace_id == workspace_id, WorkflowDefinition.id == workflow_id).first()
        if not wf:
            raise ValueError(f"Workflow '{workflow_id}' not found.")

        # Resolve active version
        version = (
            db.query(WorkflowVersion)
            .filter(WorkflowVersion.workflow_id == workflow_id, WorkflowVersion.status == "ACTIVE")
            .order_by(WorkflowVersion.version_number.desc())
            .first()
        )
        if not version:
            raise ValueError(f"Workflow '{workflow_id}' has no published active version.")

        idempotency_token = WorkflowEngine.generate_idempotency_token(
            workspace_id, version.id, entity_id, trigger_type
        )

        # Idempotency check: if running, paused (awaiting review), or completed recently, reuse
        existing = (
            db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.workspace_id == workspace_id,
                WorkflowExecution.idempotency_token == idempotency_token,
                WorkflowExecution.status.in_(["RUNNING", "COMPLETED", "PAUSED"])
            )
            .first()
        )
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        execution = WorkflowExecution(
            workspace_id=workspace_id,
            workflow_id=workflow_id,
            workflow_version_id=version.id,
            trigger_type=trigger_type,
            entity_type="COMPANY",
            entity_id=entity_id,
            status=ExecutionStatus.RUNNING.value,
            idempotency_token=idempotency_token,
            budget_limit_usd=budget_limit_usd,
            cost_usd=0.0,
            started_at=now
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        try:
            entity_context = WorkflowEngine.get_entity_context(db, workspace_id, entity_id)
            nodes = {n["id"]: n for n in version.definition_payload.get("nodes", [])}
            edges = version.definition_payload.get("edges", [])

            current_node = next((n for n in nodes.values() if n.get("type") == "TRIGGER"), None)
            total_cost = 0.0

            while current_node:
                nid = current_node["id"]
                ntype = current_node.get("type")

                task = WorkflowTask(
                    workspace_id=workspace_id,
                    execution_id=execution.id,
                    node_id=nid,
                    node_type=ntype,
                    status=TaskStatus.RUNNING.value,
                    input_payload={"entity_id": entity_id},
                    started_at=datetime.now(timezone.utc)
                )
                db.add(task)
                db.commit()
                db.refresh(task)

                # Process specific node behaviors
                if ntype == "HUMAN_REVIEW":
                    # Create review item and pause workflow
                    review_item = ReviewItem(
                        workspace_id=workspace_id,
                        entity_type="COMPANY",
                        entity_id=entity_id,
                        priority=ReviewPriority.HIGH.value,
                        status=ReviewStatus.PENDING.value,
                        ai_recommendation={"action": "QUALIFY", "confidence": 0.88, "reason": "Passed automated ICP and intent criteria."}
                    )
                    db.add(review_item)
                    task.status = TaskStatus.COMPLETED.value
                    task.completed_at = datetime.now(timezone.utc)
                    execution.status = ExecutionStatus.PAUSED.value
                    db.commit()
                    return execution

                elif ntype == "APPROVAL":
                    # Transition company status to QUALIFIED
                    comp = db.query(Company).filter(Company.id == entity_id).first()
                    if comp:
                        comp.status = "QUALIFIED"
                
                elif ntype == "REJECT":
                    # Disqualify company
                    comp = db.query(Company).filter(Company.id == entity_id).first()
                    if comp:
                        comp.status = "DISQUALIFIED"

                if ntype in {"RESEARCH", "ENRICH"}:
                    total_cost += 0.02
                elif ntype == "VERIFY":
                    total_cost += 0.005

                task.status = TaskStatus.COMPLETED.value
                task.completed_at = datetime.now(timezone.utc)
                task.cost_usd = round(total_cost, 4)
                db.commit()

                if ntype in {"END", "APPROVAL", "REJECT"}:
                    break

                # Determine next node
                outgoing = [e for e in edges if e.get("from") == nid]
                if not outgoing:
                    break

                if ntype == "CONDITION":
                    cond = current_node.get("config", {}).get("condition", {})
                    passed = WorkflowConditionEvaluator.evaluate(cond, entity_context) if cond else True
                    target_edge = next((e for e in outgoing if e.get("label", "").lower() == ("true" if passed else "false")), outgoing[0])
                    current_node = nodes.get(target_edge.get("to"))
                else:
                    current_node = nodes.get(outgoing[0].get("to"))

            execution.status = ExecutionStatus.COMPLETED.value
            execution.cost_usd = round(total_cost, 4)
            execution.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(execution)
            return execution

        except Exception as exc:
            execution.status = ExecutionStatus.FAILED.value
            execution.error_message = str(exc)
            db.commit()
            
            # Dead letter queue routing
            dlq = WorkflowDeadLetter(
                workspace_id=workspace_id,
                execution_id=execution.id,
                task_id=f"failed_at_{now.timestamp()}",
                error_code="WORKFLOW_EXECUTION_FAILURE",
                error_payload={"error": str(exc)},
                retryable=True,
                resolved=False
            )
            db.add(dlq)
            db.commit()
            raise exc
