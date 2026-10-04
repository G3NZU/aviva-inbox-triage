# Evaluation results

Written by `run_eval.py` on 2026-10-04; regenerate it, do not edit it. Model claude-haiku-4-5, rules rules_v2, as-of 2026-02-20, 50 threads, 18 expected P1.

| Prompt | Category accuracy | Missed actions | P1 precision | P1 recall | Distribution |
|---|---|---|---|---|---|
| triage_v1 | 50/50 (100%) | 0 | 17/20 (85%) | 17/18 (94%) | P1 20, P2 10, P3 2, archive 11, ignore 7 |
| triage_v2 | 49/50 (98%) | 0 | 18/21 (86%) | 18/18 (100%) | P1 21, P2 11, archive 10, ignore 8 |

- **Missed actions**: golden action_required threads the system archived or ignored without a human review — the costliest error.
- **P1 precision / recall**: against `expected_p1`, the hand label for 'act today if every signal and deadline were read correctly'.
- **Golden labels**: seeded from thread_id prefixes, then every thread hand-checked: 0 of 50 seeds changed. Judgement calls are noted in golden_labels.json.
- **Caveats**: 50 threads; labels by the developer, not independent annotators; a later prompt version tuned on these same threads scores optimistically.

## Details for triage_v1

Rows: golden label. Columns: predicted.

| | action_required | informational | irrelevant |
|---|---|---|---|
| **action_required** | 32 | 0 | 0 |
| **informational** | 0 | 11 | 0 |
| **irrelevant** | 0 | 0 | 7 |

**Misclassified threads**

- none

