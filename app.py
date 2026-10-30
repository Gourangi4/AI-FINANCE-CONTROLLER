import os
import sys
import uuid
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR / "src"))

from pipeline import run_pipeline  # noqa: E402
from export_engine import export_to_pdf, export_to_excel, export_to_json, send_email_report  # noqa: E402
from analytics_engine import AnalyticsEngine  # noqa: E402

DATA_DIR = BASE_DIR / "data"
RUNS_DIR = DATA_DIR / "uploads"
ANALYTICS_DIR = DATA_DIR / "analytics"
RUNS_DIR.mkdir(parents=True, exist_ok=True)
ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
REQUIRED_COLUMNS = {
    "purchase_orders": {"po_id", "vendor_name", "vendor_code", "po_date", "po_amount", "currency", "approver", "payment_terms_days"},
    "invoices": {"invoice_id", "po_id", "vendor_name", "vendor_code", "invoice_date", "invoice_amount", "currency", "due_date"},
    "payments": {"payment_id", "invoice_id", "vendor_name", "vendor_code", "payment_date", "payment_amount", "currency", "payment_method"},
}


app = FastAPI(title="AI Finance Controller — 3-Way Reconciliation")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", uuid.uuid4().hex),
    https_only=os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true",
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(BASE_DIR / "static" / "dashboard.html"))


def _session_id(request: Request) -> str:
    value = request.session.get("id")
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        value = str(uuid.uuid4())
        request.session["id"] = value
        return value


def _report_path(request: Request) -> Path | None:
    run_id = request.session.get("run_id")
    try:
        run_id = str(uuid.UUID(str(run_id)))
    except (ValueError, TypeError, AttributeError):
        return None
    run_dir = (RUNS_DIR / run_id).resolve()
    candidate = (run_dir / "report.json").resolve()
    return candidate if candidate.parent == run_dir else None


def _analytics_for(request: Request) -> AnalyticsEngine:
    return AnalyticsEngine(ANALYTICS_DIR / f"{_session_id(request)}.json")


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    size = 0
    with destination.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                raise HTTPException(413, f"{upload.filename} exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit")
            out.write(chunk)


def _validate_csv_headers(paths: dict[str, Path]) -> None:
    for name, path in paths.items():
        try:
            headers = set(pd.read_csv(path, nrows=0, encoding="utf-8").columns)
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            raise HTTPException(422, f"{name} must be a valid UTF-8 CSV: {exc}") from exc
        missing = REQUIRED_COLUMNS[name] - headers
        if missing:
            raise HTTPException(422, f"{name} is missing required columns: {', '.join(sorted(missing))}")


@app.get("/api/report")
def get_report(request: Request):
    report_path = _report_path(request)
    if report_path is None or not report_path.exists():
        raise HTTPException(404, "Upload purchase orders, invoices, and payments to generate a report.")
    return JSONResponse(content=_load_json(report_path))


@app.post("/api/upload-and-run")
async def upload_and_run(
    request: Request,
    po: UploadFile = File(...), inv: UploadFile = File(...), pay: UploadFile = File(...)
):
    for f in (po, inv, pay):
        if not f.filename.lower().endswith(".csv"):
            raise HTTPException(400, f"{f.filename} is not a .csv file")

    run_id = str(uuid.uuid4())
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    po_path = run_dir / "purchase_orders.csv"
    inv_path = run_dir / "invoices.csv"
    pay_path = run_dir / "payments.csv"
    for src, dest in ((po, po_path), (inv, inv_path), (pay, pay_path)):
        await _save_upload(src, dest)
    _validate_csv_headers({"purchase_orders": po_path, "invoices": inv_path, "payments": pay_path})

    out_path = run_dir / "report.json"
    try:
        report = run_pipeline(po_path, inv_path, pay_path, out_path)
    except Exception as e:
        raise HTTPException(422, f"Reconciliation failed: {e}")
    request.session["run_id"] = run_id
    _analytics_for(request).record_run(report)
    return JSONResponse(content=report)


@app.get("/api/export/pdf")
def export_pdf(request: Request):
    """Download current report as PDF."""
    report_path = _report_path(request)
    if report_path is None or not report_path.exists():
        raise HTTPException(404, "No report available. Run reconciliation first.")
    
    report = _load_json(report_path)
    pdf_bytes = export_to_pdf(report)
    
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reconciliation_report.pdf"}
    )


@app.get("/api/export/excel")
def export_excel(request: Request):
    """Download current report as Excel spreadsheet."""
    report_path = _report_path(request)
    if report_path is None or not report_path.exists():
        raise HTTPException(404, "No report available. Run reconciliation first.")
    
    report = _load_json(report_path)
    excel_bytes = export_to_excel(report)
    
    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=reconciliation_report.xlsx"}
    )


@app.get("/api/export/json")
def export_json_endpoint(request: Request):
    """Download current report as JSON."""
    report_path = _report_path(request)
    if report_path is None or not report_path.exists():
        raise HTTPException(404, "No report available. Run reconciliation first.")
    
    report = _load_json(report_path)
    json_bytes = export_to_json(report)
    
    return StreamingResponse(
        iter([json_bytes]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=reconciliation_report.json"}
    )


@app.post("/api/export/email")
def export_email(request: Request, recipient_email: str):
    """
    Send report via email with PDF and Excel attachments.
    
    Query parameter:
      recipient_email: Email address to send report to
    """
    report_path = _report_path(request)
    if report_path is None or not report_path.exists():
        raise HTTPException(404, "No report available. Run reconciliation first.")
    
    report = _load_json(report_path)
    result = send_email_report(report, recipient_email)
    
    if not result['success']:
        raise HTTPException(500, result['message'])
    
    return JSONResponse(content=result)


@app.get("/api/analytics/summary")
def analytics_summary(request: Request):
    """Get comprehensive analytics dashboard summary."""
    return JSONResponse(content=_analytics_for(request).get_dashboard_summary())


@app.get("/api/analytics/trends")
def analytics_trends(request: Request, days: int = 30):
    """Get exception trends over last N days."""
    return JSONResponse(content=_analytics_for(request).get_trends(days))


@app.get("/api/analytics/vendors")
def analytics_vendors(request: Request, limit: int = 10, metric: str = "risk"):
    """
    Get vendor rankings.
    
    Query parameters:
      limit: Number of vendors to return (default 10)
      metric: Sort by "risk" or "frequency" (default "risk")
    """
    if metric not in ["risk", "frequency"]:
        metric = "risk"
    return JSONResponse(content=_analytics_for(request).get_vendor_rankings(limit, metric))


@app.get("/api/analytics/patterns")
def analytics_patterns(request: Request):
    """Get exception type patterns and distribution."""
    return JSONResponse(content=_analytics_for(request).get_exception_patterns())


@app.get("/api/analytics/anomalies")
def analytics_anomalies(request: Request):
    """Detect anomalies in current report vs historical baseline."""
    report_path = _report_path(request)
    if report_path is None or not report_path.exists():
        raise HTTPException(404, "No report available. Run reconciliation first.")
    
    report = _load_json(report_path)
    return JSONResponse(content=_analytics_for(request).detect_anomalies(report))


@app.get("/api/analytics/vendor/{vendor_name}")
def analytics_vendor_score(request: Request, vendor_name: str):
    """Get comprehensive risk score for a specific vendor."""
    return JSONResponse(content=_analytics_for(request).get_vendor_risk_score(vendor_name))


def _load_json(path: Path):
    import json
    return json.loads(path.read_text())
