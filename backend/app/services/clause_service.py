"""First-stage clause extraction from normalized document text.

Deterministic, pattern-based (no vector DB, no RAG): numbered headings
(1 / 1.1 / 1.2.3 / A. / B.), markdown-style ## headings injected by the DOCX
extractor, [Page]/[Sheet] markers, and CPCL tender keyword headings
(Scope of Supply, Material Requirement, Inspection, ...).

A detected heading starts a candidate clause; it is a *candidate* for the
committee and Gemini — never presented as a legally valid clause by itself.
"""
from __future__ import annotations

import re
from typing import Any

KEYWORD_HEADINGS = [
    "technical specification", "technical specifications", "scope of supply",
    "scope of work", "eligibility criteria", "pre-qualification criteria",
    "material requirement", "material of construction", "inspection",
    "testing", "test procedure", "warranty", "guarantee", "delivery",
    "delivery schedule", "commercial terms", "payment terms",
    "statutory compliance", "make in india", "mse", "emd", "performance bank guarantee",
    "penalty", "liquidated damages", "safety", "hse", "documentation",
]

_NUMBER_RE = re.compile(
    r"^(?:(?:Clause|Section|Article)\s+)?(\d+(?:\.\d+)*\.?|[A-Z]\.|[IVX]{1,5}\.)(?:\s*[:\-]\s*|\s+)(.{3,120})$",
    re.IGNORECASE,
)
_MD_HEADING_RE = re.compile(r"^##\s+(.{3,160})$")
_MARKER_RE = re.compile(r"^\[(Page \d+|Sheet: [^\]]+)\]\s*$")
_TITLE_LEAD_RE = re.compile(r"^[A-Za-z]")
# Numbered body paragraphs ("1.1 Supply of two numbers 25 KL ...") also match
# _NUMBER_RE. Only short numbered lines are treated as headings — a real
# clause title is a label, not a paragraph. Longer numbered lines stay body.
_MAX_NUMBERED_TITLE_CHARS = 64


def _keyword_heading(line: str) -> str | None:
    low = line.strip().lower().rstrip(":")
    if len(low) > 80:
        return None
    for kw in KEYWORD_HEADINGS:
        if low == kw or low.startswith(kw + " ") and len(low) < len(kw) + 30:
            return line.strip()
    return None


def extract_clauses(
    text: str,
    *,
    source_document_id: str,
    source_document_name: str,
    min_body_chars: int = 20,
) -> list[dict[str, Any]]:
    lines = text.split("\n")
    clauses: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_page: int | None = None
    current_section: str | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        body = "\n".join(current["body"]).strip()
        if len(body) >= min_body_chars:
            current["text"] = body
            del current["body"]
            clauses.append(current)
        current = None

    for raw in lines:
        line = raw.strip()
        if not line:
            if current is not None:
                current["body"].append("")
            continue
        marker = _MARKER_RE.match(line)
        if marker:
            m = re.match(r"^\[Page (\d+)\]", line)
            current_page = int(m.group(1)) if m else current_page
            current_section = line.strip("[]")
            if current is not None:
                current["body"].append(line)
            continue

        number, title = "", ""
        md = _MD_HEADING_RE.match(line)
        num = _NUMBER_RE.match(line)
        kw = None if (md or num) else _keyword_heading(line)
        is_heading_like = line.isupper() and 4 <= len(line) <= 100 and not line.endswith(".")
        if md:
            title = md.group(1).strip()
        elif num:
            candidate = num.group(2).strip()
            # guard: table rows ("1 | Qty ...") and value lines are not clauses,
            # and neither are long numbered body paragraphs — only short
            # numbered labels count as headings.
            if _TITLE_LEAD_RE.match(candidate) and len(candidate) <= _MAX_NUMBERED_TITLE_CHARS:
                number, title = num.group(1).rstrip("."), candidate
        elif kw:
            title = kw
        elif is_heading_like:
            title = line

        if title:
            flush()
            current = {
                "number": number,
                "title": title[:160],
                "body": [],
                "sourceDocumentId": source_document_id,
                "sourceDocumentName": source_document_name,
                "page": current_page,
                "section": current_section,
            }
        elif current is not None:
            # cap per-clause body so one mega-section cannot swallow the document
            if sum(len(b) for b in current["body"]) < 12000:
                current["body"].append(line)
    flush()

    out = []
    for i, c in enumerate(clauses, 1):
        c["id"] = f"clause-{i:03d}"
        c["text"] = c["text"][:6000]
        out.append(c)
    return out
