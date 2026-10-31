from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.db.session import get_sync_db
from app.models.tenant import Workspace
from app.models.user import User
from app.models.analytics import (
    AnalyticsMetric,
    AnalyticsMetricVersion,
    AnalyticsDimension,
    AnalyticsView,
    AnalyticsReport,
    AnalyticsReportExecution,
    AnalyticsAnomaly,
    AnalyticsTrend,
    Prediction,
    LeadSnapshot,
    ScoreSnapshot
)
from app.services.permission_service import get_active_workspace, get_current_user

from packages.analytics.dsl import AnalyticsDSLQuery, AnalyticsDSLError
from packages.analytics.snapshot_engine import SnapshotEngine
from packages.analytics.intelligence_analytics import IntelligenceAnalyticsService
from packages.analytics.predictive_engine import PredictiveEngine
from packages.analytics.anomaly_detector import AnomalyAndTrendDetector
from packages.analytics.report_generator import ReportGenerator
from packages.analytics.nl_query import NaturalLanguageAnalytics


analytics_router = APIRouter(prefix="/analytics", tags=["Enterprise Analytics & Predictive Insights"])


# --- Pydantic Request Schemas ---

class QueryDSLRequest(BaseModel):
    entity: str = "companies"
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    group_by: List[str] = Field(default_factory=list)
    aggregations: List[Dict[str, Any]] = Field(default_factory=list)
    time_range: Optional[str] = "last_30_days"
    order_by: Optional[str] = "created_at"
    order_direction: Optional[str] = "desc"
    compare_period: Optional[bool] = False
    limit: Optional[int] = 50
    offset: Optional[int] = 0


class NLQueryRequest(BaseModel):
    prompt: str


class CreateMetricRequest(BaseModel):
    metric_code: str
    name: str
    description: Optional[str] = None
    category: str = "LEAD"
    metric_type: str = "RATE"
    formula: str


class CreateViewRequest(BaseModel):
    name: str
    dashboard_type: str = "EXECUTIVE"
    config: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class CreateReportRequest(BaseModel):
    name: str
    report_type: str = "EXECUTIVE_INTELLIGENCE"
    schedule: str = "WEEKLY"
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PredictRequest(BaseModel):
    company_id: str


# --- 1. Centralized KPIs & Metrics ---

