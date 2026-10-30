from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from matching_engine import ReconciliationEngine
from explain_engine import ExceptionExplainer

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "data"


def run_pipeline(po_path: Path, inv_path: Path, pay_path: Path, out_path: Path = None) -> dict:
    t0 = time.time()

    read_opts = dict(dtype=str, keep_default_na=False, na_values=[])
    po_df = pd.read_csv(po_path, **read_opts)
    inv_df = pd.read_csv(inv_path, **read_opts)
    pay_df = pd.read_csv(pay_path, **read_opts)

    engine = ReconciliationEngine(po_df, inv_df, pay_df)
    all_results = engine.run()
    clean_matches = [e for e in all_results if e.exception_type == "CLEAN_MATCH"]
    exceptions = [e for e in all_results if e.exception_type != "CLEAN_MATCH"]

    explainer = ExceptionExplainer()
    rows = []
    for exc in exceptions:
        expl = explainer.explain(exc)
        rows.append({
            "exception_id": exc.exception_id,
            "exception_type": exc.exception_type,
            "vendor_name": exc.vendor_name,
            "po_id": exc.po_id,
            "invoice_id": exc.invoice_id,
            "payment_id": exc.payment_id,
            "po_amount": exc.po_amount,
            "invoice_amount": exc.invoice_amount,
            "payment_amount": exc.payment_amount,
            "amount_at_risk": exc.amount_at_risk,
            "match_method": exc.match_method,
            "facts": exc.facts,
            "severity": expl.severity,
            "status": expl.status,
            "auto_resolved": expl.auto_resolved,
            "ai_summary": expl.summary,
            "recommended_action": expl.recommended_action,
            "cited_clause_id": expl.cited_clause_id,
            "cited_clause_title": expl.cited_clause_title,
            "cited_clause_text": expl.cited_clause_text,
            "retrieval_similarity": expl.retrieval_similarity,
            "generation_backend": expl.generation_backend,
        })

    elapsed = round(time.time() - t0, 2)

    flagged = [r for r in rows if not r["auto_resolved"]]
    auto = [r for r in rows if r["auto_resolved"]]
    total_at_risk = round(sum(r["amount_at_risk"] for r in flagged), 2)

    by_type = {}
    for r in rows:
        by_type.setdefault(r["exception_type"], {"count": 0, "amount_at_risk": 0.0})
        by_type[r["exception_type"]]["count"] += 1
        by_type[r["exception_type"]]["amount_at_risk"] += r["amount_at_risk"]
    for k in by_type:
        by_type[k]["amount_at_risk"] = round(by_type[k]["amount_at_risk"], 2)

    by_severity = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for r in flagged:
        by_severity[r["severity"]] = by_severity.get(r["severity"], 0) + 1

    report = {
        "run_metadata": {
            "generated_at": pd.Timestamp.now("UTC").isoformat(),
            "processing_seconds": elapsed,
            "po_rows": len(po_df),
            "invoice_rows": len(inv_df),
            "payment_rows": len(pay_df),
            "embedding_backend": explainer.rag.backend_name,
            "generation_backend": explainer.generator_name,
        },
        "summary": {
            "total_lines_processed": len(clean_matches) + len(rows),
            "clean_matches": len(clean_matches),
            "total_exceptions": len(rows),
            "needs_review": len(flagged),
            "auto_resolved": len(auto),
            "total_amount_at_risk": total_at_risk,
            "touchless_rate_pct": round(100 * (len(clean_matches) + len(auto)) / max(1, len(clean_matches) + len(rows)), 1),
            "by_type": by_type,
            "by_severity": by_severity,
        },
        "exceptions": rows,
    }

    out_path = out_path or (OUT_DIR / "report.json")
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"Processed {len(po_df)} POs / {len(inv_df)} invoices / {len(pay_df)} payments "
          f"in {elapsed}s -> {len(rows)} findings ({len(flagged)} need review, "
          f"{len(auto)} auto-resolved). Report: {out_path}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--po", default=str(DATA_DIR / "purchase_orders.csv"))
    ap.add_argument("--inv", default=str(DATA_DIR / "invoices.csv"))
    ap.add_argument("--pay", default=str(DATA_DIR / "payments.csv"))
    ap.add_argument("--out", default=str(DATA_DIR / "report.json"))
    args = ap.parse_args()
    run_pipeline(Path(args.po), Path(args.inv), Path(args.pay), Path(args.out))
