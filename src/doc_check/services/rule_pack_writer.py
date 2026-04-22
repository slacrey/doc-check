from __future__ import annotations

import csv
import json
from pathlib import Path

from doc_check.services.rule_derivation import DerivedRuleDraft


class RulePackWriter:
    def write(self, *, output_root: Path, draft: DerivedRuleDraft) -> Path:
        version_dir = output_root / "generated" / draft.version
        version_dir.mkdir(parents=True, exist_ok=False)

        (version_dir / "manifest.yaml").write_text(
            json.dumps(draft.manifest_data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (version_dir / "structure.yaml").write_text(
            json.dumps(draft.structure_data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (version_dir / "style.yaml").write_text(
            json.dumps(draft.style_data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (version_dir / "evidence.json").write_text(
            json.dumps(draft.evidence, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        _write_csv(
            version_dir / "terminology.csv",
            fieldnames=("rule_id", "canonical", "variant", "severity", "disposition", "suggestion"),
            rows=draft.terminology_rows,
        )
        _write_csv(
            version_dir / "banned_terms.csv",
            fieldnames=("rule_id", "term", "severity", "disposition", "message", "suggestion"),
            rows=draft.banned_term_rows,
        )
        return version_dir


def _write_csv(path: Path, *, fieldnames: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
