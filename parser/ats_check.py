"""ATS parse-safety check — does an ATS actually *read* this CV?

The reference repo (adrianhajdin/ai-resume-analyzer) scores an "ATS" dimension,
but delegates it to an LLM looking at the resume file. Our previous
implementation aliased ATS to the job-keyword TF-IDF overlap, which measures
something else entirely: how well the CV matches *this posting*. A CV can match
a posting perfectly and still be unreadable by an ATS parser.

This module implements the real thing, deterministically and locally: it
inspects the *document* for the structural properties that make real Applicant
Tracking Systems fail. All checks derive from data we already extract (raw text,
segmented sections, PDF page geometry) — no LLM, no cloud, no new hard deps.

Each check returns a penalty and a tip. The resulting score is job-independent,
which is the whole point: it is a property of your CV, not of the match.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Sections an ATS expects to find by heading. Missing headings are the single
# most common reason a parser dumps everything into one blob.
_EXPECTED_SECTIONS = ("experience", "education", "skills")

# Glyphs that commonly survive extraction but break naive tokenizers, plus
# bullet characters that some older parsers emit as literal text.
_PROBLEM_GLYPHS = ("\uf0b7", "\uf0a7", "\uf06c", "\ufffd", "\u2022\u2022")

# Contact patterns — an ATS that cannot find email/phone often discards the CV.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE_RE = re.compile(r"(\+?\d[\d\s()/-]{7,}\d)")

# A text layer this thin for a whole CV means the PDF is image-based/scanned.
_MIN_CHARS_PER_PAGE = 250


def check_ats_parse_safety(
    *,
    raw_text: str,
    sections: dict[str, str] | None = None,
    pdf_path: str | Path | None = None,
) -> dict[str, Any]:
    """Assess how safely an ATS can parse this CV document.

    Unlike keyword overlap, this score is **job-independent** — it describes the
    document itself. Start at 100 and subtract for each structural hazard.

    Args:
        raw_text: The full extracted CV text.
        sections: Output of segment_sections(), if already computed.
        pdf_path: Optional source PDF; enables page-geometry checks
            (text-layer density, column detection). Non-PDF inputs skip these.

    Returns:
        {
          "score": int,                 # 0-100, job-independent
          "tips": [ {type, tip, explanation}, ... ],
          "checks": { <name>: bool },   # True = passed
        }
    """
    sections = sections or {}
    tips: list[dict[str, str]] = []
    checks: dict[str, bool] = {}
    score = 100

    # --- 1. Section headings ---------------------------------------------
    found = [s for s in _EXPECTED_SECTIONS if s in sections]
    missing = [s for s in _EXPECTED_SECTIONS if s not in sections]
    collapsed = list(sections.keys()) == ["header"]
    checks["section_headings"] = not missing and not collapsed

    if collapsed:
        score -= 35
        tips.append({
            "type": "improve",
            "tip": "No section headings detected",
            "explanation": (
                "The whole CV collapsed into a single block: no recognised "
                "headings were found. ATS parsers key on headings like "
                "'Experience', 'Education' and 'Skills' to assign content to "
                "fields. Without them your roles and dates may be discarded. "
                "Add plain, left-aligned headings on their own line."
            ),
        })
    elif missing:
        score -= 12 * len(missing)
        tips.append({
            "type": "improve",
            "tip": f"Missing standard heading(s): {', '.join(missing)}",
            "explanation": (
                "ATS parsers map content to fields via conventional headings. "
                f"Found {', '.join(found) or 'none'}; missing "
                f"{', '.join(missing)}. Use exactly these conventional words "
                "rather than creative alternatives such as 'My Journey'."
            ),
        })
    else:
        tips.append({
            "type": "good",
            "tip": "Standard section headings present",
            "explanation": (
                "Experience, Education and Skills headings were all detected, "
                "so an ATS can map your content to the right fields."
            ),
        })

    # --- 2. Machine-findable contact details ----------------------------
    has_email = bool(_EMAIL_RE.search(raw_text))
    has_phone = bool(_PHONE_RE.search(raw_text))
    checks["contact_details"] = has_email and has_phone
    if not has_email:
        score -= 20
        tips.append({
            "type": "improve",
            "tip": "No machine-readable email found",
            "explanation": (
                "No email address survived text extraction. If your contact "
                "details sit in a header, text box, or image, most ATS engines "
                "drop them and you become uncontactable. Put the address in "
                "the normal body text of the document."
            ),
        })
    if not has_phone:
        score -= 8
        tips.append({
            "type": "improve",
            "tip": "No machine-readable phone number found",
            "explanation": (
                "No phone number was detected in the extracted text. Write it "
                "in the body text in plain digits, not inside a graphic."
            ),
        })
    if has_email and has_phone:
        tips.append({
            "type": "good",
            "tip": "Contact details are machine-readable",
            "explanation": "Both an email address and a phone number survived text extraction.",
        })

    # --- 3. Glyph / encoding hazards ------------------------------------
    bad_glyphs = [g for g in _PROBLEM_GLYPHS if g in raw_text]
    checks["clean_glyphs"] = not bad_glyphs
    if bad_glyphs:
        score -= 10
        tips.append({
            "type": "improve",
            "tip": "Private-use or replacement glyphs in text layer",
            "explanation": (
                "Extraction produced characters from a private-use font range "
                "(typically Wingdings/Symbol bullets) or replacement markers. "
                "These corrupt tokenisation and can mangle nearby words. Use "
                "the word processor's native bullet list instead of a symbol font."
            ),
        })

    # --- 4. Date parseability -------------------------------------------
    # ATS timelines need year-bearing ranges. Accepts 2019-2021, 03/2019,
    # "Jan 2019", German "seit 2019" / "01.2019", and en/em dashes.
    date_hits = re.findall(
        r"(?:\b(?:19|20)\d{2}\b)"
        r"|(?:\b\d{1,2}[./]\d{4}\b)"
        r"|(?:\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
        r"|m\u00e4r|mai|okt|dez)[a-z\u00e4\u00f6\u00fc.]*\s+(?:19|20)\d{2}\b)",
        raw_text.lower(),
    )
    checks["dates_present"] = len(date_hits) >= 2
    if len(date_hits) < 2:
        score -= 15
        tips.append({
            "type": "improve",
            "tip": "Few or no parseable dates",
            "explanation": (
                f"Only {len(date_hits)} date-like token(s) were found. ATS "
                "engines build your employment timeline from date ranges and "
                "compute total experience from it; without them your seniority "
                "reads as zero. Use an explicit format such as '03/2019 - 08/2021'."
            ),
        })

    # --- 5. PDF-only geometry checks ------------------------------------
    if pdf_path is not None:
        geo = _pdf_geometry(pdf_path)
        if geo.get("error"):
            checks["text_layer"] = True  # unknown — do not penalise
        else:
            pages = geo["page_count"] or 1
            chars_per_page = len(raw_text) / pages
            checks["text_layer"] = chars_per_page >= _MIN_CHARS_PER_PAGE
            if chars_per_page < _MIN_CHARS_PER_PAGE:
                score -= 30
                tips.append({
                    "type": "improve",
                    "tip": "Sparse text layer — likely scanned or image-based",
                    "explanation": (
                        f"Only ~{chars_per_page:.0f} characters per page were "
                        "extractable. The CV is probably a scan or exported as "
                        "images, so an ATS reads almost nothing. Export a true "
                        "text PDF from the source document, or run OCR."
                    ),
                })

            if geo.get("multi_column"):
                score -= 18
                checks["single_column"] = False
                tips.append({
                    "type": "improve",
                    "tip": "Multi-column layout detected",
                    "explanation": (
                        "Text blocks appear side by side. Many ATS parsers read "
                        "strictly left-to-right across the full width, which "
                        "interleaves the two columns into nonsense. A "
                        "single-column layout is the safest choice."
                    ),
                })
            else:
                checks["single_column"] = True

    score = max(0, min(100, score))
    return {"score": score, "tips": tips, "checks": checks}


def _pdf_geometry(pdf_path: str | Path) -> dict[str, Any]:
    """Inspect PDF page geometry for ATS hazards (page count, column layout).

    Uses PyMuPDF if available. Degrades to {"error": ...} so callers never
    crash and never penalise the CV for a missing optional dependency.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        return {"error": "not a pdf"}
    try:
        import fitz  # PyMuPDF — optional, lazy.
    except ImportError:
        return {"error": "pymupdf not installed"}

    try:
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        multi_column = False
        if page_count:
            page = doc[0]
            width = page.rect.width or 1.0
            blocks = [b for b in page.get_text("blocks") if (b[4] or "").strip()]
            # Two blocks are side-by-side when they overlap vertically but sit
            # in opposite horizontal halves of the page.
            for i, a in enumerate(blocks):
                for b in blocks[i + 1:]:
                    v_overlap = min(a[3], b[3]) - max(a[1], b[1])
                    if v_overlap <= 8:
                        continue
                    a_mid = (a[0] + a[2]) / 2
                    b_mid = (b[0] + b[2]) / 2
                    if abs(a_mid - b_mid) > width * 0.30:
                        multi_column = True
                        break
                if multi_column:
                    break
        doc.close()
        return {"page_count": page_count, "multi_column": multi_column, "error": None}
    except Exception as e:  # noqa: BLE001 — never crash the parser
        return {"error": f"pdf geometry inspection failed: {e}"}


__all__ = ["check_ats_parse_safety"]
