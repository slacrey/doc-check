from __future__ import annotations

from pathlib import Path

from doc_check.config import AppConfig


def make_test_config(tmp_path: Path) -> AppConfig:
    return AppConfig.from_env(
        {
            "DOC_CHECK_RULESETS_DIR": str(Path("rulesets").resolve()),
            "DOC_CHECK_TEMPLATES_DIR": str((Path("src") / "doc_check" / "web" / "templates").resolve()),
        },
        cwd=tmp_path,
    )
