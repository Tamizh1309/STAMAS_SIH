"""Consistent API error format: {"success": false, "message": ...}."""
from fastapi import Request
from fastapi.responses import JSONResponse


import logging
import traceback

log = logging.getLogger("stamas.api")


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    log.warning("API error on %s %s (%s): %s", request.method, request.url.path, exc.status_code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message},
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("Unhandled error on %s %s: %s\n%s", request.method, request.url.path, exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": f"Internal server error: {str(exc)}"},
    )
