import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_PATH = BASE_DIR / "data" / "report.json"
TEMPLATE_PATH = BASE_DIR / "static" / "dashboard.html"
OUT_PATH = BASE_DIR / "dashboard_snapshot.html"


def main():
    report = json.loads(REPORT_PATH.read_text())
    template = TEMPLATE_PATH.read_text()

    injected = template.replace(
        "let REPORT = window.__EMBEDDED_REPORT__ || null;",
        f"let REPORT = {json.dumps(report)};",
    )
    injected = injected.replace(
        '<span class="badge badge-live">LIVE</span>',
        '<span class="badge" style="background:#EDE7D8;color:#5B6270;">SNAPSHOT</span>',
    )
    OUT_PATH.write_text(injected)
    print(f"Wrote standalone snapshot: {OUT_PATH}")


if __name__ == "__main__":
    main()
