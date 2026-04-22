from __future__ import annotations

from pathlib import Path
import re

from docx import Document as load_document
from docx.document import Document as DocumentObject
from docx.opc.exceptions import PackageNotFoundError
from docx.section import _Footer, _Header
from docx.shared import Length
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from doc_check.domain.documents import (
    DocumentSnapshot,
    ParagraphFormatSnapshot,
    ParagraphNode,
    RunSnapshot,
    StorySnapshot,
    StoryType,
    TocEntry,
)
from doc_check.parsers.location_index import build_location_index

HEADING_STYLE_PATTERNS = (
    re.compile(r"heading\s*(\d+)", re.IGNORECASE),
    re.compile(r"标题\s*(\d+)"),
)
TOC_STYLE_PATTERN = re.compile(r"toc\s*(\d+)", re.IGNORECASE)


class DocumentReadError(ValueError):
    """Raised when a DOCX file cannot be parsed into a snapshot."""


def read_docx_snapshot(path: str | Path) -> DocumentSnapshot:
    source_path = Path(path).resolve()
    try:
        document = load_document(source_path)
    except (PackageNotFoundError, KeyError, ValueError) as exc:
        raise DocumentReadError(f"Unable to read DOCX document: {source_path.name}") from exc

    main_story = _read_document_story(document)
    headers = tuple(
        _read_header_or_footer_story(section.header, story_type=StoryType.HEADER, section_index=index)
        for index, section in enumerate(document.sections)
    )
    footers = tuple(
        _read_header_or_footer_story(section.footer, story_type=StoryType.FOOTER, section_index=index)
        for index, section in enumerate(document.sections)
    )
    toc_entries = _extract_toc_entries(main_story)

    snapshot = DocumentSnapshot(
        source_path=source_path,
        main_story=main_story,
        headers=headers,
        footers=footers,
        toc_entries=toc_entries,
    )
    location_index = build_location_index(snapshot)
    return snapshot.with_locations(
        commentable_locations=location_index.commentable_locations,
        summary_only_locations=location_index.summary_only_locations,
    )


def iter_container_paragraphs(container, prefix: tuple[str, ...] = ()):
    yield from _iter_container_paragraphs(container, prefix)


def _read_document_story(document: DocumentObject) -> StorySnapshot:
    current_headings: list[str] = []
    paragraphs: list[ParagraphNode] = []

    for paragraph_index, (block_path, paragraph) in enumerate(_iter_container_paragraphs(document)):
        heading_level = _extract_heading_level(paragraph.style.name if paragraph.style else None)
        chapter_path = tuple(current_headings)
        if heading_level is not None and paragraph.text.strip():
            current_headings = current_headings[: heading_level - 1]
            current_headings.append(paragraph.text.strip())
            chapter_path = tuple(current_headings)

        paragraphs.append(
            _build_paragraph_node(
                paragraph=paragraph,
                story_type=StoryType.MAIN,
                section_index=None,
                paragraph_index=paragraph_index,
                block_path=block_path,
                chapter_path=chapter_path,
                heading_level=heading_level,
            )
        )

    return StorySnapshot(
        story_type=StoryType.MAIN,
        section_index=None,
        label="main",
        paragraphs=tuple(paragraphs),
    )


def _read_header_or_footer_story(
    story: _Header | _Footer,
    *,
    story_type: StoryType,
    section_index: int,
) -> StorySnapshot:
    label = f"{story_type.value}[{section_index}]"
    paragraphs = tuple(
        _build_paragraph_node(
            paragraph=paragraph,
            story_type=story_type,
            section_index=section_index,
            paragraph_index=paragraph_index,
            block_path=block_path,
            chapter_path=(),
            heading_level=None,
        )
        for paragraph_index, (block_path, paragraph) in enumerate(_iter_container_paragraphs(story))
    )
    return StorySnapshot(
        story_type=story_type,
        section_index=section_index,
        label=label,
        paragraphs=paragraphs,
    )


