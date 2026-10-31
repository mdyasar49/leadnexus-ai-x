"""
LeadNexus AI X - Phase 28: Enterprise Developer Platform
Integration Template Engine: Pre-packaged, parameter-driven integration templates with variable validation.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TemplateVariable:
    name: str
    label: str
    var_type: str  # "string", "number", "boolean", "secret", "url"
    required: bool = True
    default: Optional[Any] = None
    description: str = ""
    pattern: Optional[str] = None


@dataclass
class IntegrationTemplateDefinition:
    id: str
    name: str
    category: str
    description: str
    version: str
    variables: List[TemplateVariable]
    steps: List[Dict[str, Any]]
    sample_config: Dict[str, Any] = field(default_factory=dict)


class TemplateRegistry:
    """Standard pre-packaged integration blueprints for enterprise workflows."""

    BUILTIN_TEMPLATES: Dict[str, IntegrationTemplateDefinition] = {
        "template_google_sheets_sync": IntegrationTemplateDefinition(
            id="template_google_sheets_sync",
            name="Google Sheets Lead Intelligence Sync",
            category="Productivity & Spreadsheets",
            description="Two-way grounded synchronization between LeadNexus verified leads and Google Sheets.",
            version="1.0.0",
            variables=[
                TemplateVariable(
                    name="spreadsheet_id",
                    label="Google Spreadsheet ID",
                    var_type="string",
                    required=True,
                    description="The unique identifier extracted from your Google Sheets URL.",
                ),
                TemplateVariable(
                    name="sheet_name",
                    label="Sheet Tab Name",
                    var_type="string",
                    required=False,
                    default="LeadNexus_Intelligence",
                    description="Name of the specific sheet tab to synchronize.",
                ),
                TemplateVariable(
                    name="sync_frequency_minutes",
                    label="Sync Frequency (Minutes)",
                    var_type="number",
                    required=False,
                    default=60,
                    description="Interval between automated sync passes.",
                ),
            ],
            steps=[
                {
                    "step_name": "validate_sheet_access",
                    "action": "sheets.verify_access",
                    "parameters": {"spreadsheet_id": "${spreadsheet_id}"},
                },
                {
                    "step_name": "reconcile_and_write",
                    "action": "sheets.sync_records",
                    "parameters": {
                        "spreadsheet_id": "${spreadsheet_id}",
                        "sheet_name": "${sheet_name}",
                        "escape_formulas": True,
                    },
                },
            ],
            sample_config={
                "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                "sheet_name": "Verified_Leads",
                "sync_frequency_minutes": 30,
            },
        ),
        "template_slack_high_intent_alerts": IntegrationTemplateDefinition(
            id="template_slack_high_intent_alerts",
            name="Slack High-Intent Lead Alerts",
            category="Alerts & Notifications",
            description="Post real-time alerts to a dedicated Slack channel when a Tier-1 high-intent lead is discovered.",
            version="1.0.0",
            variables=[
                TemplateVariable(
                    name="webhook_url",
                    label="Slack Incoming Webhook URL",
                    var_type="url",
                    required=True,
                    description="HTTPS URL for Slack Incoming Webhook (starts with https://hooks.slack.com/).",
                ),
                TemplateVariable(
                    name="min_score_threshold",
                    label="Minimum Lead Score Threshold",
                    var_type="number",
                    required=False,
                    default=80,
                    description="Only notify on verified leads meeting or exceeding this score (0-100).",
                ),
            ],
            steps=[
                {
                    "step_name": "filter_leads",
                    "action": "rules.filter_by_score",
                    "parameters": {"min_score": "${min_score_threshold}"},
                },
                {
                    "step_name": "dispatch_slack_message",
                    "action": "webhook.dispatch",
                    "parameters": {
                        "url": "${webhook_url}",
                        "template": "New Tier-1 Lead Detected: *${company_name}* (Score: ${lead_score})",
                    },
                },
            ],
            sample_config={
                "webhook_url": "https://hooks.slack.com/services/T000/B000/XXXX",
                "min_score_threshold": 85,
            },
        ),
        "template_public_job_feed_signals": IntegrationTemplateDefinition(
            id="template_public_job_feed_signals",
            name="Public Job Feed Technology Signals",
            category="Signal Ingestion",
            description="Continuously monitors public job feeds for enterprise ERP and software hiring signals.",
            version="1.0.0",
            variables=[
                TemplateVariable(
                    name="target_technology",
                    label="Target Technology Keyword",
                    var_type="string",
                    required=True,
                    default="Odoo",
                    description="Technology or software stack to monitor (e.g. Odoo, NetSuite, SAP).",
                ),
                TemplateVariable(
                    name="feed_endpoint",
                    label="Public Job Feed API Endpoint",
                    var_type="url",
                    required=True,
                    description="Public REST endpoint returning career posting feeds.",
                ),
            ],
            steps=[
                {
                    "step_name": "fetch_job_feed",
                    "action": "http.get",
                    "parameters": {"url": "${feed_endpoint}"},
                },
                {
                    "step_name": "extract_signals",
                    "action": "nlp.extract_tech_signals",
                    "parameters": {"keyword": "${target_technology}"},
                },
            ],
            sample_config={
                "target_technology": "Odoo",
                "feed_endpoint": "https://api.jobfeed.org/v1/posts",
            },
        ),
    }

    @classmethod
    def get_template(cls, template_id: str) -> Optional[IntegrationTemplateDefinition]:
        return cls.BUILTIN_TEMPLATES.get(template_id)

    @classmethod
    def list_templates(cls) -> List[IntegrationTemplateDefinition]:
        return list(cls.BUILTIN_TEMPLATES.values())


class IntegrationTemplateEngine:
    """Validates parameters, substitutes variables, and instantiates runnable integration workflows."""

    @classmethod
    def validate_variables(
        cls,
        template: IntegrationTemplateDefinition,
        provided_vars: Dict[str, Any],
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validates provided variables against template schema, applies defaults.
        Returns: (is_valid, errors, resolved_variables)
        """
        errors: List[str] = []
        resolved: Dict[str, Any] = {}

        for var_def in template.variables:
            val = provided_vars.get(var_def.name)

            if val is None or val == "":
                if var_def.required and var_def.default is None:
                    errors.append(f"Required variable '{var_def.name}' is missing.")
                    continue
                val = var_def.default

            # Type Validation
            if val is not None:
                if var_def.var_type == "number":
                    try:
                        val = float(val) if "." in str(val) else int(val)
                    except (ValueError, TypeError):
                        errors.append(f"Variable '{var_def.name}' must be a numeric value.")
                elif var_def.var_type == "boolean":
                    if isinstance(val, str):
                        val = val.lower() in ("true", "1", "yes")
                    else:
                        val = bool(val)
                elif var_def.var_type == "url":
                    val_str = str(val).strip()
                    if not val_str.startswith("http://") and not val_str.startswith("https://"):
                        errors.append(f"Variable '{var_def.name}' must be a valid HTTP(S) URL.")

            resolved[var_def.name] = val

        return len(errors) == 0, errors, resolved

    @classmethod
    def instantiate_template(
        cls,
        template_id: str,
        parameters: Dict[str, Any],
        workspace_id: str,
    ) -> Dict[str, Any]:
        """
        Substitutes variables into template steps to produce an instantiated runnable config.
        """
        template = TemplateRegistry.get_template(template_id)
        if not template:
            raise ValueError(f"Integration template '{template_id}' not found.")

        is_valid, errors, resolved = cls.validate_variables(template, parameters)
        if not is_valid:
            raise ValueError(f"Template validation failed: {'; '.join(errors)}")

        # Serialize steps to string for substitution
        steps_json = json.dumps(template.steps)

        for var_name, var_value in resolved.items():
            pattern = re.compile(rf"\${{{var_name}}}")
            steps_json = pattern.sub(str(var_value), steps_json)

        instantiated_steps = json.loads(steps_json)

        return {
            "instance_id": str(uuid.uuid4()),
            "template_id": template.id,
            "template_name": template.name,
            "version": template.version,
            "workspace_id": workspace_id,
            "resolved_parameters": resolved,
            "execution_steps": instantiated_steps,
            "instantiated_at": datetime.now(timezone.utc).isoformat(),
        }

