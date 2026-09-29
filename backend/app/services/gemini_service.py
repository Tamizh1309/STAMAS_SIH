"""Centralized Gemini integration (official google-genai Python SDK).

Single client instance; routes stay thin and call verify_bid /
generate_notice / detect_cartel / copilot_chat. Every method degrades to the
local rule engine when no API key is configured or a call fails.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..core.config import settings
from . import cartel_service, compliance_service

log = logging.getLogger("stamas.gemini")

_client: Any = None
_client_init_attempted = False


def _get_client() -> Any:
    global _client, _client_init_attempted
    if _client_init_attempted:
        return _client
    _client_init_attempted = True
    if not settings.gemini_configured:
        log.info("GEMINI_API_KEY not configured — Local Rule Engine mode.")
        return None
    try:
        from google import genai

        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
        log.info("Gemini client initialized (model=%s).", settings.GEMINI_MODEL)
    except Exception as exc:  # pragma: no cover - import/init failure
        log.warning("Gemini client init failed, using Local Rule Engine: %s", exc)
        _client = None
    return _client


def is_live() -> bool:
    return _get_client() is not None


def get_engine_status() -> dict[str, Any]:
    live = is_live()
    return {
        "engine": "Gemini AI" if live else "Local Rule Engine",
        "model": settings.GEMINI_MODEL if live else "Deterministic Rule Engine v3.8",
        "isLive": live,
    }


def _generate(prompt: str, *, json_mode: bool = False, system: str | None = None) -> str | None:
    client = _get_client()
    if client is None:
        return None
    models = list(dict.fromkeys([settings.GEMINI_MODEL, "gemini-2.5-flash"]))
    last_error: Exception | None = None
    for model in models:
        try:
            kwargs: dict[str, Any] = {}
            if json_mode:
                kwargs["config"] = {"response_mime_type": "application/json", "temperature": 0.2}
            elif system:
                kwargs["config"] = {"system_instruction": system, "temperature": 0.3}
            response = client.models.generate_content(model=model, contents=prompt, **kwargs)
            return (response.text or "").strip()
        except Exception as exc:
            last_error = exc
            msg = str(exc)
            if "503" in msg or "404" in msg or "NOT_FOUND" in msg:
                log.warning("Gemini model %s unavailable, trying next.", model)
                continue
            raise
    if last_error:
        raise last_error
    return None


# -- public service API -------------------------------------------------
def verify_bid(
    tender_details: dict[str, Any],
    bidder_details: dict[str, Any],
    clauses_to_verify: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = (
        "You are the Lead Procurement & Technical Compliance Auditor for Chennai Petroleum "
        "Corporation Limited (CPCL) and GeM (Government e-Marketplace), evaluating public tenders "
        "under GFR 2017 & CVC Guidelines.\n\n"
        "IMPORTANT DOMAIN SAFETY:\n"
        "- Present all findings as decision-support indicators for tender committee officials, "
        "not as an unquestionable legal verdict.\n\n"
        f"TENDER SPECIFICATIONS:\nTitle: {tender_details.get('title') or 'Refinery Equipment Tender'}\n"
        f"Tender No: {tender_details.get('tenderNo') or 'CPCL/REF/2026/094'}\n"
        f"Estimated Value: {tender_details.get('estimatedValue') or '₹14.85 Cr'}\n"
        f"Make-in-India Min Local Content: {tender_details.get('minLocalContent') or '50%'}\n\n"
        f"BIDDER SUBMISSION:\nBidder Name: {bidder_details.get('name') or 'Bidder'}\n"
        f"Declared Local Content: {bidder_details.get('localContent') or '58%'}\n"
        f"MSE Status: {'Registered MSE (Udyam Verified)' if bidder_details.get('isMSE') else 'Non-MSE Enterprise'}\n\n"
        f"CLAUSES TO AUDIT:\n{json.dumps(clauses_to_verify or [], indent=2)}\n\n"
        "Provide a strict, professional techno-commercial audit in valid JSON matching this schema:\n"
        '{"overallComplianceScore": number (0-100), '
        '"qualificationStatus": "QUALIFIED" | "CONDITIONALLY_QUALIFIED" | "DISQUALIFIED", '
        '"executiveSummary": "string", '
        '"anomalyAlerts": [{"type": "COLLUSION_RISK" | "TECH_SPEC_MISMATCH" | "STATUTORY_GAP" | "FINANCIAL_RISK", '
        '"severity": "HIGH" | "MEDIUM" | "LOW", "description": "string", "remedy": "string"}], '
        '"evaluatedClauses": [{"clauseId": "string", "clauseTitle": "string", "requiredSpec": "string", '
        '"offeredSpec": "string", "complianceStatus": "COMPLIANT" | "MINOR_DEVIATION" | "MAJOR_DEVIATION" | "MISSING_DOC", '
        '"riskScore": number (1-10), "auditorRemarks": "string", "clarificationQuestion": "string"}], '
        '"miiMseAudit": {"miiCompliant": boolean, '
        '"miiClass": "Class-I Local Supplier (>=50%)" | "Class-II Local Supplier (20-49%)" | "Non-Local Supplier (<20%)", '
        '"mseExemptionGranted": boolean, "remarks": "string"}}\n'
        "Respond with pure JSON only without markdown formatting."
    )
    try:
        text = _generate(prompt, json_mode=True)
        if text:
            cleaned = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            parsed["engine"] = "Gemini AI"
            parsed["fallback"] = False
            return parsed
    except Exception as exc:
        log.warning("Gemini verify-bid failed, rule-engine fallback: %s", exc)
    return compliance_service.verify_bid(tender_details, bidder_details, clauses_to_verify)


def generate_notice(
    tender_no: str,
    tender_title: str,
    bidder_name: str,
    deviations: list[dict[str, Any]],
    contact_officer: str | None = None,
) -> str:
    prompt = (
        f'Draft a formal Government of India / CPCL Technical Clarification Notice (GeM CSQ Query Notice) '
        f'to be issued to bidder "{bidder_name}" for Tender "{tender_no}: {tender_title}".\n'
        f"Deviations/Observations noted by AI evaluation:\n{json.dumps(deviations or [], indent=2)}\n"
        f"Officer In-Charge: {contact_officer or 'General Manager (Contracts & Procurement), CPCL Manali Refinery, Chennai'}\n\n"
        "Format requirements:\n"
        "- Formal GoI / PSU procurement language referencing GFR 2017 & GeM GTC (General Terms & Conditions).\n"
        "- Clear tabular or bulleted list of clause deficiencies.\n"
        "- Strict 48-hour response window for uploading supporting documents on GeM portal.\n"
        "- Clause warning regarding technical rejection if clarifications are unsatisfactory.\n"
        "Return plain text formatted letter."
    )
    try:
        text = _generate(prompt)
        if text:
            return text
    except Exception as exc:
        log.warning("Gemini notice generation failed, local template: %s", exc)
    return compliance_service.clarification_notice(
        tender_no, tender_title, bidder_name, deviations, contact_officer
    )


def detect_cartel(tender: dict[str, Any] | None) -> dict[str, Any]:
    # Deterministic local signals are the source of truth; Gemini is not
    # consulted for accusations. Kept local by design (see cartel_service).
    return cartel_service.detect_cartel_anomalies(tender)


def verify_extracted_clause(
    tender: dict[str, Any],
    clause: dict[str, Any],
    bidder_name: str | None = None,
    requirement: str | None = None,
) -> dict[str, Any]:
    """Verify one extracted tender clause (chunked, evidence-grounded).

    Reuses the single Gemini client via _generate; falls back to a local
    heuristic that never invents evidence. Only a bounded slice of the
    clause text is ever sent (see MAX_GEMINI_CHARS).
    """
    tender_no = (tender or {}).get("tenderNo") or "CPCL/REF/2026/094"
    tender_title = (tender or {}).get("title") or "CPCL tender"
    clause_text = str(clause.get("text") or "")[: settings.MAX_GEMINI_CHARS]
    clause_label = f"{clause.get('number') or 'n/a'} — {clause.get('title') or 'Untitled clause'}"
    source = clause.get("sourceDocumentName") or "tender document"
    context = (
        f"Tender {tender_no}: {tender_title}. "
        f"Bidder context: {bidder_name or 'general tender requirement'}. "
        f"Stated requirement: {requirement or 'the clause text as written in the tender document'}."
    )

    prompt = (
        "You are a procurement compliance assistant for CPCL/GeM tenders under GFR 2017 & CVC guidelines. "
        "Assess the tender clause below as DECISION SUPPORT for the tender committee — never a final legal verdict. "
        "Base the verdict ONLY on the quoted evidence. If the evidence is insufficient, say so explicitly.\n\n"
        f"CONTEXT: {context}\n\n"
        f"CLAUSE [{clause_label}] (source: {source}):\n{clause_text}\n\n"
        "Respond in pure JSON with exactly these keys:\n"
        '{"status": "COMPLIANT" | "NON_COMPLIANT" | "PARTIALLY_COMPLIANT" | "NEEDS_CLARIFICATION" | "NOT_ENOUGH_EVIDENCE", '
        '"finding": "one-paragraph assessment", '
        '"evidence": ["short verbatim excerpts from the clause text"], '
        '"reasoning": "why the evidence supports the status", '
        '"confidence": number 0..1}'
    )
    try:
        text = _generate(prompt, json_mode=True)
        if text:
            cleaned = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            status = str(parsed.get("status") or "").upper()
            if status not in ("COMPLIANT", "NON_COMPLIANT", "PARTIALLY_COMPLIANT", "NEEDS_CLARIFICATION", "NOT_ENOUGH_EVIDENCE"):
                status = "NEEDS_CLARIFICATION"
            evidence = [str(e) for e in (parsed.get("evidence") or []) if str(e).strip()][:5]
            return {
                "status": status,
                "finding": str(parsed.get("finding") or ""),
                "evidence": evidence,
                "reasoning": str(parsed.get("reasoning") or ""),
                "confidence": max(0.0, min(1.0, float(parsed.get("confidence") or 0.0))),
                "engine": "Gemini AI",
            }
    except Exception as exc:
        log.warning("Gemini clause verification failed, local heuristic: %s", exc)
    return _local_clause_check(clause_text)


def analyze_tender_opportunity(
    tender: dict[str, Any],
    doc_texts: list[tuple[str, str]],
    bidder: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evidence-grounded tender value / opportunity analysis.

    Concatenates extracted document text (bounded by MAX_GEMINI_CHARS),
    asks for the fixed decision-support schema, and coerces the response
    into shape. Missing values must come back as
    "Not available / Not found in document" — never invented.
    Falls back to an explicit INSUFFICIENT DATA skeleton.
    """
    tender_no = (tender or {}).get("tenderNo") or "Unknown tender"
    tender_title = (tender or {}).get("title") or "Untitled tender"
    budget = settings.MAX_GEMINI_CHARS
    parts: list[str] = []
    used = 0
    for name, text in doc_texts:
        room = budget - used
        if room <= 200:
            break
        chunk = (text or "")[:room]
        parts.append(f"--- SOURCE DOCUMENT: {name} ---\n{chunk}")
        used += len(chunk)
    corpus = "\n\n".join(parts).strip()
    if bidder:
        bidder_ctx = (
            f"Bidder context (may be partial): name={bidder.get('name')}, "
            f"quotedPrice={bidder.get('quotedPriceFormatted') or bidder.get('quotedPrice')}, "
            f"localContent={bidder.get('localContentPercent')}%, "
            f"MSE={bidder.get('isMSE')}, qualification={bidder.get('qualificationStatus')}."
        )
    else:
        bidder_ctx = "No bidder/company data was provided."

    prompt = (
        "You are a tender analyst for Indian public procurement (GeM/GFR 2017/CVC). "
        "Analyse the tender document text below as DECISION SUPPORT for a bid/no-bid review — "
        "never a final commercial or legal decision, never an instruction to bid.\n"
        "STRICT RULES:\n"
        "1. Every factual claim must be traceable to a verbatim quote in 'evidence'.\n"
        "2. If a field is absent from the text, write exactly: Not available / Not found in document.\n"
        "3. Never invent company capabilities, values, dates or requirements.\n"
        "4. Distinguish absence of evidence from negative evidence.\n\n"
        f"TENDER: {tender_no} — {tender_title}\n{bidder_ctx}\n\n"
        f"DOCUMENT TEXT:\n{corpus}\n\n"
        "Respond in pure JSON with exactly these keys:\n"
        '{"tenderInfo": {"title": "string", "referenceNumber": "string", '
        '"organization": "string", "department": "string", "category": "string", '
        '"scope": "string", "estimatedValue": "string", "emd": "string", "tenderFee": "string", '
        '"submissionDeadline": "string", "contractDuration": "string", '
        '"eligibility": ["string"], "technicalRequirements": ["string"], '
        '"financialRequirements": ["string"], "keyCommercialTerms": ["string"]}, '
        '"eligibility": {"requirements": ["string"], "evidence": ["verbatim quotes"], '
        '"missingInformation": ["string"]}, '
        '"commercial": {"value": "string", "emd": "string", "fee": "string", '
        '"otherFinancial": ["string"], "evidence": ["verbatim quotes"]}, '
        '"technical": {"skills": ["string"], "certifications": ["string"], '
        '"experience": ["string"], "resources": ["string"], "evidence": ["verbatim quotes"]}, '
        '"risks": [{"risk": "string", "impact": "HIGH|MEDIUM|LOW", "evidence": "verbatim quote or Not available / Not found in document"}], '
        '"bidderFit": {"evaluable": ["string"], "evidenceAvailable": ["string"], '
        '"evidenceMissing": ["string"]}, '
        '"opportunitySignal": "HIGH|MEDIUM|LOW|INSUFFICIENT DATA", '
        '"signalReasoning": "string"}'
    )
    try:
        text = _generate(prompt, json_mode=True)
        if text:
            cleaned = text.replace("```json", "").replace("```", "").strip()
            return {
                "engine": "Gemini AI",
                "result": _coerce_opportunity(json.loads(cleaned)),
            }
    except Exception as exc:
        log.warning("Gemini opportunity analysis failed, local skeleton: %s", exc)
    return {"engine": "Local Rule Engine", "result": _local_opportunity(tender_no, tender_title)}


