from __future__ import annotations

from doc_check.parsers.docx_reader import read_docx_snapshot
from tests.support.docx_samples import ensure_docx_samples


def test_docx_reader_extracts_story_structure_and_toc_entries(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)

    snapshot = read_docx_snapshot(fixture_paths["valid"])

    main_texts = [paragraph.text for paragraph in snapshot.main_story.paragraphs if paragraph.text.strip()]
    assert "本制度适用于 AEOS 管理体系。" in main_texts
    assert "表格中的适用条款" in main_texts
    assert [entry.title for entry in snapshot.toc_entries] == ["1 总则", "1.1 目的"]
    assert [entry.page_label for entry in snapshot.toc_entries] == ["1", "2"]

    header_texts = [
        paragraph.text for story in snapshot.headers for paragraph in story.paragraphs if paragraph.text.strip()
    ]
    footer_texts = [
        paragraph.text for story in snapshot.footers for paragraph in story.paragraphs if paragraph.text.strip()
    ]
    assert header_texts == ["AEOS 文件页眉"]
    assert footer_texts == ["AEOS 文件页脚"]


def test_docx_reader_resolves_inherited_paragraph_formatting(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)

    snapshot = read_docx_snapshot(fixture_paths["format_errors"])

    inherited_paragraph = next(
        paragraph
        for paragraph in snapshot.main_story.paragraphs
        if paragraph.text == "继承样式的正文段落。"
    )
    overridden_paragraph = next(
        paragraph
        for paragraph in snapshot.main_story.paragraphs
        if paragraph.text == "直接设置为单倍行距的段落。"
    )

    assert inherited_paragraph.format.line_spacing == 1.5
    assert inherited_paragraph.format.line_spacing_mode == "multiple"
    assert inherited_paragraph.format.left_indent_pt == 24.0
    assert inherited_paragraph.format.space_after_pt == 6.0
    assert overridden_paragraph.format.line_spacing == 1.0
    assert overridden_paragraph.format.space_after_pt == 0.0