@analytics_router.get("/kpis")
def list_kpis(
    category: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists centralized KPI definitions to prevent conflicting metric logic across dashboards."""
    q = db.query(AnalyticsMetric).filter(AnalyticsMetric.workspace_id == ws.id)
    if category:
        q = q.filter(AnalyticsMetric.category == category.upper())
    metrics = q.all()
    if not metrics:
        # Default built-in KPIs
        return [
            {
                "metric_code": "HIGH_PRIORITY_LEAD_RATE",
                "name": "High Priority Lead Rate",
                "category": "LEAD",
                "formula": "HIGH_PRIORITY_LEADS / TOTAL_LEADS",
                "metric_type": "PERCENTAGE"
            },
            {
                "metric_code": "EVIDENCE_COVERAGE_RATE",
                "name": "Evidence Coverage Rate",
                "category": "QUALITY",
                "formula": "LEADS_WITH_CORROBORATION / TOTAL_LEADS",
                "metric_type": "PERCENTAGE"
            },
            {
                "metric_code": "SOURCE_EFFICIENCY_SCORE",
                "name": "Source Intelligence Efficiency",
                "category": "SOURCE",
                "formula": "USEFUL_INTELLIGENCE_POINTS / RESEARCH_COST",
                "metric_type": "RATIO"
            }
        ]
    return metrics


@analytics_router.post("/kpis", status_code=status.HTTP_201_CREATED)
def create_kpi(
    req: CreateMetricRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Registers a standardized, versioned KPI definition."""
    metric = AnalyticsMetric(
        workspace_id=ws.id,
        metric_code=req.metric_code.upper(),
        name=req.name,
        description=req.description,
        category=req.category.upper(),
        metric_type=req.metric_type.upper(),
        formula=req.formula,
        owner=user.email or "analyst",
        is_active=True
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)

    ver = AnalyticsMetricVersion(
        metric_id=metric.id,
        version_number=1,
        formula=req.formula,
        change_reason="Initial registration",
        created_by=user.id
    )
    db.add(ver)
    db.commit()
    return metric


# --- 2. Lead Intelligence & Funnel Analytics ---

@analytics_router.get("/leads")
def get_lead_analytics(
    campaign_id: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lead Intelligence Funnel, stage conversion rates, and velocity."""
    svc = IntelligenceAnalyticsService(db)
    funnel = svc.get_lead_funnel(workspace_id=ws.id, campaign_id=campaign_id)
    aging = svc.get_lead_aging(workspace_id=ws.id)
    priority = svc.get_priority_and_icp_analytics(workspace_id=ws.id)
    return {
        "funnel": funnel,
        "aging": aging,
        "priority_and_icp": priority
    }


# --- 3. Intent & Signals Analytics ---

@analytics_router.get("/intent")
def get_intent_analytics(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Intent categories, timeline trends, and temporal decay."""
    svc = IntelligenceAnalyticsService(db)
    return svc.get_intent_analytics(workspace_id=ws.id)


@analytics_router.get("/signals")
def get_signal_analytics(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Signal effectiveness score and evidence coverage metrics."""
    svc = IntelligenceAnalyticsService(db)
    return svc.get_signal_and_evidence_analytics(workspace_id=ws.id)


# --- 4. Source Intelligence Analytics ---

@analytics_router.get("/sources")
def get_source_analytics(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Source Intelligence Efficiency ranking and cost-utility ratios."""
    svc = IntelligenceAnalyticsService(db)
    return svc.get_source_analytics(workspace_id=ws.id)


# --- 5. Contact, Decision-Maker & Buying Committee Analytics ---

@analytics_router.get("/contacts")
def get_contact_analytics(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Decision-maker coverage and buying committee completeness."""
    svc = IntelligenceAnalyticsService(db)
    return svc.get_contact_and_buying_committee_analytics(workspace_id=ws.id)


# --- 6. Geographic & Australian Market Intelligence ---

@analytics_router.get("/geography")
def get_geography_analytics(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Geographic breakdown with Australia-specific lead intelligence."""
    svc = IntelligenceAnalyticsService(db)
    return svc.get_geographic_and_industry_analytics(workspace_id=ws.id)


# --- 7. Predictive Analytics & Evaluations ---

@analytics_router.post("/predictions/lead-priority")
def predict_lead_priority(
    req: PredictRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Computes bounded lead priority probability with explainable features."""
    pred_engine = PredictiveEngine(db)
    return pred_engine.predict_lead_priority_probability(workspace_id=ws.id, company_id=req.company_id)


@analytics_router.post("/predictions/staleness-risk")
def predict_staleness_risk(
    req: PredictRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Estimates probability that company records will become stale."""
    pred_engine = PredictiveEngine(db)
    return pred_engine.predict_staleness_risk(workspace_id=ws.id, company_id=req.company_id)


# --- 8. Anomalies & Trends ---

@analytics_router.get("/anomalies")
def list_anomalies(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists statistically significant anomalies detected across collection and research."""
    return db.query(AnalyticsAnomaly).filter(
        AnalyticsAnomaly.workspace_id == ws.id
    ).order_by(desc(AnalyticsAnomaly.detected_at)).limit(50).all()


@analytics_router.get("/trends")
def list_trends(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists statistical trends across intent, tech adoption, and lead volume."""
    return db.query(AnalyticsTrend).filter(
        AnalyticsTrend.workspace_id == ws.id
    ).order_by(desc(AnalyticsTrend.created_at)).limit(50).all()


# --- 9. Snapshots & Historical Evolution ---

@analytics_router.post("/snapshots/capture", status_code=status.HTTP_201_CREATED)
def trigger_snapshot_capture(
    campaign_id: Optional[str] = None,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Captures an on-demand historical snapshot."""
    engine = SnapshotEngine(db)
    lead_snap = engine.capture_lead_snapshot(workspace_id=ws.id, campaign_id=campaign_id)
    engine.capture_company_snapshots(workspace_id=ws.id)
    engine.capture_intent_snapshot(workspace_id=ws.id, campaign_id=campaign_id)
    return {"status": "success", "snapshot_id": lead_snap.id, "captured_at": lead_snap.snapshot_date.isoformat()}


@analytics_router.get("/snapshots/history/{company_id}")
def get_score_history(
    company_id: str,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Retrieves chronological score history for an entity."""
    engine = SnapshotEngine(db)
    return engine.get_score_history(workspace_id=ws.id, company_id=company_id)


# --- 10. Safe Analytics DSL Queries & NL Analytics ---

@analytics_router.post("/query")
def execute_dsl_query(
    req: QueryDSLRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Executes a safe Analytics DSL query with parameter whitelisting and tenant isolation."""
    dsl_engine = AnalyticsDSLQuery(db)
    try:
        return dsl_engine.execute(workspace_id=ws.id, query_dsl=req.model_dump())
    except AnalyticsDSLError as e:
        raise HTTPException(status_code=400, detail=str(e))


@analytics_router.post("/explain")
def explain_dsl_query(
    req: QueryDSLRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Returns estimated complexity, plan, and safe interpretation for a DSL query."""
    dsl_engine = AnalyticsDSLQuery(db)
    try:
        return dsl_engine.explain(workspace_id=ws.id, query_dsl=req.model_dump())
    except AnalyticsDSLError as e:
        raise HTTPException(status_code=400, detail=str(e))


@analytics_router.post("/nl-query")
def natural_language_query(
    req: NLQueryRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Parses natural-language business question into safe Analytics DSL and executes it."""
    nl_engine = NaturalLanguageAnalytics(db)
    return nl_engine.execute_nl_query(workspace_id=ws.id, prompt=req.prompt)


# --- 11. Saved Analytics Views ---

@analytics_router.get("/views")
def list_views(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists saved analytics views."""
    return db.query(AnalyticsView).filter(
        and_(AnalyticsView.workspace_id == ws.id, AnalyticsView.user_id == user.id)
    ).all()


@analytics_router.post("/views", status_code=status.HTTP_201_CREATED)
def create_view(
    req: CreateViewRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Saves custom dashboard view configuration."""
    view = AnalyticsView(
        workspace_id=ws.id,
        user_id=user.id,
        name=req.name,
        dashboard_type=req.dashboard_type,
        config=req.config,
        is_default=req.is_default
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return view


# --- 12. Automated Reports & Exports ---

@analytics_router.get("/reports")
def list_reports(
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Lists configured enterprise reports."""
    return db.query(AnalyticsReport).filter(AnalyticsReport.workspace_id == ws.id).all()


@analytics_router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(
    req: CreateReportRequest,
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Registers a scheduled report definition."""
    gen = ReportGenerator(db)
    return gen.create_or_get_report_definition(
        workspace_id=ws.id,
        name=req.name,
        report_type=req.report_type,
        schedule=req.schedule,
        parameters=req.parameters
    )


@analytics_router.post("/reports/{report_id}/run")
def run_report(
    report_id: str,
    export_format: str = Query("JSON", regex="^(JSON|CSV|XLSX|GOOGLE_SHEETS)$"),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Executes a report and preserves historical data snapshot."""
    gen = ReportGenerator(db)
    return gen.run_report(
        workspace_id=ws.id,
        report_id=report_id,
        generated_by=user.id,
        export_format=export_format
    )


@analytics_router.get("/reports/executions/{execution_id}/export")
def export_report_execution(
    execution_id: str,
    format_type: str = Query("CSV", regex="^(CSV|JSON)$"),
    ws: Workspace = Depends(get_active_workspace),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Exports an execution snapshot to CSV or JSON with formula injection safety."""
    execution = db.query(AnalyticsReportExecution).filter(
        and_(AnalyticsReportExecution.workspace_id == ws.id, AnalyticsReportExecution.id == execution_id)
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    gen = ReportGenerator(db)
    content = gen.export_execution(execution, format_type=format_type)

    media_type = "text/csv" if format_type == "CSV" else "application/json"
    filename = f"report_execution_{execution_id}.{'csv' if format_type == 'CSV' else 'json'}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
