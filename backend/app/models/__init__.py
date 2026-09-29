"""STAMAS domain models (plain dataclasses/dicts — persistence-agnostic)."""
from .tender import TenderSummaryStats
from .bidder import BidderMeta
from .clause import ClauseMeta
from .compliance import ComplianceMeta

__all__ = ["TenderSummaryStats", "BidderMeta", "ClauseMeta", "ComplianceMeta"]
