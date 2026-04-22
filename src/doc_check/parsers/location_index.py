from __future__ import annotations

from dataclasses import dataclass

from doc_check.domain.documents import (
    DocumentSnapshot,
    LocationAnchorKind,
    LocationRef,
    ParagraphNode,
    StorySnapshot,
    StoryType,
)


@dataclass(frozen=True, slots=True)
class LocationIndex:
    commentable_locations: tuple[LocationRef, ...]
    summary_only_locations: tuple[LocationRef, ...]

    @property
    def all_locations(self) -> tuple[LocationRef, ...]:
        return self.commentable_locations + self.summary_only_locations


def build_location_index(snapshot: DocumentSnapshot) -> LocationIndex:
    commentable: list[LocationRef] = []
    summary_only: list[LocationRef] = []
    current_page_hint = 1

    for story in _iter_stories(snapshot):
        for paragraph in story.paragraphs:
            if not paragraph.text.strip() and not _paragraph_has_breaks(paragraph):
                continue

            page_hint = current_page_hint if story.story_type is StoryType.MAIN else None
            if paragraph.is_commentable:
                run_start, run_end = _resolve_run_bounds(paragraph)
                location = LocationRef(
                    location_id=_build_location_id(
                        story=story,
                        paragraph=paragraph,
                        anchor_kind=LocationAnchorKind.COMMENTABLE,
                    ),
                    story_type=story.story_type,
                    anchor_kind=LocationAnchorKind.COMMENTABLE,
                    section_index=story.section_index,
                    paragraph_index=paragraph.paragraph_index,
                    run_start=run_start,
                    run_end=run_end,
                    block_path=paragraph.block_path,
                    chapter_path=paragraph.chapter_path,
                    text_excerpt=paragraph.text_excerpt,
                    page_hint=page_hint,
                    label=_format_label(story=story, paragraph=paragraph, page_hint=page_hint),
                )
                commentable.append(location)
            else:
                location = LocationRef(
                    location_id=_build_location_id(
                        story=story,
                        paragraph=paragraph,
                        anchor_kind=LocationAnchorKind.SUMMARY_ONLY,
                    ),
                    story_type=story.story_type,
                    anchor_kind=LocationAnchorKind.SUMMARY_ONLY,
                    section_index=story.section_index,
                    paragraph_index=paragraph.paragraph_index,
                    run_start=None,
                    run_end=None,
                    block_path=paragraph.block_path,
                    chapter_path=paragraph.chapter_path,
                    text_excerpt=paragraph.text_excerpt,
                    page_hint=page_hint,
                    label=_format_label(story=story, paragraph=paragraph, page_hint=page_hint),
                )
                summary_only.append(location)

            if story.story_type is StoryType.MAIN:
                current_page_hint += _page_increment(paragraph)

    return LocationIndex(
        commentable_locations=tuple(commentable),
        summary_only_locations=tuple(summary_only),
    )


def _iter_stories(snapshot: DocumentSnapshot) -> tuple[StorySnapshot, ...]:
    return (snapshot.main_story, *snapshot.headers, *snapshot.footers)


def _paragraph_has_breaks(paragraph: ParagraphNode) -> bool:
    return (paragraph.hard_page_break_count + paragraph.rendered_page_break_count) > 0


def _resolve_run_bounds(paragraph: ParagraphNode) -> tuple[int | None, int | None]:
    candidate_indexes = [
        run.run_index
        for run in paragraph.runs
        if run.text.strip() or run.contains_break
    ]
    if not candidate_indexes:
        return None, None
    return candidate_indexes[0], candidate_indexes[-1]


def _page_increment(paragraph: ParagraphNode) -> int:
    if paragraph.rendered_page_break_count:
        return paragraph.rendered_page_break_count
    return paragraph.hard_page_break_count


def _build_location_id(
    *,
    story: StorySnapshot,
    paragraph: ParagraphNode,
    anchor_kind: LocationAnchorKind,
) -> str:
    section = story.section_index if story.section_index is not None else "body"
    return (
        f"{story.story_type.value}:{section}:"
        f"{paragraph.paragraph_index}:{anchor_kind.value}"
    )


def _format_label(
    *,
    story: StorySnapshot,
    paragraph: ParagraphNode,
    page_hint: int | None,
) -> str:
    base = {
        StoryType.MAIN: "正文",
        StoryType.HEADER: "页眉",
        StoryType.FOOTER: "页脚",
    }[story.story_type]

    section_label = (
        f"第{story.section_index + 1}节"
        if story.section_index is not None
        else "正文"
    )
    block_label = " / ".join(paragraph.block_path)
    label = f"{base} {section_label} 段落#{paragraph.paragraph_index + 1}"
    if block_label:
        label = f"{label} ({block_label})"
    if page_hint is not None:
        label = f"{label} [页码提示 {page_hint}]"
    return label
