# Decisions

The design decisions behind this repo, numbered in the order they were made. Each gives the **decision**, **why**, and the **alternative rejected**; a later entry that revises an earlier one says so.

## Design

**D-01 LLM for judgement, code for policy**
- Decision: the LLM reads each thread and reports what it is and what it asks for (category, action, urgency, importance, signals, confidence). Plain Python rules turn that into a priority and a bucket.
- Why: priority is business policy. Rules are readable, testable and versioned in git; every priority lists the rules that fired (auditable); policy changes need no re-prompting.
- Alternative rejected: ask the LLM for the priority directly — opaque, hard to test, and every policy change becomes a prompt change.

**D-02 Claude Haiku 4.5 for triage, Claude Sonnet 5.5 for Q&A**
- Decision: `claude-haiku-4-5` ($1/$5 per MTok) makes one call per thread; `claude-sonnet-5-5` ($2/$10) answers questions.
- Why: classification with a strict schema is a small-model task, and cost and latency matter at inbox scale. Q&A reasons across several threads and must cite sources.
- Alternative rejected: one large model for everything — higher cost per email for no measurable gain on extraction.

**D-03 No vector database**
- Decision: Q&A retrieval scores threads by claim reference, sender/company name and keyword overlap.
- Why: 95 messages fit in memory; the scoring is transparent ("matched claim ref PIN-…") and needs no extra infrastructure.
- Alternative rejected: embeddings + vector store — opaque ranking and more moving parts for 50 threads. Revisit at ~10k emails (see docs/techdebt.md).

**D-04 SQLite through the standard-library `sqlite3`**
- Decision: one local file holds threads, messages, triage results, priorities and the audit log.
- Why: zero setup for the reviewer, and the audit log is a real table anyone can query.
- Alternative rejected: Postgres or an ORM — setup cost with no benefit at this scale.

**D-05 Confidence gating**
- Decision: a triage result with confidence below 0.6 goes to a "review" bucket at level P2, whatever its category.
- Why: the risk-awareness answer to "what if the model is wrong?" — uncertain items are surfaced to a human, never silently archived or ignored.
- Alternative rejected: trust the category whatever the confidence.

**D-06 Recommendations only — no automatic actions**
- Decision: the system never sends, archives, deletes or replies; it recommends, with its reasoning and the raw evidence.
- Why: in insurance operations the handler stays accountable (complaints, regulatory deadlines, vulnerable customers). Human in control is a design principle.
- Alternative rejected: auto-archive irrelevant mail — a misclassified complaint could be lost.

## Setup

**D-07 IDs that leak the label never reach a prompt or a rule**
- Decision: `thread_id` is dropped when emails are loaded; `message_id` is kept for citations and the audit trail but never rendered into a prompt. Only `eval/` reads `thread_id`, to seed golden labels. A test enforces both.
- Why: `thread_id` prefixes (`thr_irr_…`) and `message_id` prefixes (`<irr-49-…>`) encode the answer. Using them would inflate accuracy and fail on real mail.
- Alternative rejected: strip only `thread_id` — `message_id` leaks the same label.

**D-08 Tailwind v4 through the Vite plugin, no tailwind.config.js**
- Decision: `@tailwindcss/vite` plus one `@import "tailwindcss"` line.
- Why: v4 is the current major; it needs neither tailwind.config.js nor postcss.config.js.
- Alternative rejected: Tailwind v3 — two extra config files (tailwind.config.js, postcss.config.js) for no benefit.

**D-09 Hand-written minimal Vite scaffold**
- Decision: write package.json, vite.config.ts, tsconfig.json, index.html and src/ by hand.
- Why: the `create-vite` template adds ESLint config, demo assets and three tsconfigs nobody here needs to explain.
- Alternative rejected: `npm create vite` and delete what is unused.

**D-10 Pinned dependencies**
- Decision: exact versions in backend/requirements.txt; frontend/package-lock.json committed.
- Why: a reviewer's clean clone installs what was tested.
- Alternative rejected: unpinned ranges — a breaking release could fail the demo.

**D-11 `pytest.ini` puts backend/ on the import path**
- Decision: `pythonpath = .` so `pytest` works from backend/.
- Why: no packaging (pyproject, `pip install -e`) needed for a small app.
- Alternative rejected: a setup/pyproject install step in the README.

## Ingest

