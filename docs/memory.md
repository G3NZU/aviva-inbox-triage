# Memory — durable facts and hard-won gotchas

Facts that stay true across sessions. NOT the why of decisions (docs/decisions.md), NOT file locations (docs/map.md), NOT current state (docs/session.md). Replace entries on the same subject; never stack. Cap: 8 KB.

## Dataset (data/emails_candidate.json)
- 50 threads / 95 messages; 26 single-message threads; longest 6. Dates 2026-02-01 → 2026-02-20. 35 messages carry attachment metadata (no content).
- Fictional insurer Pinnacle Insurance; inbox claims@pinnacle-insurance.co.uk; internal domain pinnacle-insurance.co.uk. The handler covers Home, Motor, Liability.
- Claim refs match `PIN-[A-Z]{3}-\d{6}`: 19 distinct refs.
- `importance_flag` is "high" on 52/95 messages. It is set by the sender, so it is not trusted.
- **Label leak:** thread_id prefixes (`thr_hom/mtr/lia/gen/info/irr`) and message_id prefixes (`hom-`, `mtr-`, `lia-`, `gen-`, `info-`, `irr-`) reveal the category.
- Seed labels by prefix: hom 14 + mtr 7 + lia 6 + gen 5 = 32 action_required; info 11 informational; irr 7 irrelevant.
- Same claim ref, conflicting details across threads (data quality or fraud signal; per-thread triage cannot see it):
  - PIN-MTR-552301: Steel City Bodyshop repair vs a QuickFix Garage final invoice.
  - PIN-LIA-744552: Glasgow West Physio notes vs a PhysioCare Scotland invoice.
  - PIN-HOM-419876: NG2 West Bridgford subsidence vs a Leeds LS17 monitoring invoice.
  - PIN-HOM-547299: Swansea SA1 roof tarp vs a York YO24 oak tree.
  - PIN-HOM-520119: Liam Mitchell's e-bike vs feedback from "Mr Lane".
  - PIN-LIA-771045 (Leith) attaches `Orthopaedic_Report_Davies_…`; Davies is the claimant in the unrelated Cardiff café claim — possibly a mis-sent document.

