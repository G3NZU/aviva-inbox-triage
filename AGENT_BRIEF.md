# AGENT BRIEF — Aviva Inbox Triage (Round 2 take-home task)

> **Read this whole file before writing any code.** It is the single source of truth for this project.
> Owner: Victor Gamargo Franco. Hard deadline: **submission by Sunday 5 Oct 2026, 12:00 UK**. Interview: Monday 6 Oct 13:00 UK.
> The owner must be able to read the finished repo and explain every file, every decision and every limitation in a 45-minute interview. **Optimise for explainability, not cleverness.**

---

## 0. Agent rules (non-negotiable)

1. **Follow the Aviva brief literally** (section 1). Before each phase, re-read the brief and check the work maps to a requirement. If a feature is not asked for and not needed to make an asked-for feature work, do not build it.
2. **Do not over-engineer.** No microservices, no message queues, no vector database, no auth, no Docker, no ORM beyond `sqlite3`, no state-management libraries in React. SQLite + FastAPI + Vite/React is the whole stack. If you are unsure whether something is over-engineering, it is — leave it out and note it in `docs/techdebt.md` as a possible future improvement.
3. **Work step by step.** Complete and verify one phase (section 5) before starting the next. Never start a phase while a previous phase has failing tests or unverified behaviour. Do not rush; a smaller working system beats a larger broken one.
4. **Every function gets a docstring** stating *what* it does, *why* it exists, inputs and outputs. Keep functions under ~40 lines. Type hints everywhere in Python; strict TypeScript in the frontend.
5. **Organise code by responsibility** exactly as the structure in section 4. One module = one job. No "utils.py" dumping grounds.
6. **Document only what is needed to read and explain** — short, factual, no padding. Prefer a table or a bullet list over paragraphs. The owner will read every doc file; respect their time.
7. **Use the owner's project-tracking skill** (the one that maintains `.md` tracking files: `map.md`, `memory.md`, `session.md`, `techdebt.md`, etc.). Invoke it at the start of the session and keep those files current after every phase. If the skill is not available, maintain the same files manually under `docs/` using the templates in section 7.
8. **Log every meaningful decision** in `docs/decisions.md` as *Decision / Why / Alternative rejected*. This file is the owner's interview script.
9. **Never use `thread_id` as a model input or a rule input.** The thread IDs leak the category (`thr_hom`, `thr_info`, `thr_irr`…). They may be used **only** in `eval/` to seed golden labels. Enforce this: the triage code must strip `thread_id` before building the prompt, and a test must assert it.
10. **No automatic actions.** The system recommends; it never sends, archives, deletes or replies. This is a deliberate design principle for an insurance operations environment — state it in the README.
11. **Versioned prompts.** Prompts live in `backend/app/prompts/*.md` with a version suffix. Every stored LLM result records prompt version, model name and timestamp.
12. **Verify from a clean clone** before declaring done: `git clone` → follow README only → everything runs. If a step in the README is missing, the work is not finished.
13. **Report back honestly.** If something does not work, the eval score is low, or a requirement is only partially met, say so in `docs/session.md` and in the README's Limitations section. Do not hide gaps.
14. **Ask before deviating** from this brief. If a choice is genuinely open, pick the simplest option, log it in `decisions.md`, and continue.

---

## 1. The Aviva brief (verbatim essentials)

**Problem.** Operational handlers receive high volumes of emails from customers, internal teams, brokers and automated systems. They manually scan inboxes to decide what needs action, what can be ignored, and what to do first. This is time-consuming and error-prone.

**Goal.** Design a solution that *continuously ingests emails, identifies the email type based on the actions required by a handler, prioritises the workload, provides a clear summary view of required actions, and, where appropriate, allows the handler to interact with the mailbox using free-text questions.*

**Must address:**
1. Differentiate email types: **action required** / **informational (can be archived)** / **irrelevant** to the handler's workload.
2. For actionable emails: extract the **specific topic/task** stated or implied; evaluate **urgency and importance** → assign a **priority level**.
3. **Summarise the handler's workload in a single view.**
4. **Free-text questions** over the mailbox, e.g. *"Was there any action required for Broker X?"*

