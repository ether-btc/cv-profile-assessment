#!/usr/bin/env python3
"""CLI: Convert match_scout_jobs JSON output → single PDF (one job per page).

The PDF is intended for offline reading in a Syncthing-shared folder.
Pass the JSON file produced by match_scout_jobs.py (-o output.json).

Usage:
    python match_to_pdf.py <match.json> [-o out.pdf] [--include-only | --exclude-flagged]

Layout (one page per job):
  Header:  Title, Company, Location
  Body:    Overall score + component scores
           Filter decision (include / flag / exclude + reasons)
           Skills (required, preferred)
           Description (truncated to 1 page)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling packages importable when run as a script
sys.path.insert(0, str(Path(__file__).parent.parent))


def _safe_pdf_text(s: str) -> str:
    """Strip non-latin1 chars (fpdf2 default fonts only support latin-1)."""
    if not isinstance(s, str):
        s = str(s)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def render_pdf(match_json_path: Path, output_pdf_path: Path,
               include_only: bool, exclude_flagged: bool) -> int:
    data = json.loads(match_json_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    ranked = data.get("ranked", [])
    excluded = data.get("excluded", [])

    # fpdf2 import is local so this script stays self-contained
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)

    rendered = 0
    sections = []

    if include_only:
        sections.append(("Ranked jobs", [j for j in ranked
                                        if j.get("_filter", {}).get("decision") != "flag"]))
    else:
        sections.append(("Ranked jobs", ranked))

    if not exclude_flagged and not include_only:
        sections.append(("Flagged (kept; check reasons)", [j for j in ranked
                         if j.get("_filter", {}).get("decision") == "flag"]))
    sections.append(("Excluded by bias filter", excluded))

    for section_title, jobs in sections:
        if not jobs:
            continue

        # Section divider page (only if there are multiple sections with content)
        if sum(1 for _, js in sections if js) > 1:
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 12, _safe_pdf_text(section_title), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        for job in jobs:
            _render_job_page(pdf, job, section_title)
            rendered += 1

    if rendered == 0:
        # Always emit at least a placeholder page so we never write an empty PDF
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, _safe_pdf_text("No matching jobs"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, _safe_pdf_text(
            f"match_scout_jobs reported 0 jobs in any bucket. "
            f"summary={summary}"
        ))
        rendered = 1

    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_pdf_path))
    print(f"PDF written to {output_pdf_path} ({rendered} job pages)")
    return 0


def _render_job_page(pdf, job: dict, section_title: str) -> None:
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 8, _safe_pdf_text(job.get("job_title", "Unknown title")))
    pdf.ln(1)

    # Company / Location
    pdf.set_font("Helvetica", "", 11)
    meta_bits = []
    if job.get("company"):
        meta_bits.append(job["company"])
    if job.get("location"):
        meta_bits.append(job["location"])
    if meta_bits:
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 6, _safe_pdf_text(" · ".join(meta_bits)))
        pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # Section header (so the user knows which bucket)
    if section_title:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 5, _safe_pdf_text(f"Section: {section_title}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    # Filter annotation
    f = job.get("_filter") or {}
    if f.get("decision") in ("flag", "exclude"):
        pdf.set_font("Helvetica", "B", 11)
        if f["decision"] == "exclude":
            pdf.set_text_color(180, 30, 30)
        else:
            pdf.set_text_color(180, 130, 0)
        reasons = ", ".join(f.get("reasons", []))
        pdf.cell(0, 6, _safe_pdf_text(f"FILTER {f['decision'].upper()}: {reasons}"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # Scores (only for ranked jobs — excluded jobs don't have scores)
    if "overall_score" in job:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, _safe_pdf_text(f"Overall score: {job['overall_score']:.3f}"),
                 new_x="LMARGIN", new_y="NEXT")
        comp = job.get("component_scores") or {}
        weights = job.get("weights") or {}
        pdf.set_font("Helvetica", "", 10)
        for k, v in comp.items():
            w = weights.get(k, "")
            pdf.cell(0, 5, _safe_pdf_text(f"  {k}: {v:.3f}    weight={w}"),
                     new_x="LMARGIN", new_y="NEXT")
        if job.get("blocked"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(180, 30, 30)
            pdf.cell(0, 5, _safe_pdf_text(f"BLOCKED (deal-breaker): {job.get('block_reason','')}"),
                     new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(3)

    # URL (so user can click from PDF reader)
    if job.get("url"):
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(40, 80, 160)
        pdf.multi_cell(0, 5, _safe_pdf_text(f"Source: {job['url']}"))
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # Description (best-effort; jobs may not have descriptions in scout rows)
    desc = job.get("description")
    if desc:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, _safe_pdf_text("Description"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        # Truncate to keep page count manageable
        desc = desc if len(desc) <= 1800 else desc[:1800] + "…[truncated]"
        pdf.multi_cell(0, 5, _safe_pdf_text(desc))
    else:
        # Excluded jobs sometimes don't carry description; show whatever we have
        reqs = job.get("required_skills") or []
        if reqs:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, _safe_pdf_text("Required skills"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, _safe_pdf_text(", ".join(reqs)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert match_scout_jobs JSON output to a PDF",
    )
    parser.add_argument("match_json", help="JSON output of match_scout_jobs.py")
    parser.add_argument("-o", "--output", required=True, help="Output PDF path")
    parser.add_argument("--include-only", action="store_true",
                        help="Render only 'include' jobs (no flagged)")
    parser.add_argument("--exclude-flagged", action="store_true",
                        help="Skip the flagged bucket entirely")
    args = parser.parse_args()

    return render_pdf(
        Path(args.match_json),
        Path(args.output),
        include_only=args.include_only,
        exclude_flagged=args.exclude_flagged,
    )


if __name__ == "__main__":
    sys.exit(main())
