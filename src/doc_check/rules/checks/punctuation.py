from __future__ import annotations

import re

from doc_check.domain.documents import StoryType
from doc_check.domain.rules import (
    FindingDisposition,
    FindingSeverity,
    RuleFinding,
    RulePack,
    paragraph_location,
)
from doc_check.domain.documents import DocumentSnapshot

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def run_punctuation_checks(snapshot: DocumentSnapshot, rule_pack: RulePack) -> list[RuleFinding]:
    punctuation_rules = rule_pack.manifest.punctuation_rules
    findings: list[RuleFinding] = []

    for paragraph in snapshot.main_story.paragraphs:
        if not paragraph.text.strip():
            continue

        location = paragraph_location(
            snapshot,
            story_type=StoryType.MAIN,
            paragraph_index=paragraph.paragraph_index,
        )

        if (
            punctuation_rules.get("detect_mixed_commas", True)
            and "," in paragraph.text
            and "，" in paragraph.text
        ):
            findings.append(
                RuleFinding(
                    rule_id="punctuation.mixed-comma",
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="punctuation",
                    severity=FindingSeverity.WARNING,
                    disposition=FindingDisposition.SUGGESTION,
                    message="同一段落中存在中英文逗号混用。",
                    suggestion="请统一使用中文全角逗号或按规范统一标点风格。",
                    evidence=paragraph.text_excerpt,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )
            continue

        if (
            punctuation_rules.get("detect_ascii_comma_in_cjk", True)
            and "," in paragraph.text
            and CJK_PATTERN.search(paragraph.text)
        ):
            findings.append(
                RuleFinding(
                    rule_id="punctuation.ascii-comma-cjk",
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="punctuation",
                    severity=FindingSeverity.WARNING,
                    disposition=FindingDisposition.SUGGESTION,
                    message="中文语境中使用了英文逗号。",
                    suggestion="请将英文逗号替换为中文全角逗号。",
                    evidence=paragraph.text_excerpt,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

    return findings
