from __future__ import annotations

from pathlib import Path

from doc_check.rules.rule_pack import load_rule_pack


def test_rule_pack_loader_reads_aeos_ruleset():
    rule_pack = load_rule_pack(Path("rulesets/aeos"))

    assert rule_pack.ruleset_id == "aeos"
    assert rule_pack.version == "2026.04"
    assert len(rule_pack.structure_rules.required_headings) == 2
    assert len(rule_pack.style_rules) == 5
    assert len(rule_pack.preferred_terms) == 1
    assert len(rule_pack.banned_terms) == 1
