from __future__ import annotations

from doc_check.parsers.docx_reader import read_docx_snapshot
from tests.support.docx_samples import ensure_docx_samples


def test_location_index_marks_main_story_as_commentable_and_headers_as_summary_only(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)

    snapshot = read_docx_snapshot(fixture_paths["valid"])

    commentable_texts = {location.text_excerpt for location in snapshot.commentable_locations}
    summary_only_texts = {location.text_excerpt for location in snapshot.summary_only_locations}

    assert "本制度适用于 AEOS 管理体系。" in commentable_texts
    assert "AEOS 文件页眉" in summary_only_texts
    assert "AEOS 文件页脚" in summary_only_texts
    assert any("table[0]" in "/".join(location.block_path) for location in snapshot.commentable_locations)


def test_location_index_assigns_chapter_paths_and_page_hints(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)

    snapshot = read_docx_snapshot(fixture_paths["valid"])

    follow_up = next(
        location for location in snapshot.commentable_locations if location.text_excerpt == "统一检查格式和术语。"
    )

    assert follow_up.chapter_path == ("1 总则", "1.1 目的")
    assert follow_up.page_hint == 2
