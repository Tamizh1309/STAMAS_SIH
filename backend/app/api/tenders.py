"""Tender routes — thin handlers over tender_service."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..schemas.tender import CreateTenderRequest, IngestBidRequest
from ..services import tender_service

router = APIRouter(tags=["tenders"])


@router.get(
    "",
    summary="List all tenders",
    description="Returns every tender with bidders and summary stats.",
)
async def list_tenders(db: AsyncSession = Depends(get_db)):
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
    description="Creates a tender. `title` and `tenderNo` are mandatory.",
)
async def create_tender(payload: CreateTenderRequest, db: AsyncSession = Depends(get_db)):
    tender = await tender_service.create_tender(db, payload.model_dump(exclude_none=True))
    return {
        "success": True,
        "data": tender,
        "message": f"Tender \"{tender['tenderNo']}\" registered successfully in the system.",
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
