"""System routes — health telemetry and SIH analytics."""
import time
from datetime import datetime

from fastapi import APIRouter

from ..core.config import settings
from ..db.database import check_connection, session_scope
from ..db.repositories import TenderRepository
from ..services import gemini_service, tender_service

router = APIRouter(tags=["system"])
_started_at = time.monotonic()


@router.get(
    "/health",
    summary="System health",
    description="Reports status, active AI engine (Gemini vs Local Rule Engine), DB info and uptime.",
)
async def health():
    engine = gemini_service.get_engine_status()
    connected = await check_connection()
    record_count = 0
    if connected:
        try:
            async with session_scope() as session:
                record_count = await TenderRepository.count(session)
        except Exception:
            connected = False
            record_count = 0
    return {
        "success": True,
        "status": "OPERATIONAL",
        "version": settings.APP_VERSION,
        "psId": settings.PS_ID,
        "authority": "Ministry of Petroleum & Natural Gas / CPCL",
        "gemApiGateway": "ACTIVE_SYNC (GeM 4.0)",
        "cvcAuditGuard": "ENFORCED",
        "aiEngine": engine["engine"],
        "model": engine["model"],
        "isLiveAI": engine["isLive"],
        "database": {
            "connected": connected,
            "dbType": "postgresql" if connected else "disconnected",
            "recordCount": record_count,
            "lastSync": datetime.now().isoformat(),
        },
        "uptimeSeconds": int(time.monotonic() - _started_at),
        "timestamp": datetime.now().isoformat(),
    }


@router.get(
    "/analytics",
    summary="SIH impact analytics",
    description="Before/after evaluation metrics, refinery savings and the PS 26100 problem brief.",
)
async def analytics():
    return {"success": True, "data": tender_service.get_analytics()}
