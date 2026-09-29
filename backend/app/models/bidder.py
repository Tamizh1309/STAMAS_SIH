"""Lightweight domain metadata for bidder classification."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class BidderMeta:
    mii_class: str = "Class-I Local (>=50%)"
    qualification: str = "QUALIFIED"
    cartel_risk: str = "LOW"
    udyam_number: Optional[str] = None
