"""Local deterministic rule engine — fallback when Gemini is unavailable.

Ported from geminiService.localRuleEngineVerify / localClarificationNotice /
localCopilotResponse in backend/services/geminiService.ts.
"""
from __future__ import annotations

import random
from typing import Any


def _norm(text: Any) -> str:
    return str(text or "").lower()


def verify_bid(
    tender_details: dict[str, Any],
    bidder_details: dict[str, Any],
    clauses_to_verify: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluated = []
    for c in clauses_to_verify or []:
        offered = _norm(c.get("offeredSpec"))
        status_in = c.get("status")
        if status_in == "COMPLIANT":
            compliant, minor = True, False
        elif status_in == "MINOR_DEVIATION":
            compliant, minor = False, True
        else:
            fatal_kw = ("cast" in offered) or ("missing" in offered)
            compliant = not fatal_kw and not status_in
            minor = not compliant and not fatal_kw and ("cast" not in offered)
            if status_in in ("MAJOR_DEVIATION", "MISSING_DOC"):
                compliant, minor = False, False
        status = "COMPLIANT" if compliant else ("MINOR_DEVIATION" if minor else "MAJOR_DEVIATION")
        risk = 1 if compliant else (4 if minor else 9)
        evaluated.append(
            {
                "clauseId": c.get("id") or f"c-{random.randint(10000, 99999)}",
                "clauseTitle": c.get("title") or "Technical Parameter",
                "requiredSpec": c.get("requiredSpec") or "Standard CPCL Refinery Spec",
                "offeredSpec": c.get("offeredSpec") or "Vendor Specification",
                "complianceStatus": status,
                "riskScore": c.get("riskScore") or risk,
                "auditorRemarks": c.get("auditorRemarks")
                or ("Meets ASME/API requirements." if compliant else "Requires technical clarification."),
                "clarificationQuestion": None
                if compliant
                else f"Confirm acceptance of tender specifications for {c.get('number') or 'clause'}.",
            }
        )

    compliant_count = sum(1 for e in evaluated if e["complianceStatus"] == "COMPLIANT")
    score = round((compliant_count / len(evaluated)) * 100) if evaluated else 88
    has_major = any(e["complianceStatus"] in ("MAJOR_DEVIATION", "MISSING_DOC") for e in evaluated)
    has_minor = any(e["complianceStatus"] == "MINOR_DEVIATION" for e in evaluated)
    qual = "DISQUALIFIED" if has_major else ("CONDITIONALLY_QUALIFIED" if has_minor else "QUALIFIED")
    bidder_name = bidder_details.get("name") if isinstance(bidder_details, dict) else "Applicant"

    return {
        "fallback": True,
        "engine": "Local Rule Engine",
        "overallComplianceScore": score,
        "qualificationStatus": qual,
        "executiveSummary": (
            f"Local Rule Engine evaluation completed. Bidder {bidder_name} evaluated against "
            f"CPCL refinery standards. {score}% compliance detected. "
            f"Decision-support recommendation: {qual}."
        ),
        "anomalyAlerts": (
            [
                {
                    "type": "TECH_SPEC_MISMATCH",
                    "severity": "HIGH",
                    "description": "Critical specification divergence detected during rule-engine audit.",
                    "remedy": "Seek formal clarification or reject per GeM GTC clause 11.",
                }
            ]
            if has_major
            else []
        ),
        "evaluatedClauses": evaluated,
        "miiMseAudit": {
            "miiCompliant": True,
            "miiClass": "Class-I Local Supplier (>=50%)",
            "mseExemptionGranted": bool((bidder_details or {}).get("isMSE")),
            "remarks": "Statutory verification verified through rule parameters.",
        },
    }


def clarification_notice(
    tender_no: str,
    tender_title: str,
    bidder_name: str,
    deviations: list[dict[str, Any]],
    contact_officer: str | None = None,
) -> str:
    if deviations:
        items = "\n".join(
            f"[{i + 1}] Clause: {d.get('clause') or 'Clause'} - {d.get('title') or 'Technical Spec'}\n"
            f"Required Specification: {d.get('required') or 'As specified in tender'}\n"
            f"Offered Specification: {d.get('offered') or 'Deviation noted'}\n"
            f"Audit Observation: {d.get('remark') or 'Requires documentary confirmation'}\n"
            "Required Action: Submit certified OEM test report / compliance letter.\n"
            for i, d in enumerate(deviations)
        )
    else:
        items = "[1] All major specifications evaluated. Please confirm unconditional compliance to all commercial terms and warranty provisions."

    return (
        "GOVERNMENT OF INDIA / CHENNAI PETROLEUM CORPORATION LIMITED (CPCL)\n"
        "(A Group Company of Indian Oil Corporation Ltd.)\n"
        "Refinery Headquarters, Manali, Chennai - 600068, Tamil Nadu\n"
        "\n"
        f"TENDER REF: {tender_no or 'CPCL/REF/2026/094'}\n"
        "SUBJECT: Technical Evaluation Clarification Notice (GeM CSQ Query Notice)\n"
        "\n"
        "To:\n"
        "The Authorized Signatory,\n"
        f"{bidder_name}\n"
        "\n"
        "Dear Sir/Madam,\n"
        "\n"
        f'During the techno-commercial evaluation of your bid against Tender "{tender_title or "CPCL Procurement"}", '
        "the Technical Evaluation Committee has recorded the following observations requiring clarification "
        "under GFR 2017 & GeM General Terms and Conditions:\n"
        "\n"
        f"{items}\n"
        "\n"
        "You are hereby requested to submit your point-by-point clarification along with authenticated "
        "documentary proof on the GeM Portal within 48 hours of receipt of this notice.\n"
        "\n"
        "Please note that failure to furnish satisfactory compliance within the stipulated deadline may lead "
        "to technical disqualification of your bid without further reference.\n"
        "\n"
        "Yours faithfully,\n"
        f"{contact_officer or 'Chief General Manager (Contracts & Materials)'}\n"
        "Chennai Petroleum Corporation Limited, Manali, Chennai"
    )


def copilot_response(query: str, context: dict[str, Any]) -> str:
    q = (query or "").lower()
    tender_no = (context or {}).get("tenderNo") or "CPCL/REF/2026/094"

    if any(k in q for k in ("disqualif", "reject", "apex")):
        return (
            "Technical Evaluation Summary:\n"
            '• Bidder "Apex Valvetech Global Solutions" has fatal non-compliances under CPCL Tender Criteria:\n'
            "  1. Material of Construction: Offered Cast Steel (ASTM A216 WCB) instead of mandatory "
            "Forged Stainless Steel (ASTM A182 F316/F316L).\n"
            "  2. NACE MR0175 sour service hardness test certificates were missing from submittal.\n"
            "  3. Declared Make-in-India content is 32% (Class-II), falling below the mandatory 50% Class-I threshold.\n"
            "Recommendation: Disqualification under GeM GTC Clause 11 is technically substantiated."
        )
    if any(k in q for k in ("cartel", "collusion", "anomaly", "rig")):
        return (
            "Potential Vigilance Anomaly Indicator:\n"
            "• STAMAS detected technical correlations between Microtech Fluidics and Apex Valvetech:\n"
            '  1. Identical PDF workstation author metadata tag ("DELL-LATITUDE-ADMIN").\n'
            "  2. Both bids submitted from the identical Coimbatore ISP subnet (AS24336) within 12 minutes.\n"
            "  3. Microtech pricing reflects a consistent +12.50% step increment over the L1 baseline.\n"
            "Domain Safety Notice: These are potential anomaly indicators for committee review, requiring human "
            "evaluation under CVC Procurement Guidelines before price opening."
        )
    if any(k in q for k in ("clarification", "notice", "bvis")):
        return (
            "Technical Clarification Guidance:\n"
            "• For BVIS Flow Systems, minor deviations were observed:\n"
            "  1. Dual certified F316/F316L marking was not explicitly noted on the MOC datasheet.\n"
            "  2. Gas seat leak test was offered at 300 bar instead of the required 330 bar.\n"
            "Action: Generate a GeM CSQ Notice granting 48 hours for submission of test coupon and pressure acceptance."
        )
    if any(k in q for k in ("mse", "make in india", "mii", "local content")):
        return (
            "Statutory Policy Matrix (MoPNG / DPIIT):\n"
            "• Class-I Local Supplier: Local content >= 50% (Eligible for purchase preference).\n"
            "• Class-II Local Supplier: Local content 20% to 49% (No purchase preference in domestic tenders).\n"
            "• MSE Benefits: Exemption from EMD submission under Rule 170 of GFR 2017 upon valid UDYAM certificate submission.\n"
            f"Tender {tender_no} mandates Class-I Local Supplier status."
        )
    return (
        "STAMAS Copilot (Local Rule Engine):\n"
        "I have reviewed your query against the active tender parameters and GFR 2017 / CVC guidelines.\n"
        f"• Active Tender: {tender_no}\n"
        "• Compliance Status: 4 bidders audited across metallurgy (ASTM A182), sour service (NACE MR0175), "
        "hydro testing (API 598), and statutory Make-in-India mandates.\n"
        "Feel free to ask for specific clause comparisons, clarification draft recommendations, "
        "or statutory compliance audits."
    )
