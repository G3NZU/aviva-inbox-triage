# Tech debt

Deliberate shortcuts and deferred work, with the reason and the fix.

| Item | Why it was skipped | How to fix | Effort |
|---|---|---|---|
| No linter (ruff, eslint) | Not asked for; keeps the toolchain small | Add ruff and eslint, run them in CI | S |
| Retrieval is keyword-based, no embeddings | 50 threads; transparency matters more than recall here (D-03) | At ~10k emails: embeddings in pgvector or similar, hybrid with the keyword score | M |
| A company name run together in one domain word matches only through a first word of 5+ letters: "City Deli" gets no domain match on citydeli-leeds (found by shared words alone), and Harper Broking ties with Harper Vale | Keeps the whole-word rule simple (D-35) | Also match consecutive question words joined together ("city" + "deli" = citydeli, "harper" + "broking" = harperbroking) | S |
| JSON by prompt, not API structured outputs | Parse + retry is simple and model-agnostic (D-15) | Pass the `TriageResult` schema as `output_config.format`; keep Pydantic as a second check | S |
| Triage is per thread: conflicts across threads go unseen | One call per thread keeps cost and reasoning simple | A rule that flags a claim ref whose threads disagree (provider, postcode, name), e.g. two garages on PIN-MTR-552301, a Swansea roof and a York tree on PIN-HOM-547299 | M |
| Batch over a JSON file, not a live mailbox | The data comes as a file | Mailbox connector (Microsoft Graph webhooks) + a queue; the pipeline is already incremental (D-17) | L |
| Triage runs one thread at a time (~2 min for 50) | Simplest to read and debug | A small thread pool, or the Message Batches API (asynchronous, half price) | S |
| No authentication; single user; local only | Out of scope for a local demo | SSO in front of the API; per-handler queues and assignment | M |
| Signal precision (P1 precision 86%) and stability (3/50 threads change between runs) | One prompt iteration only (D-27); Haiku ignores negative definitions; temperature 0 is not deterministic (D-32) | Triage twice and send disagreements to review; per-signal golden set + few-shot examples; a stronger model only for the P1-deciding signals; narrow `injury` to new or worsening harm | M |
| Help bubbles need a 2025 browser | Native popover is Baseline since Jan 2025; iPads before iOS 18.3 lack click-outside closing (Esc and a second tap still work) | A small fallback (state, Esc and outside-click listeners) if older browsers matter | S |
| Browser Back leaves the app | No router (D-31): screens are state, not URLs | Mirror the view in `location.hash` with one `hashchange` listener | S |
| Answers list their sources, not one per sentence | Needs another Q&A prompt version and a paid eval re-run | A prompt that cites per sentence; the UI shows numbered markers | M |
| The open workload goes whole with every question (~6k of ~10k input tokens) | 32 open threads; one rule, easy to explain (D-47) | Prompt caching for the workload block (it only changes after a run); at scale, retrieve from it | S |
| A refusal does not say why | QAAnswer stores no reason (no match, no valid citation, unusable reply) | Add `refusal_reason` to QAAnswer and show it | S |
| No frontend unit tests | They would add test dependencies; the strict build and typed labels cover part of it | vitest for labels.ts, help.ts and workload.ts, plus a few component tests | M |
| An open thread keeps its old reading when a run finishes | Found in the final review; a remount would move focus | Key ThreadView on the last run time | S |
| `GET /threads?level=P2` also returns review threads (stored at P2), unlike the P2 card | The UI filters in the browser by `card`; the query filters are for curl | Filter by card on the server too | S |
| No split view (the list beside the open thread) | At 1366 px a reading pane leaves the list too narrow (D-36, D-50) | From ~1600 px wide, show ThreadView beside the list; keep one screen below | M |
