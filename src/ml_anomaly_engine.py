from __future__ import annotations

from math import log1p
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


MIN_TRAINING_RUNS = 8


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def report_features(report: dict) -> list[float]:
    """Create stable, scale-friendly features from a pipeline report."""
    summary = report.get("summary", report)
    severity = summary.get("by_severity", {})
    return [
        _number(summary.get("total_exceptions", summary.get("exception_count"))),
        log1p(max(0.0, _number(summary.get("total_amount_at_risk", summary.get("total_risk"))))),
        _number(summary.get("touchless_rate_pct")),
        _number(severity.get("High")) + _number(severity.get("Critical")),
    ]


def history_features(entry: dict) -> list[float]:
    """Extract the same features from a persisted analytics entry."""
    summary = dict(entry.get("summary", {}))
    summary.setdefault("exception_count", entry.get("exception_count", 0))
    summary.setdefault("total_risk", entry.get("total_risk", 0))
    return report_features(summary)


class RunAnomalyDetector:
    """Isolation Forest detector with deterministic, inspectable settings."""

    def analyze(self, history: list[dict], current_report: dict) -> dict:
        valid_history = [entry for entry in history if isinstance(entry, dict)]
        if len(valid_history) < MIN_TRAINING_RUNS:
            return {
                "model_ready": False,
                "training_runs": len(valid_history),
                "minimum_training_runs": MIN_TRAINING_RUNS,
                "reason": "More historical reconciliation runs are needed before ML anomaly detection is reliable.",
            }

        training = np.asarray([history_features(entry) for entry in valid_history], dtype=float)
        current = np.asarray([report_features(current_report)], dtype=float)
        scaler = StandardScaler().fit(training)
        model = IsolationForest(
            n_estimators=200,
            contamination="auto",
            random_state=42,
        ).fit(scaler.transform(training))

        current_score = float(model.score_samples(scaler.transform(current))[0])
        threshold = float(model.offset_)
        is_anomaly = bool(model.predict(scaler.transform(current))[0] == -1)

        return {
            "model_ready": True,
            "training_runs": len(valid_history),
            "features": {
                "exception_count": current[0][0],
                "log_amount_at_risk": round(float(current[0][1]), 4),
                "touchless_rate_pct": current[0][2],
                "high_or_critical_exceptions": current[0][3],
            },
            "anomaly_score": round(current_score, 4),
            "threshold": round(threshold, 4),
            "threshold_strategy": "isolation_forest_auto_decision_boundary",
            "is_anomaly": bool(is_anomaly),
        }
