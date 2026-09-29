"""Lightweight domain metadata for clause evaluation."""
from dataclasses import dataclass


@dataclass
class ClauseMeta:
    status: str = "COMPLIANT"
    risk_score: int = 1
    clarification_required: bool = False
