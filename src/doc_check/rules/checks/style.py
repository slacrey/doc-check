from __future__ import annotations

from doc_check.domain.documents import StoryType
from doc_check.domain.rules import RuleFinding, RulePack, paragraph_location
from doc_check.domain.documents import DocumentSnapshot

FLOAT_TOLERANCE = 0.01


def run_style_checks(snapshot: DocumentSnapshot, rule_pack: RulePack) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for paragraph in snapshot.main_story.paragraphs:
        if not paragraph.text.strip():
            continue

        for rule in rule_pack.style_rules:
            if rule.applies_to_style not in paragraph.style_chain:
                continue

            actual_value, evidence = _resolve_style_field(paragraph, rule.field)
            if _matches_expected(actual_value, rule.expected):
                continue

            location = paragraph_location(
                snapshot,
                story_type=StoryType.MAIN,
                paragraph_index=paragraph.paragraph_index,
            )
            findings.append(
                RuleFinding(
                    rule_id=rule.rule_id,
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="style",
                    severity=rule.severity,
                    disposition=rule.disposition,
                    message=rule.message,
                    suggestion=f"当前值为 {actual_value!r}，应调整为 {rule.expected!r}。",
                    evidence=evidence,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

    return findings


def _resolve_style_field(paragraph, field: str):
    if hasattr(paragraph.format, field):
        return getattr(paragraph.format, field), paragraph.text_excerpt

    if field in {"font_name", "font_size_pt"}:
        for run in paragraph.runs:
            if not run.text.strip():
                continue
            value = getattr(run, field)
            if value is not None:
                return value, run.text
        return None, paragraph.text_excerpt

    raise ValueError(f"Unsupported style field: {field}")


def _matches_expected(actual_value, expected_value) -> bool:
    if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
        return abs(float(actual_value) - float(expected_value)) <= FLOAT_TOLERANCE
    return actual_value == expected_value