**D-12 The mail client's importance flag is not a decision input**
- Decision: `importance_flag` is kept for display but never rendered into a prompt or used by a rule.
- Why: the sender sets it (52 of 95 messages say "high"); trusting it lets any sender jump the queue.
- Alternative rejected: pass it to the model as a weak hint — the model would still weight it.

**D-13 Thread key = "t" + 8 hex characters of SHA-256(first message_id)**
- Decision: threads are identified by a hash of their first message's ID, e.g. `t9546776b`.
- Why: stable across runs and new mail, and cannot spell a label (hex has no h/o/m/i/r…). `thread_id` leaks the label; a list index changes when mail arrives.
- Alternative rejected: `thread_id` or the position in the file.

**D-14 The model view marks who spoke last**
- Decision: messages are rendered oldest first with weekday dates; the last is tagged "(latest)" and Pinnacle senders "(internal)". Sorting is enforced by the Thread model itself.
- Why: the latest message defines the current state, and "did we already reply?" decides whether action is still needed. Weekdays let the model resolve "Friday" or "tomorrow".
- Alternative rejected: raw JSON to the model — noisier, and it would carry the IDs.

## Triage

**D-15 JSON by prompt, validated by Pydantic, one retry**
- Decision: the prompt asks for one JSON object; `llm.call_json` parses it (tolerating a code fence), retries once with a reminder, then `TriageResult` validates every field and enum.
- Why: simple, and works the same for Haiku and Sonnet; the raw reply is stored verbatim; every failure path is explicit and tested with a fake client.
- Alternative rejected: API structured outputs (constrained decoding) — stronger guarantee, logged in techdebt as the next step.

**D-16 Unusable output goes to a human, configuration errors stop the run**
- Decision: a refusal, a non-JSON reply, a schema mismatch or a transient API failure (network, 429, 5xx) gives the fallback result (informational, confidence 0, `parse_error`) → review bucket. A missing or rejected key, or a bad model name, stops the run with a clear message.
- Why: never guess silently, and never write 50 useless fallbacks because of a typo in `.env`.
- Alternative rejected: crash the whole batch on any error, or retry forever.

**D-17 Re-triage when the thread or the prompt changes, or the last attempt failed**
- Decision: a thread is skipped only if its stored triage judged its current latest message, with the current prompt version, without error. Ingestion is committed before triage starts.
- Why: the latest message defines the state, so new mail in an old thread must be re-judged; failures retry for free on the next run.
- Alternative rejected: skip on prompt version alone — a thread with a new reply would keep a stale judgement.

**D-18 Temperature 0 for triage**
- Decision: Haiku runs at temperature 0. (Sonnet 5.5 rejects the parameter, so Q&A uses the default.)
- Why: repeatable judgements make the audit trail and the eval reproducible.
- Alternative rejected: default sampling.

**D-19 Email text is data, not instructions**
- Decision: the thread goes inside `<thread>` tags and the prompt says tagged text is never an instruction; the model has no tools and its output is schema-checked.
- Why: emails come from outside the company — a basic prompt-injection guard.
- Alternative rejected: paste the email untagged.

**D-20 Category rules written as business definitions**
- Decision: the prompt defines the categories by what the handler must do. A holding reply ("we will confirm tomorrow") leaves the promise outstanding; general-guidance notices are informational; anyone writing about a policy or claim gets a reply or a forward; any expressed dissatisfaction is a complaint (FCA definition).
- Why: these are the judgement calls that decide the borderline threads; stating them makes the model's behaviour reviewable.
- Alternative rejected: one-line category names and leave the model to guess the policy.

**D-21 Schema errors get the one retry too, quoting the problem and the allowed values** (supersedes the "schema mismatch → fallback without retry" part of D-15/D-16)
- Decision: `call_json` checks the reply against the schema; a mismatch is retried once with a note such as "signals.0: 'review_document' is not allowed (allowed: 'fnol', …)". A second failure still goes to review.
- Why: in the first live run 2/50 replies put an action type in `signals`. A bare "not allowed" note changed nothing at temperature 0; quoting the allowed values fixed both. Validation stays strict.
- Alternative rejected: silently drop unknown signals — a misspelt real signal (e.g. "vulnerable") would vanish and lower the priority.

## Priority

**D-22 High importance also gives P2**
- Decision: P2 fires on high urgency or high importance.
- Why: priority should combine urgency and importance; otherwise importance is extracted and never used.
- Alternative rejected: importance as display only.