def _coerce_opportunity(parsed: dict[str, Any]) -> dict[str, Any]:
    """Force the fixed schema with safe defaults (missing → Not available)."""
    if not isinstance(parsed, dict):
        return _blank_opportunity()

    def s(v: Any) -> str:
        t = str(v).strip() if v is not None else ""
        return t or "Not available / Not found in document"

    def lst(v: Any) -> list[str]:
        if isinstance(v, list):
            out = [str(x).strip() for x in v if str(x).strip()]
            return out
        return []

    info = parsed.get("tenderInfo") if isinstance(parsed.get("tenderInfo"), dict) else {}
    info_keys = ("title", "referenceNumber", "organization", "department", "category",
                 "scope", "estimatedValue", "emd", "tenderFee", "submissionDeadline",
                 "contractDuration")
    list_keys = ("eligibility", "technicalRequirements", "financialRequirements", "keyCommercialTerms")
    tender_info = {k: s(info.get(k)) for k in info_keys}
    for k in list_keys:
        tender_info[k] = lst(info.get(k))

    def section(src: Any, keys: tuple[str, ...]) -> dict[str, Any]:
        d = src if isinstance(src, dict) else {}
        return {k: (lst(d.get(k)) if k != "value" and k != "emd" and k != "fee" else s(d.get(k))) for k in keys}

    risks_in = parsed.get("risks")
    risks: list[dict[str, str]] = []
    if isinstance(risks_in, list):
        for r in risks_in[:12]:
            if not isinstance(r, dict):
                continue
            impact = str(r.get("impact") or "").upper()
            risks.append({
                "risk": s(r.get("risk")),
                "impact": impact if impact in ("HIGH", "MEDIUM", "LOW") else "MEDIUM",
                "evidence": s(r.get("evidence")),
            })

    signal = str(parsed.get("opportunitySignal") or "").upper()
    commercial_src = parsed.get("commercial") if isinstance(parsed.get("commercial"), dict) else {}
    return {
        "tenderInfo": tender_info,
        "eligibility": section(parsed.get("eligibility"), ("requirements", "evidence", "missingInformation")),
        "commercial": {**section(commercial_src, ("value", "emd", "fee")),
                       "otherFinancial": lst(commercial_src.get("otherFinancial")),
                       "evidence": lst(commercial_src.get("evidence"))},
        "technical": section(parsed.get("technical"), ("skills", "certifications", "experience", "resources", "evidence")),
        "risks": risks,
        "bidderFit": section(parsed.get("bidderFit"), ("evaluable", "evidenceAvailable", "evidenceMissing")),
        "opportunitySignal": signal if signal in ("HIGH", "MEDIUM", "LOW", "INSUFFICIENT DATA") else "INSUFFICIENT DATA",
        "signalReasoning": s(parsed.get("signalReasoning")),
    }


