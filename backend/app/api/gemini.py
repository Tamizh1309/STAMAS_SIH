"""Gemini routes — thin handlers over gemini_service."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ApiError
from ..db.database import get_db
from ..schemas.gemini import CartelDetectRequest, CopilotRequest, NoticeRequest, VerificationRequest
from ..services import gemini_service
from ..services import tender_service

router = APIRouter(tags=["gemini"])


@router.post(
    "/verify-bid",
    summary="Deep AI clause verification",
    description="Audits bidder clauses against tender specs (Gemini, or local rule engine fallback).",
)
def verify_bid(payload: VerificationRequest):
    result = gemini_service.verify_bid(
        payload.tenderDetails, payload.bidderDetails, payload.clausesToVerify
    )
    return {
        "success": True,
        "data": result,
        "engine": result.get("engine") or ("Local Rule Engine" if result.get("fallback") else "Gemini AI"),
    }


@router.post(
    "/generate-notice",
    summary="Generate clarification notice",
    description="Drafts a formal GoI/CPCL GeM CSQ clarification notice for the bidder's deviations.",
)
def generate_notice(payload: NoticeRequest):
    notice = gemini_service.generate_notice(
        payload.tenderNo,
        payload.tenderTitle,
        payload.bidderName,
        [d.model_dump() for d in payload.deviations],
        payload.contactOfficer,
    )
    return {"success": True, "noticeText": notice}


@router.post(
    "/detect-cartel",
    summary="Collusion radar",
    description="Returns decision-support risk indicators (never accusations) for the tender.",
)
async def detect_cartel(payload: CartelDetectRequest, db: AsyncSession = Depends(get_db)):
    try:
        tender = await tender_service.get_tender(db, payload.tenderId)
    except ApiError:
        tender = await tender_service.get_tender(db, "tender-1") if payload.tenderId != "tender-1" else None
    return gemini_service.detect_cartel(tender)


@router.post(
    "/copilot-chat",
    summary="Procurement copilot chat",
    description="Grounded Q&A over GFR 2017, CVC, GeM, MII/MSE and oil & gas standards.",
)
def copilot_chat(payload: CopilotRequest):
    if not payload.message or not payload.message.strip():
        raise ApiError("Message query string is required.", 400)
    response = gemini_service.copilot_chat(payload.message, payload.tenderContext)
    return {"success": True, "reply": response["reply"], "engine": response["engine"]}
