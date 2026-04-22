from __future__ import annotations

from doc_check.domain.documents import DocumentSnapshot
from doc_check.domain.rules import RuleEvaluation, RuleFinding, RulePack
from doc_check.rules.checks.layout import run_layout_checks
from doc_check.rules.checks.punctuation import run_punctuation_checks
from doc_check.rules.checks.structure import run_structure_checks
from doc_check.rules.checks.style import run_style_checks
from doc_check.rules.checks.terminology import run_terminology_checks

SEVERITY_ORDER = {
    "error": 0,
    "warning": 1,
    "info": 2,
}


class RuleEngine:
    def evaluate(self, snapshot: DocumentSnapshot, rule_pack: RulePack) -> RuleEvaluation:
        findings: list[RuleFinding] = []
        findings.extend(run_structure_checks(snapshot, rule_pack))
        findings.extend(run_layout_checks(snapshot, rule_pack))
        findings.extend(run_style_checks(snapshot, rule_pack))
        findings.extend(run_terminology_checks(snapshot, rule_pack))
        findings.extend(run_punctuation_checks(snapshot, rule_pack))

        findings.sort(
            key=lambda finding: (
                SEVERITY_ORDER[finding.severity.value],
                finding.category,
                finding.location_label,
                finding.rule_id,
            )
        )

        return RuleEvaluation(
            ruleset_id=rule_pack.ruleset_id,
            ruleset_version=rule_pack.version,
            findings=tuple(findings),
        )
