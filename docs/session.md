# Session

**Read this first.** "Now" is rewritten every session; the log below is newest first (at most six short lines per entry; fold older entries to one line). Cap: 8 KB. Decisions: docs/decisions.md. Facts and gotchas: docs/memory.md. Where things live: docs/map.md.

## Now (2026-10-04, session 6)
- The process files are now in git (D-58); the README is rewritten; D-59–D-60 logged; two code reviews' fixes applied. `ui-redesign` holds the work; `main` has it as one squash commit, **local only: the owner reviews, then pushes**.
- Checks: 103 tests; strict build; docs check (150.6 of 152 KB). A reviewer's zip install ran end to end (pipeline, API, UI checked in Chrome). Total spent $1.69.
- Caps raised by the owner today: README 16 KB, decisions 36 KB, total 152 KB.

### Before sending to Aviva (deadline 12:00 UK)
1. Review `git show --stat main` and the README; then `git push origin main`. Never push `private-history`; never `git add -f` the walkthrough or `.env`.
2. Reviewer access: the repo is private with no collaborators. Add the reviewers, or send a zip.
3. Clean clone from GitHub, README only: install, 103 tests, build; delete the clone.
4. Covering email: link or zip, how to run in three lines, ask them to confirm receipt.
5. Before the demo: restart :8000 (it serves qa_v2 until restarted), look at each screen; slides and backup screenshots; rehearse.

## Log
### 2026-10-04 — Publish the process, README rewrite, review fixes (session 6)
- Audit against the brief's own wording: every ask met; open items were the submission steps and the presentation.
- Published (D-58): AGENT_BRIEF.md, AGENTS.md, CLAUDE.md, session, memory, the docs check and hooks; the walkthrough stays local.
- README: quick start, how it works (diagram, rules table, one worked example), decisions with the alternatives rejected (D-59 one provider, D-60 no framework), how it was built.
- Backend review: a failed question is now audited (`ask_error`); "company domain" reasons; stale docstrings; unused `LLMResult.attempts`. A review agent's stray Sonnet call cost $0.016.
- Frontend review: About this data stays open after a run; Ask keeps focus; a failed AI reading says so; dead icon, CSS and exports gone. Two findings left in techdebt.
- Clean clone, then a reviewer's zip install: 103 tests, build, pipeline ($0.18; same P1/P2 counts, 2 threads swapped), API, UI. `.gitattributes` keeps .md LF; the checker skips the verbatim brief; README gained Security and Connecting a real mailbox (caps 18/156 KB, owner). Ask centred (D-61).

### Earlier (one line each; `git log` for detail)
- 2026-10-04 Session 5: Ask names the top three (qa_v3, D-52); colour for scanning, dark mode, then a toggle (D-53–D-57); no "Start here"; line of business per row.
- 2026-10-04 Ask reads the workload (qa_v2, D-47); a simpler UI: 5 sizes, the promise once, one (i), 9 rows on screen (D-48–D-51); doc audit.
- 2026-10-03 UI redesign (`ui-redesign`): calm queue, words, one filter; two reviews fixed (D-36–D-46).
- 2026-10-03 Review fixes (`review`): rules_v2 "waiting on us" (D-33), `/run` lock (D-34), whole-word domain match (D-35).
- 2026-10-03 Published copy: private files local-only, docs reworded, one clean commit pushed to the new repo.
- Phase 8 docs and clean clone: README in the brief's order; clean clone ran from the README alone ($0.18); run-to-run variance found (D-32).
- Phase 7 frontend: Dashboard, ThreadView, Ask, verified in Chrome against the live API (D-31).
- Phase 6 Q&A: retrieval with reasons (D-30), cited answers or refusal (D-29); refusals 9/9, refs 6/6, facts 17/17, $0.087.
- Phase 5 API: six routes, CORS, reads only stored results (D-28).
- Phase 4 eval: golden labels (0 seeds changed, 18 expected P1), `run_eval.py`; v1 50/50, P1 85%/94%; owner-approved v2: 49/50, P1 82%/100% (D-26, D-27).
- Phase 3 priority: named rules + overrides, 32 tests; first distribution P1 20 · P2 9 · P3 3 · archive 11 · ignore 7 (D-22–D-25).
- Phase 2 triage: live run $0.16; `temperature` via `extra_body`; schema retry (D-15–D-21).
- Phase 1 ingest: models, `thread_for_model`, leak tests (D-12–D-14). Phase 0 setup: repo, dataset, scaffold, docs system (D-01–D-11).
