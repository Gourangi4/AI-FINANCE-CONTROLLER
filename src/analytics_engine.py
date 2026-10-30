from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path
import json

from ml_anomaly_engine import RunAnomalyDetector


AnalyticsRecord = dict[str, Any]

TREND_CHANGE_RATIO = 0.10

RUN_SPIKE_RATIO = 1.30
CRITICAL_RISK_SPIKE_RATIO = 2.00

VENDOR_RISK_CURRENCY_UNIT = 10_000.0
VENDOR_EXCEPTION_WEIGHT = 0.10
VENDOR_FREQUENCY_WEIGHT = 10.0
VENDOR_RISK_LEVELS = ((8.0, "critical"), (5.0, "high"), (2.0, "medium"))

RANKING_RISK_CURRENCY_UNIT = 1_000.0
RANKING_EXCEPTION_DIVISOR = 10.0


class AnalyticsEngine:
    
    def __init__(self, history_path: Path | None = None) -> None:
        self.history_path = history_path or Path("data/analytics_history.json")
        self.history: list[AnalyticsRecord] = self._load_history()
    
    def _load_history(self) -> list[AnalyticsRecord]:
        """Load persisted run history, or return an empty history if absent."""
        if self.history_path.exists():
            return json.loads(self.history_path.read_text())
        return []
    
    def _save_history(self) -> None:
        """Write the current run history as human-readable JSON."""
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(json.dumps(self.history, indent=2))
    
    def record_run(self, report: AnalyticsRecord) -> AnalyticsRecord:
        """Record one completed reconciliation report for future comparisons."""
        timestamp = datetime.now().isoformat()
        
        entry = {
            "timestamp": timestamp,
            "summary": report.get("summary", {}),
            "exception_count": len(report.get("exceptions", [])),
            "total_risk": report.get("summary", {}).get("total_amount_at_risk", 0),
            "vendor_summary": self._analyze_vendors(report.get("exceptions", [])),
            "exception_types": self._count_exception_types(report.get("exceptions", [])),
        }
        
        self.history.append(entry)
        self._save_history()
        return entry
    
    def _analyze_vendors(self, exceptions: list[AnalyticsRecord]) -> dict[str, AnalyticsRecord]:
        """Aggregate exception count, monetary exposure, and types by vendor."""
        vendor_stats = defaultdict(lambda: {"count": 0, "total_risk": 0, "types": {}})
        
        for exc in exceptions:
            vendor = exc.get("vendor_name", "Unknown")
            vendor_stats[vendor]["count"] += 1
            vendor_stats[vendor]["total_risk"] += exc.get("amount_at_risk", 0)
            
            exc_type = exc.get("exception_type", "Unknown")
            vendor_stats[vendor]["types"][exc_type] = vendor_stats[vendor]["types"].get(exc_type, 0) + 1
        
        return dict(vendor_stats)
    
    def _count_exception_types(self, exceptions: list[AnalyticsRecord]) -> dict[str, AnalyticsRecord]:
        """Aggregate exception count, exposure, and severity by exception type."""
        type_counts = defaultdict(lambda: {"count": 0, "total_risk": 0, "severity": {}})
        
        for exc in exceptions:
            exc_type = exc.get("exception_type", "Unknown")
            type_counts[exc_type]["count"] += 1
            type_counts[exc_type]["total_risk"] += exc.get("amount_at_risk", 0)
            
            severity = exc.get("severity", "Unknown")
            type_counts[exc_type]["severity"][severity] = type_counts[exc_type]["severity"].get(severity, 0) + 1
        
        return dict(type_counts)
    
    def get_trends(self, days: int = 30) -> AnalyticsRecord:
        """Return daily run points and a 10%-tolerant exception-count trend."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent_runs = [r for r in self.history if r["timestamp"] >= cutoff]
        
        if not recent_runs:
            return {
                "trend": [],
                "avg_exceptions": 0,
                "avg_risk": 0,
                "trend_direction": "stable"
            }
        
        trend_points = []
        for run in recent_runs:
            trend_points.append({
                "date": run["timestamp"][:10],
                "exceptions": run["exception_count"],
                "risk": run["total_risk"]
            })
        
        if len(trend_points) > 1:
            first_avg = sum(r["exceptions"] for r in trend_points[:len(trend_points)//2]) / max(1, len(trend_points)//2)
            last_avg = sum(r["exceptions"] for r in trend_points[len(trend_points)//2:]) / max(1, len(trend_points) - len(trend_points)//2)
            
            if last_avg > first_avg * (1 + TREND_CHANGE_RATIO):
                direction = "increasing"
            elif last_avg < first_avg * (1 - TREND_CHANGE_RATIO):
                direction = "decreasing"
            else:
                direction = "stable"
        else:
            direction = "stable"
        
        avg_exceptions = sum(r["exception_count"] for r in recent_runs) / len(recent_runs)
        avg_risk = sum(r["total_risk"] for r in recent_runs) / len(recent_runs)
        
        return {
            "trend": trend_points,
            "avg_exceptions": round(avg_exceptions, 1),
            "avg_risk": round(avg_risk, 2),
            "trend_direction": direction,
            "data_points": len(trend_points)
        }
    
    def get_vendor_rankings(self, limit: int = 10, metric: str = "risk") -> list[AnalyticsRecord]:
        if not self.history:
            return []
        
        vendor_stats = defaultdict(lambda: {"count": 0, "total_risk": 0, "runs": 0})
        
        for run in self.history:
            vendor_data = run.get("vendor_summary", {})
            for vendor, stats in vendor_data.items():
                vendor_stats[vendor]["count"] += stats.get("count", 0)
                vendor_stats[vendor]["total_risk"] += stats.get("total_risk", 0)
                vendor_stats[vendor]["runs"] += 1
        
        if metric == "risk":
            sorted_vendors = sorted(vendor_stats.items(), key=lambda x: x[1]["total_risk"], reverse=True)
        else:
            sorted_vendors = sorted(vendor_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        
        result = []
        for vendor, stats in sorted_vendors[:limit]:
            result.append({
                "vendor": vendor,
                "exception_count": stats["count"],
                "total_risk": round(stats["total_risk"], 2),
                "avg_risk_per_exception": round(stats["total_risk"] / max(1, stats["count"]), 2),
                "occurrences_in_runs": stats["runs"],
                "risk_score": round(
                    (stats["total_risk"] / RANKING_RISK_CURRENCY_UNIT)
                    * (stats["count"] / RANKING_EXCEPTION_DIVISOR),
                    2,
                ),
            })
        
        return result
    
    def get_exception_patterns(self) -> dict[str, AnalyticsRecord]:
        if not self.history:
            return {}
        
        patterns = defaultdict(lambda: {"count": 0, "total_risk": 0, "severity_dist": {}})
        
        for run in self.history:
            exc_types = run.get("exception_types", {})
            for exc_type, data in exc_types.items():
                patterns[exc_type]["count"] += data.get("count", 0)
                patterns[exc_type]["total_risk"] += data.get("total_risk", 0)
                
                severity_dist = data.get("severity", {})
                for sev, count in severity_dist.items():
                    patterns[exc_type]["severity_dist"][sev] = patterns[exc_type]["severity_dist"].get(sev, 0) + count
        
        result = {}
        total_exceptions = sum(p["count"] for p in patterns.values())
        
        for exc_type, data in sorted(patterns.items(), key=lambda x: x[1]["total_risk"], reverse=True):
            result[exc_type] = {
                "frequency": data["count"],
                "percentage": round(100 * data["count"] / max(1, total_exceptions), 1),
                "total_risk": round(data["total_risk"], 2),
                "avg_risk": round(data["total_risk"] / max(1, data["count"]), 2),
                "severity_distribution": data["severity_dist"]
            }
        
        return result
    
    def detect_anomalies(self, current_report: AnalyticsRecord) -> AnalyticsRecord:
        history = self.history
        if history and self._matches_report(history[-1], current_report):
            history = history[:-1]

        if len(history) < 2:
            return {"anomalies": [], "baseline_established": False}
        
        recent_runs = history[-10:] if len(history) >= 10 else history
        
        baseline_exceptions = sum(r["exception_count"] for r in recent_runs) / len(recent_runs)
        baseline_risk = sum(r["total_risk"] for r in recent_runs) / len(recent_runs)
        
        current_exceptions = len(current_report.get("exceptions", []))
        current_risk = current_report.get("summary", {}).get("total_amount_at_risk", 0)
        
        anomalies = []
        
        if current_exceptions > baseline_exceptions * RUN_SPIKE_RATIO:
            anomalies.append({
                "type": "exception_spike",
                "severity": "high",
                "message": f"Exception count ({current_exceptions}) is {round((current_exceptions/baseline_exceptions - 1)*100)}% above baseline ({round(baseline_exceptions)})",
                "value": current_exceptions,
                "baseline": round(baseline_exceptions, 1)
            })
        
        if current_risk > baseline_risk * RUN_SPIKE_RATIO:
            anomalies.append({
                "type": "risk_spike",
                "severity": "critical" if current_risk > baseline_risk * CRITICAL_RISK_SPIKE_RATIO else "high",
                "message": f"Risk amount (${current_risk:,.0f}) is {round((current_risk/baseline_risk - 1)*100)}% above baseline (${baseline_risk:,.0f})",
                "value": round(current_risk, 2),
                "baseline": round(baseline_risk, 2)
            })
        
        current_vendors = set(exc["vendor_name"] for exc in current_report.get("exceptions", []))
        historical_vendors = set()
        for run in recent_runs:
            historical_vendors.update(run.get("vendor_summary", {}).keys())
        
        new_vendors = current_vendors - historical_vendors
        if new_vendors:
            anomalies.append({
                "type": "new_vendor_exceptions",
                "severity": "medium",
                "message": f"New vendors with exceptions: {', '.join(list(new_vendors)[:3])}",
                "vendors": list(new_vendors)
            })

        ml_result = RunAnomalyDetector().analyze(history, current_report)
        if ml_result.get("is_anomaly"):
            anomalies.append({
                "type": "ml_multivariate_outlier",
                "severity": "high",
                "message": "ML anomaly detection found this run unusual across exception volume, risk, touchless rate, and high-severity findings.",
                "model": "IsolationForest",
                "anomaly_score": ml_result["anomaly_score"],
                "threshold": ml_result["threshold"],
            })
        
        return {
            "anomalies": anomalies,
            "baseline_established": len(self.history) >= 2,
            "baseline_exceptions": round(baseline_exceptions, 1),
            "baseline_risk": round(baseline_risk, 2)
        }

    @staticmethod
    def _matches_report(entry: AnalyticsRecord, report: AnalyticsRecord) -> bool:
        """Return whether a just-persisted history entry represents ``report``."""
        summary = report.get("summary", {})
        return (
            entry.get("exception_count") == len(report.get("exceptions", []))
            and entry.get("total_risk") == summary.get("total_amount_at_risk")
        )
    
    def get_vendor_risk_score(self, vendor_name: str) -> AnalyticsRecord:
        """Return an explainable, cumulative vendor-prioritization score.

        The score combines total exposure, exception volume, and the share of
        historical runs in which the vendor appeared.  It is for triage only,
        not a prediction of fraud, loss, or vendor performance.
        """
        vendor_data = defaultdict(lambda: {"count": 0, "total_risk": 0, "severity_count": {}})
        
        for run in self.history:
            vendor_summary = run.get("vendor_summary", {})
            if vendor_name in vendor_summary:
                v_data = vendor_summary[vendor_name]
                vendor_data[vendor_name]["count"] += v_data.get("count", 0)
                vendor_data[vendor_name]["total_risk"] += v_data.get("total_risk", 0)
        
        if vendor_name not in vendor_data:
            return {
                "vendor": vendor_name,
                "risk_score": 0,
                "risk_level": "low",
                "exception_count": 0,
                "total_risk": 0
            }
        
        data = vendor_data[vendor_name]
        
        frequency = len([r for r in self.history if vendor_name in r.get("vendor_summary", {})])
        frequency_factor = min(frequency / max(1, len(self.history)), 1.0)
        
        risk_score = (
            (data["total_risk"] / VENDOR_RISK_CURRENCY_UNIT)
            + (data["count"] * VENDOR_EXCEPTION_WEIGHT)
            + (frequency_factor * VENDOR_FREQUENCY_WEIGHT)
        )
        
        risk_level = next(
            (level for threshold, level in VENDOR_RISK_LEVELS if risk_score >= threshold),
            "low",
        )
        
        return {
            "vendor": vendor_name,
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "exception_count": data["count"],
            "total_risk": round(data["total_risk"], 2),
            "appearance_frequency": frequency
        }
    
    def get_dashboard_summary(self) -> AnalyticsRecord:
        """Return the dashboard-ready summary for the recorded run history."""
        if not self.history:
            return {
                "status": "no_data",
                "message": "No historical data available yet. Run reconciliation to start tracking trends."
            }
        
        latest_run = self.history[-1]
        trends = self.get_trends(30)
        vendors = self.get_vendor_rankings(5)
        patterns = self.get_exception_patterns()
        
        return {
            "status": "ready",
            "latest_run": latest_run["timestamp"],
            "total_runs": len(self.history),
            "trends": trends,
            "top_vendors": vendors,
            "exception_patterns": patterns,
            "current_metrics": {
                "total_exceptions": latest_run["exception_count"],
                "total_risk": latest_run["total_risk"],
                "touchless_rate": latest_run["summary"].get("touchless_rate_pct", 0),
            }
        }
