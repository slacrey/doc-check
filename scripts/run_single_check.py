from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from doc_check.config import AppConfig
from doc_check.domain.documents import CreateArtifactCommand, UserContext
from doc_check.persistence.repositories import ArtifactRepository
from doc_check.services.check_execution import CheckExecutionService
from doc_check.services.check_pipeline import ArtifactValidationError, CheckPipelineService
from doc_check.services.review_service import ReviewService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one AEOS DOCX check locally")
    parser.add_argument("input_path", help="Path to the source .docx file")
    parser.add_argument(
        "--workspace-dir",
        default=str(ROOT),
        help="Workspace directory used for data, config, and artifacts",
    )
    parser.add_argument("--ruleset-id", default="aeos", help="Ruleset identifier")
    parser.add_argument("--ruleset-version", default="2026.04", help="Ruleset version")
    parser.add_argument("--user-id", default="local-cli", help="Audit user id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_dir = Path(args.workspace_dir).resolve()
    input_path = Path(args.input_path).resolve()

    if not input_path.exists():
        print(f"Input file was not found: {input_path}", file=sys.stderr)
        return 1

    env = dict(os.environ)
    env.setdefault("DOC_CHECK_RULESETS_DIR", str(ROOT / "rulesets"))
    env.setdefault(
        "DOC_CHECK_TEMPLATES_DIR",
        str(ROOT / "src" / "doc_check" / "web" / "templates"),
    )

    config = AppConfig.from_env(env, cwd=workspace_dir)
    config.ensure_directories()

    repository = ArtifactRepository(config.database_path)
    repository.init_schema()

    execution_service = CheckExecutionService(
        check_service=CheckPipelineService(config=config, repository=repository),
        review_service=ReviewService(config=config, repository=repository),
    )

    try:
        result = execution_service.run_check(
            CreateArtifactCommand(
                original_filename=input_path.name,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                payload=input_path.read_bytes(),
                ruleset_id=args.ruleset_id,
                ruleset_version=args.ruleset_version,
                user=UserContext.local(args.user_id),
            )
        )
    except ArtifactValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Single check failed: {exc}", file=sys.stderr)
        return 1

    payload = result.as_public_dict()
    payload["outputs"] = {
        "artifact_dir": str(result.artifact.storage_path.parent),
        "original_docx": str(result.artifact.storage_path),
        "annotated_docx": (
            str(result.artifact.annotated_path) if result.artifact.annotated_path is not None else None
        ),
        "summary_json": (
            str(result.artifact.summary_path) if result.artifact.summary_path is not None else None
        ),
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
