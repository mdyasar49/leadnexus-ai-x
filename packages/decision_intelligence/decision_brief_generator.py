from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc

from app.models.lead import Company, IntentSignal
from app.models.scoring import LeadScore
from app.models.source import ResearchSource
from app.models.decision_intelligence import (
    DecisionBrief,
    DecisionBriefVersion,
    DecisionBriefExecution,
    AnalyticsSegment,
    SegmentSnapshot,
    Forecast,
    SLAForecast,
    ResearchRecommendation,
    RecommendationStatus,
    Scorecard,
    ScorecardHealth
)
from packages.decision_intelligence.segmentation_engine import SegmentationEngine
from packages.decision_intelligence.recommendation_engine import RecommendationEngine
from packages.decision_intelligence.capacity_sla_engine import CapacitySLAEngine


class DecisionBriefGenerator:
    """
    Synthesizes and generates strategic decision intelligence briefs for executive and research leads.
    Compiles:
      - Executive summary & strategic recommendations
      - Emerging segments & market momentum
      - Intent trends & signal velocity
      - Source intelligence & attribution yield
      - Lead quality distribution
      - Operational & SLA risks
      - Forecasting highlights
      - Prioritized research action items
    """

    def __init__(self, db: Session):
        self.db = db
        self.seg_engine = SegmentationEngine(db)
        self.rec_engine = RecommendationEngine(db)
        self.sla_engine = CapacitySLAEngine(db)

    def generate_brief(
        self,
        workspace_id: str,
        title: Optional[str] = None
    ) -> DecisionBrief:
        now = datetime.now(timezone.utc)
        brief_title = title or f"Strategic Decision Intelligence Brief — {now.strftime('%Y-W%W')}"

        # 1. Emerging segments
        emerging_segments_data = self.seg_engine.detect_emerging_segments(workspace_id, min_growth_pct=10.0)
        emerging_summary = [
            {
                "segment_name": seg.name,
                "growth_pct": seg.growth_percentage,
                "momentum": seg.momentum_score,
                "intent_density": seg.intent_density,
                "size": seg.company_count
            }
            for seg in emerging_segments_data[:5]
        ]

        # 2. Intent trends
        intent_records = (
            self.db.query(IntentSignal)
            .filter(IntentSignal.workspace_id == workspace_id)
            .all()
        )
        type_counts: Dict[str, int] = {}
        for sig in intent_records:
            stype = getattr(sig, "signal_type", None) or getattr(sig, "intent_type", "GENERAL")
            type_counts[stype] = type_counts.get(stype, 0) + 1
        
        intent_trends = {
            "total_signals": len(intent_records),
            "signal_breakdown": type_counts,
            "high_intent_ratio": round(
                sum(1 for s in intent_records if getattr(s, "signal_strength", 0.0) >= 70.0) / max(1, len(intent_records)), 2
            )
        }

        # 3. Source performance
        sources = (
            self.db.query(ResearchSource)
            .limit(10)
            .all()
        )
        source_performance = [
            {
                "source_name": s.name,
                "source_type": s.source_type.value if hasattr(s.source_type, "value") else str(s.source_type),
                "reliability": getattr(s, "reliability_score", 1.0),
                "is_active": s.is_active
            }
            for s in sources
        ]

        # 4. Lead quality
        scores = (
            self.db.query(LeadScore)
            .filter(LeadScore.workspace_id == workspace_id)
            .all()
        )
        avg_readiness = (
            sum(getattr(sc, "buying_readiness_score", 50.0) for sc in scores) / max(1, len(scores))
            if scores else 0.0
        )
        lead_quality = {
            "total_scored_leads": len(scores),
            "avg_buying_readiness": round(avg_readiness, 2),
            "high_quality_count": sum(1 for sc in scores if getattr(sc, "buying_readiness_score", 0.0) >= 75.0)
        }

        # 5. Operational risks
        sla_risks = self.sla_engine.evaluate_sla_risks(workspace_id)
        operational_risks = [
            {
                "workload_type": risk.workload_type,
                "target_hours": risk.sla_target_hours,
                "forecasted_hours": risk.forecasted_completion_hours,
                "sla_status": risk.sla_status,
                "risk_status": risk.sla_status
            }
            for risk in sla_risks
        ]

        # 6. Forecast highlights
        recent_forecasts = (
            self.db.query(Forecast)
            .filter(Forecast.workspace_id == workspace_id)
            .order_by(desc(Forecast.created_at))
            .limit(3)
            .all()
        )
        forecast_highlights = [
            {
                "target_metric": f.target_metric,
                "horizon_days": f.forecast_horizon_days,
                "model_name": f.model_name,
                "points_count": len(f.points) if f.points else 0
            }
            for f in recent_forecasts
        ]

        # 7. Recommended investigations
        recs = (
            self.db.query(ResearchRecommendation)
            .filter(ResearchRecommendation.workspace_id == workspace_id)
            .limit(5)
            .all()
        )
        recommended_investigations = [
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

        # 8. Executive summary narrative
        top_segment_name = emerging_summary[0]["segment_name"] if emerging_summary else "N/A"
        executive_summary = (
            f"Strategic Intelligence Summary for {now.strftime('%B %d, %Y')}: "
            f"Evaluated {len(intent_records)} intent signals across {len(scores)} active leads. "
            f"Fastest-growing market cluster is '{top_segment_name}' with {emerging_summary[0]['growth_pct'] if emerging_summary else 0}% momentum. "
            f"Operational health indicates {len([r for r in operational_risks if r['risk_status'] != 'ON_TRACK'])} queues at SLA breach risk. "
            f"Recommended {len(recommended_investigations)} high-EIV research investigations to maximize intelligence yield."
        )

        brief = DecisionBrief(
            workspace_id=workspace_id,
            title=brief_title,
            executive_summary=executive_summary,
            emerging_segments=emerging_summary,
            intent_trends=intent_trends,
            source_performance=source_performance,
            lead_quality=lead_quality,
            operational_risks=operational_risks,
            forecast_highlights=forecast_highlights,
            recommended_investigations=recommended_investigations,
            generated_at=now
        )
        self.db.add(brief)
        self.db.commit()
        self.db.refresh(brief)

        # Store initial version snapshot
        version = DecisionBriefVersion(
            brief_id=brief.id,
            version=1,
            content_snapshot={
                "title": brief.title,
                "summary": brief.executive_summary,
                "emerging_segments": emerging_summary,
                "intent_trends": intent_trends,
                "operational_risks": operational_risks,
                "lead_quality": lead_quality
            }
        )
        self.db.add(version)
        self.db.commit()

        return brief

    def record_brief_execution(
        self,
        workspace_id: str,
        brief_id: str,
        executed_by: str = "system",
        export_format: str = "JSON"
    ) -> DecisionBriefExecution:
        execution = DecisionBriefExecution(
            workspace_id=workspace_id,
            brief_id=brief_id,
            executed_by=executed_by,
            export_format=export_format,
            executed_at=datetime.now(timezone.utc)
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution
