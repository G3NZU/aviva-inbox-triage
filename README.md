# Aviva Inbox Triage

A triage assistant for an insurance claims inbox. It reads every email thread, sorts it into **action required**, **informational** or **irrelevant**, gives each action a priority (P1–P4) with transparent rules, shows the handler's whole workload on one screen, and answers free-text questions about the mailbox with cited messages. It only recommends: it never sends, archives or deletes email.

## Architecture

```
data/emails_candidate.json         50 threads / 95 messages
        │
        ▼
 ingest.py    threads oldest first; the latest message is the current state; label-leaking IDs dropped
        │
        ▼
 triage.py    one Claude Haiku 4.5 call per thread → JSON checked by Pydantic: category, action,
        │     urgency, importance, signals, confidence, reasoning (one retry, else human review)
        ▼
 priority.py  plain Python rules, no LLM → bucket (act/review/archive/ignore) + level (P1–P4) + rules fired
        │
        ▼
 store.py     SQLite: threads, messages, triage (with raw model output), priority, append-only audit log
        │
        ├──▶ main.py (FastAPI) ──▶ React UI: Workload · Thread · Ask
        └──▶ qa.py   claim-ref / company / tag / keyword search with reasons → Claude Sonnet 5.5 answers
                     from those threads only, citing messages, or refuses
```

## Setup

Requires Python 3.14 (tested; 3.11+ should work), Node.js 20.19+ (tested on 24) and an **Anthropic API key**.

