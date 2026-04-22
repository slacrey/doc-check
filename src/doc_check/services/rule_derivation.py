from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from doc_check.domain.derivation import NormalizedSourceSnapshot
from doc_check.domain.rule_drafts import RuleDraftSource, RuleDraftSourceType, RuleDraftTask
from doc_check.rules.rule_pack import load_rule_pack

PREFERRED_TERM_PATTERN = re.compile(
    r'统一使用[“"](?P<canonical>[^”"]+)[”"][^。；]*?(?:不要使用|不使用|不得使用)[“"](?P<variant>[^”"]+)[”"]'
)
BANNED_TERM_PATTERN = re.compile(r'(?:不得使用|禁止使用|不应使用)[“"](?P<term>[^”"]+)[”"]')


@dataclass(frozen=True, slots=True)
class DerivedRuleDraft:
    version: str
    manifest_data: dict[str, object]
    structure_data: dict[str, object]
    style_data: dict[str, object]
    terminology_rows: list[dict[str, object]]
    banned_term_rows: list[dict[str, object]]
    evidence: dict[str, object]


class RuleDerivationService:
    def __init__(self, *, now_factory=None) -> None:
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def derive(
        self,
        *,
        task: RuleDraftTask,
        sources: tuple[RuleDraftSource, ...],
        rulesets_dir: Path,
    ) -> DerivedRuleDraft:
        active_pack = load_rule_pack(rulesets_dir / task.ruleset_id)
        normalized_sources = tuple(
            (source, self._load_snapshot(source.normalized_path))
            for source in sources
            if not source.is_excluded and source.normalized_path is not None and source.parse_error is None
        )
        if not normalized_sources:
            raise ValueError("No normalized sources are available for derivation")

        by_type = {
            source_type: [
                snapshot
                for source, snapshot in normalized_sources
                if source.source_type is source_type
            ]
            for source_type in RuleDraftSourceType
        }

        version = f"draft-{self._now_factory().strftime('%Y%m%d%H%M%S%f')}"
        headings = _derive_required_headings(by_type)
        toc_required = any(snapshot.toc_titles for snapshot in _preferred_snapshots(by_type, RuleDraftSourceType.TEMPLATE, RuleDraftSourceType.STANDARD, RuleDraftSourceType.SAMPLE))
        layout_rules = _derive_layout_rules(by_type)
        paragraph_rules = _derive_paragraph_rules(by_type)
        terminology_rows, banned_term_rows = _derive_term_rows(by_type)

        evidence = {
            "sources": {
                source_type.value: len(items)
                for source_type, items in by_type.items()
            },
            "required_headings": [item["text"] for item in headings],
            "toc_required": toc_required,
            "layout_rule_count": len(layout_rules),
            "paragraph_rule_count": len(paragraph_rules),
            "terminology_count": len(terminology_rows),
            "banned_term_count": len(banned_term_rows),
            "baseline_inheritance": {
                "document_type": active_pack.manifest.document_type,
                "punctuation_rules": dict(active_pack.manifest.punctuation_rules),
            },
        }

        return DerivedRuleDraft(
            version=version,
            manifest_data={
                "ruleset_id": active_pack.ruleset_id,
                "version": version,
                "name": f"{active_pack.manifest.name}（草案）",
                "document_type": active_pack.manifest.document_type,
                "punctuation_rules": dict(active_pack.manifest.punctuation_rules),
            },
            structure_data={
                "required_headings": headings,
                "toc": {
                    "rule_id": "structure.toc.required",
                    "required": toc_required,
                    "match_headings": toc_required,
                    "severity": "error",
                    "disposition": "mandatory",
                },
                "story_text_rules": [],
            },
            style_data={
                "paragraph_rules": paragraph_rules,
                "section_rules": layout_rules,
            },
            terminology_rows=terminology_rows,
            banned_term_rows=banned_term_rows,
            evidence=evidence,
        )

    @staticmethod
    def _load_snapshot(path: Path) -> NormalizedSourceSnapshot:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return NormalizedSourceSnapshot.from_dict(payload)


def _derive_required_headings(by_type: dict[RuleDraftSourceType, list[NormalizedSourceSnapshot]]) -> list[dict[str, object]]:
    selected = _preferred_snapshots(
        by_type,
        RuleDraftSourceType.TEMPLATE,
        RuleDraftSourceType.STANDARD,
        RuleDraftSourceType.SAMPLE,
    )
    ordered: list[tuple[str, int]] = []
    seen: set[str] = set()
    for snapshot in selected:
        for paragraph in snapshot.body_paragraphs:
            if paragraph.heading_level is None:
                continue
            text = paragraph.text.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append((text, paragraph.heading_level))

    return [
        {
            "rule_id": f"structure.required-heading.{index:03d}",
            "text": text,
            "level": level,
            "severity": "error",
            "disposition": "mandatory",
        }
        for index, (text, level) in enumerate(ordered, start=1)
    ]


