import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.config import get_settings


def execute_analysis(
    records: list[dict], columns: list[str], question: str, previous: dict | None = None
) -> dict:
    """Run a fixed analysis tool in a short-lived process; never accepts user Python code."""
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="analyst-job-") as tmp:
        source = Path(tmp) / "request.json"
        source.write_text(
            json.dumps(
                {"rows": records, "columns": columns, "question": question, "previous": previous}
            ),
            encoding="utf-8",
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(root),
            "PYTHONIOENCODING": "utf-8",
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "app.execution.worker", str(source)],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=get_settings().analysis_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("Analysis exceeded its execution time limit.") from exc
        if proc.returncode != 0:
            raise RuntimeError("Analysis worker failed.")
        if len(proc.stdout) > 2_000_000:
            raise RuntimeError("Analysis result exceeded the output limit.")
        return json.loads(proc.stdout)
