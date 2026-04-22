from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from tests.support.docx_samples import ensure_docx_samples


def test_run_single_check_script_outputs_summary_and_generated_files(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path / "fixtures")
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    project_root = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts" / "run_single_check.py"),
            str(fixture_paths["format_errors"]),
            "--workspace-dir",
            str(workspace_dir),
        ],
        capture_output=True,
        check=False,
        cwd=project_root,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr

    payload = json.loads(completed.stdout)

    assert payload["artifact"]["status"] == "completed"
    assert payload["summary"]["total_findings"] == 17
    assert Path(payload["outputs"]["artifact_dir"]).exists()
    assert Path(payload["outputs"]["annotated_docx"]).exists()
    assert Path(payload["outputs"]["summary_json"]).exists()