def _blank_opportunity() -> dict[str, Any]:
    na = "Not available / Not found in document"
    return {
        "tenderInfo": {k: ([] if k in ("eligibility", "technicalRequirements",
                        "financialRequirements", "keyCommercialTerms") else na)
                       for k in ("title", "referenceNumber", "organization", "department",
                                 "category", "scope", "estimatedValue", "emd", "tenderFee",
                                 "submissionDeadline", "contractDuration", "eligibility",
                                 "technicalRequirements", "financialRequirements",
                                 "keyCommercialTerms")},
        "eligibility": {"requirements": [], "evidence": [], "missingInformation": []},
        "commercial": {"value": na, "emd": na, "fee": na, "otherFinancial": [], "evidence": []},
        "technical": {"skills": [], "certifications": [], "experience": [], "resources": [], "evidence": []},
        "risks": [],
        "bidderFit": {"evaluable": [], "evidenceAvailable": [], "evidenceMissing": []},
        "opportunitySignal": "INSUFFICIENT DATA",
        "signalReasoning": na,
    }


def _local_opportunity(tender_no: str, tender_title: str) -> dict[str, Any]:
    result = _blank_opportunity()
    result["tenderInfo"]["title"] = tender_title
    result["tenderInfo"]["referenceNumber"] = tender_no
    result["signalReasoning"] = (
        "Local Rule Engine cannot perform tender value analysis without Gemini; "
        "human review of the source documents is required."
    )
    return result


