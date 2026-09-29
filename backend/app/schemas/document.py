"""Pydantic schemas for tender document ingestion and clause extraction."""
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class ClauseVerificationStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"


class DocumentMetadata(BaseModel):
    id: str = Field(description="Server-generated unique document ID")
    tenderId: str
    fileName: str = Field(description="Original client filename")
    fileType: str = Field(description="Lowercase extension without dot, e.g. pdf")
    mimeType: str = ""
    size: int = Field(ge=0, description="File size in bytes")
    status: DocumentStatus = DocumentStatus.UPLOADED
    uploadedAt: str = ""
    extractedTextLength: int = 0
    pageCount: Optional[int] = None
    error: Optional[str] = Field(default=None, description="Processing failure reason, if any")


class DocumentUploadResponse(BaseModel):
    success: bool = True
    documents: list[DocumentMetadata] = Field(default_factory=list)
    message: str = ""


class DocumentListResponse(BaseModel):
    success: bool = True
    documents: list[DocumentMetadata] = Field(default_factory=list)
    count: int = 0


class DocumentTextResponse(BaseModel):
    success: bool = True
    documentId: str
    text: str = ""
    textLength: int = 0
    truncated: bool = False


class ExtractedClause(BaseModel):
    id: str
    number: str = Field(default="", description="Detected clause number, e.g. 4.2.3 (may be empty)")
    title: str
    text: str = ""
    sourceDocumentId: str = ""
    sourceDocumentName: str = ""
    page: Optional[int] = None
    section: Optional[str] = None


class ClauseListResponse(BaseModel):
    success: bool = True
    tenderId: str = ""
    clauses: list[ExtractedClause] = Field(default_factory=list)
    count: int = 0


class ClauseVerifyRequest(BaseModel):
    bidderName: Optional[str] = Field(default=None, description="Bidder submission context for verification")
    requirement: Optional[str] = Field(default=None, description="Tender requirement text the clause is checked against")


class ClauseVerificationResult(BaseModel):
    success: bool = True
    clauseId: str
    status: ClauseVerificationStatus
    finding: str = ""
    evidence: list[str] = Field(default_factory=list)
    reasoning: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    engine: str = "Local Rule Engine"
    sourceDocumentId: str = ""
    sourceDocumentName: str = ""
    disclaimer: str = (
        "Decision-support indicator for the tender committee. Requires human review; "
        "not a final legal or procurement decision."
    )


class DeleteResponse(BaseModel):
    success: bool = True
    message: str = ""


class RenameDocumentRequest(BaseModel):
    fileName: str = Field(min_length=1, max_length=255, description="New display filename (same extension required)")


class AnalyzeRequest(BaseModel):
    bidderName: Optional[str] = Field(default=None, description="Bidder/company context for fit assessment")


class AnalysisRecord(BaseModel):
    id: str
    tenderId: str
    documentId: Optional[str] = None
    kind: str = "opportunity"
    engine: str = "Local Rule Engine"
    result: dict = Field(default_factory=dict)
    createdAt: str = ""


class AnalyzeResponse(BaseModel):
    success: bool = True
    analysis: AnalysisRecord
    message: str = ""


class LatestAnalysisResponse(BaseModel):
    success: bool = True
    analysis: Optional[AnalysisRecord] = None


ProcessingStatus = Literal["UPLOADED", "PROCESSING", "PROCESSED", "FAILED"]
