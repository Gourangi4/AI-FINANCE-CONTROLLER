import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ml_anomaly_engine import RunAnomalyDetector  # noqa: E402


def report(exceptions, risk, touchless=70, high=1):
    return {
        "summary": {
            "total_exceptions": exceptions,
            "total_amount_at_risk": risk,
            "touchless_rate_pct": touchless,
            "by_severity": {"High": high, "Critical": 0},
        }
    }


class RunAnomalyDetectorTests(unittest.TestCase):
    def test_requires_sufficient_history(self):
        result = RunAnomalyDetector().analyze([], report(10, 1000))
        self.assertFalse(result["model_ready"])

    def test_flags_clear_multivariate_outlier(self):
        history = [
            {"summary": report(10 + index % 2, 1000 + index * 20, 70, 1)["summary"]}
            for index in range(12)
        ]
        result = RunAnomalyDetector().analyze(history, report(80, 500000, 5, 30))
        self.assertTrue(result["model_ready"])
        self.assertTrue(result["is_anomaly"])
        self.assertEqual(
            result["threshold_strategy"],
            "isolation_forest_auto_decision_boundary",
        )
        self.assertEqual(result["threshold"], -0.5)


if __name__ == "__main__":
    unittest.main()
