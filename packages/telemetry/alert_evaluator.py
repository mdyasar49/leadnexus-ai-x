"""
LeadNexus AI X - Phase 44: SLA Anomaly & Alert Rule Evaluator
Monitors time-series metric observations against dynamic threshold conditions (GT, LT, EQ, GTE, LTE)
and manages alert triggering and resolution states.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


class AlertRule:
    def __init__(
        self,
        rule_id: str,
        name: str,
        metric_name: str,
        condition: str,  # GT, LT, EQ, GTE, LTE
        threshold: float,
        severity: str = "WARNING",  # INFO, WARNING, CRITICAL
        is_active: bool = True,
    ):
        self.rule_id = rule_id
        self.name = name
        self.metric_name = metric_name
        self.condition = condition.upper()
        self.threshold = threshold
        self.severity = severity.upper()
        self.is_active = is_active

    def evaluates_true(self, observed_value: float) -> bool:
        """Evaluates whether an observed metric value breaches the threshold."""
        if not self.is_active:
            return False

        if self.condition == "GT":
            return observed_value > self.threshold
        elif self.condition == "GTE":
            return observed_value >= self.threshold
        elif self.condition == "LT":
            return observed_value < self.threshold
        elif self.condition == "LTE":
            return observed_value <= self.threshold
        elif self.condition == "EQ":
            return abs(observed_value - self.threshold) < 1e-6
        return False


class AlertEvent:
    def __init__(
        self,
        event_id: str,
        rule_id: str,
        metric_name: str,
        observed_value: float,
        threshold: float,
        severity: str,
        status: str = "TRIGGERED",  # TRIGGERED, RESOLVED, ACKNOWLEDGED
        details: Optional[Dict[str, Any]] = None,
    ):
        self.event_id = event_id
        self.rule_id = rule_id
        self.metric_name = metric_name
        self.observed_value = observed_value
        self.threshold = threshold
        self.severity = severity
        self.status = status
        self.details = details or {}
        self.triggered_at = datetime.now(timezone.utc).isoformat()
        self.resolved_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "rule_id": self.rule_id,
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
            "severity": self.severity,
            "status": self.status,
            "details": self.details,
            "triggered_at": self.triggered_at,
            "resolved_at": self.resolved_at,
        }


class AlertEvaluator:
    """Evaluates metrics against active rules and tracks alert events."""

    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._events: List[AlertEvent] = []

    def register_rule(
        self,
        name: str,
        metric_name: str,
        condition: str,
        threshold: float,
        severity: str = "WARNING",
        rule_id: Optional[str] = None,
    ) -> AlertRule:
        r_id = rule_id or str(uuid.uuid4())
        rule = AlertRule(
            rule_id=r_id,
            name=name,
            metric_name=metric_name,
            condition=condition,
            threshold=threshold,
            severity=severity,
        )
        self._rules[r_id] = rule
        return rule

    def evaluate_metric(self, metric_name: str, observed_value: float) -> List[AlertEvent]:
        """Evaluates all rules matching the metric and generates alert events if breached."""
        triggered: List[AlertEvent] = []
        for rule in self._rules.values():
            if rule.metric_name == metric_name and rule.evaluates_true(observed_value):
                event = AlertEvent(
                    event_id=str(uuid.uuid4()),
                    rule_id=rule.rule_id,
                    metric_name=metric_name,
                    observed_value=observed_value,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    details={"rule_name": rule.name, "condition": rule.condition},
                )
                self._events.append(event)
                triggered.append(event)
        return triggered

    def get_active_events(self) -> List[AlertEvent]:
        return [e for e in self._events if e.status == "TRIGGERED"]

    def resolve_event(self, event_id: str) -> Optional[AlertEvent]:
        for e in self._events:
            if e.event_id == event_id:
                e.status = "RESOLVED"
                e.resolved_at = datetime.now(timezone.utc).isoformat()
                return e
        return None
