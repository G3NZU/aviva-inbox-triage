# Aviva Inbox Triage

A triage assistant for an insurance claims inbox. It reads every email thread, sorts it into **action required**, **informational** or **irrelevant**, says what the handler has to do, gives each action a priority (P1–P4) with readable business rules, shows the whole workload on one screen, and answers free-text questions about the mailbox, citing the emails it used. It only recommends: it never sends, archives or deletes email.

## Quick start

You need Python 3.14 (tested; 3.11+ should work), Node.js 20.19+ (tested on 24) and an **Anthropic API key**.

1. **Download**: `git clone https://github.com/G3NZU/aviva-inbox-triage.git` then `cd aviva-inbox-triage` (or unzip the copy you were sent).
2. **Key**: copy `.env.example` to `.env` in the repo root and set `ANTHROPIC_API_KEY`, the only secret.
3. **Backend** (Python packages pinned in `backend/requirements.txt`: FastAPI, uvicorn, anthropic, pydantic, python-dotenv, pytest, httpx):
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   python -m app.pipeline             # triage all 50 threads: ~2 min, ~$0.18
   uvicorn app.main:app               # API on http://localhost:8000 (interactive docs at /docs)
   ```
4. **Frontend** (a second terminal; packages in `frontend/package.json`: React, Vite, TypeScript, Tailwind):
   ```bash
   cd frontend
   npm install
   npm run dev                        # UI on http://localhost:5173
   ```
5. **Tests** (no key or network needed; the model is mocked): `cd backend` then `pytest`.
6. **Evaluation**: `cd backend` then `python -m eval.run_eval` (re-scores the stored results, free) or `python -m eval.run_eval --qa` (also re-asks the 12 Q&A questions, ~$0.28). It rewrites `backend/eval/results.md`, so on a fresh clone it scores your own run.

In the UI, "About this data" › "Re-run triage" runs the pipeline again; "Re-read all threads…" redoes every thread (`--force`) and asks first. The theme follows the system until you use the header's "Dark mode" toggle.

## How it works

```
data/emails_candidate.json         50 threads / 95 messages
        │
        ▼     pipeline.py (python -m app.pipeline, or "Re-run triage") runs the next four steps
 ingest.py    threads oldest first; the latest message is the current state; label-leaking IDs dropped
        │
        ▼
 triage.py    one Claude Haiku 4.5 call per thread → JSON checked by Pydantic: category, action,
        │     urgency, importance, signals, confidence, reasoning (one retry, else human review)
        ▼
 priority.py  plain Python rules, no LLM → bucket + level (P1–P4) + the rules that fired
        │
        ▼
 store.py     SQLite: threads, messages, triage (with the raw model output), priority, append-only audit log
        │
        ▼
 main.py      FastAPI, reads stored results only ──▶ React UI: Workload · Thread · Ask
        │     POST /ask
        ▼
 qa.py        keyword search with reasons + the open workload in the rules' order →
              Claude Sonnet 5.5 answers from those only, citing messages, or refuses
