# Map — where things live

One line per file — what it does — key functions. The why: docs/decisions.md.

## Root
- README.md — for the reviewer: setup, how it works, decisions and alternatives, evaluation, risks, cost, how it was built.
- .env.example — the one secret (ANTHROPIC_API_KEY); copy to `.env`. .gitignore — keeps `.env`, the DB, dependencies and builds out of git.
- AGENT_BRIEF.md — the brief: task, design, eight-phase plan. AGENTS.md — the agent's rules, commands and docs map. CLAUDE.md — Claude Code's entry point.
- docs/session.md — build log. docs/decisions.md — every decision, why, the alternative rejected. docs/memory.md — facts and gotchas. docs/techdebt.md — known shortcuts. docs/map.md — this file.
- scripts/docs-check.mjs — enforces the docs map; run by the hooks in .claude/settings.json and .githooks/pre-commit.
- data/emails_candidate.json — the provided mailbox: `{"emails": [{"messages": [...]}]}`, 50 threads / 95 messages. Never edited.

## Backend (commands run from backend/)
- backend/requirements.txt — pinned Python dependencies. backend/pytest.ini — puts `app` on the path; tests in backend/tests.
- backend/app/config.py — every setting: paths, models and options, prices, prompt and rules versions, thresholds, as-of date, internal domain, CORS.
- backend/app/models.py — domain models: `Message` (no thread_id; computed `from_internal`), `Thread` (oldest first; `key`, `current`, `claim_refs`), `TriageResult`, `TriageRecord`, `PriorityResult`, `Reason`.
- backend/app/schemas.py — what the API returns: `ThreadRow` (with `card` and `reasons`), `ThreadDetail`, `AuditEntry`, `Summary` (with `Policy`), `QAAnswer`, `Citation` (sender, date), `RetrievedThread`.
- backend/app/ingest.py — JSON → threads, and the only text the LLM sees — `load_threads()`, `thread_for_model()`; `python -m app.ingest` prints the counts.
- backend/app/llm.py — the one seam to the Anthropic SDK — `call_json()` (parse, schema check, cut-off, one retry, refusal), `get_client()`, `cost_usd()`.
- backend/app/triage.py — one thread → `TriageRecord` via Haiku — `triage_thread()`, `build_user_message()`, `fallback()`.
- backend/app/prompts/ — `triage_v1.md`, `triage_v2.md` (current: tighter signal definitions, weekday deadlines), `qa_v1.md` (evidence only, cite handles, refuse), `qa_v2.md` (adds the open workload), `qa_v3.md` (current: a focus question gets the top three and the P1 count).
- backend/app/priority.py — the policy: named rules → bucket, level, rules fired, explanation — `compute_priority()`, `p1_*`/`p2_*` rules, `reasons()` (which rules set the level), `waiting_days()`, `working_days_between()`; the order of work: `workload_rank()`, `open_work()`, `workload_header()`, `verdict_line()` (for Q&A).
- backend/app/qa.py — free-text questions — `retrieve()` (claim ref > domain words > triage tag > IDF words, with reasons), `render_context()` (the open workload + matched emails, neutral handles), `answer()` (Sonnet, handle citations, refusals; every question audited, failures too).
- backend/app/store.py — SQLite schema (`threads`, `messages`, `triage`, `priority`, `audit_log`) and every save/load (`load_priorities()`, `priority_result()`…); `connect()` upgrades an older file.
- backend/app/pipeline.py — ingest → triage → priority → store, idempotent — `run_all()`, `needs_triage()`, `main()` (`python -m app.pipeline [--force]`).
- backend/app/main.py — FastAPI routes: `/health`, `/summary` (counts, versions, `policy`), `/threads`, `/threads/{key}`, `POST /ask`, `POST /run` (409 while running) — `to_thread_row()`, `_card()`, `_policy()`.
- backend/eval/ — `golden_labels.json` (hand-checked labels, `expected_p1`), `qa_questions.json` (12 questions), `run_eval.py` (`python -m eval.run_eval [--qa]`: accuracy, missed actions, P1 precision/recall, Q&A checks), `results.md` (generated).
- backend/tests/conftest.py — `FakeClient` and the `fake_llm` fixture; no test calls the API.
- backend/tests/ — `test_ingest.py` (ordering, leak tests), `test_triage_schema.py` (replies, retries, refusals), `test_pipeline.py` (skip/re-triage, upgrades), `test_api.py` (every route, card and reasons invariants), `test_qa.py` (retrieval, citations, the workload, audit), `test_priority.py` (every rule, boundaries, overrides, fairness, the order of work).

