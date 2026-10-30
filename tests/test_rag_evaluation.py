import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from evaluate_rag import evaluate_retrieval  # noqa: E402


class FakeRAG:
    def retrieve(self, query, top_k):
        return [{"clause_id": "4.2"}, {"clause_id": "4.1"}]


class RetrievalEvaluationTests(unittest.TestCase):
    def test_calculates_recall_and_reciprocal_rank(self):
        result = evaluate_retrieval(
            FakeRAG(),
            [
                {"query": "amount variance", "expected_clause_id": "4.2"},
                {"query": "missing PO", "expected_clause_id": "4.1"},
                {"query": "late", "expected_clause_id": "4.5"},
            ],
            top_k=2,
        )
        self.assertEqual(0.6667, result["recall_at_k"])
        self.assertEqual(0.5, result["mean_reciprocal_rank"])


if __name__ == "__main__":
    unittest.main()
