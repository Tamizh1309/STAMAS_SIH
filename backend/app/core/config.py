"""Central application configuration (env-driven, no secrets in code)."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Always load backend/.env regardless of the process working directory
# (e.g. `npm run dev` runs from the repo root), then honour any CWD .env.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv()


def _parse_origins(raw: str) -> list[str]:
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


class Settings:
    PORT: int = int(os.getenv("PORT", "8000"))
    GEMINI_API_KEY: str = (os.getenv("GEMINI_API_KEY") or "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    ALLOWED_ORIGINS: list[str] = _parse_origins(
        os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )
    APP_VERSION: str = "STAMAS v3.8 Enterprise"
    PS_ID: str = "26100"
    # Document ingestion (demo: local disk + in-memory metadata, no PostgreSQL)
    DOCUMENT_STORAGE_PATH: str = os.getenv("DOCUMENT_STORAGE_PATH", "./storage/documents")
    MAX_DOCUMENT_SIZE_MB: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "10"))
    # Upper bound on characters of extracted text sent to Gemini per verification
    MAX_GEMINI_CHARS: int = int(os.getenv("MAX_GEMINI_CHARS", "12000"))
    # Neon PostgreSQL (asyncpg). Only ever in backend/.env — never logged.
    DATABASE_URL: str = (os.getenv("DATABASE_URL") or "").strip()

    @property
    def gemini_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY) and self.GEMINI_API_KEY != "your_gemini_api_key_here"

    @property
    def database_configured(self) -> bool:
        return bool(self.DATABASE_URL)


settings = Settings()
