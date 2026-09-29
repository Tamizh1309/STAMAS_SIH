"""Lightweight domain metadata for compliance outcomes."""
from dataclasses import dataclass


@dataclass
class ComplianceMeta:
    score: int = 0
    qualification: str = "CONDITIONALLY_QUALIFIED"
    engine: str = "Local Rule Engine"
    fallback: bool = True
