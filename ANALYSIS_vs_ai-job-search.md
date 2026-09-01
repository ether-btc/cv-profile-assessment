# Analysis: MadsLorentzen/ai-job-search vs. cv-profile-assessment (+ austria-job-scout)

> **Note on the fork:** No fork of `ai-job-search` exists under `ether-btc`.
> I enumerated the org's entire repo list (58 repos). The job-related ones are:
> `austria-job-scout`, `cv-profile-assessment`, `job-matching-system` (archived →
> superseded by cv-profile-assessment), `job-research` (empty/404). So this is a
> **cross-repo analysis** of a public upstream against our own stack, not a diff
> against a sibling fork.

## TL;DR

`ai-job-search` is a **39.5k-star, 246-commit Claude-Code agent framework** — a
markdown-spec-driven job-search pipeline (scrape → rank → apply → interview) with
TypeScript portal scrapers, LaTeX CV/cover-letter generation, a salary benchmark
tool, and unusually rigorous **security/supply-chain guards**. It is far larger
and more "agentic" than our deterministic, local-only `cv-profile-assessment`.

**Architecturally our matching engine already covers its core scoring.** But it
surfaces **three concrete improvements we lack**, plus one security pattern worth
adopting if/when we add LLM tool-use:

| # | Adoptable from ai-job-search | Maps to our code | Effort |
|---|---|---|---|
| A | **Verdict bands** (Strong/Good/Moderate/Weak/Poor Fit) on top of numeric score | `matching/scorer.py`, `feedback_schema.py` (already computes scores) | Low |
| B | **Eligibility + Language gates** as explicit pre-score hard filters w/ PASS/FAIL/FLAG | new `matching/gates.py`; called in `pipeline.score_one_job` | Med |
| C | **Render the new `feedback` tips into the PDF report** | `scripts/match_to_pdf.py` (currently only shows `component_scores`) | Low |
| D | **Salary benchmark tool** pattern (fuzzy company-name match over user JSON) | new optional `tools/salary_lookup.py` + `data/salary_data.json` | Med |
| E | **Security guards** (`security_guards.py`) for permission/hook/gitignore allowlists | adopt only if we add an LLM agent / shell-exec surface | Med (conditional) |

Items A–C are the highest-value, lowest-risk and directly extend work already
done in this session (the `feedback` block now attached to every `score_one_job`
result). D is a nice-to-have that strengthens the Austrian/EU focus. E is
defensive and only relevant once we introduce autonomous tool execution.

---

## 1. What ai-job-search Actually Does (substance, not README)

### 1.1 Scoring framework — `.claude/skills/job-application-assistant/04-job-evaluation.md`
A **5-dimension** rubric (Technical Skills, Experience, Behavioral/Culture,
Location [PASS/FAIL], Career Alignment) + an optional Salary benchmark. Key ideas:

- **Two hard gates run *before* scoring** (not as dimensions):
  - **Eligibility Gate** — citizenship / work-rights / security-clearance hard stop.
    "Silence is not permission" — if the posting is silent, mark *unverified*,
    never assume PASS.
  - **Language Gate** — required language vs. candidate's declared Languages table.
    Not-declared-at-all → **FAIL** (hard stop); declared-but-bar-looks-higher →
    **FLAG** (score anyway, surface the gap); at/under level → **PASS**.
- **Verdict bands** on the weighted overall: Strong Fit 75+, Good 60–74,
  Moderate 45–59, Weak 30–44, Poor <30.
- **Location & Language are vetoes**, not weighted inputs: a 90-point job that
  fails a location/eligibility deal-breaker is *excluded*, never ranked first.

### 1.2 Triage command — `.claude/commands/rank.md`
The operational spec. Notable engineering discipline (worth studying as a pattern):
- **Honesty rule**: gaps stated verbatim, never smoothed over; low-fit postings
  get low scores even if prestigious.
