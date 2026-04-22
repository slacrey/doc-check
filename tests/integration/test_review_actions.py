from __future__ import annotations

import re

from fastapi.testclient import TestClient

from doc_check.api.app import build_app
from tests.support.app_config import make_test_config
from tests.support.docx_samples import ensure_docx_samples


def test_review_actions_update_pending_count_and_state_labels(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    config = make_test_config(tmp_path)
    app = build_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/reviews/upload",
            files={
                "file": (
                    "policy.docx",
                    fixture_paths["format_errors"].read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        match = re.search(r"/reviews/([a-f0-9]+)/findings/([a-f0-9]+)", response.text)
        assert match is not None
        artifact_id, finding_id = match.groups()

        updated = client.post(
            f"/reviews/{artifact_id}/findings/{finding_id}",
            data={
                "review_status": "false_positive",
                "filter_review_status": "false_positive",
            },
        )

    assert updated.status_code == 200
    assert "当前显示</span><strong>1</strong>" in updated.text
    assert "false_positive" in updated.text
    assert 'option value="false_positive" selected="selected"' in updated.text
