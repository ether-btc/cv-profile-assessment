"""Usage history — append-only JSONL log for CV processing runs.

Records each parse_cv run with metadata to enable:
- Regression detection (profile diff between runs)
- Iterative improvement measurement
- Audit trail of what was processed and when
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_LOG_PATH = Path(__file__).parent.parent / "data" / "processing_history.jsonl"


def _now_iso() -> str:
    """UTC timestamp in ISO 8601 with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_processing_run(
    source_path: str,
    profile: Dict,
    language: str = "",
    warnings: Optional[List[str]] = None,
    log_path: Optional[Path] = None,
) -> Dict:
    """Append a processing run record to the JSONL log.

    Args:
        source_path: Path to the CV file that was processed.
        profile: The resulting profile dict.
        language: Detected language code (e.g. "de", "en").
        warnings: Optional list of warning messages.
        log_path: Override log file path.

    Returns:
        The record dict that was logged.
    """
    log_path = log_path or DEFAULT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    sections_found = []
    if "skills" in profile and profile["skills"]:
        sections_found.append("skills")
    if profile.get("experience"):
        sections_found.append("experience")
    if profile.get("education"):
        sections_found.append("education")
    if profile.get("certifications"):
        sections_found.append("certifications")

    record = {
        "timestamp": _now_iso(),
        "source": source_path,
        "language": language,
        "sections_found": sections_found,
        "entity_counts": {
            "skills": len(profile.get("skills", [])),
            "experience": len(profile.get("experience", [])),
            "education": len(profile.get("education", [])),
            "certifications": len(profile.get("certifications", [])),
        },
        "confidence_scores": profile.get("metadata", {}).get("confidence_scores", {}),
        "name_extracted": profile.get("basics", {}).get("name", ""),
        "warnings": warnings or [],
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def read_history(log_path: Optional[Path] = None) -> List[Dict]:
    """Read all processing history records.

    Args:
        log_path: Override log file path.

    Returns:
        List of record dicts, oldest first.
    """
    log_path = log_path or DEFAULT_LOG_PATH
    if not log_path.exists():
        return []

    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def format_history_table(records: Optional[List[Dict]] = None) -> str:
    """Format history records as a human-readable table.

    Args:
        records: Pre-loaded records. If None, reads from default log.

    Returns:
        Formatted string for terminal display.
    """
    if records is None:
        records = read_history()

    if not records:
        return "No processing history found."

    lines = []
    header = f"{'Timestamp':<26} {'Lang':<5} {'Source':<45} {'Skills':<7} {'Exp':<5} {'Edu':<5} {'Name':<20}"
    lines.append(header)
    lines.append("-" * len(header))

    for r in records:
        ts = r.get("timestamp", "")[:19]
        lang = r.get("language", "?")
        source = Path(r.get("source", "")).name[:43]
        counts = r.get("entity_counts", {})
        skills = str(counts.get("skills", 0))
        exp = str(counts.get("experience", 0))
        edu = str(counts.get("education", 0))
        name = (r.get("name_extracted") or "")[:18].replace("\n", " ")
        lines.append(f"{ts:<26} {lang:<5} {source:<45} {skills:<7} {exp:<5} {edu:<5} {name:<20}")

    return "\n".join(lines)
