from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RecommendationType(str, Enum):
    REFRESH = "REFRESH"
    RESEARCH = "RESEARCH"
    VERIFY = "VERIFY"
    REVIEW = "REVIEW"
    PRIORITIZE = "PRIORITIZE"
    DEFER = "DEFER"
    MONITOR = "MONITOR"


class RecommendationStatus(str, Enum):
    NEW = "NEW"
    VIEWED = "VIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"


class SLAStatus(str, Enum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    LIKELY_BREACH = "LIKELY_BREACH"


class ScorecardHealth(str, Enum):
    EXCELLENT = "EXCELLENT"
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    AT_RISK = "AT_RISK"
    CRITICAL = "CRITICAL"


class ExperimentStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CONCLUDED = "CONCLUDED"


# 1. Cohorts & Snapshots
class AnalyticsCohort(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_cohorts"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    cohort_type = Column(String(50), default="DISCOVERY_DATE", nullable=False)  # DISCOVERY_DATE, FIRST_SIGNAL, CAMPAIGN
    definition_criteria = Column(JSON, default=dict, nullable=False)
    description = Column(Text, nullable=True)


class CohortSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cohort_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    cohort_id = Column(String(36), ForeignKey("analytics_cohorts.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    cohort_size = Column(Integer, default=0, nullable=False)
    persistence_rate_day_7 = Column(Float, default=100.0, nullable=False)
    persistence_rate_day_30 = Column(Float, default=100.0, nullable=False)
    persistence_rate_day_60 = Column(Float, default=100.0, nullable=False)
    persistence_rate_day_90 = Column(Float, default=100.0, nullable=False)
    average_priority_score = Column(Float, default=0.0, nullable=False)
    metrics_payload = Column(JSON, default=dict, nullable=False)


# 2. Segments & Momentum
class AnalyticsSegment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_segments"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    criteria = Column(JSON, default=dict, nullable=False)  # Multi-dimensional: industry, geo, tech, intent, ICP
    is_emerging = Column(Boolean, default=False, nullable=False)
    momentum_score = Column(Float, default=0.0, nullable=False)  # 0-100
    owner = Column(String(100), default="system", nullable=False)

    @property
    def segment_type(self) -> str:
        if self.criteria and isinstance(self.criteria, dict):
            return self.criteria.get("segment_type", "MULTI_DIMENSIONAL")
        return "MULTI_DIMENSIONAL"

    @segment_type.setter
    def segment_type(self, val: str):
        if not self.criteria:
            self.criteria = {}
        if isinstance(self.criteria, dict):
            self.criteria["segment_type"] = val



class SegmentVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "segment_versions"

    segment_id = Column(String(36), ForeignKey("analytics_segments.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    criteria_snapshot = Column(JSON, default=dict, nullable=False)
    changed_by = Column(String(36), nullable=True)


class SegmentSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "segment_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    segment_id = Column(String(36), ForeignKey("analytics_segments.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    segment_size = Column(Integer, default=0, nullable=False)
    average_score = Column(Float, default=0.0, nullable=False)
    average_quality = Column(Float, default=0.0, nullable=False)
    growth_rate_pct = Column(Float, default=0.0, nullable=False)
    distributions = Column(JSON, default=dict, nullable=False)


# 3. Forecasting & Validation
class Forecast(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "forecasts"

    workspace_id = Column(String(36), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)  # LEAD_DISCOVERY_VOLUME, INTENT_VOLUME, RESEARCH_WORKLOAD, COST
    forecast_horizon = Column(String(50), default="30_DAYS", nullable=False)
    model_name = Column(String(100), default="exponential_smoothing", nullable=False)
    model_version = Column(String(50), default="v1.0", nullable=False)
    training_window_days = Column(Integer, default=90, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    forecast_points = Column(JSON, default=list, nullable=False)  # list of {date, forecast_value, lower_bound, upper_bound, confidence}

    points = relationship("ForecastPoint", backref="forecast", cascade="all, delete-orphan", lazy="joined")

    @property
    def target_metric(self) -> str:
        return self.metric_name

    @target_metric.setter
    def target_metric(self, val: str):
        self.metric_name = val

    @property
    def generated_at(self):
        return self.created_at

    @property
    def forecast_horizon_days(self) -> int:
        try:
            return int(str(self.forecast_horizon).split("_")[0])
        except Exception:
            return 30


class ForecastPoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "forecast_points"

    forecast_id = Column(String(36), ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False, index=True)
    target_date = Column(DateTime, nullable=False)
    forecast_value = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=False)
    upper_bound = Column(Float, nullable=False)
    actual_value = Column(Float, nullable=True)

    @property
    def point_forecast(self) -> float:
        return self.forecast_value

    @property
    def lower_bound_80(self) -> float:
        return self.lower_bound

    @property
    def upper_bound_80(self) -> float:
        return self.upper_bound

    @property
    def step_number(self) -> int:
        return getattr(self, "_step_number", 1)

    @step_number.setter
    def step_number(self, val: int):
        self._step_number = val



class ForecastEvaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "forecast_evaluations"

    workspace_id = Column(String(36), nullable=False, index=True)
    forecast_id = Column(String(36), ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False, index=True)
    mae = Column(Float, default=0.0, nullable=False)
    rmse = Column(Float, default=0.0, nullable=False)
    mape = Column(Float, default=0.0, nullable=False)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# 4. Scenario Planning ("What-If" Analysis)
class Scenario(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenarios"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    parameters = Column(JSON, default=dict, nullable=False)  # {campaign_growth_pct, discovery_multiplier, refresh_frequency_days}


class ScenarioVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenario_versions"

    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    parameters_snapshot = Column(JSON, default=dict, nullable=False)


class ScenarioRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenario_runs"

    workspace_id = Column(String(36), nullable=False, index=True)
    scenario_id = Column(String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    run_by = Column(String(36), nullable=True)
    status = Column(String(50), default="COMPLETED", nullable=False)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ScenarioResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenario_results"

    run_id = Column(String(36), ForeignKey("scenario_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    estimated_workload = Column(Float, default=0.0, nullable=False)
    estimated_cost_usd = Column(Float, default=0.0, nullable=False)
    estimated_queue_pressure_pct = Column(Float, default=0.0, nullable=False)
    estimated_storage_mb = Column(Float, default=0.0, nullable=False)
    estimated_processing_time_hours = Column(Float, default=0.0, nullable=False)
    limitations_notes = Column(Text, nullable=True)

    @property
    def simulated_discoveries(self) -> int:
        return int(self.estimated_workload)

    @property
    def simulated_spend_usd(self) -> float:
        return self.estimated_cost_usd

    @property
    def projected_cost_per_lead(self) -> float:
        return round(self.estimated_cost_usd / max(1, self.estimated_workload), 2)

    @property
    def queue_pressure_ratio(self) -> float:
        return round(self.estimated_queue_pressure_pct / 100.0, 2)

    @property
    def capacity_risk(self) -> str:
        return "LOW" if self.estimated_queue_pressure_pct < 60 else "MEDIUM"

    @property
    def sla_breach_probability(self) -> float:
        return 0.05 if self.estimated_queue_pressure_pct < 60 else 0.25

    @property
    def scenario_run_id(self) -> str:
        return self.run_id


# 5. Capacity & SLA Forecasting
class CapacityForecast(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "capacity_forecasts"

    workspace_id = Column(String(36), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)  # WORKER, BROWSER, API_QUOTA, DATABASE
    horizon_days = Column(Integer, default=30, nullable=False)
    current_utilization_pct = Column(Float, default=0.0, nullable=False)
    forecasted_utilization_pct = Column(Float, default=0.0, nullable=False)
    breach_risk = Column(String(50), default="LOW", nullable=False)

    @property
    def headroom_pct(self) -> float:
        return round(max(0.0, 100.0 - self.forecasted_utilization_pct), 1)



class QueueForecast(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "queue_forecasts"

    workspace_id = Column(String(36), nullable=False, index=True)
    queue_name = Column(String(100), nullable=False)
    arrival_rate_per_hour = Column(Float, default=0.0, nullable=False)
    completion_rate_per_hour = Column(Float, default=0.0, nullable=False)
    projected_backlog_hours = Column(Float, default=0.0, nullable=False)


class SLAForecast(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sla_forecasts"

    workspace_id = Column(String(36), nullable=False, index=True)
    workload_type = Column(String(50), default="RESEARCH_RUN", nullable=False)
    sla_target_hours = Column(Float, default=24.0, nullable=False)
    forecasted_completion_hours = Column(Float, default=12.0, nullable=False)
    sla_status = Column(String(50), default="ON_TRACK", nullable=False)


# 6. Information Value & Decision Recommendations
class InformationValueAssessment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "information_value_assessments"

    workspace_id = Column(String(36), nullable=False, index=True)
    target_entity_type = Column(String(50), default="COMPANY", nullable=False)
    target_entity_id = Column(String(36), nullable=False, index=True)
    missing_field = Column(String(100), nullable=False)
    importance_weight = Column(Float, default=1.0, nullable=False)
    probability_of_finding = Column(Float, default=0.5, nullable=False)
    estimated_research_cost = Column(Float, default=5.0, nullable=False)
    expected_information_value = Column(Float, default=0.0, nullable=False)  # (prob * importance) / cost


class ResearchRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_recommendations"

    workspace_id = Column(String(36), nullable=False, index=True)
    target_entity_id = Column(String(36), nullable=False, index=True)
    target_entity_name = Column(String(255), nullable=False)
    missing_information = Column(String(255), nullable=False)
    recommended_source = Column(String(100), nullable=False)
    expected_information_value = Column(String(50), default="HIGH", nullable=False)
    reason = Column(Text, nullable=False)


class DecisionRecommendation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "decision_recommendations"

    workspace_id = Column(String(36), nullable=False, index=True)
    recommendation_type = Column(String(50), default="RESEARCH", nullable=False)  # REFRESH, RESEARCH, VERIFY, REVIEW, PRIORITIZE, DEFER, MONITOR
    target_entity = Column(String(255), nullable=False)
    target_entity_id = Column(String(36), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    supporting_metrics = Column(JSON, default=dict, nullable=False)
    supporting_evidence = Column(JSON, default=list, nullable=False)
    confidence = Column(Float, default=0.85, nullable=False)
    status = Column(String(50), default="NEW", nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)


# 7. Benchmarks, Targets & Scorecard
class Benchmark(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "benchmarks"

    workspace_id = Column(String(36), nullable=False, index=True)
    benchmark_name = Column(String(255), nullable=False)
    dimension = Column(String(100), nullable=False)  # CAMPAIGN, SOURCE, INDUSTRY, GEOGRAPHY
    metric_code = Column(String(100), nullable=False)
    baseline_value = Column(Float, default=0.0, nullable=False)
    top_quartile_value = Column(Float, default=0.0, nullable=False)


class BenchmarkSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "benchmark_snapshots"

    benchmark_id = Column(String(36), ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    recorded_value = Column(Float, default=0.0, nullable=False)


class AnalyticsTarget(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_targets"

    workspace_id = Column(String(36), nullable=False, index=True)
    target_name = Column(String(255), nullable=False)
    metric_code = Column(String(100), nullable=False)
    target_value = Column(Float, default=0.0, nullable=False)
    current_actual = Column(Float, default=0.0, nullable=False)
    gap = Column(Float, default=0.0, nullable=False)
    unit = Column(String(20), default="PERCENT", nullable=False)


class Scorecard(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scorecards"

    workspace_id = Column(String(36), nullable=False, index=True)
    scorecard_name = Column(String(255), nullable=False)
    health_status = Column(String(50), default="HEALTHY", nullable=False)  # EXCELLENT, HEALTHY, WATCH, AT_RISK, CRITICAL
    lead_quality_score = Column(Float, default=0.0, nullable=False)
    research_quality_score = Column(Float, default=0.0, nullable=False)
    data_quality_score = Column(Float, default=0.0, nullable=False)
    source_quality_score = Column(Float, default=0.0, nullable=False)
    operational_efficiency_score = Column(Float, default=0.0, nullable=False)
    decision_maker_coverage = Column(Float, default=0.0, nullable=False)
    calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def overall_health(self) -> str:
        return self.health_status

    @property
    def source_performance_score(self) -> float:
        return self.source_quality_score

    @property
    def buying_committee_coverage_score(self) -> float:
        return self.decision_maker_coverage

    @property
    def evaluated_at(self):
        return self.calculated_at



# 8. Drivers & Correlations
class DriverAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "driver_analyses"

    workspace_id = Column(String(36), nullable=False, index=True)
    target_metric = Column(String(100), nullable=False)  # LEAD_PRIORITY_SCORE, RESEARCH_SUCCESS, VERIFICATION_SUCCESS
    driver_feature = Column(String(100), nullable=False)
    importance_weight = Column(Float, default=0.0, nullable=False)
    correlation_coefficient = Column(Float, default=0.0, nullable=False)
    statistical_significance_p = Column(Float, default=0.01, nullable=False)


class CorrelationAnalysis(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "correlation_analyses"

    workspace_id = Column(String(36), nullable=False, index=True)
    variable_x = Column(String(100), nullable=False)
    variable_y = Column(String(100), nullable=False)
    pearson_r = Column(Float, default=0.0, nullable=False)
    spearman_rho = Column(Float, default=0.0, nullable=False)
    sample_size = Column(Integer, default=0, nullable=False)
    is_statistically_significant = Column(Boolean, default=True, nullable=False)


# 9. Analytics Experiments (A/B Testing Strategies)
class Experiment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "experiments"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    hypothesis = Column(Text, nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False)  # DRAFT, ACTIVE, PAUSED, CONCLUDED
    primary_metric = Column(String(100), nullable=False)


class ExperimentVariant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "experiment_variants"

    experiment_id = Column(String(36), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_name = Column(String(100), nullable=False)  # e.g., "STRATEGY_A_STANDARD", "STRATEGY_B_DEEP"
    configuration = Column(JSON, default=dict, nullable=False)
    traffic_allocation_pct = Column(Float, default=50.0, nullable=False)


class ExperimentAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "experiment_assignments"

    experiment_id = Column(String(36), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(String(36), ForeignKey("experiment_variants.id", ondelete="CASCADE"), nullable=False)
    entity_id = Column(String(36), nullable=False, index=True)


class ExperimentMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "experiment_metrics"

    experiment_id = Column(String(36), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_id = Column(String(36), nullable=False)
    sample_size = Column(Integer, default=0, nullable=False)
    mean_metric_value = Column(Float, default=0.0, nullable=False)


class ExperimentResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "experiment_results"

    experiment_id = Column(String(36), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    winning_variant_id = Column(String(36), nullable=True)
    relative_lift_pct = Column(Float, default=0.0, nullable=False)
    p_value = Column(Float, default=0.05, nullable=False)
    conclusion_summary = Column(Text, nullable=False)

    @property
    def statistically_significant(self) -> bool:
        return (self.p_value or 1.0) < 0.05

    @property
    def mean_a(self) -> float:
        return getattr(self, "_mean_a", 0.0)

    @mean_a.setter
    def mean_a(self, val: float):
        self._mean_a = val

    @property
    def mean_b(self) -> float:
        return getattr(self, "_mean_b", 0.0)

    @mean_b.setter
    def mean_b(self, val: float):
        self._mean_b = val



# 10. Strategic Decision Briefs
class DecisionBrief(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "decision_briefs"

    workspace_id = Column(String(36), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    executive_summary = Column(Text, nullable=False)
    emerging_segments = Column(JSON, default=list, nullable=False)
    intent_trends = Column(JSON, default=list, nullable=False)
    source_performance = Column(JSON, default=dict, nullable=False)
    lead_quality = Column(JSON, default=dict, nullable=False)
    operational_risks = Column(JSON, default=list, nullable=False)
    forecast_highlights = Column(JSON, default=dict, nullable=False)
    recommended_investigations = Column(JSON, default=list, nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DecisionBriefVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "decision_brief_versions"

    brief_id = Column(String(36), ForeignKey("decision_briefs.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    content_snapshot = Column(JSON, default=dict, nullable=False)


class DecisionBriefExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "decision_brief_executions"

    workspace_id = Column(String(36), nullable=False, index=True)
    brief_id = Column(String(36), ForeignKey("decision_briefs.id", ondelete="CASCADE"), nullable=False, index=True)
    executed_by = Column(String(36), nullable=True)
    export_format = Column(String(50), default="JSON", nullable=False)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
