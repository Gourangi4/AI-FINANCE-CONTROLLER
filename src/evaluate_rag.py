from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_engine import PolicyRAG

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BENCHMARK = BASE_DIR / "data" / "rag_evaluation.json"


def evaluate_retrieval(rag, examples: list[dict], top_k: int = 3) -> dict:
    """Return Recall@k and MRR for labelled policy-retrieval examples."""
    if not examples:
        raise ValueError("The RAG evaluation benchmark contains no examples.")

    results, reciprocal_ranks = [], []
    for example in examples:
        expected = str(example["expected_clause_id"])
        hits = rag.retrieve(example["query"], top_k=top_k)
        retrieved_ids = [str(hit["clause_id"]) for hit in hits]
        rank = next((index + 1 for index, clause_id in enumerate(retrieved_ids) if clause_id == expected), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        results.append({
            "query": example["query"],
            "expected_clause_id": expected,
            "retrieved_clause_ids": retrieved_ids,
            "rank": rank,
            "passed": rank is not None,
        })

    return {
        "examples": len(examples),
        "top_k": top_k,
        "recall_at_k": round(sum(result["passed"] for result in results) / len(results), 4),
        "mean_reciprocal_rank": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate AP-policy RAG retrieval.")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--offline", action="store_true", help="Use deterministic TF-IDF embeddings instead of downloading an HF model.")
    args = parser.parse_args()

    examples = json.loads(args.benchmark.read_text(encoding="utf-8"))
    metrics = evaluate_retrieval(PolicyRAG(persist=False, force_tfidf=args.offline), examples, args.top_k)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
