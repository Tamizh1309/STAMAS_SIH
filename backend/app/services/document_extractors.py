"""Server-side text extraction for tender documents (isolated layer).

Supported: PDF (PyMuPDF), DOCX (python-docx, paragraphs + tables),
XLSX (openpyxl), XLS (xlrd). Legacy .doc has no reliable extractor here and
is reported honestly as unsupported — never faked.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger("stamas.documents.extract")


class ExtractionError(Exception):
    """Raised when text cannot be extracted (corrupt/empty/unsupported)."""


class UnsupportedExtraction(ExtractionError):
    """Raised for formats with no reliable extractor (e.g. legacy .doc)."""


def normalize_text(text: str) -> str:
    """Light normalization that preserves technical meaning.

    - normalizes line endings, collapses 3+ blank lines to two
    - collapses runs of spaces/tabs (never inside the preserved structure)
    - keeps headings, numbered clauses, values (22 HRC, 450 bar, %) intact
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # strip trailing spaces per line, drop truly empty padding at ends
    lines = [ln.rstrip() for ln in text.split("\n")]
    return "\n".join(lines).strip()


def extract_pdf(path: Path) -> tuple[str, int]:
    import pymupdf  # PyMuPDF

    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise ExtractionError(f"Cannot open PDF (file may be corrupt): {exc}") from exc
    try:
        pages: list[str] = []
        for i, page in enumerate(doc):
            try:
                pages.append(f"[Page {i + 1}]\n{page.get_text('text')}")
            except Exception as exc:
                log.warning("PDF page %d text failed: %s", i + 1, exc)
        return "\n\n".join(pages), len(doc)
    finally:
        doc.close()


def extract_docx(path: Path) -> tuple[str, int]:
    from docx import Document

    try:
        doc = Document(str(path))
    except Exception as exc:
        raise ExtractionError(f"Cannot open DOCX (file may be corrupt): {exc}") from exc
    parts: list[str] = []
    for para in doc.paragraphs:
        t = (para.text or "").strip()
        if not t:
            continue
        # preserve headings explicitly so clause detection sees them
        if para.style and para.style.name.startswith("Heading"):
            parts.append(f"\n## {t}\n")
        else:
            parts.append(t)
    for table in doc.tables:
        for row in table.rows:
            cells = [(c.text or "").strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts), 1


def _sheet_to_text_cell_values(rows) -> str:
    lines = []
    for row in rows:
        vals = [str(v).strip() for v in row if v is not None and str(v).strip() != ""]
        if vals:
            lines.append(" | ".join(vals))
    return "\n".join(lines)


def extract_xlsx(path: Path) -> tuple[str, int]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(str(path), read_only=True, data_only=True)
    except Exception as exc:
        raise ExtractionError(f"Cannot open XLSX (file may be corrupt): {exc}") from exc
    try:
        parts = []
        for ws in wb.worksheets:
            parts.append(f"[Sheet: {ws.title}]")
            parts.append(_sheet_to_text_cell_values(ws.iter_rows(values_only=True)))
        return "\n".join(p for p in parts if p), len(wb.worksheets)
    finally:
        wb.close()


def extract_xls(path: Path) -> tuple[str, int]:
    import xlrd

    try:
        book = xlrd.open_workbook(str(path))
    except Exception as exc:
        raise ExtractionError(f"Cannot open XLS (file may be corrupt): {exc}") from exc
    parts = []
    for sheet in book.sheets():
        parts.append(f"[Sheet: {sheet.name}]")
        for r in range(sheet.nrows):
            vals = [str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)]
            vals = [v for v in vals if v]
            if vals:
                parts.append(" | ".join(vals))
    return "\n".join(p for p in parts if p), book.nsheets


def extract_text(extension: str, path: Path) -> tuple[str, int | None]:
    """Extract + normalize. Returns (text, page_or_sheet_count)."""
    ext = extension.lower()
    if ext == "pdf":
        raw, count = extract_pdf(path)
    elif ext == "docx":
        raw, count = extract_docx(path)
    elif ext == "xlsx":
        raw, count = extract_xlsx(path)
    elif ext == "xls":
        raw, count = extract_xls(path)
    elif ext == "doc":
        raise UnsupportedExtraction(
            "Legacy .doc extraction is not supported in this environment. "
            "Convert the document to DOCX or PDF and re-upload."
        )
    else:
        raise UnsupportedExtraction(f"Unsupported document type: .{ext}")
    text = normalize_text(raw)
    if not text:
        raise ExtractionError("No extractable text found in the document (it may be scanned images without OCR or empty).")
    return text, count
