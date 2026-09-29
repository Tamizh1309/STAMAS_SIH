"""STAMAS FastAPI application — React <-REST-> FastAPI -> services -> repositories -> Neon PostgreSQL."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import documents as document_routes
from .api import gemini as gemini_routes
from .api import system as system_routes
from .api import tenders as tender_routes
from .core.config import settings
from .core.errors import ApiError, api_error_handler, unhandled_error_handler
from .db.database import dispose_engine, session_scope
from .db.repositories import TenderRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with session_scope() as session:
            await TenderRepository.seed_initial_tenders(session)
    except Exception:
        pass
    yield
    await dispose_engine()


app = FastAPI(
    title="STAMAS — Smart Tender Analysis & Management Assessment System",
    description=(
        "AI-powered integrated bid compliance verification for GeM public procurement "
        "(CPCL / Ministry of Petroleum & Natural Gas). Tenders, clause verification, "
        "clarification notices, collusion radar, copilot chat, SIH analytics."
    ),
    version="3.8.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"success": False, "message": str(exc.errors())})


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": f'API endpoint "{request.method} {request.url.path}" not found.'},
        )
    return JSONResponse(status_code=404, content={"success": False, "message": "Not found."})


app.include_router(tender_routes.router, prefix="/api/tenders")
app.include_router(document_routes.router, prefix="/api/tenders")
app.include_router(gemini_routes.router, prefix="/api/gemini")
app.include_router(system_routes.router, prefix="/api/system")


@app.get("/api", include_in_schema=False)
def api_root():
    return {"success": True, "message": "STAMAS API. See /api/docs for Swagger UI."}
