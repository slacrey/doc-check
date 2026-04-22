from __future__ import annotations

import re

from doc_check.domain.documents import StoryType
from doc_check.domain.rules import RuleFinding, RulePack, StyleRule, StyleRuleScope, paragraph_location
from doc_check.domain.documents import DocumentSnapshot

FLOAT_TOLERANCE = 0.01
TOC_STYLE_PATTERN = re.compile(r"toc\s*\d*", re.IGNORECASE)


def run_style_checks(snapshot: DocumentSnapshot, rule_pack: RulePack) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for paragraph in snapshot.main_story.paragraphs:
        if not paragraph.text.strip():
            continue

        for rule in rule_pack.style_rules:
            if not _paragraph_matches_rule(paragraph, rule):
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


def _paragraph_matches_rule(paragraph, rule: StyleRule) -> bool:
    if len(paragraph.text.strip()) < rule.min_text_length:
        return False

    if rule.scope is StyleRuleScope.STYLE_CHAIN:
        return bool(rule.applies_to_style) and rule.applies_to_style in paragraph.style_chain

    if rule.scope is StyleRuleScope.BODY_PARAGRAPH:
        if paragraph.heading_level is not None:
            return False
        if TOC_STYLE_PATTERN.search(paragraph.style_name or ""):
            return False
        if "table[" in "/".join(paragraph.block_path):
            return False
        return paragraph.format.alignment != "center"

    return False


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
    if isinstance(expected_value, (list, tuple)):
        return any(_matches_expected(actual_value, item) for item in expected_value)
    if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
        return abs(float(actual_value) - float(expected_value)) <= FLOAT_TOLERANCE
    return actual_value == expected_value
