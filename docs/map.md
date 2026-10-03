# Map — where things live

Where things live: one line per file — what it does — key functions. Why things are this way: docs/decisions.md.

## Root
- README.md — reviewer-facing: what it does, architecture, setup, decisions, evaluation, risk controls, assumptions, limitations, cost, glossary.
- .env.example — the one secret the app needs (ANTHROPIC_API_KEY); copy to `.env`.
- .gitignore — keeps `.env`, the SQLite DB, dependencies and build output out of git.

## Docs
- docs/decisions.md — every design decision: what, why, and the alternative rejected.
- docs/map.md — this file.
- docs/techdebt.md — known shortcuts and how to fix them.

## Data
- data/emails_candidate.json — the provided mailbox: `{"emails": [{"messages": [...]}]}`, 50 threads / 95 messages. Never edited.

## Backend (commands run from backend/)
- backend/requirements.txt — pinned Python dependencies.
- backend/pytest.ini — makes `app` importable for pytest; tests live in backend/tests.
- backend/app/__init__.py — package marker.
- backend/app/config.py — every setting: paths, models and request options, prices, prompt versions, priority thresholds and rules version, as-of date, internal domain.
- backend/app/models.py — Pydantic models — `Attachment`, `Message` (no thread_id; computed `from_internal`), `Thread` (sorted oldest first; `key`, `current`, `subject`, `claim_refs`, `participants`), `TriageResult`, `TriageRecord`, `PriorityResult`; API shapes `ThreadRow`, `ThreadDetail`, `AuditEntry`, `Summary`, `QAAnswer`, `Citation`, `RetrievedThread`.
- backend/app/ingest.py — JSON → threads, and the only text the LLM sees — `load_threads()`, `thread_for_model()`, `main()` (`python -m app.ingest`).
- backend/app/llm.py — the one seam to the Anthropic SDK — `call_json()` (parse, schema check, one retry quoting the problem, refusal), `check_reply()`, `parse_json_object()`, `describe_errors()`, `get_client()`, `cost_usd()`.
- backend/app/triage.py — one thread → `TriageRecord` via Haiku — `triage_thread()`, `build_user_message()`, `load_prompt()`, `fallback()`.
- backend/app/prompts/triage_v1.md — the first triage system prompt: categories, fields, signals, output contract.
- backend/app/prompts/triage_v2.md — current triage prompt: v1 with tighter signal definitions (6-line diff, D-27).
- backend/app/priority.py — the policy: named rules → bucket, level, rules fired, explanation — `compute_priority()`, `p1_*`/`p2_*` rules, `working_days_between()`.
- backend/app/qa.py — free-text questions — `retrieve()` (claim ref > company domain > triage tag > IDF words, with reasons), `answer()` (Sonnet over the hits, handle citations, refusal rules, audit row), `render_context()`, `tokens()`.
- backend/app/prompts/qa_v1.md — the Q&A system prompt: evidence only, cite handles, refuse plainly, JSON contract.
- backend/app/store.py — SQLite schema (`threads`, `messages`, `triage`, `priority`, `audit_log`; `ask` events log every question) — saves: `save_threads()`, `save_triage()`, `save_priority()`, `log_event()`; loads: `triage_state()`, `load_triage_results()`, `load_thread_rows()`, `load_messages()`, `load_triage_record()`, `load_audit()`, `run_facts()`, `load_all_threads()`.
- backend/app/pipeline.py — ingest → triage → priority → store, idempotent — `run_all()`, `needs_triage()`, `prioritise_all()`, `main()` (`python -m app.pipeline [--force]`).
- backend/app/main.py — FastAPI routes: `GET /health`, `GET /summary`, `GET /threads?bucket&level&lob&sort`, `GET /threads/{key}`, `POST /ask`, `POST /run?force` — `to_thread_row()`; CORS for :5173.
- backend/eval/golden_labels.json — hand-checked labels per thread key: category, `expected_p1`, note for judgement calls.
- backend/eval/qa_questions.json — 9 Q&A eval questions: gist, expected claim refs, words to mention, one expected refusal.
- backend/eval/run_eval.py — `python -m eval.run_eval [--qa]`: per prompt version, category accuracy, confusion matrix, missed actions, P1 precision/recall; Q&A checks (refusal, refs, words); writes results.md — `seed_labels()` (only eval code reading thread_id), `results_by_version()`, `score()`, `ask_all()`, `latest_answers()`, `qa_section()`, `render()`.
- backend/eval/results.md — the generated evaluation report (triage per prompt version, Q&A checks and answers); regenerate, never edit.
- backend/tests/conftest.py — `FakeClient` (replays model replies, records requests) and the `fake_llm` fixture; no test calls the API.
- backend/tests/test_ingest.py — ordering, current message, claim refs, nulls, keys, and the leak tests (no thread_id, message_id or importance flag in the model view).
- backend/tests/test_triage_schema.py — valid, fenced, malformed and schema-error replies (retry, then review), refusal and API errors; no label leaks in any of the 50 prompts.
- backend/tests/test_pipeline.py — skip/re-triage rules (unchanged, new message, failure, prompt version, force) and audit rows.
- backend/tests/test_api.py — every route over a temporary database filled by the real pipeline (model faked): counts, sort, filters, 422/404, detail, `/run`, `/ask`.
- backend/tests/test_qa.py — retrieval on the real mailbox (claim ref, domain, triage tag, no match, tokens); answers with a mocked model (handle mapping, no IDs sent, citation-less → refusal, model refusal, no call without hits, audit row).
- backend/tests/test_priority.py — every rule alone, deadline and age boundaries, overrides and their order, sender-type and importance-flag invariance.

## Frontend (commands run from frontend/)
- frontend/package.json — npm scripts (`dev`, `build`) and dependencies; the lockfile pins them.
- frontend/vite.config.ts — Vite with the React and Tailwind plugins.
- frontend/tsconfig.json — strict TypeScript; `npm run build` type-checks first.
- frontend/index.html — page shell; loads the React entry point.
- frontend/src/main.tsx — React entry point; mounts `App`.
- frontend/src/App.tsx — app shell and "router": a state switch between Workload, Ask and a thread; Workload and Ask stay mounted so filters and the last answer survive.
- frontend/src/api.ts — typed fetch helpers, one per endpoint (`getSummary`, `getThreads`, `getThread`, `ask`, `runPipeline`); base URL `VITE_API_URL` or :8000.
- frontend/src/types.ts — TypeScript mirrors of the backend's models and API shapes.
- frontend/src/format.ts — display helpers: UK dates in UTC, `humanise()` for codes.
- frontend/src/pages/Dashboard.tsx — the workload view: version line, summary cards, filter chips, run-pipeline control, sorted table.
- frontend/src/pages/ThreadView.tsx — one thread: messages (latest and cited highlighted), recommendation with rules fired, triage fields, collapsible audit record.
- frontend/src/pages/Ask.tsx — free-text Q&A: example questions, answer or clear refusal, citation chips, "why these threads".
- frontend/src/components/ — `PriorityBadge`, `SummaryCards` (click to filter), `ThreadRow` (with the "why" popover), `CitationChip`.
- frontend/src/index.css — Tailwind import.
