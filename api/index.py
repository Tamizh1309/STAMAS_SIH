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

# Import the real FastAPI application
try:
    from backend.app.main import app as _app  # type: ignore[import-not-found] # noqa: E402
except ImportError:
    from app.main import app as _app  # type: ignore[import-not-found] # noqa: E402

# Top-level assignment required for Vercel's static AST analyzer (@vercel/python-analysis)
# Without a top-level assignment or direct definition, Vercel CLI treats the file as
# non-runnable and fails with: "The pattern 'api/index.py' defined in functions doesn't match..."
app = _app

__all__ = ["app"]