def _build_paragraph_node(
    *,
    paragraph: Paragraph,
    story_type: StoryType,
    section_index: int | None,
    paragraph_index: int,
    block_path: tuple[str, ...],
    chapter_path: tuple[str, ...],
    heading_level: int | None,
) -> ParagraphNode:
    runs = tuple(
        _build_run_snapshot(run, paragraph=paragraph, run_index=run_index)
        for run_index, run in enumerate(paragraph.runs)
    )
    style_name = paragraph.style.name if paragraph.style else None
    style_id = paragraph.style.style_id if paragraph.style else None

    return ParagraphNode(
        story_type=story_type,
        section_index=section_index,
        paragraph_index=paragraph_index,
        block_path=block_path,
        text=paragraph.text,
        style_id=style_id,
        style_name=style_name,
        style_chain=_style_chain_names(paragraph.style),
        heading_level=heading_level,
        chapter_path=chapter_path,
        format=_build_paragraph_format_snapshot(paragraph),
        runs=runs,
        rendered_page_break_count=len(paragraph.rendered_page_breaks),
        hard_page_break_count=sum(run.hard_page_break_count for run in runs),
    )


def _build_run_snapshot(run: Run, *, paragraph: Paragraph, run_index: int) -> RunSnapshot:
    return RunSnapshot(
        run_index=run_index,
        text=run.text,
        bold=_resolve_run_property(run, paragraph=paragraph, attr="bold"),
        italic=_resolve_run_property(run, paragraph=paragraph, attr="italic"),
        underline=_resolve_run_property(run, paragraph=paragraph, attr="underline"),
        font_name=_resolve_run_font_name(run, paragraph=paragraph),
        font_size_pt=_resolve_run_font_size(run, paragraph=paragraph),
        hard_page_break_count=sum(1 for br in run._r.br_lst if getattr(br, "type", None) == "page"),
        rendered_page_break_count=len(run._r.lastRenderedPageBreaks),
    )


def _build_paragraph_format_snapshot(paragraph: Paragraph) -> ParagraphFormatSnapshot:
    line_spacing = _resolve_paragraph_format_value(paragraph, "line_spacing")
    line_spacing_rule = _resolve_paragraph_format_value(paragraph, "line_spacing_rule")

    return ParagraphFormatSnapshot(
        alignment=_normalize_enum_name(_resolve_paragraph_format_value(paragraph, "alignment")),
        left_indent_pt=_length_to_points(_resolve_paragraph_format_value(paragraph, "left_indent")),
        right_indent_pt=_length_to_points(_resolve_paragraph_format_value(paragraph, "right_indent")),
        first_line_indent_pt=_length_to_points(
            _resolve_paragraph_format_value(paragraph, "first_line_indent")
        ),
        space_before_pt=_length_to_points(_resolve_paragraph_format_value(paragraph, "space_before")),
        space_after_pt=_length_to_points(_resolve_paragraph_format_value(paragraph, "space_after")),
        line_spacing=_normalize_line_spacing(line_spacing),
        line_spacing_mode=_normalize_line_spacing_mode(line_spacing, line_spacing_rule),
        keep_together=_resolve_paragraph_format_value(paragraph, "keep_together"),
        keep_with_next=_resolve_paragraph_format_value(paragraph, "keep_with_next"),
        page_break_before=_resolve_paragraph_format_value(paragraph, "page_break_before"),
        widow_control=_resolve_paragraph_format_value(paragraph, "widow_control"),
    )


def _resolve_paragraph_format_value(paragraph: Paragraph, attr: str):
    value = getattr(paragraph.paragraph_format, attr)
    if value is not None:
        return value

    style = paragraph.style
    while style is not None:
        value = getattr(style.paragraph_format, attr)
        if value is not None:
            return value
        style = style.base_style
    return None


