from __future__ import annotations

from pathlib import Path

from doc_check.rules.rule_pack import load_rule_pack


def test_rule_pack_loader_reads_aeos_ruleset():
    rule_pack = load_rule_pack(Path("rulesets/aeos"))

    assert rule_pack.ruleset_id == "aeos"
    assert rule_pack.version == "2026.05"
    assert len(rule_pack.structure_rules.required_headings) == 2
    assert len(rule_pack.layout_rules) == 6
    assert len(rule_pack.style_rules) == 2
    assert len(rule_pack.preferred_terms) == 1
    assert len(rule_pack.banned_terms) == 1


def test_rule_pack_loader_reads_news_publicity_ruleset():
    rule_pack = load_rule_pack(Path("rulesets/news_publicity"))

    assert rule_pack.ruleset_id == "news_publicity"
    assert rule_pack.version == "2026.05"
    assert len(rule_pack.structure_rules.paragraph_pattern_rules) == 6
    assert len(rule_pack.structure_rules.paragraph_signal_rules) == 1
    assert len(rule_pack.structure_rules.paragraph_metric_rules) == 2
    assert len(rule_pack.style_rules) == 0
    assert len(rule_pack.layout_rules) == 0
    assert len(rule_pack.banned_terms) == 4


def test_rule_pack_loader_reads_speech_ruleset():
    rule_pack = load_rule_pack(Path("rulesets/speech"))

    assert rule_pack.ruleset_id == "speech"
    assert rule_pack.version == "2026.05"
    assert len(rule_pack.structure_rules.paragraph_pattern_rules) == 8
    assert len(rule_pack.structure_rules.paragraph_signal_rules) == 1
    assert len(rule_pack.structure_rules.paragraph_metric_rules) == 0
    assert len(rule_pack.style_rules) == 0
    assert len(rule_pack.layout_rules) == 0
    assert len(rule_pack.banned_terms) == 3
