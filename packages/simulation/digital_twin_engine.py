"""
LeadNexus AI X — Enterprise Digital Twin & Operational Simulation Engine
Phase 34 (ChatGPT Master Roadmap): Discrete Event Simulation & Prescriptive What-If Modeling
STRICT INVARIANT: Simulation must NEVER mutate production data.
"""

import time
import math
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.lead import Company, Contact, IntentSignal
from app.models.events import OutboxEvent
from app.models.digital_twin import (
    SimulationScenario,
    SimulationRun,
    OperationalCapacityModel,
)

logger = logging.getLogger("leadnexus.simulation.digital_twin")


class DigitalTwinEngine:
    """
    Simulates operational dynamics, resource constraints, failure cascades,
    and cost surges on an isolated digital twin replica.
    """

    @classmethod
    def capture_baseline_snapshot(cls, db: Session, tenant_id: str) -> Dict[str, Any]:
        """
        Reads non-mutating current state metrics from production tables.
        """
        company_count = db.query(Company).count()
        contact_count = db.query(Contact).count()
        signal_count = db.query(IntentSignal).count()
        outbox_pending = db.query(OutboxEvent).filter(OutboxEvent.status == "PENDING").count()

        # Query or supply default capacity metrics
        capacities = db.query(OperationalCapacityModel).filter(
            OperationalCapacityModel.tenant_id == tenant_id
        ).all()
        cap_dict = {c.resource_name: c.utilization_pct for c in capacities}

        return {
            "timestamp": int(time.time()),
            "total_companies": company_count,
            "total_contacts": contact_count,
            "total_signals": signal_count,
            "outbox_pending": outbox_pending,
            "browser_worker_pool": 4,
            "browser_worker_utilization_pct": cap_dict.get("BROWSER_WORKERS", 32.5),
            "ai_token_burn_hourly": 45000,
            "avg_cost_per_lead_usd": 0.42,
            "avg_verification_latency_sec": 3.8,
            "monthly_budget_usd": 5000.0,
            "primary_region": "ap-southeast-2 (Sydney)",
            "secondary_region": "ap-southeast-1 (Singapore)",
        }

    @classmethod
    def simulate_scenario(
        cls,
        baseline: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Executes discrete deterministic simulation over parameters.
        Returns: { 'projections': dict, 'bottlenecks': list, 'recommendations': list }
        """
        lead_mult = float(parameters.get("lead_volume_multiplier", 1.0))
        ai_cost_mult = float(parameters.get("ai_cost_multiplier", 1.0))
        source_down = parameters.get("source_unavailable")
        region_failed = parameters.get("region_failed")
        verif_spike = float(parameters.get("verification_backlog_multiplier", 1.0))

        bottlenecks: List[str] = []
        recommendations: List[str] = []

        # 1. Lead Volume Simulation
        projected_leads_hourly = round(120 * lead_mult)
        projected_worker_utilization = round(baseline["browser_worker_utilization_pct"] * lead_mult, 1)

        if projected_worker_utilization > 100.0:
            excess = projected_worker_utilization - 100.0
            needed_workers = math.ceil((projected_worker_utilization / 100.0) * baseline["browser_worker_pool"])
            bottlenecks.append(
                f"Browser Worker Pool Exhaustion: Projected utilization is {projected_worker_utilization}% ({excess:.1f}% over capacity)."
            )
            recommendations.append(
                f"Scale Browser Worker Pool from {baseline['browser_worker_pool']} to {needed_workers} instances to absorb {lead_mult}x volume."
            )
        else:
            needed_workers = baseline["browser_worker_pool"]

        # 2. Source Outage Simulation
        projected_discovery_efficiency = 100.0
        if source_down:
            penalty = 35.0 if source_down.lower() in ["github", "web_scraper"] else 20.0
            projected_discovery_efficiency = 100.0 - penalty
            bottlenecks.append(
                f"Single-Source Degradation: Outage in '{source_down}' reduces discovery pipeline efficiency to {projected_discovery_efficiency}%."
            )
            recommendations.append(
                f"Activate secondary syndication fallbacks (RSS & Public Registries) to recover lost {penalty:.0f}% signal coverage."
            )

        # 3. AI Cost & Unit Economics Simulation
        projected_cpl = round(baseline["avg_cost_per_lead_usd"] * ai_cost_mult, 3)
        projected_monthly_spend = round((projected_leads_hourly * 720 * projected_cpl) * 0.15, 2)
        if projected_monthly_spend > baseline["monthly_budget_usd"]:
            overage = projected_monthly_spend - baseline["monthly_budget_usd"]
            bottlenecks.append(
                f"FinOps Budget Breach: Projected monthly spend of ${projected_monthly_spend:,.2f} exceeds allocated budget of ${baseline['monthly_budget_usd']:,.2f} by ${overage:,.2f}."
            )
            recommendations.append(
                "Enable Tier-2 AI Semantic Pruning (Flash-Lite models) for initial qualification to lower unit costs by ~65%."
            )

        # 4. Regional Failure Simulation
        projected_latency_sec = baseline["avg_verification_latency_sec"]
        active_region = baseline["primary_region"]
        if region_failed:
            active_region = baseline["secondary_region"]
            projected_latency_sec += 0.85  # Cross-region failover network penalty
            bottlenecks.append(
                f"Regional Outage Cascade: Primary region '{region_failed}' simulated offline. Failover traffic redirected to {active_region}."
            )
            recommendations.append(
                "Pre-warm standby PostgreSQL read-replicas in secondary region to ensure p99 latency remains under 5.0s during failover."
            )

        # 5. Verification Backlog Simulation
        if verif_spike > 1.5:
            projected_latency_sec *= verif_spike
            if projected_latency_sec > 10.0:
                bottlenecks.append(
                    f"Evidence Verification SLA Breach: Projected latency is {projected_latency_sec:.1f}s (SLA limit: 10.0s)."
                )
                recommendations.append(
                    "Partition verification queues by high-priority ICP score (Tier 1 vs Tier 2)."
                )

        projections = {
            "lead_volume_multiplier": lead_mult,
            "projected_leads_hourly": projected_leads_hourly,
            "projected_worker_utilization_pct": projected_worker_utilization,
            "projected_required_workers": needed_workers,
            "projected_discovery_efficiency_pct": projected_discovery_efficiency,
            "projected_cost_per_lead_usd": projected_cpl,
            "projected_monthly_spend_usd": projected_monthly_spend,
            "projected_verification_latency_sec": round(projected_latency_sec, 2),
            "active_serving_region": active_region,
        }

        return {
            "projections": projections,
            "bottlenecks": bottlenecks,
            "recommendations": recommendations,
        }

    @classmethod
    def execute_run(
        cls,
        db: Session,
        tenant_id: str,
        executed_by: str,
        scenario: Optional[SimulationScenario] = None,
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> SimulationRun:
        """
        Executes a digital twin simulation run without mutating production tables.
        """
        start_time = time.perf_counter()
        params = scenario.parameters if scenario else (custom_params or {})
        scenario_type = scenario.scenario_type if scenario else "WHAT_IF"

        # 1. Capture non-mutating baseline
        baseline = cls.capture_baseline_snapshot(db, tenant_id)

        # 2. Run deterministic twin projection
        sim_result = cls.simulate_scenario(baseline, params)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 3. Record simulation run (isolated to simulation table)
        run = SimulationRun(
            tenant_id=tenant_id,
            scenario_id=scenario.id if scenario else None,
            scenario_type=scenario_type,
            baseline_snapshot=baseline,
            simulated_projections=sim_result["projections"],
            bottlenecks_detected=sim_result["bottlenecks"],
            recommendations=sim_result["recommendations"],
            duration_ms=round(duration_ms, 2),
            executed_by=executed_by,
            status="COMPLETED",
        )
        db.add(run)
        if scenario:
            scenario.status = "COMPLETED"
        db.commit()
        db.refresh(run)
        return run
