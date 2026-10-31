from typing import Dict, Any, List


WORKFLOW_TEMPLATES = {
    "HIGH_INTENT_ODOO_LEAD": {
        "name": "High-Intent Odoo Lead Qualification",
        "description": "Orchestrates research, decision-maker discovery, contact verification, and human review for high-intent Odoo signals.",
        "workflow_type": "RESEARCH_WORKFLOW",
        "definition_payload": {
            "nodes": [
                {"id": "node_trigger", "type": "TRIGGER", "label": "New Intent Signal Observed"},
                {"id": "node_condition_intent", "type": "CONDITION", "label": "Intent Score >= 70", "config": {"condition": {"field": "intent_score", "operator": ">=", "value": 70}}},
                {"id": "node_tech_research", "type": "RESEARCH", "label": "Deep Odoo Version Research"},
                {"id": "node_dm_enrich", "type": "ENRICH", "label": "Discover IT / ERP Decision Makers"},
                {"id": "node_contact_verify", "type": "VERIFY", "label": "Verify Deliverable Contacts"},
                {"id": "node_human_review", "type": "HUMAN_REVIEW", "label": "Analyst Qualification Review"},
                {"id": "node_approval", "type": "APPROVAL", "label": "Mark Lead Qualified"},
                {"id": "node_end", "type": "END", "label": "Workflow Complete"}
            ],
            "edges": [
                {"from": "node_trigger", "to": "node_condition_intent"},
                {"from": "node_condition_intent", "to": "node_tech_research", "label": "true"},
                {"from": "node_condition_intent", "to": "node_end", "label": "false"},
                {"from": "node_tech_research", "to": "node_dm_enrich"},
                {"from": "node_dm_enrich", "to": "node_contact_verify"},
                {"from": "node_contact_verify", "to": "node_human_review"},
                {"from": "node_human_review", "to": "node_approval"},
                {"from": "node_approval", "to": "node_end"}
            ]
        }
    },
    "STALE_LEAD_REFRESH": {
        "name": "Stale Lead Refresh & Quality Recalculation",
        "description": "Periodically evaluates aging leads, refreshes tech and contact verification, and updates lifecycle state.",
        "workflow_type": "STALE_DATA_WORKFLOW",
        "definition_payload": {
            "nodes": [
                {"id": "node_trigger", "type": "TRIGGER", "label": "Scheduled Staleness Scan"},
                {"id": "node_condition_stale", "type": "CONDITION", "label": "Freshness Score <= 60", "config": {"condition": {"field": "freshness_score", "operator": "<=", "value": 60}}},
                {"id": "node_refresh_tech", "type": "REFRESH", "label": "Re-verify Technology Footprint"},
                {"id": "node_score", "type": "SCORE", "label": "Recalculate Lead Priority Score"},
                {"id": "node_end", "type": "END", "label": "Refresh Finished"}
            ],
            "edges": [
                {"from": "node_trigger", "to": "node_condition_stale"},
                {"from": "node_condition_stale", "to": "node_refresh_tech", "label": "true"},
                {"from": "node_condition_stale", "to": "node_end", "label": "false"},
                {"from": "node_refresh_tech", "to": "node_score"},
                {"from": "node_score", "to": "node_end"}
            ]
        }
    },
    "CONTACT_VERIFICATION_WORKFLOW": {
        "name": "Automated Contact Verification & Delivery Check",
        "description": "Validates RFC 5322 syntax, verifies domain and deliverability semantics, and rejects disposables.",
        "workflow_type": "VERIFICATION_WORKFLOW",
        "definition_payload": {
            "nodes": [
                {"id": "node_trigger", "type": "TRIGGER", "label": "Contact Discovered"},
                {"id": "node_verify", "type": "VERIFY", "label": "Deliverability Verification"},
                {"id": "node_condition_email", "type": "CONDITION", "label": "Has Verified Email", "config": {"condition": {"field": "has_email", "operator": "=", "value": True}}},
                {"id": "node_approval", "type": "APPROVAL", "label": "Confirm Deliverable Contact"},
                {"id": "node_end", "type": "END", "label": "End"}
            ],
            "edges": [
                {"from": "node_trigger", "to": "node_verify"},
                {"from": "node_verify", "to": "node_condition_email"},
                {"from": "node_condition_email", "to": "node_approval", "label": "true"},
                {"from": "node_condition_email", "to": "node_end", "label": "false"},
                {"from": "node_approval", "to": "node_end"}
            ]
        }
    },
    "GOOGLE_SHEET_SYNC_WORKFLOW": {
        "name": "Verified High-Priority Lead Google Sheet Sync",
        "description": "Prepares and enqueues high-priority leads passing all quality gates to authorized Google Sheets destination.",
        "workflow_type": "SHEET_SYNC_WORKFLOW",
        "definition_payload": {
            "nodes": [
                {"id": "node_trigger", "type": "TRIGGER", "label": "Lead Marked Ready"},
                {"id": "node_condition_score", "type": "CONDITION", "label": "Lead Score >= 80", "config": {"condition": {"field": "lead_score", "operator": ">=", "value": 80}}},
                {"id": "node_sheet_sync", "type": "SHEET_SYNC", "label": "Sync to Google Sheets Queue"},
                {"id": "node_end", "type": "END", "label": "Sync Complete"}
            ],
            "edges": [
                {"from": "node_trigger", "to": "node_condition_score"},
                {"from": "node_condition_score", "to": "node_sheet_sync", "label": "true"},
                {"from": "node_condition_score", "to": "node_end", "label": "false"},
                {"from": "node_sheet_sync", "to": "node_end"}
            ]
        }
    }
}


class TemplateLibraryService:
    """Library of reusable enterprise workflow templates."""

    @staticmethod
    def list_templates() -> List[Dict[str, Any]]:
        return [
            {
                "key": k,
                "name": v["name"],
                "description": v["description"],
                "workflow_type": v["workflow_type"],
                "node_count": len(v["definition_payload"]["nodes"]),
                "edge_count": len(v["definition_payload"]["edges"])
            }
            for k, v in WORKFLOW_TEMPLATES.items()
        ]

    @staticmethod
    def get_template(template_key: str) -> Dict[str, Any]:
        key = template_key.upper()
        if key not in WORKFLOW_TEMPLATES:
            raise ValueError(f"Template '{template_key}' not found in template library.")
        return WORKFLOW_TEMPLATES[key]