def _local_clause_check(clause_text: str) -> dict[str, Any]:
    """Deterministic fallback: flags ambiguity, never invents evidence."""
    low = clause_text.lower()
    if len(clause_text.strip()) < 40:
        return {
            "status": "NOT_ENOUGH_EVIDENCE",
            "finding": "Clause text is too short for an automated assessment.",
            "evidence": [clause_text[:200]],
            "reasoning": "Local rule engine requires at least 40 characters of clause text.",
            "confidence": 0.3,
            "engine": "Local Rule Engine",
        }
    vague = [w for w in ("as applicable", "as required", "suitable", "adequate", "tbd", "to be decided") if w in low]
    if vague:
        return {
            "status": "NEEDS_CLARIFICATION",
            "finding": f"Clause contains open-ended wording ({', '.join(vague)}) needing committee clarification.",
            "evidence": [clause_text[:300]],
            "reasoning": "Vague qualifiers prevent a definitive compliance reading.",
            "confidence": 0.6,
            "engine": "Local Rule Engine",
        }
    return {
        "status": "NEEDS_CLARIFICATION",
        "finding": "Clause recorded for committee review. Local engine cannot verify without bidder submission context.",
        "evidence": [clause_text[:300]],
        "reasoning": "Deterministic fallback: human review required.",
        "confidence": 0.5,
        "engine": "Local Rule Engine",
    }


