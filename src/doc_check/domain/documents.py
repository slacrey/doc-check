from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class ArtifactStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: str
    auth_source: str
    display_name: str | None = None
    is_authenticated: bool = False

    @classmethod
    def local(cls, user_id: str = "local") -> "UserContext":
        return cls(
            user_id=user_id,
            auth_source="local",
            display_name=user_id,
            is_authenticated=False,
        )


@dataclass(frozen=True, slots=True)
class CreateArtifactCommand:
    original_filename: str
    content_type: str
    payload: bytes
    ruleset_id: str
    ruleset_version: str
    user: UserContext


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    original_filename: str
    stored_filename: str
    storage_path: Path
    content_type: str
    size_bytes: int
    ruleset_id: str
    ruleset_version: str
    status: ArtifactStatus
    created_at: datetime
    expires_at: datetime
    created_by: str
    auth_source: str
    annotated_path: Path | None = None
    summary_path: Path | None = None

    def as_public_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "ruleset_id": self.ruleset_id,
            "ruleset_version": self.ruleset_version,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "created_by": self.created_by,
            "auth_source": self.auth_source,
        }


class StoryType(StrEnum):
    MAIN = "main"
    HEADER = "header"
    FOOTER = "footer"


class LocationAnchorKind(StrEnum):
    COMMENTABLE = "commentable"
    SUMMARY_ONLY = "summary_only"


@dataclass(frozen=True, slots=True)
class ParagraphFormatSnapshot:
    alignment: str | None
    left_indent_pt: float | None
    right_indent_pt: float | None
    first_line_indent_pt: float | None
    space_before_pt: float | None
    space_after_pt: float | None
    line_spacing: float | None
    line_spacing_mode: str | None
    keep_together: bool | None
    keep_with_next: bool | None
    page_break_before: bool | None
    widow_control: bool | None


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    run_index: int
    text: str
    bold: bool | None
    italic: bool | None
    underline: bool | None
    font_name: str | None
    font_size_pt: float | None
    hard_page_break_count: int
    rendered_page_break_count: int

    @property
    def contains_break(self) -> bool:
        return (self.hard_page_break_count + self.rendered_page_break_count) > 0


@dataclass(frozen=True, slots=True)
class ParagraphNode:
    story_type: StoryType
    section_index: int | None
    paragraph_index: int
    block_path: tuple[str, ...]
    text: str
    style_id: str | None
    style_name: str | None
    style_chain: tuple[str, ...]
    heading_level: int | None
    chapter_path: tuple[str, ...]
    format: ParagraphFormatSnapshot
    runs: tuple[RunSnapshot, ...]
    rendered_page_break_count: int
    hard_page_break_count: int

    @property
    def is_commentable(self) -> bool:
        if self.story_type is not StoryType.MAIN:
            return False
        return bool(self.runs) and bool(self.text.strip())

    @property
    def text_excerpt(self) -> str:
        text = " ".join(self.text.split())
        if len(text) <= 80:
            return text
        return f"{text[:77]}..."


@dataclass(frozen=True, slots=True)
class StorySnapshot:
    story_type: StoryType
    section_index: int | None
    label: str
    paragraphs: tuple[ParagraphNode, ...]


@dataclass(frozen=True, slots=True)
class TocEntry:
    level: int
    title: str
    page_label: str | None
    paragraph_index: int


@dataclass(frozen=True, slots=True)
class LocationRef:
    location_id: str
    story_type: StoryType
    anchor_kind: LocationAnchorKind
    section_index: int | None
    paragraph_index: int
    run_start: int | None
    run_end: int | None
    block_path: tuple[str, ...]
    chapter_path: tuple[str, ...]
    text_excerpt: str
    page_hint: int | None
    label: str


@dataclass(frozen=True, slots=True)
class DocumentSnapshot:
    source_path: Path
    main_story: StorySnapshot
    headers: tuple[StorySnapshot, ...]
    footers: tuple[StorySnapshot, ...]
    toc_entries: tuple[TocEntry, ...]
    commentable_locations: tuple[LocationRef, ...] = ()
    summary_only_locations: tuple[LocationRef, ...] = ()

    def with_locations(
        self,
        *,
        commentable_locations: tuple[LocationRef, ...],
        summary_only_locations: tuple[LocationRef, ...],
    ) -> "DocumentSnapshot":
        return replace(
            self,
            commentable_locations=commentable_locations,
            summary_only_locations=summary_only_locations,
        )
