import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.analytics import (
    AnalyticsAnomaly,
    AnalyticsTrend,
    TrendDirection
)
from app.models.lead import IntentSignal, Company
from app.models.operations import SourceHealthEvent, ResearchCostEvent


class AnomalyAndTrendDetector:
    """
    Statistical anomaly and trend detection engine.
    Computes baseline deviations, confidence intervals, and trend velocities
    across signals, research volume, source health, and costs.
    """

    def __init__(self, db: Session):
        self.db = db

    def detect_anomalies(
        self,
        workspace_id: str,
        metric_code: str,
        observed_value: float,
        historical_values: List[float],
        time_window: str = "7_DAYS",
        target_entity: Optional[str] = None
    ) -> Optional[AnalyticsAnomaly]:
        """
        Calculates baseline mean and standard deviation. If observed value deviates
        significantly (|z| >= 2.0 and min sample size >= 5), logs an AnalyticsAnomaly.
        """
        if len(historical_values) < 5:
            # Avoid false alarms from tiny sample sets
            return None

        mean = sum(historical_values) / len(historical_values)
        variance = sum((x - mean) ** 2 for x in historical_values) / len(historical_values)
        std_dev = math.sqrt(variance)

        if std_dev < 0.001:
            std_dev = 1.0  # Avoid zero-division on flat histories

        z_score = (observed_value - mean) / std_dev
        diff_pct = round(((observed_value - mean) / max(0.1, mean)) * 100.0, 1)

        if abs(z_score) >= 2.0:
            severity = "CRITICAL" if abs(z_score) >= 3.0 else "HIGH"
            direction_word = "spike" if z_score > 0 else "drop"
            description = (
                f"Statistically significant {direction_word} detected in {metric_code} ({diff_pct}% vs baseline). "
                f"Observed: {observed_value}, Expected baseline: {round(mean, 1)} ± {round(std_dev * 2, 1)} (z={round(z_score, 2)})."
            )

            anomaly = AnalyticsAnomaly(
                workspace_id=workspace_id,
                metric_code=metric_code,
                target_entity=target_entity,
                baseline_value=round(mean, 2),
                observed_value=round(observed_value, 2),
                difference_percentage=diff_pct,
                confidence=0.95 if abs(z_score) >= 2.0 else 0.99,
                severity=severity,
                description=description,
                detected_at=datetime.now(timezone.utc)
            )
            self.db.add(anomaly)
            self.db.commit()
            self.db.refresh(anomaly)
            return anomaly

        return None

    def analyze_trend(
        self,
        workspace_id: str,
        topic: str,
        time_series_points: List[Tuple[datetime, float]],
        time_window: str = "30_DAYS"
    ) -> AnalyticsTrend:
        """
        Determines trend direction (INCREASING, DECREASING, STABLE, VOLATILE, EMERGING, DECLINING)
        and velocity based on linear slope and variance over the time window.
        """
        if not time_series_points or len(time_series_points) < 2:
            trend = AnalyticsTrend(
                workspace_id=workspace_id,
                topic=topic,
                direction=TrendDirection.STABLE.value,
                velocity=0.0,
                time_window=time_window,
                evidence_count=len(time_series_points),
                details={"status": "Insufficient data points"}
            )
            self.db.add(trend)
            self.db.commit()
            self.db.refresh(trend)
            return trend

        values = [p[1] for p in time_series_points]
        n = len(values)
        first_half_avg = sum(values[:n // 2]) / max(1, n // 2)
        second_half_avg = sum(values[n // 2:]) / max(1, len(values[n // 2:]))

        delta = second_half_avg - first_half_avg
        velocity = round(delta / max(1.0, first_half_avg) * 100.0, 1)

        if velocity > 25.0:
            direction = TrendDirection.INCREASING.value
        elif velocity < -25.0:
            direction = TrendDirection.DECREASING.value
        elif abs(velocity) <= 5.0:
            direction = TrendDirection.STABLE.value
        else:
            direction = TrendDirection.EMERGING.value if velocity > 0 else TrendDirection.DECLINING.value

        trend = AnalyticsTrend(
            workspace_id=workspace_id,
            topic=topic,
            direction=direction,
            velocity=velocity,
            time_window=time_window,
            evidence_count=n,
            details={
                "first_half_mean": round(first_half_avg, 2),
                "second_half_mean": round(second_half_avg, 2),
                "velocity_percentage": velocity
            }
        )
        self.db.add(trend)
        self.db.commit()
        self.db.refresh(trend)
        return trend