## Frontend (commands run from frontend/)
- frontend/package.json, vite.config.ts, tsconfig.json, index.html — dependencies (React, Vite, TypeScript, Tailwind), strict type-check, page shell (theme set before the first paint; Dark Reader lock).
- frontend/src/main.tsx — mounts `App`. frontend/src/index.css — the design tokens (`@theme`: type scale, page width, colours with contrast notes, easings, animations), their dark values, the focus style. frontend/src/theme.ts — `useTheme()`: flips `<html data-theme>`, saves the choice.
- frontend/src/App.tsx — the shell and state-switch "router": Workload, Ask, a thread (with its list for Previous / Next); `useSummary()`, `useReturnFocus()`.
- frontend/src/api.ts — one typed fetch per endpoint; `ApiError` (`network` or `http`). frontend/src/types.ts — mirrors of the API shapes and their code unions.
- frontend/src/labels.ts — every code in words: `CARD`, `SIGNALS`, `SENDER`, `ACTION`, `LINE`, `RATING`; `ruleText()`, `decidingText()`.
- frontend/src/help.ts — definitions for About this data and the one (i), quoting thresholds from `/summary` — `CARD_HELP`, `HELP`.
- frontend/src/workload.ts — section order and grouping — `SECTION_ORDER`, `NO_ACTION`, `groupByCard()`, `matches()`. frontend/src/format.ts — UK dates in UTC, `percent()`, `workingDays()`, `tidyDetail()`.
- frontend/src/pages/Dashboard.tsx — the workload: count cards, then a toolbar (result line, line filter, About this data), then the sections; empty and error states.
- frontend/src/pages/ThreadView.tsx — one thread in decision order; `useThread()` (stale guard, dim while loading), `useArrivalFocus()`.
- frontend/src/pages/Ask.tsx — questions: label, one-line scope, examples, honest wait, the answer beside its sources (or a refusal), live status; `useQuestion()`.
- components/AppHeader.tsx — the coloured header band: title, "suggestions only" promise, as-of date, tabs (aria-current), "Dark mode" toggle, skip link.
- components/SummaryCards.tsx — the count cards: two groups of toggle buttons (label, count, one-line hint), the only priority filter.
- components/LineFilter.tsx — the Line of business dropdown.
- components/WorkloadList.tsx — column labels and the non-empty sections (a chosen card shows its own).
- components/WorkloadSection.tsx — one section: header, folding, empty sentence.
- components/ThreadRow.tsx — one row: one stretched button (its name adds the line of business), the line under the chip, Why line, claim, sender, waiting; `ROW_GRID`.
- components/PriorityBadge.tsx — words + icon per state; shared `CARD_ICON`, `MARK`, `EDGE`, `TINT`.
- components/Explain.tsx — the (i): native popover; `place()`, mouse hover with click-to-pin.
- components/AboutData.tsx — what each group means (said once), versions, last run; `Definitions`, `RunControls`, `ConfirmRereadAll`.
- components/ErrorPanel.tsx — plain cause, Try again, technical detail.
- components/Skeleton.tsx — delayed placeholders.
- components/Icon.tsx — inline SVG icons (Lucide, ISC notice).
- components/ThreadNav.tsx — Back, "Thread n of N", Previous / Next.
- components/DecisionBand.tsx — suggested next step, who is waiting, deadline.
- components/WhyPanel.tsx — rules that decided vs also true.
- components/MessageCard.tsx — one email: Latest / Pinnacle staff / Cited tags, folding.
- components/AiReading.tsx — the AI's reading, confidence vs threshold.
- components/AuditPanel.tsx — rule codes, raw AI output, history.
- components/AskIntro.tsx — example questions that fill the box (never send).
- components/AnswerCard.tsx — the AI answer or "No answer given"; `HowFound` (the search behind it, folded).
- components/SourceList.tsx — cited emails with sender and date.