**Assessed competencies:** solution design · usage of LLM for decision support · business logic for prioritisation · natural-language Q&A · user experience · code quality and modularity · **auditability and risk awareness**.

**Deliverables:** runnable, organised code; clear setup documentation (**required API keys, package dependencies, how to run**); submitted ≥ 24 h before the interview. A **presentation** on the day (approach, architecture, assumptions, limitations, evaluation) — the owner builds the slides separately; the agent's job is to make the docs good enough to build slides from.

---

## 2. The data (`data/emails_candidate.json`)

Profiled on 3 Oct 2026:

| Fact | Value |
|---|---|
| Top-level shape | `{"emails": [ {"messages": [ ...messages... ]}, ... ]}` — a list of **threads**, each a list of messages |
| Threads / messages | 50 threads / 95 messages; 26 single-message threads, longest thread 6 messages |
| Date range | 2026-02-01 → 2026-02-20 |
| Fictional insurer | "Pinnacle Insurance", main inbox `claims@pinnacle-insurance.co.uk`; handler covers **Home, Motor, Liability** |
| Claim reference pattern | `PIN-HOM-nnnnnn`, `PIN-MTR-nnnnnn`, `PIN-LIA-nnnnnn` (regex `PIN-[A-Z]{3}-\d{6}`) |
| Message fields | `body, subject, sent_from, sent_to[], sent_cc[], date_sent (ISO), attachments[] or null (filename/filesize/filetype only — no content), importance_flag ("high" or null), message_id, thread_id` |
| `importance_flag` | "high" on 52/95 messages — **not a trustworthy signal on its own**; treat as a weak hint only |
| Attachments | 35 messages have attachment metadata; there are no files to read |
| Sender types seen | brokers, customers (gmail/hotmail/etc.), repairers/bodyshops, loss adjusters, solicitors, physio clinics, internal teams (finance, compliance, IT, HR, canteen, antifraud, underwriting), automated (DPD, out-of-office), spam (SEO, deli offers, webinars) |
| **Label leak** | `thread_id` prefixes: `thr_hom`(14) `thr_mtr`(7) `thr_lia`(6) = claims threads (mostly actionable); `thr_info`(11) = informational; `thr_irr`(7) = irrelevant; `thr_gen`(5) = general/policy queries & FNOLs. **Use only for golden labels in eval. Never as a feature.** |

Examples of what is in there: a broker submitting an escape-of-water claim form and asking to confirm cover; a bodyshop chasing parts authority; a solicitor's notice of claim for a café slip-and-fall; FNOLs for storm damage, van theft, kitchen fire, flooded car; internal notices (payment runs moving to Tuesdays, Guidewire outage, fraud alert, FOS decisions summary, annual-leave rota); junk (canteen menu, SEO spam, DPD parcel, a job application, a webinar invite, a supplier rebrand notice).

**Thread semantics matter:** the **latest message defines the current state**. A request that has since been answered in the same thread may no longer need action. Earlier messages are context.

---

## 3. Solution design (what we are building)

```
emails_candidate.json
        │
        ▼
 ingest.py  ── normalise threads, sort by date, latest message = current state, strip thread_id for model use
        │
        ▼
 triage.py  ── ONE LLM call per thread (Claude Haiku) → strict JSON: category, action, urgency, importance, signals, confidence, reasoning
        │
        ▼
 priority.py ── PURE PYTHON RULES (no LLM) → P1–P4 or "review"/"archive"/"ignore", plus list of rules fired
        │
        ▼
 store.py   ── SQLite: threads, messages, triage results, audit log (raw LLM output, prompt version, model, timestamp)
        │
        ├──▶ main.py (FastAPI) ──▶ React dashboard: workload view · thread view · ask box
        │
        └──▶ qa.py ── retrieve candidate threads (keyword / claim ref / sender) → Claude Sonnet answers with message_id citations, refuses if nothing relevant
```

