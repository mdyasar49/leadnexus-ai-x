"""
LeadNexus AI X - Phase 28: Enterprise Developer Platform
Developer Sandbox Service: Test data seeding, simulated external providers, and isolated environment management.
"""

import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.developer_platform import DeveloperSandbox


class MockProviderSimulator:
    """Simulates external service behaviors (success, rate limit, outage, timeout) for developer testing."""

    @classmethod
    def simulate_call(
        cls,
        endpoint_type: str,
        simulation_mode: str = "SUCCESS",  # "SUCCESS", "RATE_LIMIT", "SERVER_ERROR", "TIMEOUT"
    ) -> Dict[str, Any]:
        if simulation_mode == "RATE_LIMIT":
            return {
                "status_code": 429,
                "error": "Too Many Requests",
                "headers": {"Retry-After": "60"},
                "payload": None,
            }
        elif simulation_mode == "SERVER_ERROR":
            return {
                "status_code": 500,
                "error": "Internal Service Error from simulated upstream",
                "headers": {},
                "payload": None,
            }
        elif simulation_mode == "TIMEOUT":
            return {
                "status_code": 504,
                "error": "Gateway Timeout: simulated upstream did not respond within 30000ms",
                "headers": {},
                "payload": None,
            }

        # SUCCESS
        if endpoint_type == "company_enrichment":
            return {
                "status_code": 200,
                "payload": {
                    "company_name": "Apex Manufacturing Ltd [SANDBOX]",
                    "domain": "apexmanufacturing.sandbox.test",
                    "technologies": ["Odoo 17.0", "PostgreSQL", "Nginx"],
                    "confidence": 0.95,
                    "evidence": "Observed Odoo login portal and public developer job listings.",
                },
            }
        elif endpoint_type == "contact_verification":
            return {
                "status_code": 200,
                "payload": {
                    "email": "sarah.jenkins@apexmanufacturing.sandbox.test",
                    "deliverability": "DELIVERABLE",
                    "mx_found": True,
                    "smtp_verified": True,
                    "is_catchall": False,
                },
            }
        else:
            return {
                "status_code": 200,
                "payload": {"message": "Mock provider success", "mock_id": str(uuid.uuid4())},
            }


class DeveloperSandboxService:
    """Manages developer sandboxes and seeds isolated synthetic test entities."""

    SYNTHETIC_COMPANIES = [
        {
            "name": "Apex Global Solutions [TEST]",
            "domain": "apex-global.sandbox.test",
            "industry": "Industrial Automation",
            "technologies": ["Odoo 16.0", "Python", "Docker"],
            "lead_score": 88,
        },
        {
            "name": "Beacon Retail Logistics [TEST]",
            "domain": "beaconlogistics.sandbox.test",
            "industry": "Supply Chain & Logistics",
            "technologies": ["Odoo 17.0", "PostgreSQL", "Redis"],
            "lead_score": 92,
        },
        {
            "name": "Crestline Manufacturing [TEST]",
            "domain": "crestlinemfg.sandbox.test",
            "industry": "Precision Machinery",
            "technologies": ["SAP ECC", "Windows Server"],
            "lead_score": 54,
        },
    ]

    def __init__(self, db_session: Any):
        self.db = db_session

    def create_sandbox(
        self,
        workspace_id: str,
        name: str,
        app_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> DeveloperSandbox:
        """Creates an isolated test sandbox environment."""
        sandbox = DeveloperSandbox(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            app_id=app_id,
            name=name,
            status="ACTIVE",
            config=config or {"auto_seed": True, "strict_isolation": True},
            is_test_data=True,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(sandbox)
        self.db.commit()
        self.db.refresh(sandbox)
        return sandbox

    def seed_synthetic_data(
        self,
        sandbox_id: str,
        workspace_id: str,
        record_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Generates synthetic grounded test companies and contacts tagged with is_test_data=True.
        """
        sandbox = self.db.query(DeveloperSandbox).filter(DeveloperSandbox.id == sandbox_id).first()
        if not sandbox:
            raise ValueError(f"Sandbox '{sandbox_id}' not found.")

        seeded_companies = []
        for i in range(min(record_count, len(self.SYNTHETIC_COMPANIES))):
            template = self.SYNTHETIC_COMPANIES[i]
            company_data = {
                "id": str(uuid.uuid4()),
                "workspace_id": workspace_id,
                "sandbox_id": sandbox_id,
                "name": template["name"],
                "domain": template["domain"],
                "industry": template["industry"],
                "technologies": template["technologies"],
                "lead_score": template["lead_score"],
                "is_test_data": True,
                "contacts": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": f"Test Contact {i+1}",
                        "title": "Head of Operations",
                        "email": f"test.ops{i+1}@{template['domain']}",
                        "is_verified": True,
                        "deliverability": "DELIVERABLE",
                        "is_test_data": True,
                    }
                ],
            }
            seeded_companies.append(company_data)

        # Store seeding metadata in sandbox config
        curr_config = dict(sandbox.config or {})
        curr_config["seeded_records_count"] = len(seeded_companies)
        curr_config["last_seeded_at"] = datetime.now(timezone.utc).isoformat()
        sandbox.config = curr_config
        self.db.commit()

        return {
            "sandbox_id": sandbox_id,
            "status": "SEEDED",
            "companies_seeded": len(seeded_companies),
            "data": seeded_companies,
        }

    def reset_sandbox(self, sandbox_id: str) -> bool:
        """Resets sandbox state and clears seeded test metadata."""
        sandbox = self.db.query(DeveloperSandbox).filter(DeveloperSandbox.id == sandbox_id).first()
        if not sandbox:
            return False

        sandbox.config = {"auto_seed": False, "reset_at": datetime.now(timezone.utc).isoformat()}
        self.db.commit()
        return True
