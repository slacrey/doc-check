from __future__ import annotations

from pathlib import Path
from typing import Mapping

from doc_check.config import AppConfig


def make_test_config(
    tmp_path: Path,
    env_overrides: Mapping[str, str] | None = None,
) -> AppConfig:
    env = {
        "DOC_CHECK_RULESETS_DIR": str(Path("rulesets").resolve()),
        "DOC_CHECK_TEMPLATES_DIR": str((Path("src") / "doc_check" / "web" / "templates").resolve()),
    }
    if env_overrides:
        env.update(env_overrides)

    return AppConfig.from_env(
        env,
        cwd=tmp_path,
    )
