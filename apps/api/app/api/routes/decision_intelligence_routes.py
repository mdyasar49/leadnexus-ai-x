from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.services.permission_service import get_active_workspace, get_current_user

from app.models.decision_intelligence import (
    AnalyticsCohort,
    AnalyticsSegment,
    Forecast,
    Scenario,
    CapacityForecast,
    QueueForecast,
    SLAForecast,
    InformationValueAssessment,
    ResearchRecommendation,
    DecisionRecommendation,
    RecommendationStatus,
    Benchmark,
    AnalyticsTarget,
    Scorecard,
    DriverAnalysis,
    CorrelationAnalysis,
    Experiment,
    DecisionBrief,
    DecisionBriefExecution
)

from packages.decision_intelligence.cohort_engine import CohortEngine
from packages.decision_intelligence.segmentation_engine import SegmentationEngine
from packages.decision_intelligence.forecasting_engine import ForecastingEngine
from packages.decision_intelligence.scenario_engine import ScenarioEngine
from packages.decision_intelligence.capacity_sla_engine import CapacitySLAEngine
from packages.decision_intelligence.recommendation_engine import RecommendationEngine
from packages.decision_intelligence.benchmark_scorecard_engine import BenchmarkScorecardEngine
from packages.decision_intelligence.driver_correlation_engine import DriverCorrelationEngine
from packages.decision_intelligence.experiment_engine import ExperimentEngine
from packages.decision_intelligence.decision_brief_generator import DecisionBriefGenerator


decision_intel_router = APIRouter(
    prefix="/decision-intelligence",
    tags=["Enterprise Decision Intelligence, BI & Forecasting"]
)


# --- Pydantic Request Models ---

class CreateCohortRequest(BaseModel):
    name: str
    cohort_type: str = "DISCOVERY_TIME"
    criteria: Dict[str, Any] = Field(default_factory=dict)
    period_type: str = "MONTHLY"


class CreateSegmentRequest(BaseModel):
    name: str
    segment_type: str = "INDUSTRY_MOMENTUM"
    criteria: Dict[str, Any] = Field(default_factory=dict)
    dimensions: List[str] = Field(default_factory=list)


class GenerateForecastRequest(BaseModel):
    target_metric: str = "NEW_DISCOVERIES"
    historical_values: List[float]
    forecast_horizon_days: int = 30
    model_name: str = "EXPONENTIAL_SMOOTHING"


class EvaluateForecastRequest(BaseModel):
    actual_values: List[float]


