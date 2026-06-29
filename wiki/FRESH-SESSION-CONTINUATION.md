# cv-profile-assessment — Fresh Session Continuation Reference

**Created:** 2026-06-29
**Last session end:** Phase 5 shipped + Scout-Pipeline wired. Bias filter + PDF generator live.

---

## Current State

### Repository
- **Path:** `/home/hermes-pi/projects/cv-profile-assessment`
- **Remote:** `git@github.com:ether-btc/cv-profile-assessment.git`
- **Branch:** `master`
- **HEAD:** `5ef8696` — "feat: bias-aware job filter + PDF generator + pipeline wrapper"
- **Status:** Clean, all pushed, tests green (127 pass + 2 skipped)

### Companion project (austria-job-scout)
- **Path:** `/home/hermes-pi/projects/austria-job-scout`
- **Status:** Operational as of 2026-06-29 — venv installed, 151/151 tests pass, db-init/db-stats CLI works.
- Symlink at `~/.hermes/projects/austria-job-scout` resolves to `/media/hermes-pi/f3fd4a1d-.../hermes/projects/austria-job-scout/`
- Job-research-framework symlink at `~/.hermes/projects/job-research-framework` **had to be repaired** 2026-06-29 — was pointing to dead `/mnt/usb/...` mount; re-linked to `/media/hermes-pi/f3fd4a1d-.../hermes/projects/job-research-framework/`.

---

## Phase 5 Deliverables (commit f657b8d, shipped 2026-06-29 earlier)

1. **Language detection** — common-word frequency heuristic, dependency-free
2. **Usage history** — append-only JSONL log + CLI `--history` flag
3. **German section segmentation** — SECTION_PATTERNS for FlowCV / DIN-style / Europass
4. **Bilingual NER** — en_core_web_sm + de_core_news_sm, routes by detected language. Austrian postal codes. DE/AT phone formats.
5. **DACH skill taxonomy** — SAP, BMC Remedy, SCCM, MDM, MS AD, Oracle/Microsoft CRM, Amdocs, Clarify, MS Office, German soft skills
6. **Pipeline integration** — detect_language → route NER → confidence scoring → history log
7. **CLI upgrades** — `--history`, `--no-log`, post-write summary
8. **Tests** — 36 new in test_german_i18n.py

## Phase 6 Deliverables (commit 5ef8696, shipped 2026-06-29 evening)

### Bias-aware job filter (`integration/job_filters.py`)
- `DEFAULT_BLOCKLIST_KEYWORDS` — Akquise, Kaltakquise, Hunter, Außendienst, etc.
- `DEFAULT_FLAG_KEYWORDS` — Neukunden, Akquiseanteil (borderline; kept in ranking with annotation)
- Pure functions: `classify_job`, `filter_jobs`, `combined_text`
- Override-able via parameters (test-friendly)
- 19 unit tests covering semantics, empty inputs, override behaviour

### Updated `scripts/match_scout_jobs.py`
- Applies filter before scoring
- Output structure: `{ranked: [...], excluded: [...], summary: {...}}`
- New CLI flag `--no-excluded` for slimmer output
- Each scored job carries `_filter: {decision, reasons}` annotation

### PDF generator (`scripts/match_to_pdf.py`)
- fpdf2-based, A4 portrait, one page per job
- Bucket headers (Ranked / Flagged / Excluded)
- Filter annotation highlighted red (exclude) / orange (flag)
- Latin-1 safe (Replaces non-latin-1 chars with `?` — ensures printable output for German/Austrian content)
- CLI flags: `--include-only`, `--exclude-flagged`

### End-to-end pipeline wrapper (`scripts/run_pipeline.sh`)
- Idempotent: seeds scout DB if missing, parses CV if profile missing
- Zero web traffic (uses `data/sample_jobs/*.json` seed data)
- Outputs: profile JSON, scout DB, match JSON, PDF

---

## Test Status

```
Pytest: 127 passed, 2 skipped in 7.61s
```

Test count progression: 19 → 57 → 65 → 72 → 108 → **127** (+19 for job_filters)

---

## Real CV Reprocessing (Phase 5 result, unchanged in Phase 6)

Source: `Matthias_K_FlowCV_Resume_2026-06-29.pdf`

- Language: de
- Name: "Matthias K."
- Location: {city: "Wien", country: "Austria"}
- Languages: German (native), Hungarian (fluent)
- Skills: 10 (SAP, MS Office, Microsoft CRM, Oracle, Oracle CRM, plus German soft skills)

Profile JSON: `/tmp/matthias_profile.json`

---

## End-to-end smoke run (Phase 6 verification)

```bash
cd /home/hermes-pi/projects/cv-profile-assessment && source venv/bin/activate
./scripts/run_pipeline.sh /tmp/matthias_profile.json /tmp/scout_pipeline.sqlite /tmp/pipeline_smoke.pdf
# → "Seeded 4 jobs"; "Results written"; "PDF written to /tmp/pipeline_smoke.pdf (4 job pages)"
```

Sample match result (4 jobs, 0 excluded, scores 0.341 across the board because sample_jobs are dev fixtures):

```
RANKED:
  [0.341] DevOps Engineer                          (include)
  [0.341] Frontend Developer (React/Next.js)       (include)
  [0.341] NLP Research Engineer                    (include)
  [0.341] Senior Backend Engineer (Python)         (include)
```

