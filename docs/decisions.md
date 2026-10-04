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

## Revisions

**D-33 "Waiting on us" runs from the latest outside message** (rules_v2; replaces rules_v1's age-based unanswered rule)
- Decision: a thread waits on us from its latest message if someone outside Pinnacle sent it; over 5 working days → P2. Every priority stores `waiting_days`; the list shows it instead of age.
- Why: rules_v1 counted from the first message and took any reply from us as an answer, so PIN-HOM-508377 sat at P3 with the adjuster waiting 9 working days (now P2). Limits: a holding reply from us stops the clock (category and deadline rules cover it); a chase restarts it.
- Alternative rejected: count from the first unanswered outside message — harder to state; here 1–2 days more on 7 threads, no priority changed.

**D-34 One pipeline run at a time; a cut-off reply says so**
- Decision: `POST /run` returns 409 while another run holds a lock. A reply stopped at `max_tokens` is not parsed: one retry, then review, with that cause stored.
- Why: overlapping runs write one SQLite file and pay twice for the same threads; a truncated reply was reported as "not a single JSON object".
- Alternative rejected: a lock row in SQLite (would also cover the CLI) — more code for a single-user demo.

**D-35 Company names match whole domain words** (revises D-30)
- Decision: domain names split on hyphens and digits; a question word matches a word it equals or, with 5+ letters, starts.
- Why: substrings let "city" match steelcity-bodyshop and "care" physiocarescotland. No eval top hit changed (two questions retrieve differently; the stored Q&A answers predate this); Harper Broking now ties with Harper Vale.
- Alternative rejected: exact words only — "bridgegate" would miss bridgegatebrokers.

## Interface

**D-36 Three screens, a thread replaces the list, Previous / Next** (keeps D-31: no router)
- Decision: Workload, Thread and Ask stay separate screens. A thread replaces the list; "Thread 3 of 50 in your list" with Previous / Next walks the list in screen order, and Back returns focus to the row that opened it.
- Why: at 1366×768 a list-and-reading-pane split leaves a ~360 px list that cuts the action summaries and reasons. One screen at a time has one focus model and is simpler to read and test.
- Alternative rejected: a list + reading-pane workspace — two focus modes, independent scrolling panes, more state.

**D-37 The workload is one list in sections, most urgent first**
- Decision: sections in a fixed order: P1 · Act today, P2 · This week, Needs a check, P3 · Normal, then P4 · No action needed and Not claims work, folded. Each keeps the API's order; the first row is tagged "Start here". Empty sections say so in one sentence.
- Why: position answers "what first?". Needs a check sits after This week because review threads are stored at P2; at 0 it reads as the safety net working. Folding the 18 no-action rows lets the 32 that need action fill the screen.
- Alternative rejected: a flat six-column table; sections cut where the level changes (would bury review threads inside P2).

**D-38 Python decides a thread's card and which rules set its priority**
- Decision: each row carries `card` (the same function as the summary counts) and `reasons`: rules_fired split into rule and detail, with `sets_level` marking the rules behind the level (`priority.reasons()`, which also builds the explanation). The API shapes move to schemas.py.
- Why: the UI groups by card and shows the deciding rules without copying policy (D-31); the card counts always equal the section sizes (tested).
- Alternative rejected: map level and bucket to a card, and pick the deciding rules, in TypeScript.

**D-39 One filter per concept**
- Decision: the six count cards are the only priority filter (toggle buttons); one Line of business control; rows are fetched once and filtered in the browser on stored fields. A sentence says what is shown.
- Why: the cards and the Bucket and Level chips filtered the same list two ways, and "bucket" vs "level" is an internal split (review is bucket review at level P2).
- Alternative rejected: keep the chip rows; a server round trip per filter.

**D-40 Words first; one (i) per concept for the definition**
- Decision: every badge, number and code reads on its own ("P1 · Act today", "13 working days", plain rule names from labels.ts). One (i) button per concept opens the browser's native popover: click, tap, Enter or a short mouse hover; Esc or a click outside closes it. Raw codes stay in the audit record.
- Why: the old hover-only "why" failed on touch and keyboard and was clipped by the table. The native popover gives dismissal, one bubble at a time, top-layer display and screen-reader state with no dependency.
- Alternative rejected: title attributes, CSS hover tooltips, a tooltip library.

**D-41 Help text quotes thresholds from GET /summary**
- Decision: `/summary` returns `policy` (confidence threshold, deadline windows, waiting days), read from config per request; help definitions are functions of it.
- Why: config.py stays the one source; change a threshold and the help changes. A grep keeps the numbers out of the frontend.
- Alternative rejected: copy 0.6, 2, 7 and 5 into TypeScript, or write help with no numbers.

**D-42 Thread page in decision order**
- Decision: suggested next step (with "a suggestion only" and who is waiting); "Why it is P1 · Act today", set by the rules, split into the rules that decided it and those also true; the emails; "How the AI read it", a suggestion with its confidence and threshold; the audit record, folded.
- Why: a handler reads what to do, why, and the proof, in that order, and sees that rules decide and the AI suggests.
- Alternative rejected: emails first with the triage fields beside them (the old page).

**D-43 Refusals read "No answer given"**
- Decision: a neutral card shows the stored sentence and a tip; no confidence. Example questions fill the box instead of sending.
- Why: the API refuses for no evidence, no valid citation or an unusable reply, so a title claiming "the mailbox doesn't say" could be false. Each question is a paid call.
- Alternative rejected: an amber "No answer from the mailbox" (amber also meant P2).

**D-44 Calm visual system from one set of tokens**
- Decision: hex colour tokens in one @theme block with measured AA contrast; a white header; one blue accent for interaction only; each state has its own words and icon shape, P1 the only filled icon and row bar, Needs a check a dashed border; system font; borders over shadows.
- Why: red and amber, and violet and blue, look alike to colour-blind users, so shape and words carry the meaning. Tailwind's palette is not used for states, so the measured ratios hold.
- Alternative rejected: hue-only pills; a web font (a third-party request, and no offline demo).

**D-45 Motion in CSS only; no new dependency**
- Decision: 150–200 ms transitions and entrances on shared easings; movement only when the user allows motion (otherwise fades); no count-up numbers, no spinner during a re-run. Icons are inline SVG.
- Why: motion explains a change and never delays reading; every effect is one class from one file.
- Alternative rejected: Motion (about +45 KB gzip and new concepts); anime.js; React's view transitions (block clicks while running).

**D-46 Re-run controls live under "About this data"**
- Decision: models, prompt and rules versions, last run and the as-of date sit in a folded panel with "Re-run triage"; re-reading every thread asks for confirmation; the result line stays outside the panel. An empty database says "No emails loaded yet"; unread threads get a notice, and zeros read "none among the threads read so far".
- Why: a demo control was the page's main button, and a paid run was one tick away.
- Alternative rejected: a primary Run button with a tick box and a quoted cost.

**D-47 Ask always reads the open workload (qa_v2)** (supersedes the "no match, no model call" part of D-29)
- Decision: every question goes to Sonnet with the open workload (only an empty mailbox, with no match and no open work, is refused without a call): each thread that needs a person, in the rules' order, one line with its priority, the rules that set it, the wait and the next step. The emails that match the question come with it, each thread tagged with the same line. Prompt qa_v2 says priorities and their order come from the rules: report them, never re-rank. qa_v1 is kept.
- Why: "Which is the most relevant thread to focus on?" is a handler's first question, and keyword search could not answer it: its words match no email, and the model never saw the priorities. Now answers agree with the Workload and the ranking stays policy (D-01). Eval: 11/11, including two new workload questions.
- Alternative rejected: a word list that routes "priority" questions to the workload (breaks on any wording it lacks); letting the model rank threads itself (judgement replacing policy). Cost: every question now calls the model (~10k input tokens, about $0.02).

**D-48 One type scale: five sizes, two weights, one font** (extends D-44)
- Decision: the theme defines only 12, 14, 16, 20 and 24 px and weights 400 and 600; Tailwind's own scales are cleared, so nothing else can be used. Reading text (next step, answers, emails) is 16 px, the interface 14, small print 12, titles 20, counts 24. List titles are regular weight; monospace is left only for raw AI output, rule codes and error details.
- Why: the screens mixed eight sizes (12–28 px), three weights and two fonts, so nothing read as more important than anything else.
- Alternative rejected: Tailwind's full scale plus a style note (nothing enforces it); a web font (D-44: a third-party request, no offline demo).

**D-49 Say each thing once; definitions live under "About this data"** (revises D-40)
- Decision: the "suggestions only" promise appears once, in the header. Subtitles that repeated it are gone; titles carry the source instead ("Set by the priority rules:", "The AI's reading", "AI answer"). What each group means, the as-of date and the sender's flag are listed once under About this data, still quoting the API's thresholds (D-41). One (i) is left: "Waiting on us", the number whose rule a handler needs where it appears.
- Why: the same caveat appeared six times and a page had up to nine (i) buttons; repetition made the screens dense and each warning weaker.
- Alternative rejected: an (i) beside every concept (D-40); dropping the definitions (a handler still needs them once).

**D-50 The workload uses the width and starts higher** (revises details of D-37 and D-39)
- Decision: the page grows to 1536 px (one width token for the header and the content). Each count card puts the count beside its label. One toolbar row holds what the list shows ("50 threads, most urgent first", or "8 of 50 threads: Motor" with Clear filters), the line-of-business dropdown and About this data. Next steps are cut to two lines (the full text is on the thread page), and empty groups stay out of the list unless their card is chosen.
- Why: on a wide screen the list used half the width, two sentences repeated what the order and "Start here" already said, and empty groups took a header and a sentence each. On a 2560 × 1318 window the first row moved up from 446 to 330 px, and 9 rows show without scrolling instead of 7.
- Alternative rejected: a split view with the list and the open thread side by side (a second layout to build and test; listed in docs/techdebt.md); five toggle buttons for the line of business (a dropdown is one control).

**D-51 Ask says what it does in one line; the answer sits beside its sources**
- Decision: the three "It can / It can't / Check it" boxes become a short note under the question box (only this mailbox and the priority rules, cited emails, no attachments, no actions, every question logged); four example questions show the rest. On wide screens the answer sits beside its sources and the search behind them, and the page shares the workload's left edge.
- Why: the boxes held about 30 words that the examples and the cited sources already show, and the answer and its sources were stacked in a 768 px column on a 2560 px screen.
- Alternative rejected: folding the boxes after the first question (one more control to open); a full-width answer (lines too long to read).

**D-52 "What should I focus on?" names the top three open threads, then the P1 count**
- Decision: prompt qa_v3 (qa_v2 plus three changes). A question about what to focus on or do first, even one asking for "the most relevant thread", gets the first three workload threads in the rules' order, one line each (claim ref or sender, what to do, why now in plain words), then the number of P1 threads. Matched threads that do not answer are left out, unmentioned. The code opens the workload with a count line ("Open threads: 32; P1 (act today): 21."). The eval gains q12, and q10 now expects the top three. Builds on D-47.
- Why: one thread is too little to plan a day, and the old answer spent a sentence on a FOS summary that matched only the word "relevant". Counting is code's job: the model reads the number instead of counting 32 lines. Eval ($0.27): q10 and q12 name the top three in order and "21 P1 threads"; q8 dropped the broker's rebrand (words 24/25), probably the cost of "leave out what does not answer".
- Alternative rejected: the model counts the P1 lines (an off-by-one is easy and hard to spot); "relevant" and "focus" as retrieval stop words (would shift the other answers, tuned on this retrieval; the prompt alone fixes the answer).

**D-53 Colour for scanning: a header band, tinted section headers, coloured card edges**
- Decision: three uses of colour, all tokens in index.css with their contrast noted. A deep-blue header band on every screen (white text 8.72:1, secondary text 7.15:1); its controls get a white focus outline, because the accent outline would vanish on it (1.30:1). Each section header is filled with its state's soft colour (the chip fills; text at least 6.91:1). Each count card's left edge takes its section's colour (`EDGE`, now shared by cards, headers and the decision band; `TINT` sits beside it in PriorityBadge.tsx). Words and icon shapes still carry every state.
- Why: the screen was white and black, so groups were told apart only by their header text. Now a group's start shows while scrolling, and the cards double as the list's legend. The page background already had a faint tint, so it stays.
- Alternative rejected: tinting whole rows or the page (busier, and long text reads worse on a tint); coloured counts beyond P1 (a second label for numbers that already have words).

**D-54 Dark mode follows the system setting**
- Decision: the same tokens get dark values under `prefers-color-scheme: dark`; `color-scheme: light dark` themes the native controls; index.html carries `<meta name="darkreader-lock">`. Text on an ink fill uses `text-surface` and the Ask button's text `text-on-accent`, so the (i) bubble, the confirm button, the "Latest email" tag and the Ask button flip with the theme. Every dark pair is AA, the lowest text pair 6.28:1 (noted in index.css).
- Why: many browsers are set to dark, and an extension like Dark Reader recoloured the light app badly (the Ask button lost its fill). One token set per theme keeps every component unchanged.
- Alternative rejected: a light/dark switch (a control and saved state for a preference the system already holds); letting Dark Reader carry on (no control over contrast).

**D-55 No "Start here" tag** (revises D-37)
- Decision: the tag on the first row goes; the first row stays first, under the P1 header.
- Why: position, the P1 header and its count already say what comes first, so the tag was one more word on the busiest screen. A handler who wants a plan asks, and Ask names the top three (D-52).
- Alternative rejected: a quieter marker, such as a bold first row or a "1" (another visual rule to learn).

**D-56 The line of business under each row's priority chip**
- Decision: each row shows Home, Motor, Liability or Not stated under its P chip, from the AI's reading via the API; nothing until the AI has read the thread. The chip cell is hidden from screen readers, so the line joins the row button's name ("P1 · Act today, Home: …") and is heard once.
- Why: the handler covers three lines and the dropdown filters by them, but a row did not say its line until opened. The chip column has room at every width.
- Alternative rejected: a seventh column (the row already has six, and it would vanish on small screens); a colour per line (hue already marks the priority states).

**D-57 A "Dark mode" toggle in the header** (revises D-54)
- Decision: one toggle button on the header band, "Dark mode" (pressed means dark; the name never changes). The first visit follows the system setting; a click saves the choice in this browser (if storage is blocked, it lasts until a reload). A few lines in index.html set `<html data-theme>` before the first paint, and index.css keys the same dark tokens on `[data-theme="dark"]`.
- Why: one click switches the theme without touching Windows or Chrome settings, for a demo, a contrast check, or a handler who wants light on a dark system.
- Alternative rejected: System / Light / Dark (a third state in a dropdown; clearing the saved choice returns to the system); applying the saved choice in React only (the page would first flash the system theme).

## Process and stack

**D-58 Publish how it was built**
- Decision: the repo carries the process files: the brief (AGENT_BRIEF.md), the agent's rules and entry point (AGENTS.md, CLAUDE.md), the build log (docs/session.md), facts and gotchas (docs/memory.md), and the docs check with its hooks. Only the interview demo script and `.env` stay local. The README gains "How this was built".
- Why: a reviewer can see how the work was planned, directed and verified, not only the result.
- Alternative rejected: code and reviewer docs only, as first published on 3 October (hides the process behind the code).

**D-59 One model provider: Claude for both jobs** (extends D-02; recorded at the end, chosen with the stack)
- Decision: triage and Q&A both use Anthropic's Claude through its official SDK; no second vendor, no local model.
- Why: one SDK, and one third party receiving the mailbox's personal data (one data processing agreement in production). `llm.py` is the only file that calls the API, and the golden labels and the eval do not depend on the model, so trying another one is a contained change plus an eval run.
- Alternative rejected: another vendor such as OpenAI or Google (not benchmarked here; a second SDK and processor for no measured gain); a local open-source model (keeps the data in-house, a real plus for PII, but every reviewer would need the hardware and the download, and it would need its own evaluation; worth testing if data-residency rules demand it).

**D-60 Call the SDK directly; no LLM framework** (recorded at the end, chosen with the stack)
- Decision: every model call goes through `llm.call_json` (one `messages.create`, parsing, schema check, one retry); triage and Q&A are plain functions that call it. No LangChain, LlamaIndex or agent framework.
- Why: the app makes two fixed kinds of call, one per thread and one per question, with no tools, chains or agents to orchestrate; every request, retry and audit row can be read in one 160-line file.
- Alternative rejected: LangChain or an agent framework (more concepts and dependencies to explain, and each request hidden behind abstractions).

**D-61 Ask is centred on the page** (revises D-51's shared left edge)
- Decision: the heading and question box form one centred 768 px block; the answer and its sources a centred 1024 px column below it.
- Why: on a wide screen the left-aligned page left most of the width empty on one side, and the owner found it lopsided. Ask is a reading page, not a list, so it need not share the Workload's left edge.
- Alternative rejected: keep the shared left edge (D-51); one centred column with the question box at its left (it still looked left-weighted before the first answer).
