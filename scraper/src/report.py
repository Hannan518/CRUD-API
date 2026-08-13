import json

from . import config


def write_run_report(metrics: dict):
    """Write the run report so a failed or successful job leaves evidence."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.OUTPUT_DIR / "run-report.json"
    path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path
