from __future__ import annotations

from doc_check.domain.rules import RuleFinding, RulePack
from doc_check.domain.documents import DocumentSnapshot

FLOAT_TOLERANCE_MM = 1.0


def run_layout_checks(snapshot: DocumentSnapshot, rule_pack: RulePack) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for section in snapshot.sections:
        for rule in rule_pack.layout_rules:
            actual_value = getattr(section, rule.field, None)
            if _matches_expected(actual_value, rule.expected):
                continue

            findings.append(
                RuleFinding(
                    rule_id=rule.rule_id,
                    ruleset_id=rule_pack.ruleset_id,
                    ruleset_version=rule_pack.version,
                    category="layout",
                    severity=rule.severity,
                    disposition=rule.disposition,
                    message=rule.message,
                    suggestion=f"当前值为 {actual_value!r}，应调整为 {rule.expected!r}。",
                    evidence=f"第{section.section_index + 1}节",
                    location=None,
                    location_label=f"第{section.section_index + 1}节版式",
                )
            )

    return findings


def _matches_expected(actual_value, expected_value) -> bool:
    if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
        return abs(float(actual_value) - float(expected_value)) <= FLOAT_TOLERANCE_MM
    return actual_value == expected_value