## Models and settings (source of truth: backend/app/config.py)
- Triage `claude-haiku-4-5` ($1 / $5 per MTok in/out). Q&A `claude-sonnet-5-5` ($2 / $10).
- Prompt versions: triage_v2 (current; v1 kept), qa_v3 (current: a focus question gets the top three and the P1 count; v1, v2 kept). Confidence threshold 0.6. As-of date 2026-02-20 (newest email).
- Priority rules: rules_v2 (2026-10-03, D-33): waiting on us = latest message from outside, > 5 working days → P2; `waiting_days` stored for every bucket. P1 rules are unchanged from rules_v1, so golden `expected_p1` (labelled "under rules_v1") still holds.
- Triage (v2) averages ~2,400 input / ~240 output tokens per thread: ≈ $0.0036 per thread, ≈ $0.18 per full run, 2 min 9 s sequential. An unchanged re-run makes no calls. Spend (triage $0.55 incl. the owner's forced re-run; Q&A $0.74 incl. the owner's UI questions and the qa_v2/qa_v3 evals; the clean-clone run $0.18; a review agent's stray Q&A call $0.016 and a reviewer-zip test, $0.18 run + $0.02 question, on 4 Oct, outside triage.db). Total $1.69.

## Evaluation (backend/eval, golden labels hand-checked 2026-10-03)
- Golden: 32 / 11 / 7 (action / informational / irrelevant), 18 expected P1; 0 of 50 seeds changed by the hand-check (5 judgement calls noted in the file).
- triage_v1: category 50/50, missed actions 0, P1 precision 17/20, recall 17/18 (over: claim form, tarp invoice, flooded car; under: the scooter).
- triage_v2 (current; results.md re-scored 2026-10-03 from the live DB, the owner's 19:08 UTC run): category 49/50 (rebrand → irrelevant), missed actions 0, P1 precision 18/21 (86%), recall 18/18; P1 21 · P2 11 · P3 0 · archive 10 · ignore 8. The earlier published run had P1 22, precision 18/22.
- Repeatability (clean-clone v2 run, 2026-10-03): same 50 categories; signals differed on 3 threads (the scooter lost `vulnerable_customer` → P2); P1 precision 17/21, recall 17/18. Temperature 0 is not deterministic (D-32).
- Signals are the weak spot. Haiku at temperature 0 ignores negative definitions ("not for vehicles", "not for work already done"); `injury` ("a personal injury claim") fires on routine PI paperwork. Haiku also wraps replies in a ```json fence despite the prompt (`parse_json_object` tolerates it).
- Q&A (qa_v3, 2026-10-04; Sonnet 5.5 effort medium; top 12 + the open workload with a count line): refusals 12/12, refs 11/11, words 24/25, 2–4 s; $0.272 for 12 (~$0.023 each, ~9.8k input tokens). Focus questions (q10, q12) → PIN-HOM-501772 complaint, James Turner's flooded Kia, PIN-HOM-547299 tree report, then "3 of the 21 P1 threads". q8 dropped the Harper & Vale rebrand.

## Gotchas
- Deadline (confirmed by the owner 2026-10-03): submit by **Sun 4 Oct 2026, 12:00 UK**. The brief's "Sunday 5 Oct" was a typo.
- Sonnet 5.5 rejects `temperature` and assistant prefill (HTTP 400); Haiku 4.5 rejects `effort`. Sonnet 5.5 always thinks: read only `text` blocks from its responses.
- anthropic 1.x removed `temperature`/`top_p`/`top_k` from `messages.create()` (TypeError); Haiku 4.5 still honours temperature, so it goes in `extra_body`. The tests' FakeClient binds every request to the real `create()` signature, so this class of drift fails a test.
- Never default a parameter to a config value (`path=config.DB_PATH`): it is frozen at import, so monkeypatched tests wrote to the real DB (2026-10-03). Defaults are `None`, resolved at call time.
- Under `python -m app.pipeline` the module's `__name__` is `__main__`: name the logger explicitly or its INFO lines vanish.
- Windows console (cp1252) cannot print the dataset's U+2011 hyphens: set `PYTHONIOENCODING=utf-8` for ad-hoc scripts.
- anthropic 1.x builds a client with no key and only fails at the first request (TypeError "Could not resolve authentication method"), so `llm.get_client` checks ANTHROPIC_API_KEY itself. The SDK is built on `httpx2`, not `httpx`: tests build SDK errors with `httpx2.Request`/`httpx2.Response`.
- The API may report a dated model ID (e.g. `claude-haiku-4-5-2025…`); price lookups match by prefix.
- Line endings: the working tree is LF but `core.autocrlf=true`. Python `write_text` on Windows writes CRLF (pass `newline="
"`), and `git stash`/`pop` rewrites files as CRLF: check `git ls-files --eol`.
- `store.connect()` alters an older file (adds `priority.waiting_days`). For a dry check that must not touch triage.db, open it with the sqlite3 URI `file:…?mode=ro`.
- `pytest | tail` masks a failing exit code: use `set -o pipefail` before chaining a commit after tests (a commit slipped through with 3 failures on 2026-10-03).
- Windows: `kill $!` after `npx vite &` leaves the node child running on :5173. Stop it by PID (`Get-NetTCPConnection -LocalPort 5173`).
- UI checks without touching the owner's servers: a scratchpad launcher copies triage.db, extends the CORS list and serves it on :8001; `VITE_API_URL=http://localhost:8001 npx vite --port 5174`. The owner's :8000 has no `--reload`; auto mode blocks stopping, restarting or even curling it, so the owner restarts it.
- The owner's Chrome prefers dark and runs Dark Reader; the `darkreader-lock` meta keeps it off the app. The theme toggle saves per origin, so :5174 checks never touch :5173's choice. Check 390 px in a same-origin iframe (`resize_window` cannot shrink the maximised window).
- Estimating tokens as characters ÷ 4 undercounts this mailbox by ~1.65× (addresses, codes, numbers): price API runs from a real call's usage.
- Importing `app.config` loads `.env`, so unsetting ANTHROPIC_API_KEY in the shell does not stop a real call: patch `llm.get_client` to raise in ad-hoc checks (cost $0.016 on 4 Oct).
- Free Ask checks: stub `window.fetch` for `/ask` with a stored answer (audit_log event 'ask'); every real question now calls Sonnet, even with no match.
- Claude in Chrome: the first screenshot after an action often times out (take another), and typing may not reach a minimised window: set inputs with the native value setter plus an `input` event.
- Chrome hides a closed `<details>` with content-visibility: `offsetParent` is set but `checkVisibility()` is false (and it is skipped by Tab).
- A native popover defaults to `position: fixed; inset: 0; margin: auto` (centred): Explain sets `absolute inset-auto m-0` and places it in `onToggle`.
- `satisfies Record<K, (x: T) => string>` keeps zero-argument arrows zero-argument, so calls with an argument fail tsc: annotate the object's type instead.