**P1 differences** (expected_p1 vs the rules applied to this version's signals)

- Over-prioritised (P1, not expected): `t9546776b` PIN-HOM-533661 - Claim form, tenancy agreement and EOW photos
- Over-prioritised (P1, not expected): `tf108e619` Invoice - PIN-HOM-547299 - Weekend make-safe (tarp)
- Over-prioritised (P1, not expected): `t92438b44` FNOL: 2018 Kia Sportage inundated by tidal surge
- Under-prioritised (expected P1): `tbbecfa7a` Policy query - Mobility scooter stolen from locked shed

## Details for triage_v2

Rows: golden label. Columns: predicted.

| | action_required | informational | irrelevant |
|---|---|---|---|
| **action_required** | 32 | 0 | 0 |
| **informational** | 0 | 10 | 1 |
| **irrelevant** | 0 | 0 | 7 |

**Misclassified threads**

- `t9830a15d` Rebrand notice - Harper & Vale Insurance: expected informational, got irrelevant (confidence 0.95). Model: This is a routine rebrand notification from a broker to its partners, sent to the claims inbox as an FYI. It contains no claim reference, no request for action, and no matter requiring a claims handler's decision or response. It is administrative notice that can be archived.

**P1 differences** (expected_p1 vs the rules applied to this version's signals)

- Over-prioritised (P1, not expected): `t92e8669a` PIN-LIA-744552 - Physiotherapy notes and discharge report
- Over-prioritised (P1, not expected): `tf108e619` Invoice - PIN-HOM-547299 - Weekend make-safe (tarp)
- Over-prioritised (P1, not expected): `t92438b44` FNOL: 2018 Kia Sportage inundated by tidal surge

## Q&A

Model claude-sonnet-5-5, prompt qa_v3, top 12 threads. Refusal: refused exactly when expected. Refs: expected claim refs among the cited threads. Words: must-mention words found in the answer. Retrieval settings were tuned on these questions.

| # | Question | Refusal | Refs | Words | Seconds |
|---|---|---|---|---|---|
| q1 | Was there any action required for Bridgegate Brokers? | yes | 1/1 | 2/2 | 2.8 |
| q2 | What is outstanding on PIN-MTR-552301? | yes | 1/1 | 2/2 | 3.1 |
| q3 | Which threads involve a solicitor? | yes | 2/2 | 3/3 | 3.5 |
| q4 | Are there any new claims (FNOL) that haven't been acknowledged? | yes | 0/0 | 3/3 | 4.1 |
| q5 | Did anyone raise a fraud concern? | yes | 1/1 | 1/1 | 2.5 |
| q6 | What internal notices affect how I work this month? | yes | 0/0 | 2/2 | 3.2 |
| q7 | Is there anything about a flooded vehicle? | yes | 0/0 | 2/2 | 2.5 |
| q8 | What did Harper Broking ask us to do? | yes | 1/1 | 1/2 | 3.2 |
| q9 | What did Zenith Brokers ask us to do? | yes | 0/0 | 0/0 | 1.9 |
| q10 | Which is the most relevant thread to focus on? | yes | 2/2 | 3/3 | 2.9 |
| q11 | Who has been waiting longest for a reply from us? | yes | 1/1 | 2/2 | 3.6 |
| q12 | tell me the most relevant thread to focus on | yes | 2/2 | 3/3 | 3.0 |

**Answers**

- **q1** Yes. Bridgegate Brokers sent the claim form, tenancy agreement and escape of water photos for PIN-HOM-533661 (Aberdeen AB10, policyholder Mr J. Fraser) on 2 February. They asked Pinnacle to confirm cover and excess and advise next steps for the initial assessment, and later that day added the tenant's contact number. Pinnacle has not replied, so the broker has waited 14 working days. This is a P2 thread (act this week). The next step is to confirm cover and excess to Bridgegate and set out the plan for the initial assessment. _[2 citation(s)]_
- **q2** Two items are outstanding on PIN-MTR-552301, and both are P1 (act today). 1) Steel City Bodyshop accepted mixed parts (OEM sensors and loom, aftermarket bumper) on 11 February and has been waiting 7 working days for written parts authority. Its target completion is today, Friday 20 February, and that deadline is due today. Send the written authority and acknowledge the completion target. 2) QuickFix Garage's invoice of GBP2,186.40 incl. VAT is unconfirmed. Motor Claims forwarded it to Finance on 18 February, but there is no confirmation of payment. QuickFix chased the same day for payment or supplementary authority, because storage charges accrue from Friday 21 February. Confirm payment or supplementary authority to QuickFix. _[6 citation(s)]_
- **q3** Three open threads involve a solicitor. 1) PIN-LIA-752388: Daniel Jameson of Taylor & Sons Solicitors alleges a data protection breach over mis-sent documents. He asked for confirmation by close of business on 19 February that the breach process has started and the unintended recipient has been contacted. The thread is 1 day overdue and Pinnacle has not replied. 2) PIN-LIA-771045: Kirsty MacLeod of Caledonia Law, acting for the claimant, is waiting for Pinnacle's indemnity position and timetable after serving the orthopaedic report on 8 February. Pinnacle's only reply (18 February) asked for the report, which she had already served, so it does not settle her request. 3) The Hayes Street Café, Cardiff (CF10) slip-and-fall of 12 February has no claim reference yet. Rhys Williams of Morgan Rowe Solicitors, acting for Ms Angharad Davies, gave notice of claim and wants acknowledgement and Pinnacle's indemnity position. He has waited 6 working days. _[6 citation(s)]_
- **q4** Yes. Four new claim notifications (FNOL) are still open with no reply from Pinnacle:
1. James Turner (motor, 2018 Kia Sportage flooded by tidal surge in Morecambe): sent 3 February, waiting 13 working days. The claim still needs registering, with recovery and a hire car arranged.
2. Mhairi Smith (home, storm-damaged listed cottage roof on Skye): sent 7 February, waiting 10 working days. The claim needs opening and an emergency make-safe arranged.
3. Amelia Hartley (home, kitchen fire in Headingley): sent 10 February, waiting 8 working days. The claim needs registering, with emergency clean-up and accommodation support.
4. Nathan Bradley (motor, stolen Renault Trafic van with tools): sent 15 February, waiting 5 working days. The claim needs opening, with advice on tools cover and a hire van.
A fifth new notification, the Hayes Street Café slip-and-fall (Cardiff, 12 February), is also unacknowledged. Both the café manager and Morgan Rowe Solicitors have asked for a public liability claim to be opened and for acknowledgement, and the solicitors also want the indemnity position. That thread has waited 6 working days. _[6 citation(s)]_
- **q5** Yes. Pinnacle's Fraud Team raised a concern on PIN-MTR-590234 (Hyundai i40 theft, Gateshead). On 13 February it flagged an unresolved telematics anomaly and asked whether the claim is still on hold and whether a recorded interview with the policyholder has been scheduled. It chased the same day for confirmation. Motor Theft forwarded the question to SIU, but nobody has confirmed the hold or the interview to the Fraud Team. The thread is P1 and the Fraud Team's deadline is 7 days overdue. _[3 citation(s)]_
- **q6** Several internal notices affect your work around this month and the next. Finance: supplier payment runs move from Wednesdays to Tuesdays from next month, with updated cut-off times in the attached notice. Underwriting: the flood excess waiver is withdrawn from next month for high-risk Cumbria postcodes, so expect customer queries and check your messaging. Fraud Team: a list of high-risk repairers and hire firms is circulated, and you should do extra checks when instructing. Legal: a summary of recent FOS subsidence decisions covers root ingress, evidence standards and communication expectations. Compliance: updated personal injury pre-action protocols for Scotland. Scotland Team: the March annual leave rota, with Glasgow and Aberdeen cover. IT Ops: a Guidewire outage on Saturday 22:00-02:00, so use downtime procedures if you work then. _[7 citation(s)]_
- **q7** Yes. James Turner (j.turner79@btinternet.com) reported on 3 February that his 2018 Kia Sportage (FN18 ZJO) was flooded by seawater in a tidal surge in Morecambe. The interior is soaked, the electrics are flickering and the engine won't start. He has no claim reference yet and has waited 13 working days. He needs a new motor claim registered, vehicle recovery and a hire car, and he asked whether it is a total loss or can be decontaminated. This is a P1 thread (act today) because the car needs making safe and the customer is vulnerable. _[1 citation(s)]_
- **q8** Harper Broking (Sam Ramsey) is waiting on us for PIN-HOM-419876 (West Bridgford, subsidence). On 9 Feb they asked for the adjuster's conclusions and contractor mobilisation dates. On 10 Feb they asked for the exact start date and decant arrangements by close on 11 Feb, and, if permits are an issue, for what is outstanding and who is chasing. On 11 Feb they chased: have the permits cleared, what is the mobilisation date, and what are the tenant decant arrangements and likely duration. Our 10 Feb reply gave only a target of w/c 23 Feb pending permits and promised an update by 11 Feb. That does not settle the request, so it is still outstanding and 9 days overdue. Next step: confirm the contractor's mobilisation date, permit status and tenant decant arrangements. _[4 citation(s)]_
- **q9** (refused) I can't find anything about Zenith Brokers in the mailbox. The matched threads are from Bridgegate Brokers, Welsh Cover Brokers and Harper Broking, and none of them is from or about Zenith Brokers. _[0 citation(s)]_
- **q10** Top three threads to focus on, in workload order:
1. PIN-HOM-501772 (Mr and Mrs Howard): send the holding response and action plan and assign a dedicated complaints handler. This is a formal complaint with regulatory risk whose deadline is 17 days overdue.
2. No claim reference (James Turner, motor FNOL): register the new claim and arrange vehicle recovery and a hire car. His Kia Sportage was flooded by a tidal surge, he is a vulnerable customer, and he has waited 13 working days.
3. PIN-HOM-547299 (Caledonian Tree Services): review the arboricultural report and confirm whether sectional dismantling is authorised, or request a second quote. This is an urgent make-safe and the sender has waited 11 working days.