**Why this shape (put these in `decisions.md` on day one):**
- **LLM for judgement, code for policy.** The model is good at reading an email and saying what it is and what it asks for. Deciding how important that is to *this business* is policy — it belongs in readable, testable, versioned Python rules, not in a prompt. This gives auditability (every priority has a list of rules that fired) and lets a non-developer change the policy without re-prompting.
- **Haiku for triage, Sonnet for Q&A.** Classification/extraction with a strict schema is a small-model task; cost and latency matter at inbox scale. Q&A needs stronger reasoning over several threads and must cite sources.
- **No vector DB.** 95 messages fit in memory; keyword + claim-reference + sender retrieval is transparent and sufficient. Note in techdebt what changes at 10k+ emails (embeddings, pgvector).
- **SQLite.** Zero setup for the reviewer, and the audit log is a real table they can query.
- **Confidence gating.** Below a threshold the item goes to a "needs human review" bucket rather than being silently archived/ignored — this is the risk-awareness answer to "what if the model is wrong?"
- **Human in control.** No auto-actions. Handler sees recommendation + reasoning + raw evidence.

---

## 4. Repository structure (create exactly this)

```
aviva-inbox-triage/
├── README.md                     # setup, keys, dependencies, run, architecture, eval results, limitations, risks
├── .env.example                  # ANTHROPIC_API_KEY=
├── .gitignore                    # .env, *.db, node_modules, __pycache__, dist
├── data/
│   └── emails_candidate.json
├── docs/
│   ├── decisions.md              # Decision / Why / Alternative rejected  (append-only log)
│   ├── map.md                    # one line per file: what it does          (tracking skill)
│   ├── memory.md                 # durable facts about the project          (tracking skill)
│   ├── session.md                # what was done this session, what's next  (tracking skill)
│   ├── techdebt.md               # known shortcuts and how to fix them      (tracking skill)
│   └── walkthrough.md            # 10-minute demo script for the interview (written in Phase 7)
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py             # env loading, model names, thresholds, prompt versions (one place)
│   │   ├── models.py             # Pydantic: Message, Thread, TriageResult, PriorityResult, QAAnswer
│   │   ├── ingest.py             # JSON → List[Thread]; sorting; current-state message; model-safe view
│   │   ├── llm.py                # thin Anthropic client wrapper: call, parse JSON, retry once, log usage
│   │   ├── triage.py             # build prompt from thread, call Haiku, validate into TriageResult
│   │   ├── priority.py           # rules → PriorityResult(level, bucket, rules_fired)
│   │   ├── qa.py                 # retrieve() + answer(): Sonnet with citations and refusal
│   │   ├── store.py              # SQLite schema + save/load; audit_log table
│   │   ├── pipeline.py           # run_all(): ingest → triage → priority → store (idempotent, --force to rerun)
│   │   ├── main.py               # FastAPI routes (see section 6)
│   │   └── prompts/
│   │       ├── triage_v1.md
│   │       └── qa_v1.md
│   ├── eval/
│   │   ├── golden_labels.json    # thread key → expected category (seeded from thread_id prefix, hand-checked)
│   │   ├── qa_questions.json     # ~8 questions with expected answer gist and expected cited claim refs
│   │   └── run_eval.py           # prints accuracy, confusion matrix, misclassified list; writes eval/results.md
│   └── tests/
│       ├── test_ingest.py        # thread ordering, current-state message, thread_id stripped from model view
│       ├── test_priority.py      # each rule, boundary cases, bucket assignment
│       └── test_triage_schema.py # parsing good/bad JSON from the model (mocked — no API calls in tests)
└── frontend/
    ├── package.json  vite.config.ts  tailwind.config.js  tsconfig.json  index.html
    └── src/
        ├── main.tsx  App.tsx
        ├── api.ts                # typed fetch helpers, one per endpoint
        ├── types.ts              # mirrors backend Pydantic models
        ├── pages/
        │   ├── Dashboard.tsx     # workload summary: counts by priority, sortable list
        │   ├── ThreadView.tsx    # messages + triage + priority reasons + raw audit record
        │   └── Ask.tsx           # free-text Q&A with clickable citations
        └── components/
            ├── PriorityBadge.tsx  SummaryCards.tsx  ThreadRow.tsx  CitationChip.tsx
```

---

## 5. Build plan — phases, in order, each verified before the next

Each phase ends with: tests green (where applicable) → update `docs/map.md`, `docs/session.md`, `docs/decisions.md` → commit with a clear message.

