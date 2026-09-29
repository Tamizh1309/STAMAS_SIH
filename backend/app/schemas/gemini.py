"""Pydantic schemas for Gemini request/response payloads."""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class VerificationRequest(BaseModel):
    tenderDetails: dict[str, Any] = Field(default_factory=dict)
    bidderDetails: dict[str, Any] = Field(default_factory=dict)
    clausesToVerify: list[dict[str, Any]] = Field(default_factory=list)


class AnomalyAlert(BaseModel):
    type: Literal["COLLUSION_RISK", "TECH_SPEC_MISMATCH", "STATUTORY_GAP", "FINANCIAL_RISK"]
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    description: str
    remedy: str


class EvaluatedClauseResult(BaseModel):
    clauseId: str
    clauseTitle: str
    requiredSpec: str = ""
    offeredSpec: str = ""
    complianceStatus: Literal["COMPLIANT", "MINOR_DEVIATION", "MAJOR_DEVIATION", "MISSING_DOC"]
    riskScore: int = Field(default=1, ge=1, le=10)
    auditorRemarks: str = ""
    clarificationQuestion: Optional[str] = None


class MIIMSEAudit(BaseModel):
    miiCompliant: bool = True
    miiClass: str = "Class-I Local Supplier (>=50%)"
    mseExemptionGranted: bool = False
    remarks: str = ""


class ComplianceResult(BaseModel):
    fallback: bool = False
    engine: str = "Gemini AI"
    overallComplianceScore: int = Field(default=0, ge=0, le=100)
    qualificationStatus: Literal["QUALIFIED", "CONDITIONALLY_QUALIFIED", "DISQUALIFIED"]
    executiveSummary: str = ""
    anomalyAlerts: list[AnomalyAlert] = Field(default_factory=list)
    evaluatedClauses: list[EvaluatedClauseResult] = Field(default_factory=list)
    miiMseAudit: MIIMSEAudit = Field(default_factory=MIIMSEAudit)


class Deviation(BaseModel):
    clause: str = ""
    title: str = ""
    required: str = ""
    offered: str = ""
    remark: str = ""


class NoticeRequest(BaseModel):
    tenderNo: str = ""
    tenderTitle: str = ""
    bidderName: str = ""
    deviations: list[Deviation] = Field(default_factory=list)
    contactOfficer: Optional[str] = None


class CartelDetectRequest(BaseModel):
    tenderId: str = "tender-1"


class CartelAnomaly(BaseModel):
    biddersInvolved: list[str]
    anomalyType: str
    confidenceScore: int = Field(default=0, ge=0, le=100)
    finding: str
    recommendedAction: str
    safetyNote: Optional[str] = None


class CartelRisk(BaseModel):
    success: bool = True
    tenderNo: str = ""
    cartelRiskLevel: str = ""
    anomalies: list[CartelAnomaly] = Field(default_factory=list)
    safetyDisclaimer: str = (
        "All cartel and collusion detections are decision-support risk indicators "
        "requiring independent administrative and human verification."
    )


class CopilotRequest(BaseModel):
    message: str
    tenderContext: dict[str, Any] = Field(default_factory=dict)
