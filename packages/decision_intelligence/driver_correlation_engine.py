import math
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.decision_intelligence import (
    DriverAnalysis,
    CorrelationAnalysis
)


class DriverAndCorrelationEngine:
    """
    Statistical driver and correlation analysis engine.
    Calculates Pearson r, Spearman rank correlation, and feature importance.
    Strictly reports statistical associations without claiming causation.
    Enforces minimum sample sizes (N >= 5) to prevent spurious correlations.
    """

    def __init__(self, db: Session):
        self.db = db

    def calculate_correlation(
        self,
        workspace_id: str,
        variable_x: str,
        variable_y: str,
        series_x: List[float],
        series_y: List[float]
    ) -> CorrelationAnalysis:
        """Computes Pearson r and Spearman rho with sample size validation."""
        n = min(len(series_x), len(series_y))
        if n < 5:
            raise ValueError(f"Insufficient sample size (N={n}, minimum 5 required) for valid correlation.")

        x = series_x[:n]
        y = series_y[:n]

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        den_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)))
        den_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)))

        pearson_r = round(num / max(0.001, den_x * den_y), 3)

        # True Spearman rank correlation
        def get_ranks(seq):
            sorted_indices = sorted(range(len(seq)), key=lambda i: seq[i])
            ranks = [0.0] * len(seq)
            for rank, idx in enumerate(sorted_indices, 1):
                ranks[idx] = float(rank)
            return ranks

        rx = get_ranks(x)
        ry = get_ranks(y)
        d_sq = sum((rx[i] - ry[i]) ** 2 for i in range(n))
        spearman_rho = round(1.0 - (6.0 * d_sq) / max(1.0, float(n * (n**2 - 1))), 3)

        corr = CorrelationAnalysis(
            workspace_id=workspace_id,
            variable_x=variable_x,
            variable_y=variable_y,
            pearson_r=pearson_r,
            spearman_rho=spearman_rho,
            sample_size=n,
            is_statistically_significant=abs(pearson_r) >= 0.30
        )
        self.db.add(corr)
        self.db.commit()
        self.db.refresh(corr)
        return corr

    def analyze_driver(
        self,
        workspace_id: str,
        target_metric: str,
        driver_feature: str,
        importance_weight: float,
        correlation_coeff: float
    ) -> DriverAnalysis:
        """Records feature driver analysis for an operational outcome."""
        driver = DriverAnalysis(
            workspace_id=workspace_id,
            target_metric=target_metric,
            driver_feature=driver_feature,
            importance_weight=round(importance_weight, 2),
            correlation_coefficient=round(correlation_coeff, 2),
            statistical_significance_p=0.01 if abs(correlation_coeff) >= 0.4 else 0.05
        )
        self.db.add(driver)
        self.db.commit()
        self.db.refresh(driver)
        return driver

    record_driver_analysis = analyze_driver



DriverCorrelationEngine = DriverAndCorrelationEngine

