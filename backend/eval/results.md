# Evaluation results

Written by `run_eval.py` on 2026-10-03; regenerate it, do not edit it. Model claude-haiku-4-5, rules rules_v1, as-of 2026-02-20, 50 threads, 18 expected P1.

| Prompt | Category accuracy | Missed actions | P1 precision | P1 recall | Distribution |
|---|---|---|---|---|---|
| triage_v1 | 50/50 (100%) | 0 | 17/20 (85%) | 17/18 (94%) | P1 20, P2 9, P3 3, archive 11, ignore 7 |
| triage_v2 | 49/50 (98%) | 0 | 18/22 (82%) | 18/18 (100%) | P1 22, P2 9, P3 1, archive 10, ignore 8 |

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

- `t9830a15d` Rebrand notice - Harper & Vale Insurance: expected informational, got irrelevant (confidence 0.95). Model: This is a routine rebrand notification from a broker to its partners, including Pinnacle as a cc. It contains no claim reference, no request for action, and no matter requiring a response. It is administrative information that can be filed for reference.

**P1 differences** (expected_p1 vs the rules applied to this version's signals)

- Over-prioritised (P1, not expected): `t9546776b` PIN-HOM-533661 - Claim form, tenancy agreement and EOW photos
- Over-prioritised (P1, not expected): `t92e8669a` PIN-LIA-744552 - Physiotherapy notes and discharge report
- Over-prioritised (P1, not expected): `tf108e619` Invoice - PIN-HOM-547299 - Weekend make-safe (tarp)
- Over-prioritised (P1, not expected): `t92438b44` FNOL: 2018 Kia Sportage inundated by tidal surge

## Q&A

Model claude-sonnet-5-5, prompt qa_v1, top 12 threads. Refusal: refused exactly when expected. Refs: expected claim refs among the cited threads. Words: must-mention words found in the answer. Retrieval settings were tuned on these questions.

| # | Question | Refusal | Refs | Words | Seconds |
|---|---|---|---|---|---|
| q1 | Was there any action required for Bridgegate Brokers? | yes | 1/1 | 2/2 | 2.8 |
| q2 | What is outstanding on PIN-MTR-552301? | yes | 1/1 | 2/2 | 3.4 |
| q3 | Which threads involve a solicitor? | yes | 2/2 | 3/3 | 3.3 |
| q4 | Are there any new claims (FNOL) that haven't been acknowledged? | yes | 0/0 | 3/3 | 3.7 |
| q5 | Did anyone raise a fraud concern? | yes | 1/1 | 1/1 | 3.0 |
| q6 | What internal notices affect how I work this month? | yes | 0/0 | 2/2 | 3.9 |
| q7 | Is there anything about a flooded vehicle? | yes | 0/0 | 2/2 | 2.4 |
| q8 | What did Harper Broking ask us to do? | yes | 1/1 | 2/2 | 3.3 |
| q9 | What did Zenith Brokers ask us to do? | yes | 0/0 | 0/0 | 1.7 |

**Answers**

- **q1** Yes. Bridgegate Brokers Claims emailed on 2 February 2026 about escape of water claim PIN-HOM-533661 (Mr J. Fraser, Aberdeen AB10), sending the claim form, tenancy agreement and photos. They asked Pinnacle to confirm cover and excess and advise next steps for the initial assessment. They followed up the same day with the tenant's contact number (07783 112909) and repeated the request. The extract shows no reply from Pinnacle, so this is still outstanding. _[2 citation(s)]_
- **q2** Two items are outstanding on PIN-MTR-552301. (1) Steel City Bodyshop accepted the mixed-parts approach on 11 Feb (OEM sensors and loom, aftermarket bumper), gave a target completion of Friday 20 Feb if parts were ordered that day, and asked for written authority so accounts could place orders. Nothing in the mailbox shows Pinnacle sending that written authority; the 11 Feb conditional authority email only asked for acceptance and a date. (2) QuickFix Garage invoiced GBP2,186.40 incl. VAT on 18 Feb, saying storage charges accrue from Friday (20 Feb), and chased again that afternoon for payment confirmation or supplementary authority. Motor Claims forwarded it to Finance (AP) on 18 Feb, but no reply to QuickFix or confirmation of payment appears. Note that two different garages (Steel City and QuickFix) are involved on this reference, and the extract does not explain why. _[5 citation(s)]_
- **q3** Three threads involve solicitors. (1) Data protection breach, PIN-LIA-752388: Daniel Jameson of Taylor & Sons Solicitors alleged a breach on 19 Feb and chased the same day, asking for confirmation by close of business that the breach report process had started and the unintended recipient contacted; no Pinnacle reply appears. (2) CF10 café slip-and-fall, Cardiff: Rhys Williams of Morgan Rowe Solicitors gave notice of a claim for Ms Angharad Davies on 12 Feb, asking for acknowledgement, indemnity position and a claim reference; no Pinnacle reply appears in the extract. (3) PIN-LIA-771045, Leith: Kirsty MacLeod of Caledonia Law asked on 18 Feb and again on 19 Feb for Pinnacle's indemnity position and timetable. Pinnacle's 18 Feb reply only asked for the report to be sent, and it has not yet confirmed the indemnity stance. _[6 citation(s)]_
- **q4** Yes. Five new claim notifications have no reply from Pinnacle in the extract: (1) Amelia Hartley, kitchen fire in Headingley, policy HOM-PL-771932, sent 10 Feb; (2) Mhairi Smith, storm-damaged listed holiday cottage on Skye, policy HOM-HOL-993241, sent 7 Feb and flagged as urgent make-safe; (3) Nathan Bradley Plumbing & Heating, van theft, policy MTR-COM-554872, sent 15 Feb; (4) James Turner, flood-damaged Kia Sportage in Morecambe, policy MTR-PL-239011, sent 3 Feb; (5) Hayes Street Café (Eleri Hughes), slip-and-fall in Cardiff, sent 12 Feb. Morgan Rowe Solicitors also gave notice of a claim from Ms Angharad Davies on 12 Feb about the same café incident and asked for acknowledgement, indemnity position and a claim reference; there is no reply to that either. None of these has been given a claim reference. The extract may not show replies sent outside it. _[6 citation(s)]_
- **q5** Yes. On 13 February Pinnacle's Fraud Team asked the Motor Theft team for a status update on PIN-MTR-590234 (Hyundai i40 theft, Gateshead). They said a telematics anomaly remains unresolved and asked whether the claim is still on hold and whether a recorded interview with the policyholder is booked. They chased the same day for confirmation. Motor Theft forwarded the hold and telematics questions to SIU, and no reply is in the extract, so these remain outstanding. Separately, on 12 February the antifraud team sent SIU a general alert listing high-risk repairers and hire firms, asking for extra checks when instructing. _[4 citation(s)]_
- **q6** Several internal notices bear on this month's work, depending on your team. Finance (3 Feb): supplier payment runs move from Wednesdays to Tuesdays from next month, with updated cut-off times in the attached notice. Underwriting (9 Feb): the flood excess waiver is withdrawn from next month for high-risk Cumbria postcodes, so expect customer queries and check your messaging. Legal (3 Feb): a summary of FOS subsidence decisions was sent to Home Claims with key learning points on root ingress, evidence standards and communication. Anti-fraud (12 Feb): a list of high-risk repairers and hire firms was circulated, and extra checks are required when instructing. Compliance (8 Feb): an overview of updated PI pre-action protocols in Scotland was sent to liability handlers. IT Ops (11 Feb): Guidewire is down on Saturday 22:00-02:00, so use downtime procedures if you work then. The NE amber wind warning (4 Feb) was for 5 Feb and has passed. The Scottish March leave rota (20 Feb) is also in the mailbox, with cover for Glasgow and Aberdeen. Many notices were sent to specific teams, so check which apply to you. _[8 citation(s)]_
- **q7** Yes. On 3 February James Turner reported that his 2018 Kia Sportage (FN18 ZJO, policy MTR-PL-239011) was soaked by seawater in a tidal surge in Morecambe (LA4). The interior is wet, the electrics are flickering and the engine won't start. He attached photos and a video, and asked for the claim to be registered, for recovery to an approved site, for a hire car, and for advice on whether it is a total loss or will be decontaminated. The extract shows no reply from Pinnacle, so those requests appear to be outstanding. _[1 citation(s)]_
- **q8** Harper Broking (Sam Ramsey, now Harper & Vale Insurance) has asked us, on PIN-HOM-419876 (West Bridgford), to confirm the adjuster's conclusions and the contractor mobilisation dates for underpinning, plus tenant decant arrangements and likely duration. On 10 Feb he asked for the exact start date and decant arrangements by close on 11 Feb, and, if permits are an issue, for what is outstanding and who is chasing. On 11 Feb he chased, asking whether permits have been cleared. Pinnacle's 10 Feb reply gave the engineers' recommendation (underpinning the front elevation, target start w/c 23 Feb pending permits, decant of about 2-3 weeks) and promised an update by 11 Feb. That is only a promise of follow-up, and the extract shows no later reply, so the request for the confirmed mobilisation date, permit status and decant arrangements is still outstanding. _[5 citation(s)]_
- **q9** (refused) I can't find anything about Zenith Brokers in the mailbox. The extract only contains emails from Bridgegate Brokers, Welsh Cover Brokers and Harper Broking (now Harper & Vale Insurance), and none mention Zenith Brokers. _[0 citation(s)]_
