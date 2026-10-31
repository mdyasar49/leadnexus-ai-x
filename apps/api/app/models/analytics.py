from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MetricType(str, Enum):
    COUNT = "COUNT"
    RATE = "RATE"
    AVERAGE = "AVERAGE"
    SUM = "SUM"
    RATIO = "RATIO"
    PERCENTAGE = "PERCENTAGE"


class MetricCategory(str, Enum):
    LEAD = "LEAD"
    INTENT = "INTENT"
    SOURCE = "SOURCE"
    QUALITY = "QUALITY"
    RESEARCH = "RESEARCH"
    WORKFLOW = "WORKFLOW"
    COST = "COST"
    PREDICTIVE = "PREDICTIVE"


class PredictionType(str, Enum):
    LEAD_PRIORITY_PROBABILITY = "LEAD_PRIORITY_PROBABILITY"
    RESEARCH_SUCCESS_PROBABILITY = "RESEARCH_SUCCESS_PROBABILITY"
    DATA_ENRICHMENT_SUCCESS_PROBABILITY = "DATA_ENRICHMENT_SUCCESS_PROBABILITY"
    CONTACT_VERIFICATION_PROBABILITY = "CONTACT_VERIFICATION_PROBABILITY"
    STALENESS_RISK = "STALENESS_RISK"
    INTENT_PERSISTENCE_PROBABILITY = "INTENT_PERSISTENCE_PROBABILITY"
    REVIEW_ESCALATION_PROBABILITY = "REVIEW_ESCALATION_PROBABILITY"


class TrendDirection(str, Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"
    EMERGING = "EMERGING"
    DECLINING = "DECLINING"


class ReportFormat(str, Enum):
    JSON = "JSON"
    CSV = "CSV"
    XLSX = "XLSX"
    GOOGLE_SHEETS = "GOOGLE_SHEETS"


# 1. Centralized KPI & Metric Registry
class AnalyticsMetric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_metrics"

    workspace_id = Column(String(36), nullable=False, index=True)
    metric_code = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), default="LEAD", nullable=False, index=True)
    metric_type = Column(String(50), default="COUNT", nullable=False)
    formula = Column(Text, nullable=False)
    owner = Column(String(100), default="system", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_metric_ws_code", "workspace_id", "metric_code", unique=True),
    )


class AnalyticsMetricVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_metric_versions"

    metric_id = Column(String(36), ForeignKey("analytics_metrics.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    formula = Column(Text, nullable=False)
    change_reason = Column(Text, nullable=True)
    created_by = Column(String(36), nullable=True)


class AnalyticsDimension(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_dimensions"

    workspace_id = Column(String(36), nullable=False, index=True)
    dimension_name = Column(String(100), nullable=False, index=True)
    field_mapping = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    allowed_values = Column(JSON, default=list, nullable=True)


# 2. Historical Snapshots
class AnalyticsSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    snapshot_type = Column(String(50), nullable=False, index=True)  # DAILY, WEEKLY, MONTHLY, EVENT
    target_entity_type = Column(String(50), nullable=False)
    target_entity_id = Column(String(36), nullable=True, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    metrics_payload = Column(JSON, default=dict, nullable=False)


class LeadSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "lead_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    total_leads = Column(Integer, default=0, nullable=False)
    discovered_count = Column(Integer, default=0, nullable=False)
    researching_count = Column(Integer, default=0, nullable=False)
    enriching_count = Column(Integer, default=0, nullable=False)
    qualifying_count = Column(Integer, default=0, nullable=False)
    review_required_count = Column(Integer, default=0, nullable=False)
    qualified_count = Column(Integer, default=0, nullable=False)
    high_priority_count = Column(Integer, default=0, nullable=False)
    ready_count = Column(Integer, default=0, nullable=False)
    stale_count = Column(Integer, default=0, nullable=False)
    suppressed_count = Column(Integer, default=0, nullable=False)
    
    average_priority_score = Column(Float, default=0.0, nullable=False)
    average_icp_fit = Column(Float, default=0.0, nullable=False)


class CompanySnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "company_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), nullable=False, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    domain = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    lead_score = Column(Float, default=0.0, nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), nullable=False)
    decision_maker_count = Column(Integer, default=0, nullable=False)
    verified_contact_count = Column(Integer, default=0, nullable=False)
    primary_technologies = Column(JSON, default=list, nullable=False)


class PersonSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "person_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    person_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), nullable=True, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    full_name = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=True)
    role_category = Column(String(100), nullable=True)
    buying_role = Column(String(50), nullable=True)
    has_verified_email = Column(Boolean, default=False, nullable=False)


class ContactSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contact_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    contact_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), nullable=True, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    email_status = Column(String(50), nullable=True)
    phone_status = Column(String(50), nullable=True)
    contact_quality_score = Column(Float, default=0.0, nullable=False)
    is_deliverable = Column(Boolean, default=False, nullable=False)


class IntentSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "intent_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    intent_type = Column(String(100), nullable=False, index=True)
    total_signals = Column(Integer, default=0, nullable=False)
    average_strength = Column(Float, default=0.0, nullable=False)
    active_companies_count = Column(Integer, default=0, nullable=False)


class QualitySnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quality_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    overall_quality_score = Column(Float, default=0.0, nullable=False)
    completeness_score = Column(Float, default=0.0, nullable=False)
    freshness_score = Column(Float, default=0.0, nullable=False)
    verification_rate = Column(Float, default=0.0, nullable=False)
    conflict_count = Column(Integer, default=0, nullable=False)


class ScoreSnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "score_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    company_id = Column(String(36), nullable=False, index=True)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    lead_priority_score = Column(Float, default=0.0, nullable=False)
    intent_score = Column(Float, default=0.0, nullable=False)
    icp_fit_score = Column(Float, default=0.0, nullable=False)
    priority_tier = Column(String(50), nullable=False)


# 3. Predictive Intelligence Models
class Prediction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "predictions"

    workspace_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(36), nullable=False, index=True)
    prediction_type = Column(String(50), nullable=False, index=True)
    
    predicted_value = Column(String(255), nullable=False)
    probability = Column(Float, default=0.0, nullable=False)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    
    feature_contributions = Column(JSON, default=dict, nullable=False)
    evidence_references = Column(JSON, default=list, nullable=False)
    
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_pred_ws_entity_type", "workspace_id", "entity_type", "entity_id", "prediction_type"),
    )


class PredictionEvaluation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prediction_evaluations"

    workspace_id = Column(String(36), nullable=False, index=True)
    prediction_id = Column(String(36), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, index=True)
    actual_outcome = Column(String(255), nullable=False)
    is_accurate = Column(Boolean, nullable=False)
    calibration_error = Column(Float, default=0.0, nullable=False)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class PredictionOutcome(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prediction_outcomes"

    workspace_id = Column(String(36), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=False)
    precision = Column(Float, default=0.0, nullable=False)
    recall = Column(Float, default=0.0, nullable=False)
    brier_score = Column(Float, default=0.0, nullable=False)
    sample_size = Column(Integer, default=0, nullable=False)
    evaluated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ModelDriftEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "model_drift_events"

    workspace_id = Column(String(36), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    metric_name = Column(String(100), nullable=False)
    baseline_value = Column(Float, default=0.0, nullable=False)
    current_value = Column(Float, default=0.0, nullable=False)
    drift_magnitude = Column(Float, default=0.0, nullable=False)
    severity = Column(String(50), default="MEDIUM", nullable=False)
    action_required = Column(String(255), nullable=True)


# 4. Safe Analytics Queries & Saved Views
class AnalyticsView(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_views"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    dashboard_type = Column(String(50), default="EXECUTIVE", nullable=False)
    config = Column(JSON, default=dict, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)


class AnalyticsQuery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_queries"

    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    query_dsl = Column(JSON, default=dict, nullable=False)
    name = Column(String(255), nullable=True)


class AnalyticsQueryExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_query_executions"

    workspace_id = Column(String(36), nullable=False, index=True)
    query_id = Column(String(36), nullable=True, index=True)
    execution_mode = Column(String(50), default="SYNC", nullable=False)
    status = Column(String(50), default="COMPLETED", nullable=False)
    duration_ms = Column(Integer, default=0, nullable=False)
    rows_returned = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)


# 5. Executive & Operational Reports
class AnalyticsReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_reports"

    workspace_id = Column(String(36), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    report_type = Column(String(50), default="EXECUTIVE_INTELLIGENCE", nullable=False)
    description = Column(Text, nullable=True)
    schedule = Column(String(50), default="WEEKLY", nullable=False)
    parameters = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class AnalyticsReportVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_report_versions"

    report_id = Column(String(36), ForeignKey("analytics_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    definition_snapshot = Column(JSON, default=dict, nullable=False)


class AnalyticsReportExecution(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_report_executions"

    workspace_id = Column(String(36), nullable=False, index=True)
    report_id = Column(String(36), ForeignKey("analytics_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    generated_by = Column(String(36), nullable=True)
    status = Column(String(50), default="COMPLETED", nullable=False)
    data_snapshot = Column(JSON, default=dict, nullable=False)
    export_format = Column(String(50), default="JSON", nullable=False)
    export_file_path = Column(String(1000), nullable=True)
    execution_time_ms = Column(Integer, default=0, nullable=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# 6. Anomalies & Trends
class AnalyticsAnomaly(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_anomalies"

    workspace_id = Column(String(36), nullable=False, index=True)
    metric_code = Column(String(100), nullable=False, index=True)
    target_entity = Column(String(100), nullable=True)
    baseline_value = Column(Float, default=0.0, nullable=False)
    observed_value = Column(Float, default=0.0, nullable=False)
    difference_percentage = Column(Float, default=0.0, nullable=False)
    confidence = Column(Float, default=0.95, nullable=False)
    severity = Column(String(50), default="HIGH", nullable=False)
    description = Column(Text, nullable=False)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class AnalyticsTrend(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_trends"

    workspace_id = Column(String(36), nullable=False, index=True)
    topic = Column(String(100), nullable=False, index=True)  # INTENT, TECHNOLOGY, QUALITY, LEAD_VOLUME
    direction = Column(String(50), default="STABLE", nullable=False)
    velocity = Column(Float, default=0.0, nullable=False)
    time_window = Column(String(50), default="30_DAYS", nullable=False)
    evidence_count = Column(Integer, default=0, nullable=False)
    details = Column(JSON, default=dict, nullable=False)


# 7. Costs & Operational Capacity
class AnalyticsCostRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_cost_records"

    workspace_id = Column(String(36), nullable=False, index=True)
    campaign_id = Column(String(36), nullable=True, index=True)
    source_name = Column(String(100), nullable=True, index=True)
    cost_category = Column(String(50), default="AI_INFERENCE", nullable=False)
    cost_amount = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    tokens_consumed = Column(Integer, default=0, nullable=False)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class AnalyticsCapacitySnapshot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "analytics_capacity_snapshots"

    workspace_id = Column(String(36), nullable=False, index=True)
    worker_utilization_pct = Column(Float, default=0.0, nullable=False)
    queue_depth = Column(Integer, default=0, nullable=False)
    browser_concurrency = Column(Integer, default=0, nullable=False)
    api_quota_used_pct = Column(Float, default=0.0, nullable=False)
    database_pool_pct = Column(Float, default=0.0, nullable=False)
    captured_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

