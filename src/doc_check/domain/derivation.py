from __future__ import annotations

from dataclasses import dataclass

from doc_check.domain.rule_drafts import RuleDraftSourceType


@dataclass(frozen=True, slots=True)
class NormalizedSectionSnapshot:
    section_index: int
    page_width_mm: float | None
    page_height_mm: float | None
    top_margin_mm: float | None
    bottom_margin_mm: float | None
    left_margin_mm: float | None
    right_margin_mm: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "section_index": self.section_index,
            "page_width_mm": self.page_width_mm,
            "page_height_mm": self.page_height_mm,
            "top_margin_mm": self.top_margin_mm,
            "bottom_margin_mm": self.bottom_margin_mm,
            "left_margin_mm": self.left_margin_mm,
            "right_margin_mm": self.right_margin_mm,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "NormalizedSectionSnapshot":
        return cls(
            section_index=int(payload["section_index"]),
            page_width_mm=_optional_float(payload.get("page_width_mm")),
            page_height_mm=_optional_float(payload.get("page_height_mm")),
            top_margin_mm=_optional_float(payload.get("top_margin_mm")),
            bottom_margin_mm=_optional_float(payload.get("bottom_margin_mm")),
            left_margin_mm=_optional_float(payload.get("left_margin_mm")),
            right_margin_mm=_optional_float(payload.get("right_margin_mm")),
        )


@dataclass(frozen=True, slots=True)
class NormalizedParagraphSnapshot:
    text: str
    style_name: str | None
    heading_level: int | None
    chapter_path: tuple[str, ...]
    font_name: str | None
    font_size_pt: float | None

    def as_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "style_name": self.style_name,
            "heading_level": self.heading_level,
            "chapter_path": list(self.chapter_path),
            "font_name": self.font_name,
            "font_size_pt": self.font_size_pt,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "NormalizedParagraphSnapshot":
        return cls(
            text=str(payload["text"]),
            style_name=_optional_str(payload.get("style_name")),
            heading_level=(
                int(payload["heading_level"])
                if payload.get("heading_level") is not None
                else None
            ),
            chapter_path=tuple(str(item) for item in payload.get("chapter_path", [])),
            font_name=_optional_str(payload.get("font_name")),
            font_size_pt=_optional_float(payload.get("font_size_pt")),
        )


@dataclass(frozen=True, slots=True)
class NormalizedSourceSnapshot:
    source_type: RuleDraftSourceType
    headings: tuple[str, ...]
    toc_titles: tuple[str, ...]
    header_texts: tuple[str, ...]
    footer_texts: tuple[str, ...]
    sections: tuple[NormalizedSectionSnapshot, ...]
    body_paragraphs: tuple[NormalizedParagraphSnapshot, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "source_type": self.source_type.value,
            "headings": list(self.headings),
            "toc_titles": list(self.toc_titles),
            "header_texts": list(self.header_texts),
            "footer_texts": list(self.footer_texts),
            "sections": [section.as_dict() for section in self.sections],
            "body_paragraphs": [paragraph.as_dict() for paragraph in self.body_paragraphs],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "NormalizedSourceSnapshot":
        return cls(
            source_type=RuleDraftSourceType(str(payload["source_type"])),
            headings=tuple(str(item) for item in payload.get("headings", [])),
            toc_titles=tuple(str(item) for item in payload.get("toc_titles", [])),
            header_texts=tuple(str(item) for item in payload.get("header_texts", [])),
            footer_texts=tuple(str(item) for item in payload.get("footer_texts", [])),
            sections=tuple(
                NormalizedSectionSnapshot.from_dict(item)
                for item in payload.get("sections", [])
            ),
            body_paragraphs=tuple(
                NormalizedParagraphSnapshot.from_dict(item)
                for item in payload.get("body_paragraphs", [])
            ),
        )


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    result = str(value)
    return result if result else None