1. **Code**: `git clone https://github.com/G3NZU/aviva-inbox-triage.git` then `cd aviva-inbox-triage`.
2. **Key**: copy `.env.example` to `.env` in the repo root and set `ANTHROPIC_API_KEY`.
3. **Backend** (Python packages in `backend/requirements.txt`: FastAPI, uvicorn, anthropic, pydantic, python-dotenv, pytest, httpx):
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   python -m app.pipeline             # triage all 50 threads: ~2 min, ~$0.18
   uvicorn app.main:app               # API on http://localhost:8000 (interactive docs at /docs)
   ```
4. **Frontend** (second terminal; packages in `frontend/package.json`: React, Vite, TypeScript, Tailwind):
   ```bash
   cd frontend
   npm install
   npm run dev                        # UI on http://localhost:5173
   ```
5. **Tests** (no key or network needed; the model is mocked): `cd backend` then `pytest`.
6. **Evaluation**: `cd backend` then `python -m eval.run_eval` (re-scores stored results, free) or `python -m eval.run_eval --qa` (re-asks the 9 Q&A questions, ~$0.10). Writes `backend/eval/results.md`.

The pipeline is incremental: a re-run only re-triages threads that are new, have a new message, failed last time or were judged by another prompt version; `--force` redoes all. The UI's "Run pipeline" button does the same.

## Design decisions

- **LLM for judgement, code for policy.** The model says what a thread is and what it asks; readable Python rules decide the priority, and every priority lists the rules that fired.
- **Haiku for triage, Sonnet for Q&A.** Schema-bound extraction is a small-model job; Q&A reasons across threads and must cite.
- **No vector database.** 50 threads: transparent keyword, claim-reference, company-domain and triage-tag scoring, with reasons shown.
- **SQLite** with an append-only audit log anyone can query. **Recommendations only.**
- **Labels never leak.** `thread_id` and `message_id` encode the category (`thr_irr_…`), so neither reaches a prompt or a rule.
- All 32 decisions, with the alternative rejected: [docs/decisions.md](docs/decisions.md).

## Evaluation

Golden labels for all 50 threads (seeded from the dataset's thread IDs, then every thread hand-checked) plus `expected_p1`: "should the handler act today if every signal and deadline were read correctly". Full report: [backend/eval/results.md](backend/eval/results.md).

| | triage_v1 | triage_v2 (current) |
|---|---|---|
| Category accuracy | 50/50 | 49/50 (a rebrand notice judged irrelevant, not informational) |
| Missed actions (action archived or ignored with no human review) | 0 | 0 |
| P1 precision | 17/20 (85%) | 18/22 (82%) |
| P1 recall | 17/18 (94%) | **18/18 (100%)** |

v2 tightened only the signal definitions and is kept for its recall: v1 left a possibly vulnerable customer (a stolen mobility scooter) at P3. **Repeatability**: a second, independent v2 run (the clean-clone test) kept every category, but signals changed on 3 of 50 threads and the scooter customer fell to P2 (P1 recall 17/18). Temperature 0 is not fully deterministic, so read the signal-driven numbers as ±1–2. **Q&A** (9 questions incl. one with no answer in the mailbox): refusals 9/9 right, expected claim refs cited 6/6, required facts 17/17, 2–4 s per answer. **Caveats**: 50 threads; labels by the developer, not independent annotators; v2 and the retrieval settings were tuned on the same data, so the numbers are optimistic.

## Auditability and risk controls

- **Human in control**: nothing is sent, archived or deleted; the handler sees the recommendation, its reasons and the raw emails.
- **Reproducible**: every triage result stores the raw model output, model, prompt version, request ID, tokens and timestamp; priorities store the rules version and as-of date; every LLM call, question and pipeline run is appended to `audit_log`.
- **Confidence gating**: confidence below 0.6, or unusable model output, sends a thread to the **review** bucket, never silently to archive.
- **Grounded Q&A**: answers come only from retrieved emails and must cite messages; no valid citation means a refusal.
- **Untrusted inputs**: email text is wrapped as data (prompt-injection guard); the sender-set importance flag is shown but never used to decide.
- **Bias**: no rule reads the sender type, so a customer and a solicitor with the same request and stakes get the same priority (tested). Solicitors' letters rank high because of the legal exposure they carry, not who sent them.
- **PII**: names, addresses and claim details go to a third-party API. Production needs a data processing agreement, data minimisation or redaction, UK/EU data residency and retention limits.

## Assumptions

- "Today" for ages and deadlines is **2026-02-20**, the newest email (`AS_OF_DATE` in `backend/app/config.py`); production would use the current date.
- One handler owns the claims inbox (Home, Motor, Liability); `@pinnacle-insurance.co.uk` senders are "us".
- A holding reply ("we will confirm tomorrow") leaves the action open; a missed deadline on an open request is P1.
- Attachments are judged by file name only (the dataset has no contents); working days ignore bank holidays.

## Limitations and next steps

- **P1 is heavy** (22 of 32 actions): the mailbox is a three-week backlog judged on its last day, and Haiku over-flags some signals (make-safe on a flooded car, injury on routine physio paperwork) even when told not to. Signals also vary between runs (3 of 50 threads), so a borderline vulnerability can be missed. Next: send threads where two runs disagree to review; a per-signal test set with few-shot examples; or a stronger model only for the P1-deciding signals.
- **Triage is per thread**, so conflicts across threads go unseen: PIN-MTR-552301 has two different garages; PIN-HOM-547299 is a Swansea roof in one thread and a York tree in another. (Q&A did spot the first.) Next: a cross-thread consistency rule.
- **Keyword retrieval** suits specific questions; broad ones ("all internal notices") are better served by the dashboard filters. At ~10k emails: embeddings with hybrid search.
- **Batch over a JSON file**, single user, no auth. Production: a mailbox connector (Microsoft Graph), a queue, the existing incremental runs, drift monitoring and periodic re-labelling.

## Cost

Triage averages ~2,400 input and ~240 output tokens per thread on Haiku 4.5: **≈ $0.0036 per thread**, ≈ $0.18 for this mailbox, ≈ $3.60 per 1,000 threads. Q&A costs about $0.01 per question on Sonnet 5.5. Everything spent building this, including the evaluation and the clean-clone test: **$0.66**.

## Glossary

- **FNOL**: first notification of loss, i.e. a new claim being reported.
- **Urgency**: how soon action is needed. **Importance**: how much is at stake (money, customer harm, legal or regulatory exposure). Priority combines both via rules.
- **Bucket**: act / review / archive / ignore. **Level**: P1 (today) / P2 (this week) / P3 (normal) / P4 (no action).

## Repository

`backend/app` the service · `backend/eval` golden labels and evaluation · `backend/tests` 79 tests · `frontend/src` the UI · `docs/` design decisions, a map of the code, known tech debt.
