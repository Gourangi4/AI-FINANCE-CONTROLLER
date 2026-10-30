# Ledger - AI Finance Controller

Ledger is a FastAPI application for accounts-payable controls. It performs
automated three-way reconciliation of purchase orders, invoices, and payments,
then presents audit-ready findings, policy evidence, analytics, and exports.

## Features

- Deterministic three-way reconciliation with missing-record, amount-mismatch,
  duplicate-invoice, unmatched-payment, and late-payment controls.
- Policy-grounded explanations using retrieval-augmented generation (RAG), with
  a transparent offline fallback when model downloads are unavailable.
- An upload-first dashboard that keeps each browser session's report and
  analytics history isolated.
- Run trends, vendor rankings, exception patterns, and rule-based alerts.
- Multivariate anomaly detection over exception volume, exposure, touchless
  rate, and high/critical findings. The detector is advisory only; it never
  changes an accounting decision or an exception severity.
- PDF, Excel, JSON, and optional email report exports.

## Required input files

Upload UTF-8 CSV files containing the following headers.

| File | Required columns |
| --- | --- |
| `purchase_orders.csv` | `po_id`, `vendor_name`, `vendor_code`, `po_date`, `po_amount`, `currency`, `approver`, `payment_terms_days` |
| `invoices.csv` | `invoice_id`, `po_id`, `vendor_name`, `vendor_code`, `invoice_date`, `invoice_amount`, `currency`, `due_date` |
| `payments.csv` | `payment_id`, `invoice_id`, `vendor_name`, `vendor_code`, `payment_date`, `payment_amount`, `currency`, `payment_method` |

Synthetic files and their expected findings are included in `data/`.

## Run locally

Python 3.11 or later is recommended.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app:app --reload --port 8000
```

Open <http://localhost:8000> and upload the three extracts. If PowerShell
blocks virtual-environment activation, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for the current
terminal first.

## How decisions are made

Matching, exception type, severity, and auto-resolution are deterministic and
reproducible. RAG retrieves the most relevant clause from
`policies/ap_policy_manual.md` to explain a finding; it does not decide the
financial control result. When Hugging Face models are available, Ledger uses
`sentence-transformers/all-MiniLM-L6-v2` for embeddings and
`google/flan-t5-base` for explanations. Otherwise it uses TF-IDF retrieval and
a deterministic, policy-grounded template, which the UI identifies as fallback
mode.

## API highlights

| Endpoint | Purpose |
| --- | --- |
| `POST /api/upload-and-run` | Upload the three CSV files and create a reconciliation report. |
| `GET /api/report` | Retrieve the current session's report. |
| `GET /api/export/{pdf,excel,json}` | Download an export of the current report. |
| `POST /api/export/email` | Send an export when email settings are configured. |
| `GET /api/analytics/{summary,trends,vendors,patterns,anomalies}` | Retrieve dashboard analytics for the current session. |
| `GET /api/analytics/vendor/{vendor_name}` | Retrieve an explainable vendor-prioritization score. |

## Tests

Install the requirements, then run:

```powershell
python -m unittest discover -s tests -v
```

## Project layout

```text
app.py                    FastAPI service and API routes
src/
  matching_engine.py      Deterministic three-way matching controls
  pipeline.py             Reconciliation orchestration
  rag_engine.py           Policy retrieval and ChromaDB integration
  explain_engine.py       Policy-grounded finding explanations
  analytics_engine.py     Trends, rankings, patterns, and alerts
  ml_anomaly_engine.py    Advisory multivariate run-outlier detection
  export_engine.py        PDF, Excel, JSON, and email exports
static/dashboard.html     Browser dashboard
policies/ap_policy_manual.md
data/                     Synthetic inputs, answer key, and RAG benchmark
tests/                    Unit and evaluation tests
```
