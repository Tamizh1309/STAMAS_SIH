import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ApiError
from ..db.database import get_db
from ..db.repositories import TenderRepository
from ..schemas.tender import CreateTenderRequest, IngestBidRequest
from ..services import tender_service

log = logging.getLogger("stamas.tenders")
router = APIRouter(tags=["tenders"])


@router.get(
    "",
    summary="List all tenders",
    description="Returns every tender with bidders and summary stats.",
)
async def list_tenders(db: AsyncSession = Depends(get_db)):
    log.info("Fetching tender list")
    tenders = await tender_service.list_tenders(db)
    return {"success": True, "data": tenders, "count": len(tenders)}


@router.get(
    "/{tender_id}",
    summary="Get tender by ID",
    description="Returns a single tender with evaluated bidders and clause audits.",
)
async def get_tender(tender_id: str, db: AsyncSession = Depends(get_db)):
    return {"success": True, "data": await tender_service.get_tender(db, tender_id)}


@router.post(
    "",
    status_code=201,
    summary="Register a new tender",
    description="Creates a tender. Accepts JSON or multipart/form-data with optional file upload.",
)
async def create_tender(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    log.info("Processing POST /api/tenders")
    content_type = request.headers.get("content-type", "")

    files_to_process: list[UploadFile] = []
    payload_dict: dict[str, Any] = {}

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        for key, val in form.multi_items():
            if hasattr(val, "filename") and getattr(val, "filename", None):
                if val not in files_to_process:
                    files_to_process.append(val)
            elif isinstance(val, str):
                if key in ("estimatedValue", "minLocalContentRequired"):
                    try:
                        payload_dict[key] = float(val)
                    except ValueError:
                        payload_dict[key] = val
                else:
                    payload_dict[key] = val
    else:
        try:
            body = await request.json()
            if isinstance(body, dict):
                payload_dict = body
        except Exception:
            payload_dict = {}

    title = payload_dict.get("title")
    tender_no = payload_dict.get("tenderNo")
    if not title or not tender_no:
        raise ApiError("Tender title and tender number are mandatory parameters.", 400)

    tender = await tender_service.create_tender(db, payload_dict)
    tender_id = tender["id"]

    staged_file_paths: list[Path] = []
    if files_to_process:
        from ..services import document_service
        try:
            for upload in files_to_process:
                content = await upload.read()
                if content:
                    meta = await document_service.ingest_file(
                        db, tender_id, upload.filename or "", content, upload.content_type
                    )
                    if meta and meta.get("storagePath"):
                        staged_file_paths.append(Path(meta["storagePath"]))
        except Exception as exc:
            log.error("File upload failed during tender creation: %s", exc)
            await TenderRepository.delete(db, tender_id)
            for p in staged_file_paths:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
            if isinstance(exc, ApiError):
                raise exc
            raise ApiError(f"Tender creation failed during file upload: {str(exc)}", 500)

    try:
        full_tender = await tender_service.get_tender(db, tender_id)
    except Exception:
        full_tender = tender

    return {
        "success": True,
        "data": full_tender,
        "message": f"Tender \"{full_tender.get('tenderNo', tender_no)}\" registered successfully in the system.",
    }


@router.post(
    "/{tender_id}/bids",
    status_code=201,
    summary="Ingest a bidder into a tender",
    description="Evaluates the submission with the clause rule engine and updates tender summary stats.",
)
async def ingest_bid(tender_id: str, payload: IngestBidRequest, db: AsyncSession = Depends(get_db)):
    bidder, tender = await tender_service.ingest_bid(db, tender_id, payload.to_bidder_dict())
    return {
        "success": True,
        "data": bidder,
        "tenderSummary": tender["summaryStats"],
        "message": f"Bidder \"{bidder['name']}\" audited and ingested into tender.",
    }