### Phase 0 — Setup (≈30 min)
- Create repo structure above, `.gitignore`, `.env.example`, `requirements.txt` (`fastapi uvicorn anthropic pydantic python-dotenv pytest httpx`), Vite + React + TS + Tailwind scaffold.
- Invoke the project-tracking skill; create `docs/*.md` tracking files with initial content (section 7).
- Write `docs/decisions.md` entries for the design choices in section 3.
- **Verify:** `pytest` runs (0 tests ok), `uvicorn app.main:app` serves `/health`, `npm run dev` shows a blank page.

### Phase 1 — Ingest (≈45 min)
- `models.py`: `Message`, `Thread` (messages sorted ascending by `date_sent`; property `current` = latest message; `claim_refs` extracted by regex from all subjects/bodies; `participants`).
- `ingest.py`: `load_threads(path) -> list[Thread]`; `thread_for_model(thread) -> str` renders subject/from/to/date/body/attachment names for each message **without thread_id or message_id**.
- Tests: ordering, current message, regex, and **assert "thr_" not in thread_for_model(...)**.
- **Verify:** script prints 50 threads / 95 messages.

### Phase 2 — Triage with Haiku (≈1.5 h)
- `prompts/triage_v1.md`: system instructions for a claims-operations triage assistant. Define the three categories precisely (action_required = *the handler must do something*; informational = *worth knowing, no action, can be archived*; irrelevant = *not related to the handler's workload: spam, marketing, misdirected, personal*). Describe each output field. Instruct: judge by the **latest message**; if the latest message shows the request is resolved, set `already_resolved` signal and category informational; output **only JSON**.
- `models.py`: `TriageResult` schema:
  ```
  category: action_required | informational | irrelevant
  action_type: respond | approve_authorise | investigate | chase_third_party | open_new_claim | review_document | escalate | none
  action_summary: str  (one imperative sentence; "" when none)
  claim_ref: str | null
  line_of_business: home | motor | liability | unknown
  sender_type: customer | broker | repairer_supplier | solicitor | loss_adjuster | internal | automated | unknown
  urgency: high | medium | low        # how soon
  importance: high | medium | low     # how much it matters (money, customer harm, legal, regulatory)
  deadline_mentioned: ISO date | null
  signals: list of [fnol, injury, make_safe_urgent, complaint, legal_threat, regulatory, fraud_flag, vulnerable_customer, repeat_chase, payment_or_authority_pending, already_resolved]
  confidence: float 0–1
  reasoning: str (2–3 sentences)
  ```
- `llm.py`: single `call_json(model, system, user) -> dict` with one retry on invalid JSON; records tokens used.
- `triage.py`: `triage_thread(thread) -> TriageResult`; validation errors → mark `confidence=0.0`, `category="informational"`, signal `parse_error`, and log.
- `store.py`: tables `threads`, `messages`, `triage` (one row per thread incl. `raw_response`, `prompt_version`, `model`, `created_at`), `audit_log`.
- `pipeline.py`: `run_all()` — skip threads already triaged with the same prompt version unless `--force`.
- Tests with **mocked** LLM responses (valid JSON, malformed JSON, missing field).
- **Verify:** run on all 50 threads; eyeball 10 results against the emails; record cost/tokens in `session.md`.

### Phase 3 — Priority rules (≈1 h)
- `priority.py`: `compute_priority(triage: TriageResult, thread: Thread, now: date) -> PriorityResult(level: P1|P2|P3|P4|None, bucket: act|review|archive|ignore, rules_fired: list[str], explanation: str)`.
- Rules (implement as small named functions, each appends its name to `rules_fired`):
  - `bucket = ignore` if category irrelevant; `archive` if informational; `act` if action_required.
  - **Override:** `confidence < CONFIDENCE_THRESHOLD (0.6)` → `bucket = review`, level P2 (a human must look).
  - P1 if any of: `injury`, `make_safe_urgent`, `legal_threat`, `regulatory`, `fraud_flag`, `vulnerable_customer`, `complaint`, deadline within 2 days of `now`.
  - P2 if: urgency high, or `repeat_chase`, or `fnol`, or `payment_or_authority_pending`, or deadline within 7 days, or thread age > 5 working days with no internal reply.
  - P3: remaining action_required.
  - P4: informational.
  - `already_resolved` → bucket archive, level P4 regardless.
- `now` defaults to the latest `date_sent` in the dataset (2026-02-20) so "age" is meaningful; make this explicit in `config.py` and the README.
- Tests: every rule individually + the confidence override + resolved override.
- **Verify:** distribution across P1–P4 looks sensible (not everything P1). Record distribution in `session.md`.

### Phase 4 — Evaluation (≈45 min)
- `eval/golden_labels.json`: build from thread_id prefix (`hom/mtr/lia/gen` → start as action_required, `info` → informational, `irr` → irrelevant), then **hand-check all 50** by reading the latest message; correct any that are resolved/informational. Record how many seeds were changed in `eval/results.md`.
- `run_eval.py`: category accuracy, 3×3 confusion matrix, list of misclassified threads with model reasoning; write `eval/results.md`.
- `eval/qa_questions.json`: ~8 questions (see section 6) with expected gist + expected claim refs cited.
- **Verify:** accuracy number exists. If < 80%, inspect errors; one prompt iteration allowed (`triage_v2.md`), re-run, keep both numbers in `results.md`. Do not iterate more than twice — document remaining errors as limitations instead.

### Phase 5 — API (≈45 min)
- `main.py` routes:
  - `GET /health`
  - `GET /summary` → counts by bucket and level, totals, last run time, model/prompt versions
  - `GET /threads?bucket=&level=&lob=&sort=` → list rows (thread key, subject, sender, sender_type, claim_ref, level, bucket, action_summary, age_days, last_date)
  - `GET /threads/{key}` → full thread + triage + priority + audit record
  - `POST /ask {question}` → `QAAnswer{answer, citations:[{thread_key, message_id, subject}], confidence, refused: bool}`
  - `POST /run?force=` → re-run pipeline (for demo)
- CORS for the Vite dev origin.
- **Verify:** curl each endpoint; `/summary` numbers match SQLite.

### Phase 6 — Q&A (≈1 h)
- `qa.py`:
  - `retrieve(question, threads, k=6)`: score threads by claim-ref match (exact, highest), sender/domain/company name match, keyword overlap on subject+body (simple tokenised scoring). Return top-k with the matching reason. **Transparent and explainable — no embeddings.**
  - `answer(question)`: Sonnet with `prompts/qa_v1.md`: answer only from provided threads, cite `message_id`s, say "I can't find anything about X in the mailbox" when evidence is absent; JSON output `{answer, citations, confidence, refused}`.
- Run `eval/qa_questions.json` and record outcomes in `results.md`.
- **Verify:** the brief's example works: *"Was there any action required for Broker X?"* using a real broker name from the data (e.g. Bridgegate Brokers, Harper Broking).

### Phase 7 — Frontend (≈2 h)
- `Dashboard.tsx`: summary cards (P1/P2/P3/P4/review/archive/ignore counts), filter chips (bucket, level, line of business), table sorted P1→P4 then oldest first; each row shows priority badge, action summary, claim ref, sender type, age, and a "why" tooltip with `rules_fired`.
- `ThreadView.tsx`: messages in order, latest highlighted; right panel with triage fields, priority + rules fired, and a collapsible "Audit" showing raw model output, prompt version, model, timestamp.
- `Ask.tsx`: input, answer, citation chips linking to `ThreadView`; show refusal clearly.
- Plain, readable Tailwind. No charts library — the counts are the chart. No routing library needed beyond a simple state switch, or `react-router-dom` if it keeps code cleaner (one dependency max).
- **Verify:** all three screens work against the real API with real data.

### Phase 8 — Docs, clean-clone test, hand-off (≈1 h)
- README sections in order: *What it does (3 lines) · Architecture diagram (ASCII from section 3) · Setup (keys, deps, run backend, run frontend, run pipeline, run tests, run eval) · Design decisions (short, link to docs/decisions.md) · Evaluation results (numbers) · Auditability & risk controls · Assumptions · Limitations & next steps · Cost note*.
- `docs/walkthrough.md`: 10-minute demo script: problem → architecture → run pipeline live → dashboard → open a P1 thread and show "why" + audit → ask two questions → eval numbers → limitations.
- Finalise `map.md`, `memory.md`, `techdebt.md`, `session.md`.
- **Clean clone test**: fresh directory, follow README only, everything runs. Fix anything missing.
- Final commit. Report: eval numbers, P-level distribution, known gaps, total API cost.

---

## 6. Reference material for the agent

**Q&A test questions (use real names from the data):**
1. Was there any action required for Bridgegate Brokers?
2. What is outstanding on PIN-MTR-552301?
3. Which threads involve a solicitor?
4. Are there any new claims (FNOL) that haven't been acknowledged?
5. Did anyone raise a fraud concern?
6. What internal notices affect how I work this month?
7. Is there anything about a flooded vehicle?
8. What did Harper Broking ask us to do? (also tests the rebrand notice → Harper & Vale)

**Definitions to use consistently (README glossary):**
- *FNOL* — first notification of loss, i.e. a new claim being reported.
- *Urgency* — how soon action is needed. *Importance* — how much is at stake (money, customer harm, legal/regulatory exposure). Priority combines both via rules.
- *Bucket* — act / review / archive / ignore. *Level* — P1 (today) / P2 (this week) / P3 (normal) / P4 (no action).

**Risk & auditability points the README must cover (short bullets):**
- PII (names, addresses, claim details) is sent to a third-party LLM API — in production: DPA, data minimisation, redaction of unnecessary fields, EU/UK data residency.
- No automatic actions; recommendations only; handler remains accountable.
- Every result stores raw model output + prompt version + model + timestamp → reproducible and reviewable.
- Confidence gating → low-confidence items are surfaced, never silently dropped.
- Q&A answers only from retrieved evidence with citations; refuses when evidence is absent.
- `importance_flag` from the mail client is not trusted as a decision input.
- Known bias risks: over-prioritising professional senders (brokers/solicitors) vs. individual customers; rules reviewed for this.
- Scale: current design is batch over a JSON file; production needs a mailbox connector (Graph API), queue, incremental runs, monitoring of model drift and periodic re-labelling.

---

## 7. Tracking-file templates (if the skill is unavailable, create these manually)

`docs/map.md` — one line per file: `path — what it does — key functions`.
`docs/memory.md` — durable facts: dataset facts (section 2), model names, thresholds, prompt versions, eval numbers, decisions summary.
`docs/session.md` — per session: date/time, phases completed, verification results, blockers, next steps. Keep the latest session at the top.
`docs/techdebt.md` — table: `item — why it was skipped — how to fix — effort (S/M/L)`.
`docs/decisions.md` — numbered entries: `D-01 Title / Decision / Why / Alternative rejected`.

Update rhythm: **after every phase**, before committing.

---

## 8. Definition of done

- [ ] All eight phases complete and verified; tests green; eval numbers recorded
- [ ] Clean clone → README → runs (backend, frontend, pipeline, tests, eval)
- [ ] Every function has a docstring; no file over ~250 lines; no dead code
- [ ] `thread_id` never reaches a prompt or a rule (test proves it)
- [ ] Docs complete and short: README, decisions, map, memory, session, techdebt, walkthrough
- [ ] Final report to the owner: eval accuracy, P-level distribution, misclassified threads, Q&A results, total API cost, known limitations

---

## 9. Kick-off prompt (paste this to start the agent)

> You are the sole developer on a 1.5-day take-home task for a job interview. Read `AGENT_BRIEF.md` in full before doing anything else, then confirm in one short paragraph: the three email categories, the stack, the deadline, and the rule about `thread_id`. Then invoke the project-tracking skill to create the tracking files, and begin **Phase 0**. Work one phase at a time; at the end of each phase, run the verification step, update `docs/map.md`, `docs/session.md`, `docs/decisions.md` (and `techdebt.md` if you skipped anything), commit, and give me a 3-line status before starting the next phase. Follow section 0 rules strictly: no over-engineering, no features the Aviva brief does not ask for, docstrings on every function, short factual docs. If anything is ambiguous, choose the simplest option, log it as a decision, and continue. If anything is broken, tell me — do not paper over it.
