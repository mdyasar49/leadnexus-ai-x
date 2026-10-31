"""
LeadNexus AI X - Phase 31: Enterprise Performance Engineering
Infrastructure Capacity Forecaster: Storage growth, resource trends, and saturation horizon forecasting.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.performance import InfrastructureCapacityForecast


class InfrastructureCapacityForecaster:
    """Forecasts platform storage and throughput demands to prevent resource saturation."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def generate_forecast(
        self,
        metric_name: str,
        current_value: float,
        monthly_growth_rate_pct: float = 15.0,
    ) -> InfrastructureCapacityForecast:
        rate = monthly_growth_rate_pct / 100.0
        # 30 days = 1 month
        projected_30d = round(current_value * (1.0 + rate), 2)
        # 90 days = 3 months compound
        projected_90d = round(current_value * ((1.0 + rate) ** 3), 2)

        forecast = InfrastructureCapacityForecast(
            id=str(uuid.uuid4()),
            metric_name=metric_name,
            current_value=round(current_value, 2),
            projected_30d=projected_30d,
            projected_90d=projected_90d,
            growth_rate_pct=round(monthly_growth_rate_pct, 2),
            calculated_at=datetime.now(timezone.utc),
        )
        self.db.add(forecast)
        self.db.commit()
        self.db.refresh(forecast)
        return forecast

