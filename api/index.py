"""Vercel serverless entrypoint for the STAMAS FastAPI backend.

Vercel's Python runtime serves the ASGI `app` from this file and routes
`/api/*` here (see vercel.json). No app code is duplicated.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app  # noqa: E402,F401  (re-exported for Vercel)
