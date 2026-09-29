"""Vercel serverless entrypoint for the STAMAS FastAPI backend.

Vercel's Python runtime serves the ASGI `app` from this file and routes
`/api/*` here (see vercel.json).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory and project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"

for path in (str(backend_dir), str(root_dir)):
    if path not in sys.path:
        sys.path.insert(0, path)

# Import the real FastAPI application directly (no masking fallback)
try:
    from backend.app.main import app  # type: ignore[import-not-found] # noqa: E402
except ImportError:
    from app.main import app  # type: ignore[import-not-found] # noqa: E402

__all__ = ["app"]
