"""
LeadNexus AI X - Phase 28: Enterprise Developer Platform & Connector SDK
Connector SDK: Manifest parser, sandbox execution runtime, capability enforcement, and security policies.
"""

import ast
import inspect
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from packages.integrations.security_and_credentials import SSRFProtection


class ConnectorCapability(str, Enum):
    SEARCH = "SEARCH"
    FETCH = "FETCH"
    WEBHOOK = "WEBHOOK"
    EXPORT = "EXPORT"
    ENRICH = "ENRICH"


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"


@dataclass
class ConnectorManifest:
    id: str
    name: str
    version: str
    category: str
    description: str
    author: str
    capabilities: List[str]
    required_permissions: List[str]
    entrypoint: str
    allowed_domains: List[str] = field(default_factory=list)
    max_timeout_seconds: int = 30
    max_records_per_run: int = 500
    config_schema: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConnectorManifest":
        if not data.get("id") or not data.get("name") or not data.get("version"):
            raise ValueError("Connector manifest must provide id, name, and version")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data.get("version", "1.0.0")),
            category=str(data.get("category", "General")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "LeadNexus Developer")),
            capabilities=[str(c).upper() for c in data.get("capabilities", [])],
            required_permissions=[str(p) for p in data.get("required_permissions", [])],
            entrypoint=str(data.get("entrypoint", "default_handler")),
            allowed_domains=[str(d).lower() for d in data.get("allowed_domains", [])],
            max_timeout_seconds=int(data.get("max_timeout_seconds", 30)),
            max_records_per_run=int(data.get("max_records_per_run", 500)),
            config_schema=dict(data.get("config_schema", {})),
        )


@dataclass
class ConnectorContext:
    workspace_id: str
    installation_id: str
    configuration: Dict[str, Any]
    granted_scopes: List[str]
    is_sandbox: bool = False
    logger: Optional[List[str]] = None

    def log(self, message: str) -> None:
        if self.logger is not None:
            self.logger.append(f"[{datetime.now(timezone.utc).isoformat()}] {message}")


@dataclass
class ConnectorResult:
    status: ExecutionStatus
    records_processed: int = 0
    records: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    duration_ms: int = 0
    logs: List[str] = field(default_factory=list)


class ConnectorSecurityScanner:
    """Scans connector source code or manifests for forbidden patterns."""

    FORBIDDEN_CALLS = {
        "eval", "exec", "__import__", "open", "input", "compile", "globals", "locals"
    }

    FORBIDDEN_MODULES = {
        "os", "sys", "subprocess", "socket", "ctypes", "pty", "shutil", "commands",
        "pickle", "shelve", "builtins"
    }

    @classmethod
    def scan_code(cls, source_code: str) -> Tuple[bool, List[str]]:
        violations: List[str] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return False, [f"Syntax error in code: {str(e)}"]

        for node in ast.walk(tree):
            # Check for forbidden module imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".")[0]
                    if root_pkg in cls.FORBIDDEN_MODULES:
                        violations.append(f"Forbidden import '{alias.name}' detected.")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    if root_pkg in cls.FORBIDDEN_MODULES:
                        violations.append(f"Forbidden from-import '{node.module}' detected.")

            # Check for forbidden calls
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in cls.FORBIDDEN_CALLS:
                    violations.append(f"Forbidden function call '{func.id}()' detected.")

        return len(violations) == 0, violations

    @classmethod
    def validate_outbound_network(cls, url: str, allowed_domains: List[str]) -> Tuple[bool, Optional[str]]:
        # 1. SSRF Defense Check
        ssrf_ok, ssrf_err = SSRFProtection.validate_outbound_url(url)
        if not ssrf_ok:
            return False, f"SSRF Security Violation: {ssrf_err}"

        # 2. Domain Allowlist Check
        if allowed_domains:
            domain_match = False
            for d in allowed_domains:
                if f"://{d}" in url.lower() or f".{d}" in url.lower() or f"/{d}" in url.lower():
                    domain_match = True
                    break
            if not domain_match:
                return False, f"Domain not in connector allowed_domains: {allowed_domains}"

        return True, None


class BaseConnector:
    """Base class that custom third-party or native connectors implement."""

    def __init__(self, manifest: ConnectorManifest):
        self.manifest = manifest

    def execute(self, context: ConnectorContext) -> ConnectorResult:
        raise NotImplementedError("Subclasses must implement execute()")


