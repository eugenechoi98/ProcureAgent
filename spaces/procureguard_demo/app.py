"""Hugging Face Spaces entrypoint for ProcureGuard AI Demo."""

from __future__ import annotations

from demo.app import build_app


app = build_app()


if __name__ == "__main__":
    app.launch(share=False)