With synthetic hunter-flavored jobs:
```
RANKED:
  [0.538] HR-Sachbearbeiter (m/w/d)                            filter=flag
  [0.479] 1st Level IT-Support (m/w/d)                         filter=include
  [0.478] Sachbearbeiter Online-Marketing (m/w/d)              filter=include
  [0.353] Trainer / Coach für Bildungsprogramm (m/w/d)         filter=include

EXCLUDED:
  [exclude] Sales Hunter (m/w/d)                                reasons=['akquise', 'neukundengewinnung', 'kaltakquise', 'hunter', 'außendienst', 'sales hunter']
```

---

## Known Limitations / Phase 6.1 Candidates

### Priority 1: Real Wien-KMU Discovery (Phase 6 main goal — NOT YET STARTED)
**Status:** Infrastructure ready, fetching not yet executed.
**Prerequisites met:**
- austria-job-scout operational (151/151 tests, CLI working)
- cv-profile-assessment bias filter live (hunter/sales roles excluded)
- Pipeline wrapper produces PDF for Syncthing-shared folder
**Blocked on:** explicit decision by user (you) to spend the daily Cloudflare/WAF budget (≤10/Tag per user PARAMOUNT rule).
**When greenlit, run:**
```bash
cd /home/hermes-pi/projects/cv-profile-assessment
source venv/bin/activate
# Strategy: use crt.sh CT log mining for Wien-KMU subdomains (NOT CF-protected),
# deduplicate against existing scout DB, then scrape career pages with curl_cffi.
# Output lands in /home/hermes-pi/Sync/shared/jobs-YYYY-MM-DD.pdf via run_pipeline.sh
```

### Priority 2: FlowCV 2-column PDF layout (still unsolved from Phase 5)
**Problem:** pdfminer.six reads top-to-bottom across columns; 13 jobs collapse into 1.
**Options:** pdfplumber (column-aware), PyMuPDF (better layout preservation).

### Priority 3: stealth-core wreq-backend build (nice-to-have)
- Missing `libclang-dev`; `sudo apt install -y libclang-dev` is the fix.
- 22 min cold build + 10 min incremental after dep install.
- Optional: curl_cffi (Python) path is functional for residential-IP/low-stealth targets. Build is only needed for hardened CF-bypass.

---

## Quickstart (fresh session)

```bash
# 0. Verify infra (one-time after reboot):
ls -la ~/.hermes/projects/job-research-framework  # symlink should resolve
ls /home/hermes-pi/projects/austria-job-scout/venv  # venv should exist
cd /home/hermes-pi/projects/cv-profile-assessment && ls venv/

# 1. End-to-end (zero web):
cd /home/hermes-pi/projects/cv-profile-assessment && source venv/bin/activate
./scripts/run_pipeline.sh  # uses defaults; outputs to /home/hermes-pi/Sync/shared/

# 2. With specific files:
./scripts/run_pipeline.sh /tmp/matthias_profile.json /tmp/scout_pipeline.sqlite /tmp/out.pdf

# 3. Tests:
cd tests && /home/hermes-pi/projects/cv-profile-assessment/venv/bin/python -m pytest -o addopts="" -q
# → "127 passed, 2 skipped"
```

---

## Pitfalls (baked-in)

- **Don't change proficiency default from "advanced"** in skill_extractor.py — the audit's "honest 0.7 fallback" was for date extraction, not proficiency.
- **Use `(?<![a-z0-9])`/`(?![a-z0-9])`** for word boundaries, NOT `\b` (fails on `c++`, `.NET`, `node.js`).
- **`profile_builder_pkg/`** stays renamed (stdlib `profile` clash — well-documented).
- **JSON Schema languages field** is `[{language, fluency}]` objects, not flat strings.
- **Pytest from project root** collects 0 tests due to duplicated `-q` from addopts. Run pytest from `tests/` directory OR pass `-o addopts=""` when running from root.
- **austria-job-scout** symlink at `~/.hermes/projects/austria-job-scout` was correctly pointing at USB UUID mount already; **job-research-framework** symlink was broken — needed `ln -sfn /media/hermes-pi/<uuid>/hermes/projects/job-research-framework`. If you see "No tests collected" or "No module named" from jrf, the symlink is likely the issue.
- **fpdf2 default fonts only support latin-1** — German umlauts (ä, ö, ü, ß) encoded as `?`. For real Ö/Umlaut PDF output, register a TTF font (e.g. Helvetica DejaVu). Not blocking; PDF still readable.

---

## Mnemosyne Persistence

Phase 5 + Phase 6 status: stored as Mnemosyne memories with IDs:
- (see Phase 5 record for cv-profile-assessment status)
- (see Phase 6 record for scout-integration status)
- 483cd74c4c263521 — Phase 6 3-cycle audit summary (Cycle 1 = correctness/security, Cycle 2 = efficiency/quality, Cycle 3 = e2e runtime; 136/138 tests green)
- eb12f22133e83fe9 — Audit self-prompt (reusable for future reviews)

Recall: `mnemosyne_recall(query="cv-profile-assessment Phase 6 bias filter")` or `mnemosyne_recall(query="Phase 6 audit cycle")`.

---

## See Also

- `wiki/DEVELOPMENT_LOG.md` — 2026-06-29 first real CV test + Phase 5 gap inventory
- `wiki/audits/cv-profile-assessment-phase6-audit-2026-06-29.md` — 3-cycle Phase-6 audit (correctness → efficiency → e2e)
- `~/projects/austria-job-scout/AUDIT_REPORT_2026-06-23.md` — pre-Phase-6 audit baseline
- `~/projects/cv-profile-assessment/development_log.md` (if exists) — pre-Phase-5 history