These are 3 of the 21 P1 threads (act today). _[3 citation(s)]_
- **q11** Two threads are tied for the longest wait, at 14 working days each. Bridgegate Brokers (claims@bridgegatebrokers.co.uk) sent the claim form, tenancy agreement and escape of water photos for PIN-HOM-533661 and still need cover and excess confirmed. Nina Patel (Skoda Fabia, Manchester) asked on 2 February about the windscreen chip repair process, NCD impact and preferred supplier, with no claim reference, and has had no reply. Both are P2 threads in the workload. Behind them, James Turner's tidal surge motor FNOL has waited 13 working days and is P1, so it is more urgent despite the shorter wait. _[3 citation(s)]_
- **q12** The first three threads in the workload are:
1. PIN-HOM-501772 - provide the holding response and action plan and assign a dedicated complaints handler. It is a formal complaint with a regulatory risk, and its deadline is 17 days overdue.
2. No claim ref (James Turner, motor) - register the new motor claim for the Kia Sportage hit by the tidal surge, and arrange recovery and a hire car. It is an urgent make-safe case with a vulnerable customer, and he has waited 13 working days.
3. PIN-HOM-547299 (Caledonian Tree Services) - review the arboricultural report and confirm whether sectional dismantling is authorised, or request a second quote. It is an urgent make-safe case, and the sender has waited 11 working days.

These are 3 of the 21 P1 threads (act today). _[3 citation(s)]_
