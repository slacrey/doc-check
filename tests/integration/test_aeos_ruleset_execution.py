from __future__ import annotations

from pathlib import Path

from doc_check.parsers.docx_reader import read_docx_snapshot
from doc_check.rules.engine import RuleEngine
from doc_check.rules.rule_pack import load_rule_pack
from tests.support.docx_samples import ensure_docx_samples


def test_aeos_rule_engine_runs_across_categories(tmp_path):
    fixture_paths = ensure_docx_samples(tmp_path)
    rule_pack = load_rule_pack(Path("rulesets/aeos"))
    engine = RuleEngine()

    valid_evaluation = engine.evaluate(read_docx_snapshot(fixture_paths["valid"]), rule_pack)
    error_evaluation = engine.evaluate(read_docx_snapshot(fixture_paths["format_errors"]), rule_pack)

    assert valid_evaluation.ruleset_id == "aeos"
    assert valid_evaluation.ruleset_version == "2026.05"
    assert valid_evaluation.findings == ()

    categories = {finding.category for finding in error_evaluation.findings}
    assert categories == {"layout", "structure", "style", "terminology", "punctuation"}
    assert all(finding.ruleset_version == "2026.05" for finding in error_evaluation.findings)
