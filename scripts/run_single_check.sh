#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

resolve_python() {
  if [[ -n "${DOC_CHECK_PYTHON:-}" ]]; then
    printf '%s\n' "${DOC_CHECK_PYTHON}"
    return
  fi

  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    printf '%s\n' "${ROOT_DIR}/.venv/bin/python"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return
  fi

  printf 'python3 is required to run a single check\n' >&2
  exit 1
}

PYTHON_BIN="$(resolve_python)"

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" "${ROOT_DIR}/scripts/run_single_check.py" "$@"
