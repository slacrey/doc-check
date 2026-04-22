from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import Path
from typing import Any

from doc_check.domain.documents import DocumentSnapshot, LocationRef, StoryType


class FindingSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class FindingDisposition(StrEnum):
    MANDATORY = "mandatory"
    SUGGESTION = "suggestion"


@dataclass(frozen=True, slots=True)
class RuleManifest:
    ruleset_id: str
    version: str
    name: str
    document_type: str
    punctuation_rules: dict[str, bool]


@dataclass(frozen=True, slots=True)
class RequiredHeadingRule:
    text: str
    level: int
    severity: FindingSeverity
    disposition: FindingDisposition
    rule_id: str


@dataclass(frozen=True, slots=True)
class StoryTextRule:
    story_type: StoryType
    expected_contains: str
    severity: FindingSeverity
    disposition: FindingDisposition
    rule_id: str


@dataclass(frozen=True, slots=True)
class TocRule:
    required: bool
    match_headings: bool
    severity: FindingSeverity
    disposition: FindingDisposition
    rule_id: str


@dataclass(frozen=True, slots=True)
class StructureRules:
    required_headings: tuple[RequiredHeadingRule, ...]
    toc_rule: TocRule | None
    story_text_rules: tuple[StoryTextRule, ...]


@dataclass(frozen=True, slots=True)
class StyleRule:
    rule_id: str
    applies_to_style: str
    field: str
    expected: Any
    severity: FindingSeverity
    disposition: FindingDisposition
    message: str


@dataclass(frozen=True, slots=True)
class PreferredTermRule:
    rule_id: str
    canonical: str
    variant: str
    severity: FindingSeverity
    disposition: FindingDisposition
    suggestion: str


@dataclass(frozen=True, slots=True)
class BannedTermRule:
    rule_id: str
    term: str
    severity: FindingSeverity
    disposition: FindingDisposition
    message: str
    suggestion: str | None


@dataclass(frozen=True, slots=True)
class RulePack:
    base_dir: Path
    manifest: RuleManifest
    structure_rules: StructureRules
    style_rules: tuple[StyleRule, ...]
    preferred_terms: tuple[PreferredTermRule, ...]
    banned_terms: tuple[BannedTermRule, ...]

    @property
    def ruleset_id(self) -> str:
        return self.manifest.ruleset_id

    @property
    def version(self) -> str:
        return self.manifest.version


@dataclass(frozen=True, slots=True)
class RuleFinding:
    rule_id: str
    ruleset_id: str
    ruleset_version: str
    category: str
    severity: FindingSeverity
    disposition: FindingDisposition
    message: str
    location: LocationRef | None
    location_label: str
    evidence: str | None = None
    suggestion: str | None = None

    @property
    def finding_id(self) -> str:
        payload = {
            "rule_id": self.rule_id,
            "category": self.category,
            "message": self.message,
            "location_id": self.location.location_id if self.location else None,
            "location_label": self.location_label,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
        }
        digest = hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return digest[:16]


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    ruleset_id: str
    ruleset_version: str
    findings: tuple[RuleFinding, ...]


def document_level_finding(
    *,
    rule_pack: RulePack,
    rule_id: str,
    category: str,
    severity: FindingSeverity,
    disposition: FindingDisposition,
    message: str,
    suggestion: str | None = None,
    evidence: str | None = None,
) -> RuleFinding:
    return RuleFinding(
        rule_id=rule_id,
        ruleset_id=rule_pack.ruleset_id,
        ruleset_version=rule_pack.version,
        category=category,
        severity=severity,
        disposition=disposition,
        message=message,
        location=None,
        location_label="文档级",
        evidence=evidence,
        suggestion=suggestion,
    )


def paragraph_location(snapshot: DocumentSnapshot, *, story_type: StoryType, paragraph_index: int) -> LocationRef | None:
    for location in snapshot.commentable_locations:
        if location.story_type is story_type and location.paragraph_index == paragraph_index:
            return location
    for location in snapshot.summary_only_locations:
        if location.story_type is story_type and location.paragraph_index == paragraph_index:
            return location
    return None


def story_location(
    snapshot: DocumentSnapshot,
    *,
    story_type: StoryType,
    section_index: int | None = None,
) -> LocationRef | None:
    for collection in (snapshot.summary_only_locations, snapshot.commentable_locations):
        for location in collection:
            if location.story_type is story_type and location.section_index == section_index:
                return location
    return None
