from __future__ import annotations

import re

from doc_check.domain.documents import StoryType
from doc_check.domain.rules import (
    ParagraphMetricKind,
    ParagraphPatternMode,
    RuleFinding,
    RulePack,
    document_level_finding,
    paragraph_location,
    story_location,
)
from doc_check.domain.documents import DocumentSnapshot


def run_structure_checks(snapshot: DocumentSnapshot, rule_pack: RulePack) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    headings = [paragraph for paragraph in snapshot.main_story.paragraphs if paragraph.heading_level is not None]

    for rule in rule_pack.structure_rules.required_headings:
        heading = next((item for item in headings if item.text.strip() == rule.text), None)
        if heading is None:
            findings.append(
                document_level_finding(
                    rule_pack=rule_pack,
                    rule_id=rule.rule_id,
                    category="structure",
                    severity=rule.severity,
                    disposition=rule.disposition,
                    message=f"缺少必备章节：{rule.text}",
                    suggestion=f"请补充 {rule.text} 章节，并使用标题 {rule.level} 样式。",
                )
            )
            continue

        if heading.heading_level != rule.level:
            location = paragraph_location(
                snapshot,
                story_type=StoryType.MAIN,
                paragraph_index=heading.paragraph_index,
            )
            findings.append(
                RuleFinding(
                    rule_id=rule.rule_id,
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="structure",
                    severity=rule.severity,
                    disposition=rule.disposition,
                    message=f"章节 {rule.text} 的标题层级不符合预期。",
                    suggestion=f"应调整为标题 {rule.level} 层级。",
                    evidence=heading.text,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

    toc_rule = rule_pack.structure_rules.toc_rule
    if toc_rule is not None:
        if toc_rule.required and not snapshot.toc_entries:
            findings.append(
                document_level_finding(
                    rule_pack=rule_pack,
                    rule_id=toc_rule.rule_id,
                    category="structure",
                    severity=toc_rule.severity,
                    disposition=toc_rule.disposition,
                    message="文档缺少目录信息。",
                    suggestion="请补充目录并更新页码。",
                )
            )
        elif toc_rule.match_headings and snapshot.toc_entries:
            heading_titles = [paragraph.text.strip() for paragraph in headings]
            toc_titles = [entry.title for entry in snapshot.toc_entries]
            if heading_titles[: len(toc_titles)] != toc_titles:
                location = paragraph_location(
                    snapshot,
                    story_type=StoryType.MAIN,
                    paragraph_index=snapshot.toc_entries[0].paragraph_index,
                )
                findings.append(
                    RuleFinding(
                        rule_id=toc_rule.rule_id,
                        ruleset_id=rule_pack.ruleset_id,
                        ruleset_version=rule_pack.version,
                        category="structure",
                        severity=toc_rule.severity,
                        disposition=toc_rule.disposition,
                        message="目录条目与正文标题不一致。",
                        suggestion="请刷新目录并核对目录标题与正文标题是否一致。",
                        evidence=" / ".join(toc_titles),
                        location=location,
                        location_label=location.label if location else "文档级",
                    )
                )

    for rule in rule_pack.structure_rules.story_text_rules:
        stories = (
            snapshot.headers if rule.story_type is StoryType.HEADER else snapshot.footers
        )
        for story in stories:
            story_text = " ".join(
                paragraph.text.strip() for paragraph in story.paragraphs if paragraph.text.strip()
            )
            if rule.expected_contains in story_text:
                continue

            location = story_location(
                snapshot,
                story_type=rule.story_type,
                section_index=story.section_index,
            )
            findings.append(
                RuleFinding(
                    rule_id=rule.rule_id,
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="structure",
                    severity=rule.severity,
                    disposition=rule.disposition,
                    message=f"{rule.story_type.value} 内容不符合预期。",
                    suggestion=f"请确认包含标准内容：{rule.expected_contains}",
                    evidence=story_text or None,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

    text_paragraphs = [paragraph for paragraph in snapshot.main_story.paragraphs if paragraph.text.strip()]
    for rule in rule_pack.structure_rules.paragraph_pattern_rules:
        target_paragraphs = _select_target_paragraphs(
            text_paragraphs,
            first_n_paragraphs=rule.first_n_paragraphs,
            last_n_paragraphs=rule.last_n_paragraphs,
        )

        if rule.mode is ParagraphPatternMode.REQUIRE_ANY:
            matched = next(
                (paragraph for paragraph in target_paragraphs if re.search(rule.pattern, paragraph.text)),
                None,
            )
            if matched is None:
                findings.append(
                    document_level_finding(
                        rule_pack=rule_pack,
                        rule_id=rule.rule_id,
                        category="structure",
                        severity=rule.severity,
                        disposition=rule.disposition,
                        message=rule.message,
                        suggestion=rule.suggestion,
                    )
                )
            continue

        for paragraph in target_paragraphs:
            match = re.search(rule.pattern, paragraph.text)
            if match is None:
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
                    category="structure",
                    severity=rule.severity,
                    disposition=rule.disposition,
                    message=rule.message,
                    suggestion=rule.suggestion,
                    evidence=match.group(0),
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

    for rule in rule_pack.structure_rules.paragraph_signal_rules:
        target_paragraphs = _select_target_paragraphs(
            text_paragraphs,
            first_n_paragraphs=rule.first_n_paragraphs,
            last_n_paragraphs=rule.last_n_paragraphs,
        )
        combined_text = "\n".join(paragraph.text for paragraph in target_paragraphs)
        matched_patterns = [
            pattern for pattern in rule.patterns if re.search(pattern, combined_text)
        ]

        if len(matched_patterns) >= rule.min_matches:
            continue

        findings.append(
            document_level_finding(
                rule_pack=rule_pack,
                rule_id=rule.rule_id,
                category="structure",
                severity=rule.severity,
                disposition=rule.disposition,
                message=rule.message,
                suggestion=rule.suggestion,
                evidence=combined_text[:200] or None,
            )
        )

    for rule in rule_pack.structure_rules.paragraph_metric_rules:
        target_paragraphs = _select_target_paragraphs(
            text_paragraphs,
            first_n_paragraphs=rule.first_n_paragraphs,
            last_n_paragraphs=rule.last_n_paragraphs,
        )
        for paragraph in target_paragraphs:
            metric_value, evidence = _measure_paragraph_metric(paragraph.text, rule)
            if metric_value <= rule.max_value:
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
                    category="structure",
                    severity=rule.severity,
                    disposition=rule.disposition,
                    message=rule.message,
                    suggestion=rule.suggestion,
                    evidence=evidence,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

    return findings


def _select_target_paragraphs(
    paragraphs,
    *,
    first_n_paragraphs: int | None,
    last_n_paragraphs: int | None,
):
    target_paragraphs = list(paragraphs)
    if first_n_paragraphs is not None:
        target_paragraphs = target_paragraphs[:first_n_paragraphs]
    if last_n_paragraphs is not None:
        target_paragraphs = target_paragraphs[-last_n_paragraphs:]
    return target_paragraphs


def _measure_paragraph_metric(text: str, rule) -> tuple[int, str]:
    if rule.kind is ParagraphMetricKind.TEXT_LENGTH:
        return len(text.strip()), text.strip()

    if rule.kind is ParagraphMetricKind.PATTERN_COUNT:
        matches = re.findall(rule.pattern or "", text)
        return len(matches), f"{text.strip()} (命中 {len(matches)} 次)"

    raise ValueError(f"Unsupported paragraph metric kind: {rule.kind}")
