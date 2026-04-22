from __future__ import annotations

from collections import Counter
from pathlib import Path

from doc_check.domain.derivation import (
    NormalizedParagraphSnapshot,
    NormalizedSectionSnapshot,
    NormalizedSourceSnapshot,
)
from doc_check.domain.rule_drafts import RuleDraftSourceType
from doc_check.parsers.docx_reader import read_docx_snapshot


class SourceNormalizer:
    def normalize(
        self,
        *,
        source_type: RuleDraftSourceType,
        source_path: str | Path,
    ) -> NormalizedSourceSnapshot:
        snapshot = read_docx_snapshot(source_path)
        headings = tuple(
            paragraph.text.strip()
            for paragraph in snapshot.main_story.paragraphs
            if paragraph.heading_level is not None and paragraph.text.strip()
        )
        toc_titles = tuple(entry.title for entry in snapshot.toc_entries if entry.title)
        header_texts = tuple(
            paragraph.text.strip()
            for story in snapshot.headers
            for paragraph in story.paragraphs
            if paragraph.text.strip()
        )
        footer_texts = tuple(
            paragraph.text.strip()
            for story in snapshot.footers
            for paragraph in story.paragraphs
            if paragraph.text.strip()
        )
        sections = tuple(
            NormalizedSectionSnapshot(
                section_index=section.section_index,
                page_width_mm=_rounded_mm(section.page_width_mm),
                page_height_mm=_rounded_mm(section.page_height_mm),
                top_margin_mm=_rounded_mm(section.top_margin_mm),
                bottom_margin_mm=_rounded_mm(section.bottom_margin_mm),
                left_margin_mm=_rounded_mm(section.left_margin_mm),
                right_margin_mm=_rounded_mm(section.right_margin_mm),
            )
            for section in snapshot.sections
        )
        body_paragraphs = tuple(
            NormalizedParagraphSnapshot(
                text=paragraph.text,
                style_name=paragraph.style_name,
                heading_level=paragraph.heading_level,
                chapter_path=paragraph.chapter_path,
                font_name=_most_common_value(
                    run.font_name for run in paragraph.runs if run.font_name
                ),
                font_size_pt=_most_common_value(
                    run.font_size_pt for run in paragraph.runs if run.font_size_pt is not None
                ),
            )
            for paragraph in snapshot.main_story.paragraphs
            if paragraph.text.strip()
        )

        return NormalizedSourceSnapshot(
            source_type=source_type,
            headings=headings,
            toc_titles=toc_titles,
            header_texts=header_texts,
            footer_texts=footer_texts,
            sections=sections,
            body_paragraphs=body_paragraphs,
        )


def _most_common_value(values):
    items = tuple(values)
    if not items:
        return None
    return Counter(items).most_common(1)[0][0]


def _rounded_mm(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)
