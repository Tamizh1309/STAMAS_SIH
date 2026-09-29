"""Document + extracted-clause routes — thin handlers over document_service."""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ApiError
from ..db.database import get_db
from ..schemas.document import (
    AnalysisRecord,
    AnalyzeRequest,
    AnalyzeResponse,
    ClauseListResponse,
    ClauseVerifyRequest,
    ClauseVerificationResult,
    DeleteResponse,
    DocumentListResponse,
    DocumentMetadata,
    DocumentTextResponse,
    DocumentUploadResponse,
    ExtractedClause,
    LatestAnalysisResponse,
    RenameDocumentRequest,
)
from ..services import document_service, gemini_service

router = APIRouter(tags=["documents"])


@router.post(
    "/{tender_id}/documents",
    status_code=201,
    summary="Upload tender documents",
    description="Accepts multiple PDF/DOC/DOCX/XLS/XLSX files (10 MB each), extracts text and clauses.",
    response_model=DocumentUploadResponse,
)
async def upload_documents(
    tender_id: str, files: list[UploadFile] = File(...), db: AsyncSession = Depends(get_db)
):
    if not files:
        raise ApiError("No files were uploaded.", 400)
    docs: list[DocumentMetadata] = []
    for upload in files:
        content = await upload.read()
        meta = await document_service.ingest_file(
            db, tender_id, upload.filename or "", content, upload.content_type
        )
        docs.append(DocumentMetadata(**meta))
    failed = sum(1 for d in docs if d.status.value == "FAILED")
    ok = len(docs) - failed
    return DocumentUploadResponse(
        success=True,
        documents=docs,
        message=(
            f"Ingested {len(docs)} document(s): {ok} processed"
            + (f", {failed} failed" if failed else "")
            + "."
        ),
    )


@router.get(
    "/{tender_id}/documents",
    summary="List tender documents",
    description="Returns metadata for all uploaded documents of the tender.",
    response_model=DocumentListResponse,
)
async def list_documents(tender_id: str, db: AsyncSession = Depends(get_db)):
    docs = [DocumentMetadata(**m) for m in await document_service.list_documents(db, tender_id)]
    return DocumentListResponse(success=True, documents=docs, count=len(docs))


@router.get(
    "/{tender_id}/documents/{document_id}",
    summary="Document details",
    description="Returns metadata and processing info (no extracted text).",
    response_model=DocumentMetadata,
)
async def get_document(tender_id: str, document_id: str, db: AsyncSession = Depends(get_db)):
    return DocumentMetadata(**await document_service.get_document(db, tender_id, document_id))


@router.get(
    "/{tender_id}/documents/{document_id}/text",
    summary="Extracted document text",
    description="Returns extracted text (bounded) for a processed document.",
    response_model=DocumentTextResponse,
)
async def get_document_text(tender_id: str, document_id: str, db: AsyncSession = Depends(get_db)):
    meta, text, truncated = await document_service.get_document_text(db, tender_id, document_id)
    return DocumentTextResponse(
        success=True, documentId=document_id, text=text, textLength=len(text), truncated=truncated
    )


@router.patch(
    "/{tender_id}/documents/{document_id}",
    summary="Rename a document",
    description="Updates the display filename only (extension must stay the same). Tender-scoped.",
    response_model=DocumentMetadata,
)
async def rename_document(
    tender_id: str, document_id: str, payload: RenameDocumentRequest, db: AsyncSession = Depends(get_db)
):
    meta = await document_service.rename_document(db, tender_id, document_id, payload.fileName)
    return DocumentMetadata(**meta)


@router.delete(
    "/{tender_id}/documents/{document_id}",
    summary="Delete a document",
    description="Removes metadata, stored file and extracted text (tender-scoped).",
    response_model=DeleteResponse,
)
async def delete_document(tender_id: str, document_id: str, db: AsyncSession = Depends(get_db)):
    name = await document_service.delete_document(db, tender_id, document_id)
    return DeleteResponse(success=True, message=f'Document "{name}" deleted.')


@router.get(
    "/{tender_id}/clauses",
    summary="Extracted tender clauses",
    description="Candidate clauses mined from processed documents (decision-support, not legal findings).",
    response_model=ClauseListResponse,
)
async def list_clauses(tender_id: str, db: AsyncSession = Depends(get_db)):
    clauses = [
        ExtractedClause(**c) for c in await document_service.get_clauses_for_tender(db, tender_id)
    ]
    return ClauseListResponse(success=True, tenderId=tender_id, clauses=clauses, count=len(clauses))


@router.post(
    "/{tender_id}/analyze",
    summary="Run tender opportunity analysis",
    description="Evidence-grounded Gemini value/eligibility/risk analysis over processed documents; result is persisted.",
    response_model=AnalyzeResponse,
)
async def analyze_tender(
    tender_id: str, payload: AnalyzeRequest, db: AsyncSession = Depends(get_db)
):
    record = await document_service.run_opportunity_analysis(db, tender_id, payload.bidderName)
    return AnalyzeResponse(
        success=True,
        analysis=AnalysisRecord(**record),
        message=f"Opportunity analysis completed via {record['engine']}.",
    )


@router.get(
    "/{tender_id}/analyses/latest",
    summary="Latest persisted analysis",
    description="Returns the most recent stored analysis of the given kind.",
    response_model=LatestAnalysisResponse,
)
async def latest_analysis(
    tender_id: str, kind: str = "opportunity", db: AsyncSession = Depends(get_db)
):
    record = await document_service.latest_analysis(db, tender_id, kind)
    return LatestAnalysisResponse(
        success=True, analysis=AnalysisRecord(**record) if record else None
    )


@router.post(
    "/{tender_id}/clauses/{clause_id}/verify",
    summary="Verify an extracted clause with AI",
    description="Evidence-grounded Gemini check with local fallback; explains status, evidence and reasoning.",
    response_model=ClauseVerificationResult,
)
async def verify_clause(
    tender_id: str, clause_id: str, payload: ClauseVerifyRequest, db: AsyncSession = Depends(get_db)
):
    tender = await document_service._require_tender(db, tender_id)
    clause = await document_service.find_clause(db, tender_id, clause_id)
    if clause is None:
        raise ApiError(f'Clause "{clause_id}" not found for this tender.', 404)
    result = gemini_service.verify_extracted_clause(
        tender, clause, payload.bidderName, payload.requirement
    )
    return ClauseVerificationResult(
        success=True,
        clauseId=clause_id,
        status=result["status"],
        finding=result.get("finding", ""),
        evidence=result.get("evidence", []),
        reasoning=result.get("reasoning", ""),
        confidence=result.get("confidence", 0.0),
        engine=result.get("engine", "Local Rule Engine"),
        sourceDocumentId=clause.get("sourceDocumentId", ""),
        sourceDocumentName=clause.get("sourceDocumentName", ""),
    )
