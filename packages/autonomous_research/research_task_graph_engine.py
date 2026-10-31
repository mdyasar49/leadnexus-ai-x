import collections
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.autonomous_research import ResearchMode, TaskType


class CyclicDependencyError(ValueError):
    """Raised when a research plan graph contains cyclic dependencies."""
    pass


class ResearchTaskGraphEngine:
    """
    Manages Directed Acyclic Graphs (DAG) for autonomous research plans,
    validating dependency integrity, detecting cycles, computing topological order,
    and calculating ready parallel execution waves.
    """

    @classmethod
    def validate_dag(cls, steps: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Validates that steps form a valid Directed Acyclic Graph without cycles
        or references to non-existent dependencies.
        Returns (is_valid, error_message).
        """
        step_ids = {s["id"] for s in steps}
        adj: Dict[str, List[str]] = {s["id"]: [] for s in steps}
        in_degree: Dict[str, int] = {s["id"]: 0 for s in steps}

        for s in steps:
            deps = s.get("depends_on") or []
            for dep in deps:
                if dep not in step_ids:
                    return False, f"Step '{s.get('title', s['id'])}' depends on unknown step '{dep}'."
                adj[dep].append(s["id"])
                in_degree[s["id"]] += 1

        # Kahn's Algorithm to check for cycles
        queue = collections.deque([sid for sid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(steps):
            return False, "Cycle detected in research plan dependency graph."

        return True, None

    @classmethod
    def get_topological_order(cls, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Returns steps sorted in topological order. Raises CyclicDependencyError if cyclic.
        """
        is_valid, err = cls.validate_dag(steps)
        if not is_valid:
            raise CyclicDependencyError(err)

        step_map = {s["id"]: s for s in steps}
        adj: Dict[str, List[str]] = {s["id"]: [] for s in steps}
        in_degree: Dict[str, int] = {s["id"]: 0 for s in steps}

        for s in steps:
            for dep in (s.get("depends_on") or []):
                adj[dep].append(s["id"])
                in_degree[s["id"]] += 1

        queue = collections.deque([sid for sid, deg in in_degree.items() if deg == 0])
        ordered = []

        while queue:
            curr = queue.popleft()
            ordered.append(step_map[curr])
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return ordered

    @classmethod
    def get_ready_steps(
        cls,
        steps: List[Dict[str, Any]],
        completed_step_ids: Set[str],
        running_step_ids: Set[str],
    ) -> List[Dict[str, Any]]:
        """
        Returns all steps whose dependencies have fully completed and are not yet running/completed.
        """
        ready = []
        for s in steps:
            sid = s["id"]
            if sid in completed_step_ids or sid in running_step_ids:
                continue
            deps = set(s.get("depends_on") or [])
            if deps.issubset(completed_step_ids):
                ready.append(s)
        return ready

    @classmethod
    def generate_default_plan(
        cls,
        company_name: str,
        domain: Optional[str] = None,
        mode: str = ResearchMode.STANDARD.value,
    ) -> List[Dict[str, Any]]:
        """
        Constructs a structured, dependency-ordered plan graph suited for the chosen research mode.
        """
        clean_name = company_name.strip()
        clean_domain = domain.strip().lower() if domain else ""

        # Step 1: Profiling
        s1_id = f"step_{uuid.uuid4().hex[:8]}"
        s1 = {
            "id": s1_id,
            "step_order": 1,
            "title": f"Profile firmographics and web properties for {clean_name}",
            "task_type": TaskType.COMPANY_PROFILING.value,
            "agent_name": "CompanyResearchAgent",
            "tool_name": "company_website_crawler",
            "parameters": {"company_name": clean_name, "domain": clean_domain},
            "depends_on": [],
        }

        # Step 2: Tech Detection (depends on S1)
        s2_id = f"step_{uuid.uuid4().hex[:8]}"
        s2 = {
            "id": s2_id,
            "step_order": 2,
            "title": f"Detect ERP & technology stack for {clean_name}",
            "task_type": TaskType.TECHNOLOGY_DETECTION.value,
            "agent_name": "TechnologyResearchAgent",
            "tool_name": "company_website_crawler",
            "parameters": {"domain": clean_domain, "target_technologies": ["Odoo", "PostgreSQL", "Python"]},
            "depends_on": [s1_id],
        }

        # Step 3: Odoo Ecosystem Verification (depends on S2)
        s3_id = f"step_{uuid.uuid4().hex[:8]}"
        s3 = {
            "id": s3_id,
            "step_order": 3,
            "title": f"Verify Odoo modules, version and GitHub commits for {clean_name}",
            "task_type": TaskType.ODOO_VERIFICATION.value,
            "agent_name": "OdooResearchAgent",
            "tool_name": "github_repository_analyzer",
            "parameters": {"company_name": clean_name, "domain": clean_domain},
            "depends_on": [s2_id],
        }

        # Step 4: Intent Discovery (depends on S1, runs in parallel with S2/S3)
        s4_id = f"step_{uuid.uuid4().hex[:8]}"
        s4 = {
            "id": s4_id,
            "step_order": 4,
            "title": f"Discover hiring & ERP migration intent signals for {clean_name}",
            "task_type": TaskType.INTENT_DISCOVERY.value,
            "agent_name": "IntentResearchAgent",
            "tool_name": "job_posting_detector",
            "parameters": {"company_name": clean_name, "keywords": ["Odoo", "ERP developer", "Odoo implementation"]},
            "depends_on": [s1_id],
        }

        # Step 5: Decision Maker Search (depends on S1)
        s5_id = f"step_{uuid.uuid4().hex[:8]}"
        s5 = {
            "id": s5_id,
            "step_order": 5,
            "title": f"Identify IT & Operations decision makers for {clean_name}",
            "task_type": TaskType.DECISION_MAKER_SEARCH.value,
            "agent_name": "PersonResearchAgent",
            "tool_name": "search_engine_query",
            "parameters": {"company_name": clean_name, "roles": ["CTO", "Head of IT", "Operations Director"]},
            "depends_on": [s1_id],
        }

        # Step 6: Contact & MX Verification (depends on S5)
        s6_id = f"step_{uuid.uuid4().hex[:8]}"
        s6 = {
            "id": s6_id,
            "step_order": 6,
            "title": f"Verify domain MX and contact patterns for {clean_name}",
            "task_type": TaskType.CONTACT_VERIFICATION.value,
            "agent_name": "ContactResearchAgent",
            "tool_name": "dns_mx_spf_checker",
            "parameters": {"domain": clean_domain},
            "depends_on": [s5_id],
        }

        # Step 7: Evidence Validation (depends on S3, S4)
        s7_id = f"step_{uuid.uuid4().hex[:8]}"
        s7 = {
            "id": s7_id,
            "step_order": 7,
            "title": f"Validate and corroborate evidence claims for {clean_name}",
            "task_type": TaskType.EVIDENCE_VALIDATION.value,
            "agent_name": "EvidenceValidationAgent",
            "tool_name": "search_engine_query",
            "parameters": {"min_independent_sources": 2},
            "depends_on": [s3_id, s4_id],
        }

        # Step 8: Quality & Synthesis Audit (depends on S6, S7)
        s8_id = f"step_{uuid.uuid4().hex[:8]}"
        s8 = {
            "id": s8_id,
            "step_order": 8,
            "title": f"Audit completeness, confidence and finalize report for {clean_name}",
            "task_type": TaskType.DATA_QUALITY_AUDIT.value,
            "agent_name": "DataQualityAgent",
            "tool_name": "semantic_ontology_classifier",
            "parameters": {},
            "depends_on": [s6_id, s7_id],
        }

        if mode.upper() == ResearchMode.QUICK.value:
            # Quick mode: S1 (profile), S2 (tech), S6 (domain verification)
            s6_quick = dict(s6)
            s6_quick["depends_on"] = [s1_id]
            return [s1, s2, s6_quick]

        if mode.upper() in (ResearchMode.DEEP.value, ResearchMode.FORENSIC.value):
            # Add deep forensic step
            s9_id = f"step_{uuid.uuid4().hex[:8]}"
            s9 = {
                "id": s9_id,
                "step_order": 9,
                "title": f"Forensic cross-source contradiction resolution for {clean_name}",
                "task_type": TaskType.EVIDENCE_VALIDATION.value,
                "agent_name": "EvidenceValidationAgent",
                "tool_name": "deep_forensic_evaluator",
                "parameters": {"strict_corroboration": True},
                "depends_on": [s8_id],
            }
            return [s1, s2, s3, s4, s5, s6, s7, s8, s9]

        return [s1, s2, s3, s4, s5, s6, s7, s8]

    @classmethod
    def inject_gap_remediation_step(
        cls,
        existing_steps: List[Dict[str, Any]],
        gap_attribute: str,
        entity_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically appends a gap remediation step to resolve missing data without violating DAG.
        """
        new_step_id = f"step_remedy_{uuid.uuid4().hex[:8]}"
        last_step_id = existing_steps[-1]["id"] if existing_steps else None

        remedy_step = {
            "id": new_step_id,
            "step_order": len(existing_steps) + 1,
            "title": f"Remediate missing {gap_attribute} for {entity_name}",
            "task_type": TaskType.GAP_REMEDIATION.value,
            "agent_name": "TechnologyResearchAgent" if "tech" in gap_attribute.lower() or "odoo" in gap_attribute.lower() else "CompanyResearchAgent",
            "tool_name": "search_engine_query",
            "parameters": {"target_gap": gap_attribute, "entity_name": entity_name},
            "depends_on": [last_step_id] if last_step_id else [],
        }

        updated_steps = list(existing_steps) + [remedy_step]
        is_valid, err = cls.validate_dag(updated_steps)
        if not is_valid:
            raise CyclicDependencyError(f"Failed to inject gap remediation: {err}")
        return updated_steps

