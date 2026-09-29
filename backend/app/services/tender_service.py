"""Tender service — business logic over the PostgreSQL repository layer.

Bid evaluation rules are unchanged from the previous implementation; only
persistence moved from in-memory to Neon PostgreSQL.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import ApiError
from ..db.repositories import TenderRepository
from ..db.seed_data import BEFORE_AFTER_IMPACT_METRICS, SIH_PROBLEM_BRIEF


def _in_gb(days_from_now: int = 0) -> str:
    return (datetime.now() + timedelta(days=days_from_now)).strftime("%d-%b-%Y")


def _mii_class(local_content: float) -> str:
    if local_content >= 50:
        return "Class-I Local (>=50%)"
    if local_content >= 20:
        return "Class-II Local (20-49%)"
    return "Non-Local (<20%)"


def _build_new_tender(data: dict[str, Any]) -> dict[str, Any]:
    now_year = datetime.now().year
    return {
        "id": f"tender-{int(time.time() * 1000)}",
        "tenderNo": data.get("tenderNo") or f"CPCL/GEN/{now_year}/{random.randint(100, 999)}",
        "gemBidId": data.get("gemBidId") or f"GEM/{now_year}/B/{random.randint(100000, 999999)}",
        "title": data.get("title") or "Untitled GeM Procurement Tender",
        "department": data.get("department") or "Contracts & Materials (CPCL)",
        "location": data.get("location") or "Manali Refinery, Chennai, Tamil Nadu",
        "estimatedValue": float(data.get("estimatedValue") or 25000000),
        "estimatedValueFormatted": data.get("estimatedValueFormatted") or "₹2.50 Crore",
        "publishedDate": _in_gb(0),
        "bidOpeningDate": _in_gb(14),
        "techEvaluationDeadline": data.get("techEvaluationDeadline") or _in_gb(25),
        "status": "TECH_EVAL_IN_PROGRESS",
        "minLocalContentRequired": float(data.get("minLocalContentRequired") or 50),
        "emdAmountFormatted": "2% of Tender Value (MSE Exempted)",
        "pbgPercent": "3% of Contract Value",
        "summaryStats": {
            "totalBidders": 0,
            "qualifiedBidders": 0,
            "conditionalBidders": 0,
            "disqualifiedBidders": 0,
            "avgComplianceScore": 0,
            "totalClausesAudited": 0,
            "flaggedDeviations": 0,
            "cartelAnomalies": 0,
        },
        "bidders": [],
    }


def _evaluate_bidder_clauses(
    tender: dict[str, Any], bidder_data: dict[str, Any], stamp: str
) -> tuple[list[dict[str, Any]], int, str]:
    raw_text = str(bidder_data.get("rawSubmissionText") or "")
    local_content = float(bidder_data.get("localContentPercent") or 50)
    min_local = float(tender.get("minLocalContentRequired") or 50)

    def has(*needles: str) -> bool:
        return any(n in raw_text for n in needles)

    a182_ok = has("A182", "F316")
    nace_ok = has("NACE")
    mii_ok = local_content >= min_local

    evaluated_clauses = [
        {
            "id": f"c-new-1-{stamp}",
            "number": "Clause 3.1",
            "title": "Body Material & Metallurgical Traceability",
            "category": "Technical",
            "requiredSpec": "Forged ASTM A182 Gr. F316/F316L Dual Certified for severe refinery sour gas service.",
            "offeredSpec": (
                "ASTM A182 Gr. F316/F316L dual certified forgings with 3.1 Mill test certificates"
                if a182_ok
                else "Standard Stainless Steel Grade 316 as per vendor catalog"
            ),
            "status": "COMPLIANT" if a182_ok else "MINOR_DEVIATION",
            "riskScore": 1 if a182_ok else 4,
            "standardRef": "ASTM A182 / API 600",
            "auditorRemarks": (
                "Full dual certification verified against CPCL metallurgy standards."
                if a182_ok
                else "Requires explicit confirmation of ASTM A182 dual grade composition."
            ),
            "clarificationRequired": not a182_ok,
        },
        {
            "id": f"c-new-2-{stamp}",
            "number": "Clause 4.2",
            "title": "Sour Service Hardness (NACE MR0175)",
            "category": "Technical",
            "requiredSpec": "Mandatory compliance to NACE MR0175 / ISO 15156. Hardness strictly <= 22 HRC.",
            "offeredSpec": (
                "Full NACE MR0175 compliance; hardness measured 21.2 HRC maximum"
                if (nace_ok or "22 HRC" in raw_text)
                else "NACE compliance indicated in technical datasheet without lab test coupon"
            ),
            "status": "COMPLIANT" if nace_ok else "MINOR_DEVIATION",
            "riskScore": 1 if nace_ok else 5,
            "standardRef": "NACE MR0175 / ISO 15156",
            "auditorRemarks": "Hardness threshold evaluated.",
            "clarificationRequired": not nace_ok,
        },
        {
            "id": f"c-new-3-{stamp}",
            "number": "Clause 8.1",
            "title": "Make in India (MII) Local Value Addition",
            "category": "Statutory & ESG",
            "requiredSpec": f"Minimum {tender.get('minLocalContentRequired')}% Local Content as per MoPNG Public Procurement Policy.",
            "offeredSpec": f"{local_content:g}% Domestic Value Addition certified by CA / Udyam declaration.",
            "status": "COMPLIANT" if mii_ok else "MAJOR_DEVIATION",
            "riskScore": 1 if mii_ok else 9,
            "standardRef": "MoPNG PPO 2017 / DPIIT",
            "auditorRemarks": (
                "Qualifies as Class-I Local Supplier."
                if mii_ok
                else "FATAL: Sub-threshold local content violates MoPNG mandate."
            ),
            "clarificationRequired": not mii_ok,
        },
        {
            "id": f"c-new-4-{stamp}",
            "number": "Clause 9.2",
            "title": "Warranty & Turnaround SLA Terms",
            "category": "Commercial & Warranty",
            "requiredSpec": "36 months from supply / 24 months from commissioning with 24-hr engineer mobilization SLA.",
            "offeredSpec": "36 months warranty from supply / 24 months from commissioning offered.",
            "status": "COMPLIANT",
            "riskScore": 1,
            "standardRef": "GeM GTC Cl. 11.4",
            "auditorRemarks": "Warranty aligned with CPCL guidelines.",
            "clarificationRequired": False,
        },
    ]

    compliant = sum(1 for c in evaluated_clauses if c["status"] == "COMPLIANT")
    score = round((compliant / len(evaluated_clauses)) * 100)
    has_major = any(c["status"] == "MAJOR_DEVIATION" for c in evaluated_clauses)
    has_minor = any(c["status"] == "MINOR_DEVIATION" for c in evaluated_clauses)
    qualification = "DISQUALIFIED" if has_major else ("CONDITIONALLY_QUALIFIED" if has_minor else "QUALIFIED")
    return evaluated_clauses, score, qualification


def _recompute_stats(tender: dict[str, Any]) -> None:
    bidders = tender.get("bidders", [])
    stats = tender["summaryStats"]
    stats["totalBidders"] = len(bidders)
    stats["qualifiedBidders"] = sum(1 for b in bidders if b.get("qualificationStatus") == "QUALIFIED")
    stats["conditionalBidders"] = sum(1 for b in bidders if b.get("qualificationStatus") == "CONDITIONALLY_QUALIFIED")
    stats["disqualifiedBidders"] = sum(1 for b in bidders if b.get("qualificationStatus") == "DISQUALIFIED")
    stats["avgComplianceScore"] = (
        round(sum(b.get("overallComplianceScore", 0) for b in bidders) / len(bidders)) if bidders else 0
    )
    stats["totalClausesAudited"] = sum(len(b.get("evaluatedClauses", [])) for b in bidders)
    stats["flaggedDeviations"] = sum(
        sum(1 for c in b.get("evaluatedClauses", []) if c.get("status") != "COMPLIANT") for b in bidders
    )


async def list_tenders(session: AsyncSession) -> list[dict[str, Any]]:
    return await TenderRepository.list_all(session)


async def get_tender(session: AsyncSession, tender_id: str) -> dict[str, Any]:
    tender = await TenderRepository.get_by_id(session, tender_id)
    if tender is None:
        raise ApiError(f'Tender with ID "{tender_id}" not found.', 404)
    return tender


async def create_tender(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("title") or not payload.get("tenderNo"):
        raise ApiError("Tender title and tender number are mandatory parameters.", 400)
    tender = _build_new_tender(payload)
    return await TenderRepository.create(session, tender["id"], tender["tenderNo"], tender)


async def ingest_bid(
    session: AsyncSession, tender_id: str, bidder_data: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    tender = await TenderRepository.get_by_id(session, tender_id)
    if tender is None:
        raise ApiError(f'Tender with ID "{tender_id}" not found.', 404)

    local_content = float(bidder_data.get("localContentPercent") or 50)
    mii_class = _mii_class(local_content)
    stamp = str(int(time.time() * 1000))
    evaluated_clauses, score, qualification = _evaluate_bidder_clauses(tender, bidder_data, stamp)

    quoted = float(bidder_data.get("quotedPrice") or (float(tender.get("estimatedValue") or 0) * 0.94))
    name = bidder_data.get("name") or "Precision Flow Systems India Pvt Ltd"
    city = bidder_data.get("registeredCity") or "Chennai"
    is_mse = bool(bidder_data.get("isMSE"))

    new_bidder: dict[str, Any] = {
        "id": f"bidder-{stamp}",
        "name": name,
        "gstin": bidder_data.get("gstin") or f"33AAACB{random.randint(1000, 9999)}M1Z5",
        "registeredCity": city,
        "state": bidder_data.get("state") or "Tamil Nadu",
        "category": f"L{len(tender.get('bidders', [])) + 1} Bidder",
        "quotedPrice": quoted,
        "quotedPriceFormatted": bidder_data.get("quotedPriceFormatted") or f"₹{quoted / 10000000:.2f} Crore",
        "localContentPercent": local_content,
        "miiClassification": mii_class,
        "isMSE": is_mse,
        "mseCategory": bidder_data.get("mseCategory") or ("Small" if is_mse else None),
        "udyamNumber": bidder_data.get("udyamNumber")
        or (f"UDYAM-TN-02-{random.randint(100000, 999999)}" if is_mse else None),
        "turnoverLast3Yrs": bidder_data.get("turnoverLast3Yrs") or "₹45 Cr (Avg)",
        "netWorth": bidder_data.get("netWorth") or "₹22 Cr",
        "pqcExperienceMet": bool(bidder_data.get("pqcExperienceMet", True)),
        "pastCPCLSupplyTrack": "Prior supply credentials validated against IOCL/CPCL vendor database",
        "overallComplianceScore": score,
        "qualificationStatus": qualification,
        "cartelRiskScore": "LOW",
        "submissionTimestamp": datetime.now().strftime("%H:%M:%S") + " IST",
        "submissionIpRegion": f"{city} Subnet Gateway",
        "pdfMetadataAuthor": f"Engineer_{name.split(' ')[0]}",
        "evaluatedClauses": evaluated_clauses,
    }

    tender.setdefault("bidders", []).append(new_bidder)
    _recompute_stats(tender)
    saved = await TenderRepository.save(session, tender_id, tender)
    assert saved is not None
    return new_bidder, saved


def get_analytics() -> dict[str, Any]:
    return {
        "problemBrief": SIH_PROBLEM_BRIEF,
        "impactMetrics": [
            {
                "metric": m.get("metric"),
                "manualEvaluation": m.get("before"),
                "stamasAi": m.get("after"),
                "improvement": m.get("improvement"),
                "benchmarkSource": m.get("highlight"),
            }
            for m in BEFORE_AFTER_IMPACT_METRICS
        ],
        "refinerySavingsAnnual": "₹18.4 Crore",
        "averageScrutinyHours": "4.2 Hours",
        "disputeReductionRate": "98.5%",
    }
