"""Vercel serverless entrypoint for the STAMAS FastAPI backend.

Vercel's Python runtime serves the ASGI `app` from this file and routes
`/api/*` here (see vercel.json).
"""
import logging
import os
import sys
from pathlib import Path

# Add possible locations of backend and root to sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
cwd_backend = Path(os.getcwd()) / "backend"

for p in [str(backend_dir), str(cwd_backend), str(root_dir), os.getcwd()]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app  # noqa: E402,F401
except ImportError:
    try:
        from backend.app.main import app  # noqa: E402,F401
    except Exception as exc:
        logging.exception("CRITICAL: Failed to import FastAPI application: %s", exc)
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        app = FastAPI(title="STAMAS Fallback Diagnostics")

        @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
        async def fallback(path: str):
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Backend import failure",
                    "message": str(exc),
                    "sys_path": sys.path,
                    "cwd": os.getcwd(),
                },
            )