def _derive_layout_rules(by_type: dict[RuleDraftSourceType, list[NormalizedSourceSnapshot]]) -> list[dict[str, object]]:
    selected = _preferred_snapshots(
        by_type,
        RuleDraftSourceType.TEMPLATE,
        RuleDraftSourceType.STANDARD,
        RuleDraftSourceType.SAMPLE,
    )
    field_specs = (
        ("page_width_mm", "layout.page-width.a4", "页面宽度应符合 A4 纸规格（210mm）。", "error"),
        ("page_height_mm", "layout.page-height.a4", "页面高度应符合 A4 纸规格（297mm）。", "error"),
        ("top_margin_mm", "layout.margin-top", "上边距宜为 37mm。", "warning"),
        ("bottom_margin_mm", "layout.margin-bottom", "下边距宜为 35mm。", "warning"),
        ("left_margin_mm", "layout.margin-left", "左边距宜为 28mm。", "warning"),
        ("right_margin_mm", "layout.margin-right", "右边距宜为 26mm。", "warning"),
    )
    rules: list[dict[str, object]] = []
    for field_name, rule_id, message, severity in field_specs:
        observed = [
            getattr(section, field_name)
            for snapshot in selected
            for section in snapshot.sections
            if getattr(section, field_name) is not None
        ]
        if not observed:
            continue
        rules.append(
            {
                "rule_id": rule_id,
                "field": field_name,
                "expected": _most_common(observed),
                "severity": severity,
                "disposition": "mandatory",
                "message": message,
            }
        )
    return rules


def _derive_paragraph_rules(by_type: dict[RuleDraftSourceType, list[NormalizedSourceSnapshot]]) -> list[dict[str, object]]:
    selected = _preferred_snapshots(
        by_type,
        RuleDraftSourceType.TEMPLATE,
        RuleDraftSourceType.STANDARD,
        RuleDraftSourceType.SAMPLE,
    )
    body_candidates = [
        paragraph
        for snapshot in selected
        for paragraph in snapshot.body_paragraphs
        if paragraph.heading_level is None and len(paragraph.text.strip()) >= 8
    ]
    rules: list[dict[str, object]] = []
    font_names = [paragraph.font_name for paragraph in body_candidates if paragraph.font_name]
    if font_names:
        rules.append(
            {
                "rule_id": "style.body.font-name",
                "scope": "body_paragraph",
                "field": "font_name",
                "expected": [_most_common(font_names)],
                "severity": "warning",
                "disposition": "mandatory",
                "message": "正文宜统一使用 3 号仿宋体。",
                "min_text_length": 8,
            }
        )
    font_sizes = [paragraph.font_size_pt for paragraph in body_candidates if paragraph.font_size_pt is not None]
    if font_sizes:
        rules.append(
            {
                "rule_id": "style.body.font-size",
                "scope": "body_paragraph",
                "field": "font_size_pt",
                "expected": _most_common(font_sizes),
                "severity": "warning",
                "disposition": "mandatory",
                "message": "正文宜统一使用 3 号字（约 16pt）。",
                "min_text_length": 8,
            }
        )
    return rules


def _derive_term_rows(by_type: dict[RuleDraftSourceType, list[NormalizedSourceSnapshot]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    preferred_rows: list[dict[str, object]] = []
    banned_rows: list[dict[str, object]] = []
    seen_preferred: set[tuple[str, str]] = set()
    seen_banned: set[str] = set()

    for snapshot in _preferred_snapshots(
        by_type,
        RuleDraftSourceType.STANDARD,
        RuleDraftSourceType.TEMPLATE,
        RuleDraftSourceType.SAMPLE,
    ):
        for paragraph in snapshot.body_paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            for match in PREFERRED_TERM_PATTERN.finditer(text):
                canonical = match.group("canonical").strip()
                variant = match.group("variant").strip()
                key = (canonical, variant)
                if key in seen_preferred:
                    continue
                seen_preferred.add(key)
                preferred_rows.append(
                    {
                        "rule_id": f"terminology.preferred.{len(preferred_rows) + 1:03d}",
                        "canonical": canonical,
                        "variant": variant,
                        "severity": "error",
                        "disposition": "mandatory",
                        "suggestion": f"建议统一使用“{canonical}”。",
                    }
                )

            for match in BANNED_TERM_PATTERN.finditer(text):
                term = match.group("term").strip()
                if term in seen_banned:
                    continue
                seen_banned.add(term)
                banned_rows.append(
                    {
                        "rule_id": f"terminology.banned.{len(banned_rows) + 1:03d}",
                        "term": term,
                        "severity": "warning",
                        "disposition": "suggestion",
                        "message": f"检测到禁用表达“{term}”。",
                        "suggestion": "请改为规范表述。",
                    }
                )

    return preferred_rows, banned_rows


def _preferred_snapshots(
    by_type: dict[RuleDraftSourceType, list[NormalizedSourceSnapshot]],
    *order: RuleDraftSourceType,
) -> list[NormalizedSourceSnapshot]:
    for source_type in order:
        snapshots = by_type.get(source_type, [])
        if snapshots:
            return snapshots
    return []


def _most_common(values):
    return Counter(values).most_common(1)[0][0]