def copilot_chat(message: str, tender_context: dict[str, Any]) -> dict[str, str]:
    system = (
        "You are STAMAS Copilot, the AI Procurement Intelligence Assistant for Chennai Petroleum "
        "Corporation Limited (CPCL) & Ministry of Petroleum & Natural Gas.\n"
        "You have deep domain knowledge of:\n"
        "1. Public Procurement in India, GeM 4.0 Portal rules, CVC guidelines, GFR 2017 Rules 144(xi), 149, 153.\n"
        "2. Oil & Gas PSU technical specifications: ASME B16.34, ASTM A182/A216, API 6D, API 600, "
        "NACE MR0175/ISO 15156 for sour crude service, cryogenic valves, EOT cranes, heat exchangers.\n"
        "3. Make in India (Public Procurement Order 2017, Class I >=50%, Class II 20-49%), MSE exemptions "
        "(EMD/turnover), Land Border Sharing restrictions (Rule 144(xi)).\n"
        "4. Anomaly detection, risk indicators, mirror pricing, and explainable audit trails.\n\n"
        "Procurement Safety Reminder:\n"
        "Always frame cartel or collusion observations as potential anomalies and risk indicators "
        "requiring human review by the competent authority.\n\n"
        f"Current Tender Context:\n{json.dumps(tender_context or {}, indent=2)}\n\n"
        "Provide concise, authoritative, structured, and helpful responses with actionable "
        "recommendations and citations. Do not present output as authoritative legal advice."
    )
    try:
        text = _generate(f"User Query: {message}", system=system)
        if text:
            return {"reply": text, "engine": "Gemini AI"}
    except Exception as exc:
        log.warning("Gemini copilot failed, local assistant: %s", exc)
    return {"reply": compliance_service.copilot_response(message, tender_context), "engine": "Local Rule Engine"}
