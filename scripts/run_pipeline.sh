#!/bin/bash
# Pipeline-Wrapper: seed scout DB, match profile, render PDF, copy to Syncthing.
#
# Usage:
#   ./scripts/run_pipeline.sh <profile.json> [<scout_db.sqlite>] [<pdf_out>]
#
# Defaults to:
#   - profile: /tmp/matthias_profile.json (regenerate via parse_cv.py if missing)
#   - scout_db: /tmp/scout_pipeline.sqlite (regenerate via seed_scout_db_from_samples.py if missing)
#   - pdf_out: /home/hermes-pi/Sync/shared/jobs-YYYY-MM-DD.pdf

set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
source venv/bin/activate

PROFILE="${1:-/tmp/matthias_profile.json}"
SCOUT_DB="${2:-/tmp/scout_pipeline.sqlite}"
PDF_OUT="${3:-/home/hermes-pi/Sync/shared/jobs-$(date +%Y-%m-%d).pdf}"

# Step 1: ensure profile exists
if [[ ! -f "$PROFILE" ]]; then
    echo "[run_pipeline] profile missing; generating from CV PDF via parse_cv.py"
    PDF_IN="${PDF_INPUT:-/home/hermes-pi/Sync/shared/Matthias_K_FlowCV_Resume_2026-06-29.pdf}"
    if [[ ! -f "$PDF_IN" ]]; then
        echo "[run_pipeline] no CV PDF at $PDF_IN — set PDF_INPUT env var or pass profile as arg 1" >&2
        exit 2
    fi
    python scripts/parse_cv.py "$PDF_IN" -o "$PROFILE" --no-log
fi

# Step 2: ensure scout DB exists
if [[ ! -f "$SCOUT_DB" ]]; then
    echo "[run_pipeline] scout DB missing; seeding from data/sample_jobs/*.json"
    python scripts/seed_scout_db_from_samples.py "$SCOUT_DB"
fi

# Step 3: match. Capture only the trailing progress-line (per the script's
# summary emit); stderr is preserved separately so python errors are visible.
MATCH_OUT="${PDF_OUT%.pdf}.json"
if ! python scripts/match_scout_jobs.py "$PROFILE" "$SCOUT_DB" -o "$MATCH_OUT" \
        2> "${PDF_OUT%.pdf}.err"; then
    echo "[run_pipeline] match_scout_jobs FAILED — see ${PDF_OUT%.pdf}.err" >&2
    exit 5
fi
# Surface only the one-line summary to stdout (matches prior UX).
tail -1 "${PDF_OUT%.pdf}.err" 2>/dev/null || true

# Step 4: PDF
if ! python scripts/match_to_pdf.py "$MATCH_OUT" -o "$PDF_OUT" \
        2> "${PDF_OUT%.pdf}.pdf.err"; then
    echo "[run_pipeline] match_to_pdf FAILED — see ${PDF_OUT%.pdf}.pdf.err" >&2
    exit 6
fi
tail -1 "${PDF_OUT%.pdf}.pdf.err" 2>/dev/null || true

echo "[run_pipeline] OK"
echo "  profile:   $PROFILE"
echo "  scout_db:  $SCOUT_DB"
echo "  json:      $MATCH_OUT"
echo "  pdf:       $PDF_OUT"