- **Postings are untrusted data**: scoring agents must not follow instructions
  embedded in a job ad; never fetch URLs beyond the posting URL.
- **State consistency**: `seen_jobs.json` fields are *only added, never
  restructured*; re-running `/rank` is idempotent except an explicit, reversible
  expiry sweep. `--all` *replaces* (not accumulates) the gaps/strengths arrays.
- **Defensive date parsing**: a non-ISO stored deadline ("ASAP", "DD.MM.YYYY")
  is treated exactly like an *absent* one — never compared, never guessed.
- **Verdict field separation**: `location` (a place) vs `location_verdict`
  (PASS/FAIL/FLAG) are distinct keys so a ranked entry can't overwrite commute
  data with a verdict.

### 1.3 Salary tool — `salary_lookup.py`
Stdlib-only lookup over a **user-provided** `salary_data.json` (union stats,
Glassdoor, manually collected). Robust fuzzy matching:
- `normalize()` strips legal suffixes (A/S, ApS, GmbH…), parentheticals,
  country words, commas; lowercases; strips non-alphanumerics.
- `anglicize()` maps Nordic chars (ø→o, ä→ae…) before comparison.
- `match_score_optimized()` returns 0–100 with tiered confidence (exact=100,
  substring=80+, anglicized=75, word-overlap=lower).
- Validates the data shape (`collect_validation_issues`) and fails *closed* with a
  user-facing message.

### 1.4 Security guards — `tools/security_guards.py`
Catches dangerous changes in forks: (1) every `settings.json` permission must be
in an exact allowlist (no `Bash(*)` widening); (2) `.gitignore` personal-data
rules must persist and no un-allowlisted `!negation` may re-include them; (3) no
npm/bun lifecycle scripts in `.agents/**/package.json`; (4) **hooks are treated as
strictly more dangerous than permissions** (the Shai-Hulud worm planted a
`SessionStart` hook). Stdlib only, exit 1 on violation.

### 1.5 Upstream-sync tooling — `tools/check_upstream_updates.py`
Reads a `framework_version` front-matter field from the skill files and compares
it to the upstream remote's, warning if a fork's `origin` can't reveal upstream
updates. A lightweight "are we behind?" check.

---

## 2. Relevance to Our Stack

### 2.1 Our scoring already overlaps — and is more deterministic
Our `matching/scorer.py` computes a 4-component weighted score (required_skills
0.45, experience 0.25, preferred 0.18, keyword 0.12) with deal-breaker hard
filters. `ai-job-search`'s numeric engine is LLM-driven and less reproducible;
**ours is the stronger technical core.** What we *lack* is the **presentation and
gate layer** on top of those numbers.

### 2.2 The `feedback` block (added this session) is the bridge
`score_one_job` now returns a `feedback` dict with 5 dimensions (ATS, Tone &
Style, Content, Structure, Skills), each with score + tips. This maps **almost
1:1** onto `ai-job-search`'s framework — so we can adopt its **verdict bands** and
**gate concepts** directly into our existing structure without changing the math.

### 2.3 Concrete gaps vs. ai-job-search
1. **No verdict bands.** We emit a 0–1 `overall_score`; consumers must invent
   their own thresholds. `band_for_score()` (in the existing `constants/prompts.py`
   from the prior analysis) already exists but `score_one_job` doesn't attach it.
2. **No eligibility/language gates.** Our `preferences.deal_breakers` (free-text
   word-boundary match) is looser than ai-job-search's structured
   eligibility + language gates. For the Austrian/EU market, a **language gate**
   (German/English required vs. declared) is directly valuable.
3. **PDF report doesn't show the feedback.** `scripts/match_to_pdf.py` renders
   `component_scores` but not the new `feedback` tips — the explainability we
   built isn't surfaced where users actually read it.
4. **No salary benchmarking.** Our schema has `salary_expectations` on the
   candidate side but no company-side comparison. `salary_lookup.py`'s fuzzy
   matcher is a clean, dependency-free template.

