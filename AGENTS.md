# AGENTS.md — Aviva Inbox Triage

## Project
Take-home task for Aviva (round 2); owner Victor Gamargo Franco. An inbox-triage assistant for an insurance claims handler: it ingests the provided mailbox (data/emails_candidate.json, 50 threads / 95 messages), classifies each thread as action_required / informational / irrelevant with Claude Haiku, assigns a priority with plain Python rules, shows the workload in a React dashboard and answers free-text questions with Claude Sonnet, citing messages. Done = the eight phases of the brief verified, tests green, eval numbers recorded, and a clean clone runs from the README alone. The owner must be able to explain every file in a 45-minute interview: optimise for explainability, not cleverness.

Settled — do not change without asking: the stack below and nothing more (no queues, vector DB, auth, Docker, ORM, React state libraries); "LLM for judgement, code for policy"; recommendations only, never automatic actions; `thread_id` and `message_id` never reach a prompt or a rule (both leak the category).

The spec is AGENT_BRIEF.md (the owner's brief, kept verbatim). Its §5 phases were the approved plan; all eight are done. Read docs/session.md before touching anything.

**Private vs published.** Everything in git is published, the agent docs included (this file, CLAUDE.md, the brief, docs/session.md, docs/memory.md, the docs check and its hooks), so a reviewer can see how the work was planned, directed and verified (D-58). Two things stay local: `.env` (gitignored) and the interview demo script, walkthrough.md under docs/ (in .git/info/exclude); never `git add -f` either. Branches: `main` is published to github.com/G3NZU/aviva-inbox-triage; `private-history` holds the early build history and has no remote — never push it.

## Stack
- Python (built and tested on 3.14) · FastAPI + uvicorn · Pydantic v2 validates every model and every LLM output.
- sqlite3 from the standard library, no ORM. The DB file is disposable: the pipeline rebuilds it.
- anthropic SDK 1.x: Claude Haiku 4.5 triages, Claude Sonnet 5.5 answers questions. Model names, thresholds and prompt versions live only in backend/app/config.py. Sonnet 5.5 rejects `temperature` and assistant prefill; Haiku 4.5 rejects `effort`.
- python-dotenv loads `.env` from the repo root. pytest + httpx (FastAPI TestClient). Tests never call the API: the LLM is mocked.
- Frontend: Vite 8 + React 19 + TypeScript 7 (strict) + Tailwind v4 via `@tailwindcss/vite` (no tailwind.config.js). No router, state or chart library.
- Deploy target: none. Runs locally.

## Commands
Backend commands run from `backend/` with the venv active (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` elsewhere); frontend commands from `frontend/`.
- Install: `python -m venv .venv` then `pip install -r requirements.txt`; `npm install`
- Dev: `uvicorn app.main:app --reload` (API on :8000); `npm run dev` (UI on :5173)
- Build: `npm run build` (tsc type-check + vite build)   <- must pass before any frontend task counts as done
- Lint: none configured — do not claim lint passes
- Test: `pytest`   <- must pass before any task counts as done (exit code 5 = no tests collected)
- Docs check: `node scripts/docs-check.mjs --strict` (repo root)   <- every .md in the docs map and under its cap; see Automation

## Working loop (every task, every session)
1. Read docs/session.md and docs/memory.md first, then the AGENT_BRIEF.md section for the current phase.
2. One phase at a time, in order; never start a phase while an earlier one has failing tests or unverified behaviour. The brief's phases are the approved plan: no extra go-ahead per phase.
3. Investigate before writing code. Every function gets a docstring (what, why, inputs, outputs); functions ≤ ~40 lines, files ≤ ~250 lines; type hints everywhere.
4. After each slice: tests, build, docs check. Fix errors before moving on.
5. End of each phase: run its verification step; update docs/map.md (if structure changed), docs/session.md (rewrite "Now", add a log entry), docs/decisions.md (append), docs/memory.md (replace entries on the same subject), docs/techdebt.md (anything skipped); commit; give the owner a 3-line status.
6. Never commit secrets. Show `git status` before committing if unsure.
7. Ambiguous → pick the simplest option, log it in docs/decisions.md, continue. Deviating from the brief or costly to reverse → ask first. Broken → say so; never paper over it.

## Docs map — one job each, with a size cap. If a fact belongs in two files, it belongs in one.
Every session reads CLAUDE.md's imports (about 20 KB); the rest is read on demand. `scripts/docs-check.mjs` enforces every cap below (see Automation); a `.md` that is not listed here fails the check. At a cap, remove at least as much as you add. Never raise a cap — that is the owner's call. File names follow the owner's brief (AGENT_BRIEF.md §4), which overrides the agent-docs defaults: docs/session.md does the job of next_session.md + CHANGELOG.md, docs/map.md of system_map.md, docs/techdebt.md of tech_debt.md. **Total ≤ 156 KB.** (Raised by the owner, last on 2026-10-04.)
- CLAUDE.md — Claude Code's entry point: `@` imports of AGENTS.md, docs/session.md and docs/memory.md, nothing else. **≤ 1 KB.**
- AGENTS.md — this file: what the project is, the rules, the stack, the commands. **≤ 12 KB.**
- AGENT_BRIEF.md — the owner's brief: spec and phase plan. Read-only, verbatim. **≤ 28 KB.**
- README.md — for the reviewer: what it does, setup (keys, dependencies, how to run), architecture, decisions and the alternatives rejected, evaluation, risks, limitations. The brief requires all of these, hence the larger cap. **≤ 18 KB** (raised by the owner, last on 2026-10-04).
- docs/session.md — **START HERE.** "Now" (state, next steps, blockers; rewritten each session), then a dated log, newest first: at most six short lines per entry, older entries folded to one line. NOT decisions. **≤ 8 KB.**
- docs/decisions.md — numbered Decision / Why / Alternative rejected entries; append-only (a reversal is a new entry naming the one it supersedes). The owner's interview script. **≤ 36 KB** (raised by the owner, last on 2026-10-04, so every design decision can be logged).
- docs/memory.md — durable facts (dataset, models, thresholds, prompt versions, eval numbers) and hard-won gotchas; replace entries, never stack. NOT the why of decisions, NOT file locations. **≤ 8 KB.**
- docs/map.md — where things live: one line per file — what it does — key functions. A snapshot, not a log. **≤ 8 KB.**
- docs/techdebt.md — deliberate shortcuts and deferred work: item — why skipped — how to fix — effort. Delete a row when it is fixed. **≤ 4 KB.**
- docs/walkthrough.md — the 10-minute interview demo script; local only, so in a clone it does not exist. **≤ 6 KB.**
- backend/app/prompts/ — versioned LLM prompts loaded by the code. Never edit a released version; add a new file. **≤ 5 files, ≤ 10 KB each** (raised from 4 by the owner on 2026-10-04).
- backend/eval/ — results.md, written by run_eval.py; regenerate, never hand-edit. **≤ 1 file, ≤ 16 KB each.**
- docs/plans/ — plans written before building. Delete a plan once it has shipped. **≤ 2 files, ≤ 8 KB each.**
- docs/scratch/ — throwaway notes. Delete before ending a session; never commit anything here. **≤ 0 files.**
Review output (an audit, a benchmark) is not a doc: put the score line in docs/session.md and the fixes in the code. The eval report is the one exception the brief requires.

## Curation — do this whenever you touch a doc
Every rule here removes or replaces something. Stale docs are worse than missing ones, because they are believed.
1. **Supersede, don't stack.** Before adding to docs/memory.md, search it for an entry on the same subject and REPLACE it. Delete any entry the code now contradicts. (docs/decisions.md is the exception: append-only, by the brief.)
2. **Delete resolved debt.** When a docs/techdebt.md row is fixed, delete it; if worth remembering, one line goes to the docs/session.md log.
3. **Fix comments that describe removed behaviour.** A comment describing a reverted design is the highest-risk rot in a repo. Treat it as a bug.
4. **One fact, one file.** Where a file lives goes in docs/map.md only.
5. **Never trust a doc over the code.** If they disagree, the code wins; fix the doc in the same session.
6. **Fold the session log.** New entries are short; at the cap the oldest detailed entries become one-liners. Never delete a dated line.
7. **Delete history; git is the archive.** Shipped plans and finished audits go; note the deletion in the session log.

## Automation — the docs police themselves
`node scripts/docs-check.mjs` reads the Docs map above and fails when a `.md` is unlisted, over its cap, over the total, or names a repo path that no longer exists. It runs without anyone asking:
- **at session start** (Claude Code hook) — problems arrive as context; curate them first
- **after every Write/Edit of a `.md`** (hook) — over-cap feedback is immediate
- **when the agent tries to stop** (hook) — the first stop is refused until the docs pass
- **before every `git commit`** (.githooks/pre-commit; enable per clone with `git config core.hooksPath .githooks`)
When it fires: fold, tighten or delete. Do not raise a cap, edit the checker, or park a `.md` outside the map to get past it — those need the owner. A doc that fails the check is a bug in the doc, not in the check.
Name files that do not exist yet relative to `backend/` (e.g. `app/ingest.py`): the checker flags any `backend/…/file.ext` path that is missing.

## Do not edit
- data/emails_candidate.json — the provided dataset; never modify it.
- frontend/package-lock.json — regenerated by `npm install`.
- results.md in backend/eval — regenerated by run_eval.py.
- The SQLite DB (config.DB_PATH) — rebuilt by the pipeline; gitignored.
