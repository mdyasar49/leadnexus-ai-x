import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


class ResearchReportEngine:
    """
    Synthesizes autonomous research findings into enterprise intelligence reports,
    computing multidimensional completeness scores, evidence-based confidence scores,
    and gap analysis.
    """

    COMPLETENESS_WEIGHTS = {
        "FIRMOGRAPHICS": 0.20,
        "TECH_STACK": 0.25,
        "ODOO_INTELLIGENCE": 0.25,
        "DECISION_MAKERS": 0.15,
        "CONTACT_VERIFICATION": 0.15,
    }

    @classmethod
    def calculate_completeness_score(
        cls,
        findings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculates research completeness percentage and breakdown across key dimensions.
        """
        present_types = {f.get("finding_type") for f in findings}
        breakdown = {}
        total_score = 0.0

        for dim, weight in cls.COMPLETENESS_WEIGHTS.items():
            is_present = dim in present_types
            breakdown[dim] = {
                "weight": weight,
                "achieved": weight if is_present else 0.0,
                "status": "COMPLETED" if is_present else "MISSING",
            }
            if is_present:
                total_score += weight

        completeness_pct = round(total_score * 100.0, 1)
        missing_fields = [dim for dim, info in breakdown.items() if info["status"] == "MISSING"]

        return {
            "completeness_score": round(total_score, 3),
            "completeness_pct": completeness_pct,
            "missing_fields": missing_fields,
            "breakdown": breakdown,
        }

    @classmethod
    def calculate_confidence_score(
        cls,
        findings: List[Dict[str, Any]],
        conflicts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Computes overall confidence score based on source diversity, corroboration,
        and absence of conflicting claims.
        """
        if not findings:
            return {
                "overall_confidence": 0.0,
                "corroboration_ratio": 0.0,
                "source_diversity_score": 0.0,
                "conflict_penalty": 0.0,
            }

        # Collect unique domains and corroboration
        all_domains: Set[str] = set()
        corroborated_findings = 0

        for f in findings:
            sources = f.get("source_urls") or []
            domains = set()
            for s in sources:
                if "://" in s:
                    domain = s.split("://")[1].split("/")[0].lower()
                    domains.add(domain)
                    all_domains.add(domain)
            if len(domains) >= 2 or f.get("confidence_score", 0) >= 0.95:
                corroborated_findings += 1

        corroboration_ratio = round(corroborated_findings / max(1, len(findings)), 2)
        source_diversity_score = min(1.0, round(len(all_domains) / 3.0, 2))

        # Conflict penalty
        conflict_list = conflicts or []
        open_conflicts = [c for c in conflict_list if c.get("resolution_status") == "OPEN"]
        conflict_penalty = min(0.3, len(open_conflicts) * 0.15)

        # Base confidence is mean finding confidence
        avg_base_conf = sum(f.get("confidence_score", 0.5) for f in findings) / len(findings)
        overall = max(0.05, min(0.99, (avg_base_conf * 0.6) + (corroboration_ratio * 0.25) + (source_diversity_score * 0.15) - conflict_penalty))

        return {
            "overall_confidence": round(overall, 3),
            "corroboration_ratio": corroboration_ratio,
            "source_diversity_score": source_diversity_score,
            "conflict_penalty": conflict_penalty,
            "conflicting_signals_count": len(open_conflicts),
        }

    @classmethod
    def generate_research_report(
        cls,
        workspace_id: str,
        run_id: str,
        company_name: str,
        findings: List[Dict[str, Any]],
        conflicts: Optional[List[Dict[str, Any]]] = None,
        unresolved_gaps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compiles findings, completeness metrics, confidence ratings, and gap analysis
        into a finalized ResearchReport document.
        """
        comp_metrics = cls.calculate_completeness_score(findings)
        conf_metrics = cls.calculate_confidence_score(findings, conflicts)

        # Build executive summary
        summary_lines = [
            f"Autonomous Research Intelligence Report for {company_name}.",
            f"Overall Research Completeness: {comp_metrics['completeness_pct']}% | Confidence: {conf_metrics['overall_confidence'] * 100:.1f}%.",
        ]

        tech_finding = next((f for f in findings if f.get("finding_type") == "TECH_STACK"), None)
        odoo_finding = next((f for f in findings if f.get("finding_type") == "ODOO_INTELLIGENCE"), None)
        dm_finding = next((f for f in findings if f.get("finding_type") == "DECISION_MAKERS"), None)

        if odoo_finding:
            v = odoo_finding.get("data", {}).get("version", "Unknown")
            ed = odoo_finding.get("data", {}).get("edition", "Unknown")
            summary_lines.append(f"Confirmed Odoo Deployment: Version {v} ({ed} Edition).")
        elif tech_finding:
            summary_lines.append(f"Primary Tech Stack: {', '.join(tech_finding.get('data', {}).get('detected_stack', []))}.")

        if dm_finding:
            dms = dm_finding.get("data", {}).get("decision_makers", [])
            summary_lines.append(f"Key Decision Makers: {len(dms)} identified.")

        summary_text = " ".join(summary_lines)

        report_id = f"rep_{uuid.uuid4().hex[:12]}"
        return {
            "id": report_id,
            "workspace_id": workspace_id,
            "run_id": run_id,
            "title": f"Autonomous Lead Intelligence: {company_name}",
            "summary": summary_text,
            "findings_summary": {f.get("finding_type"): f.get("data") for f in findings},
            "completeness_score": comp_metrics["completeness_score"],
            "completeness_pct": comp_metrics["completeness_pct"],
            "confidence_score": conf_metrics["overall_confidence"],
            "confidence_metrics": conf_metrics,
            "gaps_unresolved": unresolved_gaps or comp_metrics["missing_fields"],
            "report_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def diff_report_versions(
        cls,
        v1: Dict[str, Any],
        v2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compares two report versions and highlights changes in metrics and data."""
        return {
            "completeness_delta": round(v2.get("completeness_score", 0.0) - v1.get("completeness_score", 0.0), 3),
            "confidence_delta": round(v2.get("confidence_score", 0.0) - v1.get("confidence_score", 0.0), 3),
            "added_sections": list(set(v2.get("findings_summary", {}).keys()) - set(v1.get("findings_summary", {}).keys())),
            "removed_sections": list(set(v1.get("findings_summary", {}).keys()) - set(v2.get("findings_summary", {}).keys())),
            "v1_version": v1.get("report_version", 1),
            "v2_version": v2.get("report_version", 2),
        }
