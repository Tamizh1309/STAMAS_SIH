"""Lightweight domain metadata for a tender's summary statistics."""
from dataclasses import dataclass


@dataclass
class TenderSummaryStats:
    total_bidders: int = 0
    qualified_bidders: int = 0
    conditional_bidders: int = 0
    disqualified_bidders: int = 0
    avg_compliance_score: float = 0.0
    total_clauses_audited: int = 0
    flagged_deviations: int = 0
    cartel_anomalies: int = 0
