from __future__ import annotations

import csv
import json
from pathlib import Path

from doc_check.domain.documents import StoryType
from doc_check.domain.rules import (
    BannedTermRule,
    FindingDisposition,
    FindingSeverity,
    PreferredTermRule,
    RequiredHeadingRule,
    RuleManifest,
    RulePack,
    StoryTextRule,
    StructureRules,
    StyleRule,
    TocRule,
)


class RulePackError(ValueError):
    """Raised when a ruleset cannot be loaded."""


def load_rule_pack(base_dir: str | Path) -> RulePack:
    ruleset_dir = Path(base_dir).resolve()
    manifest_data = _load_mapping_file(ruleset_dir / "manifest.yaml")
    structure_data = _load_mapping_file(ruleset_dir / "structure.yaml")
    style_data = _load_mapping_file(ruleset_dir / "style.yaml")

    manifest = RuleManifest(
        ruleset_id=_required_str(manifest_data, "ruleset_id"),
        version=_required_str(manifest_data, "version"),
        name=_required_str(manifest_data, "name"),
        document_type=_required_str(manifest_data, "document_type"),
        punctuation_rules=dict(manifest_data.get("punctuation_rules", {})),
    )

    structure_rules = StructureRules(
        required_headings=tuple(
            RequiredHeadingRule(
                text=_required_str(item, "text"),
                level=int(item["level"]),
                severity=_parse_severity(item.get("severity", "error")),
                disposition=_parse_disposition(item.get("disposition", "mandatory")),
                rule_id=_required_str(item, "rule_id"),
            )
            for item in structure_data.get("required_headings", [])
        ),
        toc_rule=(
            TocRule(
                required=bool(structure_data["toc"].get("required", False)),
                match_headings=bool(structure_data["toc"].get("match_headings", False)),
                severity=_parse_severity(structure_data["toc"].get("severity", "error")),
                disposition=_parse_disposition(
                    structure_data["toc"].get("disposition", "mandatory")
                ),
                rule_id=_required_str(structure_data["toc"], "rule_id"),
            )
            if "toc" in structure_data
            else None
        ),
        story_text_rules=tuple(
            StoryTextRule(
                story_type=StoryType(_required_str(item, "story_type")),
                expected_contains=_required_str(item, "expected_contains"),
                severity=_parse_severity(item.get("severity", "warning")),
                disposition=_parse_disposition(item.get("disposition", "mandatory")),
                rule_id=_required_str(item, "rule_id"),
            )
            for item in structure_data.get("story_text_rules", [])
        ),
    )

    style_rules = tuple(
        StyleRule(
            rule_id=_required_str(item, "rule_id"),
            applies_to_style=_required_str(item, "applies_to_style"),
            field=_required_str(item, "field"),
            expected=item["expected"],
            severity=_parse_severity(item.get("severity", "error")),
            disposition=_parse_disposition(item.get("disposition", "mandatory")),
            message=_required_str(item, "message"),
        )
        for item in style_data.get("paragraph_rules", [])
    )

    preferred_terms = tuple(
        PreferredTermRule(
            rule_id=_required_str(item, "rule_id"),
            canonical=_required_str(item, "canonical"),
            variant=_required_str(item, "variant"),
            severity=_parse_severity(item.get("severity", "error")),
            disposition=_parse_disposition(item.get("disposition", "mandatory")),
            suggestion=_required_str(item, "suggestion"),
        )
        for item in _load_csv_rows(ruleset_dir / "terminology.csv")
    )

    banned_terms = tuple(
        BannedTermRule(
            rule_id=_required_str(item, "rule_id"),
            term=_required_str(item, "term"),
            severity=_parse_severity(item.get("severity", "warning")),
            disposition=_parse_disposition(item.get("disposition", "suggestion")),
            message=_required_str(item, "message"),
            suggestion=item.get("suggestion") or None,
        )
        for item in _load_csv_rows(ruleset_dir / "banned_terms.csv")
    )

    return RulePack(
        base_dir=ruleset_dir,
        manifest=manifest,
        structure_rules=structure_rules,
        style_rules=style_rules,
        preferred_terms=preferred_terms,
        banned_terms=banned_terms,
    )


def _load_mapping_file(path: Path) -> dict:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RulePackError(f"Missing ruleset file: {path.name}") from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RulePackError(
            f"Ruleset file {path.name} must contain JSON-compatible YAML"
        ) from exc

    if not isinstance(data, dict):
        raise RulePackError(f"Ruleset file {path.name} must define a mapping")
    return data


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError as exc:
        raise RulePackError(f"Missing ruleset file: {path.name}") from exc


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if value is None:
        raise RulePackError(f"Missing required field: {key}")
    result = str(value).strip()
    if not result:
        raise RulePackError(f"Field {key} must be a non-empty string")
    return result


def _parse_severity(raw_value: str) -> FindingSeverity:
    try:
        return FindingSeverity(str(raw_value).strip().lower())
    except ValueError as exc:
        raise RulePackError(f"Unsupported severity: {raw_value}") from exc


def _parse_disposition(raw_value: str) -> FindingDisposition:
    try:
        return FindingDisposition(str(raw_value).strip().lower())
    except ValueError as exc:
        raise RulePackError(f"Unsupported disposition: {raw_value}") from exc
