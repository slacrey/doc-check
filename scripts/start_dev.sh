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

  printf 'python3 is required to start the service\n' >&2
  exit 1
}

PYTHON_BIN="$(resolve_python)"

cd "${ROOT_DIR}"
export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

exec "${PYTHON_BIN}" -m uvicorn \
  doc_check.main:app \
  --host "${DOC_CHECK_HOST:-127.0.0.1}" \
  --port "${DOC_CHECK_PORT:-8000}" \
  --reload
