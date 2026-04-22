from __future__ import annotations

from doc_check.api.app import build_app

app = build_app()


def main() -> None:
    import uvicorn

    uvicorn.run("doc_check.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
