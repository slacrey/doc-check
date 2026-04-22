from __future__ import annotations

from doc_check.domain.documents import StoryType
from doc_check.domain.rules import RuleFinding, RulePack, paragraph_location
from doc_check.domain.documents import DocumentSnapshot


def run_terminology_checks(snapshot: DocumentSnapshot, rule_pack: RulePack) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for paragraph in snapshot.main_story.paragraphs:
        if not paragraph.text.strip():
            continue

        location = paragraph_location(
            snapshot,
            story_type=StoryType.MAIN,
            paragraph_index=paragraph.paragraph_index,
        )

        for term_rule in rule_pack.preferred_terms:
            if term_rule.variant not in paragraph.text:
                continue

            findings.append(
                RuleFinding(
                    rule_id=term_rule.rule_id,
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="terminology",
                    severity=term_rule.severity,
                    disposition=term_rule.disposition,
                    message=f"发现非标准术语：{term_rule.variant}",
                    suggestion=term_rule.suggestion,
                    evidence=term_rule.variant,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

        for banned_term in rule_pack.banned_terms:
            if banned_term.term not in paragraph.text:
                continue

            findings.append(
                RuleFinding(
                    rule_id=banned_term.rule_id,
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="terminology",
                    severity=banned_term.severity,
                    disposition=banned_term.disposition,
                    message=banned_term.message,
                    suggestion=banned_term.suggestion,
                    evidence=banned_term.term,
                    location=location,
                    location_label=location.label if location else "文档级",
                )
            )

    return findings
