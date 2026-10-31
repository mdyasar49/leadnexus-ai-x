from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.lead import Company
from app.models.operations import ResearchCostEvent
from app.models.decision_intelligence import (
    Scenario,
    ScenarioVersion,
    ScenarioRun,
    ScenarioResult
)


class ScenarioEngine:
    """
    Controlled 'What-If' scenario simulation engine.
    Computes estimated workload, costs, queue pressure, and processing time
    without mutating production database records.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_scenario(
        self,
        workspace_id: str,
        name: str,
        parameters: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> Scenario:
        """Registers a scenario definition and initial version."""
        params = parameters or {}
        scenario = Scenario(
            workspace_id=workspace_id,
            name=name,
            description=description or f"Scenario: {name}",
            parameters=params
        )
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)

        ver = ScenarioVersion(
            scenario_id=scenario.id,
            version=1,
            parameters_snapshot=params
        )
        self.db.add(ver)
        self.db.commit()
        return scenario

    def run_simulation(
        self,
        workspace_id: str,
        scenario_id: str,
        simulated_by: Optional[str] = "system",
        workload_multiplier: float = 1.0,
        cost_adjustment_pct: float = 0.0,
        **kwargs
    ) -> ScenarioResult:
        """Runs a simulated what-if scenario without mutating production records."""
        scenario = self.db.query(Scenario).filter(
            and_(Scenario.workspace_id == workspace_id, Scenario.id == scenario_id)
        ).first()
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found.")

        current_leads = self.db.query(Company).filter(Company.workspace_id == workspace_id).count()
        baseline_cost = 150.0

        estimated_workload = round(max(10.0, current_leads * workload_multiplier * 5.0), 1)
        estimated_cost = round(baseline_cost * workload_multiplier * (1.0 + (cost_adjustment_pct / 100.0)), 2)
        queue_pressure = round(min(100.0, 35.0 * workload_multiplier), 1)
        storage_mb = round(current_leads * 0.05 * workload_multiplier, 2)
        processing_hours = round((estimated_workload / 150.0) * 2.5, 1)

        run = ScenarioRun(
            workspace_id=workspace_id,
            scenario_id=scenario.id,
            run_by=simulated_by,
            status="COMPLETED",
            run_at=datetime.now(timezone.utc)
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        result = ScenarioResult(
            run_id=run.id,
            estimated_workload=estimated_workload,
            estimated_cost_usd=estimated_cost,
            estimated_queue_pressure_pct=queue_pressure,
            estimated_storage_mb=storage_mb,
            estimated_processing_time_hours=processing_hours,
            limitations_notes="SCENARIO ESTIMATE: Projections assume linear queue consumption without database mutation."
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result


    def run_scenario(
        self,
        workspace_id: str,
        scenario_id: str,
        run_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Simulates scenario parameters against current baseline.
        Returns isolated ScenarioResult with explicit limitations notes.
        """
        scenario = self.db.query(Scenario).filter(
            and_(Scenario.workspace_id == workspace_id, Scenario.id == scenario_id)
        ).first()
        if not scenario:
            raise ValueError(f"Scenario '{scenario_id}' not found.")

        params = scenario.parameters or {}
        growth_pct = params.get("campaign_growth_pct", 0.0)
        discovery_mult = params.get("discovery_multiplier", 1.0)
        depth_mult = params.get("research_depth_modifier", 1.0)

        # Baseline metrics
        current_leads = self.db.query(Company).filter(Company.workspace_id == workspace_id).count()
        baseline_cost = 150.0  # Baseline monthly spend

        # Simulation
        sim_multiplier = (1.0 + (growth_pct / 100.0)) * discovery_mult
        estimated_workload = round(current_leads * sim_multiplier * depth_mult, 1)
        estimated_cost = round(baseline_cost * sim_multiplier * (1.0 + (depth_mult - 1.0) * 0.5), 2)
        queue_pressure = round(min(100.0, 35.0 * sim_multiplier * depth_mult), 1)
        storage_mb = round(current_leads * 0.05 * sim_multiplier, 2)
        processing_hours = round((estimated_workload / 150.0) * 2.5, 1)

        run = ScenarioRun(
            workspace_id=workspace_id,
            scenario_id=scenario.id,
            run_by=run_by,
            status="COMPLETED",
            run_at=datetime.now(timezone.utc)
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        result = ScenarioResult(
            run_id=run.id,
            estimated_workload=estimated_workload,
            estimated_cost_usd=estimated_cost,
            estimated_queue_pressure_pct=queue_pressure,
            estimated_storage_mb=storage_mb,
            estimated_processing_time_hours=processing_hours,
            limitations_notes=(
                "SCENARIO ESTIMATE: Projections assume linear queue consumption and "
                "standard browser concurrency without external rate-limiting spikes."
            )
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)

        return {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "run_id": run.id,
            "label": "SCENARIO ESTIMATE",
            "baseline_leads": current_leads,
            "estimated_workload_leads": estimated_workload,
            "estimated_cost_usd": estimated_cost,
            "estimated_queue_pressure_pct": queue_pressure,
            "estimated_storage_mb": storage_mb,
            "estimated_processing_time_hours": processing_hours,
            "notes": result.limitations_notes
        }