class CreateScenarioRequest(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class RunScenarioRequest(BaseModel):
    simulated_by: str = "system"
    workload_multiplier: float = 1.0
    budget_limit_usd: Optional[float] = None
    cost_adjustment_pct: float = 0.0


class CalculateEIVRequest(BaseModel):
    company_id: str
    missing_field: str = "decision_maker"
    importance: float = 1.5
    prob_finding: float = 0.80
    estimated_cost: float = 2.50


class ProcessDecisionRequest(BaseModel):
    action: str = "ACCEPTED"  # ACCEPTED, REJECTED, DEFERRED, EXECUTED
    decided_by: str = "system"
    notes: Optional[str] = None


class RegisterBenchmarkRequest(BaseModel):
    benchmark_name: str
    dimension: str = "LEAD_QUALITY"
    metric_code: str = "BUYING_READINESS"
    baseline_value: float = 50.0
    top_quartile_value: float = 80.0


class UpsertTargetRequest(BaseModel):
    target_name: str
    metric_code: str
    target_value: float
    timeframe: str = "MONTHLY"


class DriverCorrelationRequest(BaseModel):
    variable_x: str
    variable_y: str
    series_x: List[float]
    series_y: List[float]


class DriverImportanceRequest(BaseModel):
    target_metric: str
    driver_feature: str
    importance_weight: float
    correlation_coeff: float


class CreateExperimentRequest(BaseModel):
    name: str
    hypothesis: str
    strategy_a: str = "STANDARD_RESEARCH"
    strategy_b: str = "DEEP_MULTI_SOURCE_RESEARCH"
    target_metric: str = "BUYING_READINESS"


class EvaluateExperimentRequest(BaseModel):
    metric_name: str = "BUYING_READINESS"
    values_a: List[float]
    values_b: List[float]


class GenerateBriefRequest(BaseModel):
    title: Optional[str] = None


class ExecuteBriefRequest(BaseModel):
    executed_by: str = "system"
    export_format: str = "JSON"


# --- 1. Cohort Analytics ---

@decision_intel_router.post("/cohorts")
def create_cohort(
    req: CreateCohortRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CohortEngine(db)
    cohort = engine.create_cohort(
        workspace_id=ws.id,
        name=req.name,
        cohort_type=req.cohort_type,
        criteria=req.criteria,
        period_type=req.period_type
    )
    return {
        "status": "success",
        "cohort_id": cohort.id,
        "name": cohort.name,
        "cohort_type": cohort.cohort_type,
        "created_at": cohort.created_at
    }


@decision_intel_router.get("/cohorts")
def list_cohorts(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    cohorts = db.query(AnalyticsCohort).filter(AnalyticsCohort.workspace_id == ws.id).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "cohort_type": c.cohort_type,
            "description": c.description,
            "created_at": c.created_at
        }
        for c in cohorts
    ]


@decision_intel_router.post("/cohorts/{cohort_id}/evaluate")
def evaluate_cohort(
    cohort_id: str,
    period_label: str = "CURRENT",
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CohortEngine(db)
    snapshot = engine.evaluate_cohort_snapshot(
        workspace_id=ws.id,
        cohort_id=cohort_id,
        period_label=period_label
    )
    return {
        "status": "success",
        "snapshot_id": snapshot.id,
        "cohort_id": snapshot.cohort_id,
        "cohort_size": snapshot.cohort_size,
        "average_priority_score": snapshot.average_priority_score,
        "persistence_rate_day_7": snapshot.persistence_rate_day_7,
        "persistence_rate_day_30": snapshot.persistence_rate_day_30,
        "snapshot_date": snapshot.snapshot_date
    }


@decision_intel_router.get("/cohorts/{cohort_id}/persistence")
def get_intent_persistence(
    cohort_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CohortEngine(db)
    persistence = engine.track_intent_persistence(
        workspace_id=ws.id,
        cohort_id=cohort_id
    )
    return {
        "cohort_id": cohort_id,
        "intent_persistence": persistence
    }


# --- 2. Advanced Segmentation & Emerging Segments ---

@decision_intel_router.post("/segments")
def create_segment(
    req: CreateSegmentRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = SegmentationEngine(db)
    segment = engine.create_segment(
        workspace_id=ws.id,
        name=req.name,
        segment_type=req.segment_type,
        criteria=req.criteria,
        dimensions=req.dimensions
    )
    return {
        "status": "success",
        "segment_id": segment.id,
        "name": segment.name,
        "segment_type": segment.segment_type,
        "created_at": segment.created_at
    }


@decision_intel_router.get("/segments")
def list_segments(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    segments = db.query(AnalyticsSegment).filter(AnalyticsSegment.workspace_id == ws.id).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "segment_type": s.segment_type,
            "created_at": s.created_at
        }
        for s in segments
    ]


@decision_intel_router.post("/segments/{segment_id}/evaluate")
def evaluate_segment(
    segment_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = SegmentationEngine(db)
    snapshot = engine.evaluate_segment_snapshot(
        workspace_id=ws.id,
        segment_id=segment_id
    )
    return {
        "status": "success",
        "snapshot_id": snapshot.id,
        "segment_id": snapshot.segment_id,
        "company_count": snapshot.company_count,
        "growth_pct": snapshot.growth_percentage,
        "intent_density": snapshot.intent_density,
        "momentum_score": snapshot.momentum_score,
        "evaluated_at": snapshot.evaluated_at
    }


@decision_intel_router.get("/segments/emerging")
def get_emerging_segments(
    min_growth_pct: float = 10.0,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = SegmentationEngine(db)
    emerging = engine.detect_emerging_segments(
        workspace_id=ws.id,
        min_growth_pct=min_growth_pct
    )
    return [
        {
            "segment_id": s.segment_id,
            "name": s.name,
            "company_count": s.company_count,
            "growth_percentage": s.growth_percentage,
            "intent_density": s.intent_density,
            "momentum_score": s.momentum_score,
            "evaluated_at": s.evaluated_at
        }
        for s in emerging
    ]


# --- 3. Bounded Aggregate Forecasting ---

@decision_intel_router.post("/forecasts/generate")
def generate_forecast(
    req: GenerateForecastRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = ForecastingEngine(db)
    forecast = engine.forecast_bounded(
        workspace_id=ws.id,
        target_metric=req.target_metric,
        historical_values=req.historical_values,
        horizon_days=req.forecast_horizon_days,
        model_name=req.model_name
    )
    return {
        "status": "success",
        "forecast_id": forecast.id,
        "target_metric": forecast.target_metric,
        "horizon_days": forecast.forecast_horizon_days,
        "model_name": forecast.model_name,
        "points": [
            {
                "step": p.step_number,
                "target_date": p.target_date,
                "point_forecast": p.point_forecast,
                "lower_bound": p.lower_bound_80,
                "upper_bound": p.upper_bound_80
            }
            for p in forecast.points
        ]
    }


@decision_intel_router.get("/forecasts")
def list_forecasts(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    forecasts = (
        db.query(Forecast)
        .filter(Forecast.workspace_id == ws.id)
        .order_by(desc(Forecast.created_at))
        .limit(20)
        .all()
    )
    return [
        {
            "id": f.id,
            "target_metric": f.target_metric,
            "horizon_days": f.forecast_horizon_days,
            "model_name": f.model_name,
            "generated_at": f.generated_at,
            "points_count": len(f.points) if f.points else 0
        }
        for f in forecasts
    ]


@decision_intel_router.post("/forecasts/{forecast_id}/evaluate")
def evaluate_forecast(
    forecast_id: str,
    req: EvaluateForecastRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = ForecastingEngine(db)
    eval_record = engine.evaluate_accuracy(
        workspace_id=ws.id,
        forecast_id=forecast_id,
        actual_values=req.actual_values
    )
    return {
        "status": "success",
        "evaluation_id": eval_record.id,
        "forecast_id": eval_record.forecast_id,
        "mae": eval_record.mae,
        "rmse": eval_record.rmse,
        "mape": eval_record.mape,
        "evaluated_at": eval_record.evaluated_at
    }


# --- 4. What-If Scenarios & Simulations ---

@decision_intel_router.post("/scenarios")
def create_scenario(
    req: CreateScenarioRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = ScenarioEngine(db)
    scenario = engine.create_scenario(
        workspace_id=ws.id,
        name=req.name,
        description=req.description,
        parameters=req.parameters
    )
    return {
        "status": "success",
        "scenario_id": scenario.id,
        "name": scenario.name,
        "created_at": scenario.created_at
    }


@decision_intel_router.get("/scenarios")
def list_scenarios(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    scenarios = db.query(Scenario).filter(Scenario.workspace_id == ws.id).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "created_at": s.created_at
        }
        for s in scenarios
    ]


@decision_intel_router.post("/scenarios/{scenario_id}/run")
def run_scenario(
    scenario_id: str,
    req: RunScenarioRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = ScenarioEngine(db)
    sim_result = engine.run_simulation(
        workspace_id=ws.id,
        scenario_id=scenario_id,
        simulated_by=req.simulated_by,
        workload_multiplier=req.workload_multiplier,
        cost_adjustment_pct=req.cost_adjustment_pct
    )
    return {
        "status": "success",
        "run_id": sim_result.scenario_run_id,
        "simulated_discoveries": sim_result.simulated_discoveries,
        "simulated_spend_usd": sim_result.simulated_spend_usd,
        "projected_cost_per_lead": sim_result.projected_cost_per_lead,
        "queue_pressure_ratio": sim_result.queue_pressure_ratio,
        "capacity_risk": sim_result.capacity_risk,
        "sla_breach_probability": sim_result.sla_breach_probability
    }


# --- 5. Capacity Planning & SLA Risk ---

@decision_intel_router.get("/capacity")
def get_capacity_forecasts(
    horizon_days: int = 30,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CapacitySLAEngine(db)
    forecasts = engine.evaluate_capacity_forecast(
        workspace_id=ws.id,
        horizon_days=horizon_days
    )
    return [
        {
            "resource_type": f.resource_type,
            "current_utilization": f.current_utilization_pct,
            "forecasted_utilization": f.forecasted_utilization_pct,
            "headroom_pct": f.headroom_pct,
            "breach_risk": f.breach_risk
        }
        for f in forecasts
    ]


@decision_intel_router.get("/capacity/queues")
def get_queue_forecasts(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CapacitySLAEngine(db)
    queues = engine.evaluate_queue_forecast(workspace_id=ws.id)
    return [
        {
            "queue_name": q.queue_name,
            "arrival_rate": q.arrival_rate_per_hour,
            "completion_rate": q.completion_rate_per_hour,
            "backlog_hours": q.projected_backlog_hours
        }
        for q in queues
    ]


@decision_intel_router.get("/capacity/sla")
def get_sla_forecasts(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = CapacitySLAEngine(db)
    risks = engine.evaluate_sla_risks(workspace_id=ws.id)
    return [
        {
            "workload_type": r.workload_type,
            "target_hours": r.sla_target_hours,
            "forecasted_hours": r.forecasted_completion_hours,
            "sla_status": r.sla_status
        }
        for r in risks
    ]


# --- 6. Expected Information Value & Recommendations ---

@decision_intel_router.post("/recommendations/eiv")
def calculate_eiv(
    req: CalculateEIVRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = RecommendationEngine(db)
    assessment = engine.calculate_expected_information_value(
        workspace_id=ws.id,
        company_id=req.company_id,
        missing_field=req.missing_field,
        importance=req.importance,
        prob_finding=req.prob_finding,
        estimated_cost=req.estimated_cost
    )
    return {
        "status": "success",
        "assessment_id": assessment.id,
        "company_id": assessment.target_entity_id,
        "missing_field": assessment.missing_field,
        "expected_information_value": assessment.expected_information_value
    }


@decision_intel_router.post("/recommendations/generate")
def generate_recommendations(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = RecommendationEngine(db)
    recs = engine.recommend_priority_investigations(workspace_id=ws.id)
    return [
        {
            "id": r.id,
            "target_entity_id": r.target_entity_id,
            "target_entity_name": r.target_entity_name,
            "missing_information": r.missing_information,
            "recommended_source": r.recommended_source,
            "expected_information_value": r.expected_information_value,
            "reason": r.reason
        }
        for r in recs
    ]


@decision_intel_router.get("/recommendations")
def list_recommendations(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    recs = (
        db.query(ResearchRecommendation)
        .filter(ResearchRecommendation.workspace_id == ws.id)
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "target_entity_id": r.target_entity_id,
            "target_entity_name": r.target_entity_name,
            "missing_information": r.missing_information,
            "recommended_source": r.recommended_source,
            "expected_information_value": r.expected_information_value,
            "reason": r.reason
        }
        for r in recs
    ]


@decision_intel_router.post("/recommendations/{recommendation_id}/decision")
def process_recommendation_decision(
    recommendation_id: str,
    req: ProcessDecisionRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = RecommendationEngine(db)
    dec = engine.process_decision(
        workspace_id=ws.id,
        recommendation_id=recommendation_id,
        action=req.action,
        decided_by=req.decided_by,
        notes=req.notes
    )
    return {
        "status": "success",
        "decision_id": dec.id,
        "target_entity_id": dec.target_entity_id,
        "decision": dec.status,
        "recommendation_type": dec.recommendation_type,
        "updated_at": dec.updated_at
    }


# --- 7. Internal Benchmarking & Strategic Scorecard ---

@decision_intel_router.post("/benchmarks")
def register_benchmark(
    req: RegisterBenchmarkRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = BenchmarkScorecardEngine(db)
    bm = engine.register_benchmark(
        workspace_id=ws.id,
        benchmark_name=req.benchmark_name,
        dimension=req.dimension,
        metric_code=req.metric_code,
        baseline_value=req.baseline_value,
        top_quartile_value=req.top_quartile_value
    )
    return {
        "status": "success",
        "benchmark_id": bm.id,
        "benchmark_name": bm.benchmark_name,
        "dimension": bm.dimension,
        "baseline": bm.baseline_value,
        "top_quartile": bm.top_quartile_value
    }


@decision_intel_router.post("/targets")
def upsert_target(
    req: UpsertTargetRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = BenchmarkScorecardEngine(db)
    target = engine.create_or_update_target(
        workspace_id=ws.id,
        target_name=req.target_name,
        metric_code=req.metric_code,
        target_value=req.target_value,
        timeframe=req.timeframe
    )
    return {
        "status": "success",
        "target_id": target.id,
        "target_name": target.target_name,
        "metric_code": target.metric_code,
        "target_value": target.target_value
    }


@decision_intel_router.get("/scorecard")
def get_strategic_scorecard(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = BenchmarkScorecardEngine(db)
    scorecard = engine.calculate_scorecard(workspace_id=ws.id)
    return {
        "scorecard_id": scorecard.id,
        "overall_health": scorecard.overall_health,
        "lead_quality_score": scorecard.lead_quality_score,
        "research_quality_score": scorecard.research_quality_score,
        "data_quality_score": scorecard.data_quality_score,
        "source_performance_score": scorecard.source_performance_score,
        "buying_committee_coverage_score": scorecard.buying_committee_coverage_score,
        "evaluated_at": scorecard.evaluated_at
    }


# --- 8. Driver & Correlation Analysis ---

@decision_intel_router.post("/drivers/correlations")
def calculate_driver_correlation(
    req: DriverCorrelationRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = DriverCorrelationEngine(db)
    analysis = engine.calculate_correlation(
        workspace_id=ws.id,
        variable_x=req.variable_x,
        variable_y=req.variable_y,
        series_x=req.series_x,
        series_y=req.series_y
    )
    return {
        "status": "success",
        "analysis_id": analysis.id,
        "variable_x": analysis.variable_x,
        "variable_y": analysis.variable_y,
        "pearson_r": analysis.pearson_r,
        "spearman_rho": analysis.spearman_rho,
        "sample_size": analysis.sample_size,
        "confidence_level": analysis.confidence_level
    }


@decision_intel_router.post("/drivers/importance")
def record_driver_importance(
    req: DriverImportanceRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = DriverCorrelationEngine(db)
    driver = engine.record_driver_analysis(
        workspace_id=ws.id,
        target_metric=req.target_metric,
        driver_feature=req.driver_feature,
        importance_weight=req.importance_weight,
        correlation_coeff=req.correlation_coeff
    )
    return {
        "status": "success",
        "driver_id": driver.id,
        "target_metric": driver.target_metric,
        "driver_feature": driver.driver_feature,
        "importance_weight": driver.importance_weight,
        "correlation_coefficient": driver.correlation_coefficient
    }


# --- 9. A/B Analytics Strategy Experiments ---

@decision_intel_router.post("/experiments")
def create_experiment(
    req: CreateExperimentRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = ExperimentEngine(db)
    exp = engine.create_experiment(
        workspace_id=ws.id,
        name=req.name,
        hypothesis=req.hypothesis,
        strategy_a=req.strategy_a,
        strategy_b=req.strategy_b,
        target_metric=req.target_metric
    )
    return {
        "status": "success",
        "experiment_id": exp.id,
        "name": exp.name,
        "status": exp.status,
        "created_at": exp.created_at
    }


@decision_intel_router.get("/experiments")
def list_experiments(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    experiments = db.query(Experiment).filter(Experiment.workspace_id == ws.id).all()
    return [
        {
            "id": e.id,
            "name": e.name,
            "hypothesis": e.hypothesis,
            "status": e.status,
            "created_at": e.created_at
        }
        for e in experiments
    ]


@decision_intel_router.post("/experiments/{experiment_id}/evaluate")
def evaluate_experiment(
    experiment_id: str,
    req: EvaluateExperimentRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    engine = ExperimentEngine(db)
    result = engine.evaluate_experiment(
        workspace_id=ws.id,
        experiment_id=experiment_id,
        metric_name=req.metric_name,
        values_a=req.values_a,
        values_b=req.values_b
    )
    return {
        "status": "success",
        "result_id": result.id,
        "experiment_id": result.experiment_id,
        "mean_a": result.mean_a,
        "mean_b": result.mean_b,
        "relative_lift_pct": result.relative_lift_pct,
        "p_value": result.p_value,
        "statistically_significant": result.statistically_significant
    }


# --- 10. Strategic Decision Briefs ---

@decision_intel_router.post("/briefs/generate")
def generate_decision_brief(
    req: GenerateBriefRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    generator = DecisionBriefGenerator(db)
    brief = generator.generate_brief(
        workspace_id=ws.id,
        title=req.title
    )
    return {
        "status": "success",
        "brief_id": brief.id,
        "title": brief.title,
        "executive_summary": brief.executive_summary,
        "emerging_segments": brief.emerging_segments,
        "intent_trends": brief.intent_trends,
        "source_performance": brief.source_performance,
        "lead_quality": brief.lead_quality,
        "operational_risks": brief.operational_risks,
        "forecast_highlights": brief.forecast_highlights,
        "recommended_investigations": brief.recommended_investigations,
        "generated_at": brief.generated_at
    }


@decision_intel_router.get("/briefs")
def list_decision_briefs(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    briefs = (
        db.query(DecisionBrief)
        .filter(DecisionBrief.workspace_id == ws.id)
        .order_by(desc(DecisionBrief.generated_at))
        .limit(10)
        .all()
    )
    return [
        {
            "id": b.id,
            "title": b.title,
            "executive_summary": b.executive_summary,
            "generated_at": b.generated_at
        }
        for b in briefs
    ]


@decision_intel_router.get("/briefs/{brief_id}")
def get_decision_brief(
    brief_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    brief = (
        db.query(DecisionBrief)
        .filter(
            DecisionBrief.workspace_id == ws.id,
            DecisionBrief.id == brief_id
        )
        .first()
    )
    if not brief:
        raise HTTPException(status_code=404, detail="Decision brief not found")
    return {
        "id": brief.id,
        "title": brief.title,
        "executive_summary": brief.executive_summary,
        "emerging_segments": brief.emerging_segments,
        "intent_trends": brief.intent_trends,
        "source_performance": brief.source_performance,
        "lead_quality": brief.lead_quality,
        "operational_risks": brief.operational_risks,
        "forecast_highlights": brief.forecast_highlights,
        "recommended_investigations": brief.recommended_investigations,
        "generated_at": brief.generated_at
    }


@decision_intel_router.post("/briefs/{brief_id}/execute")
def execute_decision_brief(
    brief_id: str,
    req: ExecuteBriefRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    generator = DecisionBriefGenerator(db)
    execution = generator.record_brief_execution(
        workspace_id=ws.id,
        brief_id=brief_id,
        executed_by=req.executed_by,
        export_format=req.export_format
    )
    return {
        "status": "success",
        "execution_id": execution.id,
        "brief_id": execution.brief_id,
        "executed_by": execution.executed_by,
        "export_format": execution.export_format,
        "executed_at": execution.executed_at
    }