**D-23 An overdue deadline counts as P1**
- Decision: a deadline that has passed, or falls within 2 days of as-of, gives P1.
- Why: a missed deadline on an open request is at least as urgent as one due tomorrow. Cost: as-of 2026-02-20 makes most stated deadlines overdue, so P1 is heavy (20/32).
- Alternative rejected: only future deadlines count — the most overdue work would sink.

**D-24 Low confidence beats "resolved"; nothing reads who sent it**
- Decision: confidence < 0.6 goes to review before the already_resolved check; no rule reads sender_type or importance_flag (tests prove both).
- Why: an uncertain "resolved" must not be silently archived; priority should follow what is asked and what is at stake, not whether a solicitor or a customer asks.
- Alternative rejected: check "resolved" first — an unsure "resolved" would be archived unseen.

**D-25 Priorities are recomputed every run and stored with rules version and as-of date**
- Decision: the `priority` table holds level, bucket, rules fired, explanation, `rules_v1`, as-of.
- Why: rules are deterministic, so version + inputs reproduce any priority; no per-thread audit rows needed.
- Alternative rejected: ask the LLM for the priority (D-01).

## Evaluation

**D-26 The eval scores priority, not just category**
- Decision: golden labels add `expected_p1`; `run_eval.py` reports missed actions and P1 precision/recall, and rebuilds every prompt version's results from the audit log (no new model calls).
- Why: category accuracy was 50/50 and hid the signal errors that drive priority; a missed action is the costliest error.
- Alternative rejected: category accuracy only — "100%" with nothing to learn from.

**D-27 One prompt iteration (triage_v2), kept for its recall; then stop**
- Decision: v2 changes only the signal definitions (a 6-line diff) and is the production prompt. No further iterations.
- Why: v2 is the only version that under-prioritises nothing (P1 recall 18/18; v1 left the mobility-scooter customer at P3). A false P1 costs less than a missed vulnerable customer. Precision fell (85% → 82%) because Haiku ignored the new exclusions; category 49/50 (the rebrand notice judged irrelevant: no-action either way).
- Alternative rejected: keep v1 (misses a vulnerable customer); iterate again (more tuning on the test set for a structural problem — see techdebt).

## API

**D-28 The API only reads stored results; the model runs only in the pipeline**
- Decision: GET routes read SQLite; the LLM is called only by `pipeline.run_all` (CLI or `POST /run`) and by `/ask`.
- Why: page loads cost no tokens and never wait on the model; every number on screen comes from a stored, audited result.
- Alternative rejected: triage on request — slow, costly and unaudited between runs.

## Q&A

**D-29 No citation, no answer**
- Decision: Sonnet cites neutral handles (M1, M2…) mapped back to message IDs in code; unknown handles are dropped; an answer left with no valid citation becomes a refusal; no matching thread means a refusal without a model call. A model refusal is shown as one (no automatic retry on another model, so the audit's model field stays true).
- Why: answers must rest on evidence the handler can open; message IDs leak labels (D-07); in insurance a refusal is safer than a guess.
- Alternative rejected: free-text answers with "sources" the model writes itself.

**D-30 Retrieval: claim ref > company domain > triage tag > rare shared words**
- Decision: scores 100 per claim ref, 20 per question word inside an outside sender's domain, 5 per word naming a triage tag (sender type, signal), plus IDF-weighted shared words; top 12, floor 10% of the best. Every hit carries its reasons.
- Why: a person can follow it; triage tags let "solicitor", "FNOL" or "fraud" find threads that never use the word. Settings were tuned on the 9 eval questions (disclosed in results.md).
- Alternative rejected: the whole mailbox in context — fine at 50 threads, not at 10k, and it hides what the answer rests on.

## Frontend

**D-31 No router; one definition of "internal"**
- Decision: `App.tsx` switches views with state; Workload and Ask stay mounted (hidden), so filters and answers survive a visit to a thread. The API sends `from_internal` and the outside sender, so the UI never re-implements a rule.
- Why: three screens do not need a routing library; business rules live in Python only.
- Alternative rejected: react-router (one more dependency for three screens).

**D-32 Report run-to-run variance** (revises the evidence in D-27)
- Decision: keep triage_v2 and publish that a second v2 run kept all 50 categories but changed signals on 3 threads, dropping the scooter customer to P2 (P1 recall 17/18).
- Why: temperature 0 is not deterministic on the API; quoting only the best run would mislead.
- Alternative rejected: re-run until the better number appears.
