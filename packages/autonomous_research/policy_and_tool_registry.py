import ipaddress
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from app.models.autonomous_research import (
    AutonomyPolicy,
    ResearchBudget,
    ToolRiskLevel,
)


class PolicyViolationError(PermissionError):
    """Raised when an autonomous action breaches autonomy boundaries or policies."""
    pass


class AutonomyPolicyValidator:
    """
    Enforces autonomy policies, risk levels, domain allow/block lists,
    budget thresholds, and strict public-web safety boundaries.
    """

    # Absolutely forbidden actions - cannot be overridden by any policy
    FORBIDDEN_TOOLS: Set[str] = {
        "raw_sql",
        "raw_shell_command",
        "filesystem_write",
        "secret_store_access",
        "outreach_sender",
        "send_email",
        "send_sms",
        "make_phone_call",
        "linkedin_auto_connect",
        "sales_pipeline_create_deal",
    }

    # SSRF / Private IP block patterns
    BLOCKED_HOST_PATTERNS = [
        re.compile(r"^localhost$", re.I),
        re.compile(r"^127\.\d+\.\d+\.\d+$"),
        re.compile(r"^10\.\d+\.\d+\.\d+$"),
        re.compile(r"^192\.168\.\d+\.\d+$"),
        re.compile(r"^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$"),
        re.compile(r"^169\.254\.\d+\.\d+$"),  # Cloud metadata IP
        re.compile(r".*\.internal$", re.I),
        re.compile(r".*\.local$", re.I),
    ]

    RISK_HIERARCHY = {
        ToolRiskLevel.LOW.value: 1,
        ToolRiskLevel.MEDIUM.value: 2,
        ToolRiskLevel.HIGH.value: 3,
        ToolRiskLevel.RESTRICTED.value: 4,
    }

    @classmethod
    def validate_tool_execution(
        cls,
        policy: Optional[AutonomyPolicy],
        tool_name: str,
        tool_risk_level: str,
        parameters: Optional[Dict[str, Any]] = None,
        budget: Optional[ResearchBudget] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a tool call is permitted under the given policy and budgets.
        Returns (is_allowed, error_reason).
        """
        # 1. Hard invariant: Forbidden tools
        if tool_name.lower() in cls.FORBIDDEN_TOOLS:
            return False, f"Tool '{tool_name}' is strictly forbidden by platform safety boundaries (NO_OUTREACH / NO_RAW_SYSTEM)."

        # 2. Hard invariant: RESTRICTED risk level is never executed automatically
        if tool_risk_level.upper() == ToolRiskLevel.RESTRICTED.value:
            return False, f"Tool '{tool_name}' has RESTRICTED risk level and cannot be executed autonomously."

        # 3. Check Budget Bounds (applies universally)
        if budget:
            if budget.is_exceeded:
                return False, "Research budget has already been exceeded."
            if budget.tool_calls_used >= budget.max_tool_calls:
                return False, f"Budget max tool calls ({budget.max_tool_calls}) reached."
            if budget.cost_usd_used >= budget.max_cost_usd:
                return False, f"Budget max cost (${budget.max_cost_usd:.2f}) reached."
            if budget.runtime_seconds_used >= budget.max_runtime_seconds:
                return False, f"Budget max runtime ({budget.max_runtime_seconds}s) reached."

        # If no policy attached, default to safe LOW-risk only
        if not policy:
            if tool_risk_level.upper() != ToolRiskLevel.LOW.value:
                return False, f"No policy specified; non-LOW risk tool '{tool_name}' rejected."
            return True, None

        # 4. Check Policy Active status
        if not policy.is_active:
            return False, "Policy is disabled."

        # 4. Check Policy Forbidden Tools
        forbidden_in_policy = [t.lower() for t in (policy.forbidden_tools or [])]
        if tool_name.lower() in forbidden_in_policy:
            return False, f"Tool '{tool_name}' is explicitly forbidden by workspace policy '{policy.name}'."

        # 5. Check Policy Allowed Tools (if allowlist is populated)
        allowed_in_policy = [t.lower() for t in (policy.allowed_tools or [])]
        if allowed_in_policy and tool_name.lower() not in allowed_in_policy:
            return False, f"Tool '{tool_name}' is not in allowed_tools list of policy '{policy.name}'."

        # 6. Check Risk Level Comparison
        policy_risk_val = cls.RISK_HIERARCHY.get(policy.risk_level.upper(), 1)
        tool_risk_val = cls.RISK_HIERARCHY.get(tool_risk_level.upper(), 1)
        if tool_risk_val > policy_risk_val:
            return False, f"Tool risk '{tool_risk_level}' exceeds policy max risk level '{policy.risk_level}'."

        # 7. Check Target Domain / URL (SSRF & Domain Restrictions)
        params = parameters or {}
        url_or_domain = params.get("url") or params.get("target_url") or params.get("domain") or params.get("target_domain")
        if url_or_domain:
            domain = cls._extract_domain(str(url_or_domain))
            is_valid_domain, domain_err = cls.validate_domain(policy, domain)
            if not is_valid_domain:
                return False, domain_err

        # 8. Check Budget Bounds
        if budget:
            if budget.is_exceeded:
                return False, "Research budget has already been exceeded."
            if budget.tool_calls_used >= budget.max_tool_calls:
                return False, f"Budget max tool calls ({budget.max_tool_calls}) reached."
            if budget.cost_usd_used >= budget.max_cost_usd:
                return False, f"Budget max cost (${budget.max_cost_usd:.2f}) reached."
            if budget.runtime_seconds_used >= budget.max_runtime_seconds:
                return False, f"Budget max runtime ({budget.max_runtime_seconds}s) reached."

        return True, None

    @classmethod
    def validate_domain(cls, policy: Optional[AutonomyPolicy], domain: str) -> Tuple[bool, Optional[str]]:
        """Validates that a domain or IP is safe to access (SSRF defense + policy blocks)."""
        clean_domain = domain.strip().lower()

        # Check SSRF / Private patterns
        for pattern in cls.BLOCKED_HOST_PATTERNS:
            if pattern.match(clean_domain):
                return False, f"Access to private/internal host '{clean_domain}' is blocked by SSRF defense."

        # IP address check
        try:
            ip_obj = ipaddress.ip_address(clean_domain)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local:
                return False, f"Access to non-public IP '{clean_domain}' is blocked."
        except ValueError:
            pass  # It is a domain name, not a raw IP

        if policy:
            # Check blocked domains
            blocked_domains = [d.lower() for d in (policy.blocked_domains or [])]
            for b in blocked_domains:
                if clean_domain == b or clean_domain.endswith("." + b):
                    return False, f"Domain '{clean_domain}' is in the policy blocked domains list."

            # Check allowed domains (if specified)
            allowed_domains = [d.lower() for d in (policy.allowed_domains or [])]
            if allowed_domains:
                matched = any(clean_domain == a or clean_domain.endswith("." + a) for a in allowed_domains)
                if not matched:
                    return False, f"Domain '{clean_domain}' is not in policy allowed domains list."

        return True, None

    @staticmethod
    def _extract_domain(url_or_domain: str) -> str:
        """Extracts domain host from a URL or bare domain string."""
        if not url_or_domain:
            return ""
        if "://" not in url_or_domain:
            url_or_domain = "https://" + url_or_domain
        parsed = urlparse(url_or_domain)
        host = parsed.hostname or ""
        return host.lower()


class ToolRegistry:
    """
    In-memory and persistent Tool Registry managing tool metadata,
    schemas, risk classifications, and safe invocations.
    """

    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        defaults = [
            {
                "name": "search_engine_query",
                "category": "DISCOVERY",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Executes public web search queries for companies, software, or leadership.",
                "parameters_schema": {"query": "string", "limit": "int"},
            },
            {
                "name": "company_website_crawler",
                "category": "SCRAPING",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Safely crawls public pages of a company website for firmographics and tech stack.",
                "parameters_schema": {"url": "string", "max_pages": "int"},
            },
            {
                "name": "github_repository_analyzer",
                "category": "CODE_INTEL",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Inspects public GitHub repositories and OCA commits for Odoo module contributions.",
                "parameters_schema": {"org_or_repo": "string"},
            },
            {
                "name": "job_posting_detector",
                "category": "INTENT",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Detects active job openings mentioning Odoo, ERP implementation, or tech keywords.",
                "parameters_schema": {"company_name": "string", "keywords": "list"},
            },
            {
                "name": "dns_mx_spf_checker",
                "category": "VERIFICATION",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Verifies DNS records, MX routing, and SPF policy for domain legitimacy.",
                "parameters_schema": {"domain": "string"},
            },
            {
                "name": "smtp_handshake_verifier",
                "category": "VERIFICATION",
                "risk_level": ToolRiskLevel.MEDIUM.value,
                "description": "Conducts non-intrusive SMTP RCPT TO handshake verification without sending email.",
                "parameters_schema": {"email": "string"},
            },
            {
                "name": "odoo_app_store_scanner",
                "category": "ECOSYSTEM",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Scans official Odoo app store and forums for public publisher/author profiles.",
                "parameters_schema": {"author": "string"},
            },
            {
                "name": "knowledge_graph_traversal",
                "category": "GRAPH",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Traverses internal knowledge graph to find known subsidiaries, partners, and contacts.",
                "parameters_schema": {"entity_id": "string", "depth": "int"},
            },
            {
                "name": "semantic_ontology_classifier",
                "category": "SEMANTICS",
                "risk_level": ToolRiskLevel.LOW.value,
                "description": "Classifies company text against industry, technology, and role taxonomies.",
                "parameters_schema": {"text": "string"},
            },
            {
                "name": "entity_resolution_matcher",
                "category": "RESOLUTION",
                "risk_level": ToolRiskLevel.MEDIUM.value,
                "description": "Resolves entity ambiguities, links duplicates, and determines parent/subsidiary hierarchy.",
                "parameters_schema": {"name": "string", "domain": "string"},
            },
            {
                "name": "deep_forensic_evaluator",
                "category": "FORENSIC",
                "risk_level": ToolRiskLevel.HIGH.value,
                "description": "Performs deep forensic cross-source reconciliation of contradictory corporate claims.",
                "parameters_schema": {"entity_name": "string", "claims": "list"},
            },
            {
                "name": "outreach_sender",
                "category": "RESTRICTED",
                "risk_level": ToolRiskLevel.RESTRICTED.value,
                "description": "FORBIDDEN OUTREACH TOOL. Permanently disabled by platform invariants.",
                "parameters_schema": {},
            },
            {
                "name": "raw_shell_command",
                "category": "RESTRICTED",
                "risk_level": ToolRiskLevel.RESTRICTED.value,
                "description": "FORBIDDEN SYSTEM TOOL. Permanently disabled by platform invariants.",
                "parameters_schema": {},
            },
        ]
        for t in defaults:
            self._registry[t["name"]] = t

    def register_tool(self, name: str, category: str, risk_level: str, description: str, parameters_schema: Dict[str, Any]):
        self._registry[name] = {
            "name": name,
            "category": category,
            "risk_level": risk_level,
            "description": description,
            "parameters_schema": parameters_schema,
        }

    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        return self._registry.get(name)

    def list_tools(self, max_risk_level: Optional[str] = None) -> List[Dict[str, Any]]:
        if not max_risk_level:
            return list(self._registry.values())
        max_val = AutonomyPolicyValidator.RISK_HIERARCHY.get(max_risk_level.upper(), 4)
        return [
            t for t in self._registry.values()
            if AutonomyPolicyValidator.RISK_HIERARCHY.get(t["risk_level"].upper(), 1) <= max_val
        ]