```

**Triage is the model's judgement.** Haiku reads one thread (the latest message decides its state) and returns the category, the specific task, including an implied one (a broker sending a claim form becomes "confirm cover and excess, and advise next steps"), the sender type, urgency (how soon) and importance (what is at stake) as separate ratings, any stated deadline, risk signals, a confidence and its reasoning.

**Priority is business policy, in code.** The rules in `backend/app/priority.py` run in this order, and every result stores the rules that fired:

| When | Result |
|---|---|
| Confidence below 0.6, or unusable model output | **Needs a check**: a person decides |
| Resolved by the latest message, or informational | **P4 · No action needed** (archive) |
| Irrelevant to the claims workload | **Not claims work** (ignore) |
| An action with injury, urgent make-safe, legal threat, regulatory issue, fraud flag, vulnerable customer or complaint, or a deadline overdue or due within 2 days | **P1 · Act today** |
| Otherwise: high urgency or high importance, a repeat chase, a new claim (FNOL), a payment or authority pending, a deadline within 7 days, or waiting on us over 5 working days | **P2 · This week** |
| Any other action | **P3 · Normal** |

**Example.** Bridgegate Brokers sent a claim form and photos for PIN-HOM-533661, then chased. Haiku: action required, "Confirm cover and excess … and advise next steps", medium urgency and importance, no risk signal. The rules: nothing for P1; the broker has waited 14 working days, so **P2 · This week**. (Another run flagged the leak as an urgent make-safe, making it P1: the signal variance under Evaluation.) Asked "Was there any action required for Bridgegate Brokers?", Ask says yes, gives that next step and the wait, and cites both emails.

**Continuous ingestion.** Runs are incremental and idempotent: the model is called only for threads that are new, have a new message, failed last time or were judged by another prompt version, and every priority is recomputed for free, so model calls grow with new mail, not with the size of the mailbox. [Connecting a real mailbox](#connecting-a-real-mailbox) shows the live feed.

## The UI

Three screens, no extra libraries; every number comes from the API.
- **Workload**: six count cards (the summary, and the only priority filter), a line-of-business filter, then every thread in sections, most urgent first. Each row says what to do, why ("Why: Complaint · Regulatory issue"), its line of business and how many working days the sender has waited on us.
- **Thread**: the suggested next step, why it has its priority (set by the rules), the emails, the AI's reading with its confidence, and the audit record. Previous / Next walks the list.
- **Ask**: example questions, then the answer beside the emails it cites (sender and date), or "No answer given".

Keyboard and screen-reader friendly; AA contrast in both themes.

## Decisions and the alternatives rejected

The main choices; all 61, with reasons and the alternatives rejected, are in [docs/decisions.md](docs/decisions.md).

- **LLM for judgement, code for policy** (D-01). Priority is business policy: rules are readable, tested and versioned, and every priority lists the rules that fired. *Rejected:* the model sets the priority (opaque, hard to test, and every policy change becomes a prompt change).
- **Haiku 4.5 triages, Sonnet 5.5 answers** (D-02). Extraction into a fixed schema is a small-model job (≈ $0.0036 a thread, 49/50 categories right); Q&A reasons across threads and must cite. *Rejected:* one large model for everything (more cost per email, no gain on categories).
- **One provider, called directly** (D-59, D-60). One SDK and one third party receiving the PII; every request is visible in `llm.py`. *Rejected:* another vendor such as OpenAI or Google (not benchmarked; `llm.py` is the only file that talks to the API and the eval scores any model, so a trial is cheap); a local open-source model (keeps data in-house, but needs hardware and its own evaluation); LangChain or an agent framework (two fixed calls need no orchestration).
- **Keyword retrieval with reasons, no vector database** (D-03, D-30). 95 messages fit in memory; scoring by claim reference, company domain, triage tag and rare shared words shows why each thread matched. *Rejected:* embeddings in a vector index (opaque ranking and another service for 50 threads). At ~10k emails: hybrid keyword and embedding search, e.g. pgvector.
- **Ask reads the open workload in the rules' order** (D-47, D-52). "What should I focus on?" matches no email, so every question also gets the open threads as the rules ranked them; the model reports that order and never re-ranks. *Rejected:* the model ranks threads (judgement replacing policy); the whole mailbox in context (hides what an answer rests on, and does not scale).
- **SQLite through the standard library, no ORM** (D-04). Nothing to install, one disposable file, and the audit log is a table anyone can query. *Rejected:* PostgreSQL (a database server to install and run for one local user; the right move when several handlers write at once, with the same tables); an ORM (five tables read fine as SQL).
- **JSON by prompt, checked by Pydantic, one retry** (D-15, D-21). The same code serves both models, the raw reply is stored, and every failure path is tested. *Rejected:* API structured outputs, a stronger guarantee listed as the next step.
- **Confidence gate, recommendations only** (D-05, D-06). An unsure call goes to a person, never silently to archive; the handler stays accountable. *Rejected:* trusting every category; auto-archiving irrelevant mail (a misread complaint could be lost).
- **The API reads stored results; the model runs in the pipeline** (D-28). Pages cost nothing and never wait, and every number on screen is stored and audited. *Rejected:* triage on request (slow, costly, unaudited between runs).
- **React and Vite, no router, state or chart library** (D-09, D-31). Three screens, and the counts are the chart. *Rejected:* react-router and state or chart libraries (dependencies with nothing to do here).

## Evaluation

Golden labels for all 50 threads (seeded from the dataset's thread IDs, then every thread hand-checked) plus `expected_p1`: "should the handler act today if every signal and deadline were read correctly". Full report: [backend/eval/results.md](backend/eval/results.md).

| | triage_v1 | triage_v2 (current) |
|---|---|---|
| Category accuracy | 50/50 | 49/50 (a rebrand notice judged irrelevant, not informational) |
| Missed actions (action archived or ignored with no human review) | 0 | 0 |
| P1 precision | 17/20 (85%) | 18/21 (86%) |
| P1 recall | 17/18 (94%) | **18/18 (100%)** |

v2 tightened the signal definitions and how a weekday deadline ("by Friday") is dated, and is kept for its recall: v1 left a possibly vulnerable customer (a stolen mobility scooter) at P3.

- **Repeatability**: a second v2 run kept every category, but signals changed on 3 of 50 threads and the scooter customer fell to P2 (P1 recall 17/18). Temperature 0 is not fully deterministic, so read the signal-driven numbers as ±1–2.
- **Q&A** (12 questions: one with no answer in the mailbox, three about the workload): refusals 12/12 right, expected claim refs cited 11/11, required facts 24/25, 2–4 s each.
- **Caveats**: 50 threads; labels by the developer, not independent annotators; v2 and the retrieval settings were tuned on the same data, so the numbers are optimistic.

## Security, audit and risk controls

- **Human in control**: nothing is sent, archived or deleted; the handler sees the recommendation, its reasons and the raw emails.
- **Reproducible**: every triage result stores the raw model output, model, prompt version, request ID, tokens and timestamp; priorities store the rules version and as-of date; every model call, question and run is appended to `audit_log` (append-only in code, not tamper-proof).
- **Confidence gating**: confidence below 0.6, or unusable model output, sends a thread to review, never silently to archive.
- **Grounded Q&A**: answers come only from the matched emails and the open workload, and must cite messages; no valid citation means a refusal.
- **Prompt injection**: an email is data, not instructions: the model reads it inside tags it is told never to obey, has no tools and can change nothing, and must reply in a strict schema. This limits the damage rather than preventing injection: a crafted email can still steer its own category, signals or confidence, so nothing is archived unseen and the raw email sits beside the AI's reasoning. Next: injection cases in the eval, and keyword backstops for complaint, legal and vulnerability cues. The sender-set importance flag is never used to decide.
- **Secrets**: the API key lives only in `.env` (gitignored) on the server; the browser never sees it. Production: a key vault and rotation.
- **Access**: a single-user local demo: the API listens on localhost only and has no login. CORS only stops other web pages reading its replies; it is not access control (curl, or a page posting to `/run`, still gets through). Production: single sign-on checked by the API (e.g. Entra ID), roles (only an admin or the scheduler starts runs), each handler limited to the claims they may see, CSRF and Host checks, and rate limits and spend caps on `/ask` and `/run`.
- **Data**: names, addresses and claim details go to a third-party API, and the SQLite file keeps whole emails, model replies and every question, unencrypted, on one machine. Production: a data processing agreement, minimisation or redaction, UK/EU residency, an encrypted managed database, and retention limits that cover the audit log too.
- **Code**: SQL is always parameterised; the UI renders text, never HTML; the npm tree is locked and the seven Python packages pinned (a hashed lock of every dependency is next); the UI makes no third-party requests.
- **Bias**: no rule reads the sender type, so a customer and a solicitor with the same request and stakes get the same priority (tested). Solicitors' letters rank high for the legal exposure they carry, not for who sent them.

## Connecting a real mailbox

The JSON file stands in for the mailbox; `ingest.py` is the only code that knows its shape. On Microsoft 365 (Exchange Online), through Microsoft Graph:

1. **Access**: an Entra ID app with read-only `Mail.Read`, scoped to the claims mailbox alone (Exchange RBAC for applications), its certificate in a key vault.
2. **New mail**: a change-notification subscription on the inbox calls a webhook, which checks the validation token and client state and is renewed before it expires; a delta query catches up after an outage, since notifications can be missed.
3. **Processing**: the webhook only queues the message ID. A worker fetches the message, groups it into a thread by `conversationId`, upserts it and runs the existing incremental pipeline, which calls the model only for threads with a new message. Retries honour Graph throttling (429 with Retry-After).

Gmail has the same shape (`users.watch` with Pub/Sub, then `history.list`); IMAP IDLE suits older servers. Writing back (moving or flagging mail) would need its own audited permission.

## Assumptions

- "Today" for waiting times and deadlines is **2026-02-20**, the newest email (`AS_OF_DATE` in `backend/app/config.py`); production would use the current date.
- One handler owns the claims inbox (Home, Motor, Liability); `@pinnacle-insurance.co.uk` senders are "us".
- A thread waits on us when its latest message came from outside Pinnacle, counted from that message. A holding reply ("we will confirm tomorrow") stops that clock but leaves the action open; a missed deadline on an open request is P1.
- Attachments are judged by file name only (the dataset has no contents); working days ignore bank holidays.

## Limitations and next steps

- **P1 is heavy** (21 of 32 actions): the mailbox is a three-week backlog judged on its last day, and Haiku over-flags some signals (make-safe on a flooded car, injury on routine physio paperwork) even when told not to; signals also vary between runs. Next: send threads where two runs disagree to review; a per-signal test set with few-shot examples; a stronger model only for the P1-deciding signals.
- **Triage is per thread**, so conflicts across threads go unseen: PIN-MTR-552301 names two different garages; PIN-HOM-547299 is a Swansea roof in one thread and a York tree in another. Next: a cross-thread consistency rule.
- **Keyword retrieval** suits specific questions; broad ones ("all internal notices") are better served by the Workload filters. The open workload goes whole with every question; at scale it would be retrieved.
- **Batch over a JSON file**, single user, no login: production needs the mailbox feed and the access controls above, plus drift monitoring and periodic re-labelling.

## Cost

Triage averages ~2,400 input and ~240 output tokens per thread on Haiku 4.5: **≈ $0.0036 per thread**, ≈ $0.18 for this mailbox, ≈ $3.60 per 1,000 threads. Q&A costs about $0.02 per question on Sonnet 5.5. At 5,000 new or changed threads a day, triage would cost ≈ $18 a day (half that through the Message Batches API) and take ~3.5 hours one call at a time, so production would run calls in parallel or in batches. Everything spent building this, evaluations and two clean-install tests included: **$1.69**.

## How this was built

Built with Claude Code, an AI coding agent, working from a written brief and rules: one phase at a time, each verified before the next. These files show the process:

- [AGENT_BRIEF.md](AGENT_BRIEF.md): the brief: the task, the design and an eight-phase plan, each phase with its check.
- [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md): the agent's rules: tests that never call the API, a docstring on every function, every judgement call logged as a decision, docs with one job each and a size cap.
- [docs/session.md](docs/session.md) (build log), [docs/decisions.md](docs/decisions.md), [docs/memory.md](docs/memory.md) (facts and gotchas), [docs/map.md](docs/map.md) (where things live), [docs/techdebt.md](docs/techdebt.md) (known shortcuts).
- `scripts/docs-check.mjs` keeps the docs within their caps; hooks in `.claude/settings.json` and `.githooks/pre-commit` run it on every doc edit and commit.

## Glossary

- **FNOL**: first notification of loss, i.e. a new claim being reported.
- **Urgency**: how soon action is needed. **Importance**: how much is at stake (money, customer harm, legal or regulatory exposure). Priority combines both through the rules.
- **Bucket**: act / review / archive / ignore. **Level**: P1 (today) / P2 (this week) / P3 (normal) / P4 (no action).
- **P1 precision and recall**: precision is the share of threads marked P1 that should be P1; recall is the share of threads that should be P1 that were marked P1.

## Repository

`backend/app` the service · `backend/eval` golden labels and evaluation · `backend/tests` 103 tests · `frontend/src` the UI · `docs/` decisions, build log, code map, tech debt · `scripts/` the docs check.
