"""Pydantic schemas for tender / bidder / clause domain objects."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

ClauseCategory = Literal["Technical", "Quality & Testing", "Statutory & ESG", "Commercial & Warranty"]
ClauseStatus = Literal["COMPLIANT", "MINOR_DEVIATION", "MAJOR_DEVIATION", "MISSING_DOC"]
QualificationStatus = Literal["QUALIFIED", "CONDITIONALLY_QUALIFIED", "DISQUALIFIED"]


class Clause(BaseModel):
    id: str
    number: str
    title: str
    category: ClauseCategory = "Technical"
    requiredSpec: str = ""
    offeredSpec: str = ""
    status: ClauseStatus = "COMPLIANT"
    riskScore: int = Field(default=1, ge=1, le=10)
    standardRef: str = ""
    auditorRemarks: str = ""
    clarificationRequired: bool = False
    clarificationDraft: Optional[str] = None


class Bidder(BaseModel):
    id: str
    name: str
    gstin: str = ""
    registeredCity: str = ""
    state: str = ""
    category: str = ""
    quotedPrice: float = 0
    quotedPriceFormatted: str = ""
    localContentPercent: float = 0
    miiClassification: str = ""
    isMSE: bool = False
    mseCategory: Optional[str] = None
    udyamNumber: Optional[str] = None
    turnoverLast3Yrs: str = ""
    netWorth: str = ""
    pqcExperienceMet: bool = True
    pastCPCLSupplyTrack: str = ""
    overallComplianceScore: float = 0
    qualificationStatus: QualificationStatus = "CONDITIONALLY_QUALIFIED"
    disqualificationReason: Optional[str] = None
    cartelRiskScore: str = "LOW"
    cartelNotes: Optional[str] = None
    submissionTimestamp: str = ""
    submissionIpRegion: str = ""
    pdfMetadataAuthor: str = ""
    evaluatedClauses: list[Clause] = Field(default_factory=list)


class TenderSummaryStats(BaseModel):
    totalBidders: int = 0
    qualifiedBidders: int = 0
    conditionalBidders: int = 0
    disqualifiedBidders: int = 0
    avgComplianceScore: float = 0
    totalClausesAudited: int = 0
    flaggedDeviations: int = 0
    cartelAnomalies: int = 0


class Tender(BaseModel):
    id: str
    tenderNo: str
    gemBidId: str = ""
    title: str
    department: str = ""
    location: str = ""
    estimatedValue: float = 0
    estimatedValueFormatted: str = ""
    publishedDate: str = ""
    bidOpeningDate: str = ""
    techEvaluationDeadline: str = ""
    status: str = "TECH_EVAL_IN_PROGRESS"
    minLocalContentRequired: float = 50
    emdAmountFormatted: str = ""
    pbgPercent: str = ""
    bidders: list[Bidder] = Field(default_factory=list)
    summaryStats: TenderSummaryStats = Field(default_factory=TenderSummaryStats)


class CreateTenderRequest(BaseModel):
    title: Optional[str] = None
    tenderNo: Optional[str] = None
    gemBidId: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    estimatedValue: Optional[float] = None
    estimatedValueFormatted: Optional[str] = None
    techEvaluationDeadline: Optional[str] = None
    minLocalContentRequired: Optional[float] = None


class IngestBidRequest(BaseModel):
    """Bidder ingestion payload — all fields optional except name-ish; extra keys allowed."""

    model_config = {"extra": "allow"}

    name: Optional[str] = None
    gstin: Optional[str] = None
    registeredCity: Optional[str] = None
    state: Optional[str] = None
    quotedPrice: Optional[float] = None
    quotedPriceFormatted: Optional[str] = None
    localContentPercent: Optional[float] = None
    isMSE: Optional[bool] = None
    mseCategory: Optional[str] = None
    udyamNumber: Optional[str] = None
    turnoverLast3Yrs: Optional[str] = None
    netWorth: Optional[str] = None
    pqcExperienceMet: Optional[bool] = None
    rawSubmissionText: Optional[str] = None

    def to_bidder_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)
