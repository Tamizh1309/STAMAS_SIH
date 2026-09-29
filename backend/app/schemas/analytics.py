"""Pydantic schemas for analytics / health payloads."""
from pydantic import BaseModel, Field


class ImpactMetric(BaseModel):
    metric: str
    manualEvaluation: str
    stamasAi: str
    improvement: str
    benchmarkSource: str


class TargetUser(BaseModel):
    role: str
    need: str


class ProblemBrief(BaseModel):
    psId: str
    title: str
    org: str
    theme: str
    category: str
    problemStatement: str
    ourSolution: str
    targetUsers: list[TargetUser] = Field(default_factory=list)


class Analytics(BaseModel):
    problemBrief: ProblemBrief
    impactMetrics: list[ImpactMetric] = Field(default_factory=list)
    refinerySavingsAnnual: str = ""
    averageScrutinyHours: str = ""
    disputeReductionRate: str = ""


class DatabaseStatus(BaseModel):
    connected: bool = True
    dbType: str = "in-memory"
    recordCount: int = 0
    lastSync: str = ""


class SystemHealth(BaseModel):
    success: bool = True
    status: str = "OPERATIONAL"
    version: str = "STAMAS v3.8 Enterprise"
    psId: str = "26100"
    authority: str = "Ministry of Petroleum & Natural Gas / CPCL"
    gemApiGateway: str = "ACTIVE_SYNC (GeM 4.0)"
    cvcAuditGuard: str = "ENFORCED"
    aiEngine: str = "Local Rule Engine"
    model: str = ""
    isLiveAI: bool = False
    database: DatabaseStatus = Field(default_factory=DatabaseStatus)
    uptimeSeconds: int = 0
    timestamp: str = ""
