# Tech debt

Deliberate shortcuts and deferred work, with the reason and the fix.

| Item | Why it was skipped | How to fix | Effort |
|---|---|---|---|
| No linter (ruff, eslint) | Not asked for; keeps the toolchain small | Add ruff and eslint, run them in CI | S |
| Retrieval is keyword-based, no embeddings | 50 threads; transparency matters more than recall here (D-03) | At ~10k emails: embeddings in pgvector or similar, hybrid with the keyword score | M |
| JSON by prompt, not API structured outputs | Parse + retry is simple and model-agnostic (D-15) | Pass the `TriageResult` schema as `output_config.format`; keep Pydantic as a second check | S |
| Triage is per thread: conflicts across threads go unseen | One call per thread keeps cost and reasoning simple | A rule that flags a claim ref whose threads disagree (provider, postcode, name), e.g. two garages on PIN-MTR-552301, a Swansea roof and a York tree on PIN-HOM-547299 | M |
| Batch over a JSON file, not a live mailbox | The task supplies a file | Mailbox connector (Microsoft Graph webhooks) + a queue; the pipeline is already incremental (D-17) | L |
| Triage runs one thread at a time (~2 min for 50) | Simplest to read and debug | A small thread pool, or the Message Batches API (asynchronous, half price) | S |
| No authentication; single user; local only | Out of scope for a local demo | SSO in front of the API; per-handler queues and assignment | M |
| Signal precision (P1 precision 82%) and stability (3/50 threads change between runs) | One prompt iteration only (D-27); Haiku ignores negative definitions; temperature 0 is not deterministic (D-32) | Triage twice and send disagreements to review; per-signal golden set + few-shot examples; a stronger model only for the P1-deciding signals; narrow `injury` to new or worsening harm | M |