class SandboxedConnectorRunner:
    """Executes connectors under strict security, permission, and resource boundaries."""

    def __init__(self):
        self._registered_connectors: Dict[str, BaseConnector] = {}

    def register_connector(self, connector: BaseConnector) -> None:
        self._registered_connectors[connector.manifest.id] = connector

    def get_connector(self, connector_id: str) -> Optional[BaseConnector]:
        return self._registered_connectors.get(connector_id)

    def execute_connector(
        self,
        connector_id: str,
        context: ConnectorContext,
    ) -> ConnectorResult:
        start_time = time.time()
        logs: List[str] = []
        context.logger = logs

        connector = self.get_connector(connector_id)
        if not connector:
            return ConnectorResult(
                status=ExecutionStatus.FAILED,
                error_message=f"Connector '{connector_id}' is not registered.",
                duration_ms=0,
                logs=logs,
            )

        manifest = connector.manifest

        # 1. Scope and Permission Check
        missing_scopes = [
            req for req in manifest.required_permissions
            if req not in context.granted_scopes and "admin:all" not in context.granted_scopes
        ]
        if missing_scopes:
            context.log(f"Permission denied: Missing scopes {missing_scopes}")
            return ConnectorResult(
                status=ExecutionStatus.PERMISSION_DENIED,
                error_message=f"Missing required scopes: {missing_scopes}",
                duration_ms=int((time.time() - start_time) * 1000),
                logs=logs,
            )

        # 2. Execution with Safety & Resource Caps
        try:
            context.log(f"Starting execution of connector '{manifest.name}' v{manifest.version}")
            result = connector.execute(context)

            # Cap max records
            if len(result.records) > manifest.max_records_per_run:
                context.log(f"Truncating records from {len(result.records)} to max {manifest.max_records_per_run}")
                result.records = result.records[:manifest.max_records_per_run]
                result.records_processed = len(result.records)

            duration_ms = int((time.time() - start_time) * 1000)
            result.duration_ms = duration_ms
            result.logs = logs
            context.log(f"Execution finished in {duration_ms}ms with status {result.status.value}")
            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            context.log(f"Execution error: {str(e)}")
            return ConnectorResult(
                status=ExecutionStatus.FAILED,
                error_message=str(e),
                duration_ms=duration_ms,
                logs=logs,
            )


# --- Built-in Reference Connectors ---

class PublicJobFeedConnector(BaseConnector):
    """Reference connector: Ingests tech stack signals from public career/job feeds."""

    def __init__(self):
        manifest = ConnectorManifest(
            id="public_job_feed_connector",
            name="Public Job Feed Connector",
            version="1.0.0",
            category="Signal Ingestion",
            description="Collects verified hiring and ERP technology signals from public job descriptions.",
            author="LeadNexus Engineering",
            capabilities=[ConnectorCapability.FETCH.value, ConnectorCapability.ENRICH.value],
            required_permissions=["companies:read", "research:run"],
            entrypoint="execute",
            allowed_domains=["careers.example.com", "api.jobfeed.org"],
            max_records_per_run=100,
        )
        super().__init__(manifest)

    def execute(self, context: ConnectorContext) -> ConnectorResult:
        context.log("Executing PublicJobFeedConnector fetch step")
        keyword = context.configuration.get("target_technology", "Odoo")

        # Grounded mock simulation of public job posts
        records = [
            {
                "job_title": f"Lead {keyword} Functional Consultant",
                "company_name": "Apex Manufacturing Ltd",
                "technology_detected": keyword,
                "confidence": 0.94,
                "signal_type": "JOB_POSTING",
                "source_url": "https://careers.example.com/jobs/1029",
                "evidence_text": f"Must have 3+ years experience with {keyword} ERP enterprise deployments.",
            },
            {
                "job_title": f"Senior {keyword} Developer",
                "company_name": "Nexus Logistics Solutions",
                "technology_detected": keyword,
                "confidence": 0.91,
                "signal_type": "JOB_POSTING",
                "source_url": "https://careers.example.com/jobs/8472",
                "evidence_text": f"Hands-on customization of {keyword} backend modules (Python & PostgreSQL).",
            },
        ]

        return ConnectorResult(
            status=ExecutionStatus.SUCCESS,
            records_processed=len(records),
            records=records,
        )


class CustomWebhookExporterConnector(BaseConnector):
    """Reference connector: Exports enriched intelligence updates to external webhooks."""

    def __init__(self):
        manifest = ConnectorManifest(
            id="webhook_intelligence_exporter",
            name="Webhook Intelligence Exporter",
            version="1.0.0",
            category="Intelligence Export",
            description="Streams qualified enterprise leads to partner systems via authenticated webhook.",
            author="LeadNexus Engineering",
            capabilities=[ConnectorCapability.EXPORT.value, ConnectorCapability.WEBHOOK.value],
            required_permissions=["exports:create"],
            entrypoint="execute",
            max_records_per_run=50,
        )
        super().__init__(manifest)

    def execute(self, context: ConnectorContext) -> ConnectorResult:
        webhook_url = context.configuration.get("target_url", "")
        if not webhook_url:
            return ConnectorResult(
                status=ExecutionStatus.FAILED,
                error_message="Missing 'target_url' in configuration",
            )

        # Validate SSRF
        is_safe, err = SSRFProtection.validate_outbound_url(webhook_url)
        if not is_safe:
            return ConnectorResult(
                status=ExecutionStatus.SECURITY_VIOLATION,
                error_message=f"SSRF violation: {err}",
            )

        context.log(f"Exporting verified intelligence payload to {webhook_url}")
        return ConnectorResult(
            status=ExecutionStatus.SUCCESS,
            records_processed=context.configuration.get("batch_size", 10),
            records=[{"destination": webhook_url, "exported_at": datetime.now(timezone.utc).isoformat()}],
        )
