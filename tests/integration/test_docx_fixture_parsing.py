from __future__ import annotations

from pathlib import Path

from doc_check.parsers.docx_reader import read_docx_snapshot
from tests.support.docx_samples import ensure_docx_samples


def test_docx_fixture_paths_can_be_read_from_repo_fixture_directory(tmp_path):
    fixture_dir = Path("tests/fixtures/docx")
    fixture_paths = ensure_docx_samples(fixture_dir)

    valid_snapshot = read_docx_snapshot(fixture_paths["valid"])
    error_snapshot = read_docx_snapshot(fixture_paths["format_errors"])

    assert valid_snapshot.source_path.name == "aeos-valid-sample.docx"
    assert error_snapshot.source_path.name == "aeos-format-errors.docx"
    assert len(valid_snapshot.main_story.paragraphs) >= 5
    assert len(error_snapshot.summary_only_locations) >= 2