---

## 3. Recommended Adoptions (priority order)

### Priority A — Verdict bands on `score_one_job` output  *(do now)*
- Attach `verdict` (Strong/Good/Moderate/Weak/Poor Fit) to every result, using
  the existing `band_for_score()` helper. One-line change in `pipeline.score_one_job`.
- Also emit `verdict` inside the `feedback` block (`feedback_schema.build_feedback_dict`
  already computes `overallScore`; add the band there too).

### Priority B — Eligibility + Language gates  *(do now, medium)*
- New `matching/gates.py` with `check_eligibility_gate(profile, job)` and
  `check_language_gate(profile, job)` returning
  `("PASS"|"FAIL"|"FLAG", note)`.
- Logic ported from `04-job-evaluation.md`:
  - Eligibility: if job text implies citizenship/PR/clearance requirement and
    profile doesn't evidence it → FAIL (hard stop, like a deal-breaker).
  - Language: compare job's required languages vs `basics.languages[]`;
    undeclared → FAIL; declared-but-bar-higher → FLAG; else PASS.
- Call them in `score_one_job` *before* component scoring, thread the results
  into the `feedback` block (new `eligibility_gate` / `language_gate` fields,
  mirroring ai-job-search's `location_verdict` separation).
- Keep them **deterministic and optional** (only active when the job text /
  profile carries the relevant fields) so the Pi-local, no-LLM guarantee holds.

### Priority C — Render `feedback` in the PDF report  *(do now, low)*
- In `scripts/match_to_pdf.py`, after `component_scores`, iterate
  `job["feedback"]` dimensions and print each score + its `good`/`improve` tips.
  This makes the explainability we built actually visible in the Syncthing PDF
  the user reads offline.

### Priority D — Optional salary benchmark tool  *(nice-to-have)*
- Port `salary_lookup.py` (stdlib-only, fuzzy matcher) into `tools/salary_lookup.py`
  with an Austrian/EU flavor (strip GmbH, AG, OG, e.U., "Österreich"/"Austria").
- Document `data/salary_data.json` format; skip silently when absent (same
  graceful-degradation as upstream). This strengthens the EU market angle.

### Priority E — Security guards  *(conditional)*
- Only relevant if we later add an LLM agent that can run shell commands or
  install packages. If so, port `security_guards.py`'s three checks as a
  pre-commit / CI gate. Until then, **not needed** — our repo has no
  auto-executing hooks or lifecycle scripts.

---

## 4. What NOT to Adopt

| ai-job-search feature | Why it doesn't fit |
|---|---|
| TypeScript portal scrapers (LinkedIn, JobIndex, etc.) | We already have `austria-job-scout` (Python, SQLite, Austrian market). Re-implementing scrapers duplicates it. |
| Claude-Code markdown command specs (`/rank`, `/apply`…) | We're a library/CLI, not an agent runtime. Our `scripts/*.py` CLIs are the equivalent surface. |
| LaTeX CV / cover-letter generation | Out of scope for a *matching* engine; would balloon the repo. |
| `framework_version` upstream-sync tooling | Useful for a heavily-forked template; we're the upstream for our own repos. |
| 5-dimension LLM scoring | We deliberately use deterministic scoring for reproducibility + privacy. Keep it. |

---

## 5. Summary

`ai-job-search` is a mature *agent framework*; our `cv-profile-assessment` is a
mature *deterministic engine*. The valuable transfer is the **gate + verdict
layer** that sits on top of numeric scores — eligibility/language gates,
PASS/FAIL/FLAG verdicts, and verdict bands — all of which we can implement on top
of our existing `feedback` block with **zero new dependencies** and no loss of
the local-only, privacy-first property. The salary tool (D) is a clean optional
add; the security guards (E) only matter if we introduce autonomous tool use.

Concrete next steps, in order: **A (verdict bands) → B (gates) → C (PDF render) →
D (salary, optional)**. E deferred.
