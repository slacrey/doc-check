from __future__ import annotations

from pathlib import Path

from doc_check.domain.documents import (
    DocumentSnapshot,
    ParagraphFormatSnapshot,
    ParagraphNode,
    RunSnapshot,
    StorySnapshot,
    StoryType,
)
from doc_check.parsers.location_index import build_location_index
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


def test_location_index_falls_back_to_full_run_span_for_field_backed_text():
    paragraph = ParagraphNode(
        story_type=StoryType.MAIN,
        section_index=None,
        paragraph_index=0,
        block_path=("paragraph[0]",),
        text="1 目的和适用范围\t1",
        style_id="TOC1",
        style_name="TOC 1",
        style_chain=("TOC 1",),
        heading_level=None,
        chapter_path=(),
        format=ParagraphFormatSnapshot(
            alignment=None,
            left_indent_pt=None,
            right_indent_pt=None,
            first_line_indent_pt=None,
            space_before_pt=None,
            space_after_pt=None,
            line_spacing=None,
            line_spacing_mode=None,
            keep_together=None,
            keep_with_next=None,
            page_break_before=None,
            widow_control=None,
        ),
        runs=(
            RunSnapshot(
                run_index=0,
                text="",
                bold=None,
                italic=None,
                underline=None,
                font_name=None,
                font_size_pt=None,
                hard_page_break_count=0,
                rendered_page_break_count=0,
            ),
            RunSnapshot(
                run_index=1,
                text="",
                bold=None,
                italic=None,
                underline=None,
                font_name=None,
                font_size_pt=None,
                hard_page_break_count=0,
                rendered_page_break_count=0,
            ),
            RunSnapshot(
                run_index=2,
                text="",
                bold=None,
                italic=None,
                underline=None,
                font_name=None,
                font_size_pt=None,
                hard_page_break_count=0,
                rendered_page_break_count=0,
            ),
        ),
        rendered_page_break_count=0,
        hard_page_break_count=0,
    )
    snapshot = DocumentSnapshot(
        source_path=Path("/tmp/field-backed.docx"),
        main_story=StorySnapshot(
            story_type=StoryType.MAIN,
            section_index=None,
            label="main",
            paragraphs=(paragraph,),
        ),
        headers=(),
        footers=(),
        sections=(),
        toc_entries=(),
    )

    location_index = build_location_index(snapshot)

    assert len(location_index.commentable_locations) == 1
    location = location_index.commentable_locations[0]
    assert location.run_start == 0
    assert location.run_end == 2