def _resolve_run_property(run: Run, *, paragraph: Paragraph, attr: str):
    value = getattr(run, attr)
    if value is not None:
        return value

    style = run.style
    while style is not None:
        value = getattr(style.font, attr)
        if value is not None:
            return value
        style = style.base_style

    style = paragraph.style
    while style is not None:
        value = getattr(style.font, attr)
        if value is not None:
            return value
        style = style.base_style

    return None


def _resolve_run_font_name(run: Run, *, paragraph: Paragraph) -> str | None:
    if run.font.name:
        return run.font.name

    style = run.style
    while style is not None:
        if style.font.name:
            return style.font.name
        style = style.base_style

    style = paragraph.style
    while style is not None:
        if style.font.name:
            return style.font.name
        style = style.base_style

    return None


def _resolve_run_font_size(run: Run, *, paragraph: Paragraph) -> float | None:
    if run.font.size is not None:
        return float(run.font.size.pt)

    style = run.style
    while style is not None:
        if style.font.size is not None:
            return float(style.font.size.pt)
        style = style.base_style

    style = paragraph.style
    while style is not None:
        if style.font.size is not None:
            return float(style.font.size.pt)
        style = style.base_style

    return None


def _style_chain_names(style) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[int] = set()
    current = style
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        names.append(current.name)
        current = current.base_style
    return tuple(names)


def _normalize_enum_name(value) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    if name is not None:
        return name.lower()
    return str(value).lower()


def _normalize_line_spacing(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Length):
        return float(value.pt)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_line_spacing_mode(value, rule) -> str | None:
    if value is None:
        return None
    if isinstance(value, Length):
        return _normalize_enum_name(rule) or "points"
    if isinstance(value, (int, float)):
        return "multiple"
    return _normalize_enum_name(rule)


def _length_to_points(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Length):
        return float(value.pt)
    return None


def _extract_heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    for pattern in HEADING_STYLE_PATTERNS:
        match = pattern.search(style_name)
        if match:
            return int(match.group(1))
    return None


def _extract_toc_entries(story: StorySnapshot) -> tuple[TocEntry, ...]:
    entries: list[TocEntry] = []
    for paragraph in story.paragraphs:
        style_name = paragraph.style_name or ""
        match = TOC_STYLE_PATTERN.search(style_name)
        if not match or not paragraph.text.strip():
            continue

        title, page_label = _split_toc_text(paragraph.text)
        entries.append(
            TocEntry(
                level=int(match.group(1)),
                title=title,
                page_label=page_label,
                paragraph_index=paragraph.paragraph_index,
            )
        )
    return tuple(entries)


def _split_toc_text(text: str) -> tuple[str, str | None]:
    cleaned = text.strip()
    if "\t" in cleaned:
        title, page_label = cleaned.rsplit("\t", 1)
        return title.strip(), page_label.strip() or None

    match = re.match(r"^(.*?)(\d+)$", cleaned)
    if match:
        return match.group(1).strip(), match.group(2)
    return cleaned, None


def _iter_container_paragraphs(container, prefix: tuple[str, ...] = ()):
    paragraph_index = 0
    table_index = 0

    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            yield prefix + (f"paragraph[{paragraph_index}]",), block
            paragraph_index += 1
            continue

        if isinstance(block, Table):
            table_path = prefix + (f"table[{table_index}]",)
            yield from _iter_table_paragraphs(block, table_path)
            table_index += 1


def _iter_table_paragraphs(table: Table, prefix: tuple[str, ...]):
    for row_index, row in enumerate(table.rows):
        for cell_index, cell in enumerate(row.cells):
            cell_prefix = prefix + (f"row[{row_index}]", f"cell[{cell_index}]")
            yield from _iter_cell_paragraphs(cell, cell_prefix)


def _iter_cell_paragraphs(cell: _Cell, prefix: tuple[str, ...]):
    yield from _iter_container_paragraphs(cell, prefix)
