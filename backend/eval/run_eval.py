"""Score triage, priority and Q&A against hand-written expectations, and write eval/results.md.

Usage (from backend/, after `python -m app.pipeline`):  python -m eval.run_eval [--qa]
Every prompt version's triage is rebuilt from the audit log, so versions can be
compared without calling the model again; priorities are recomputed with the
current rules. --qa asks the Q&A questions afresh (12 Sonnet calls, ~$0.28); without
it, the latest audited answers are re-scored. This module and one leak test are
the only code that reads thread_id: here only to count how many golden labels
differ from the seeds that the thread_id prefixes imply.
"""

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app import config, qa, store
from app.ingest import load_threads
from app.models import Thread, TriageResult
from app.priority import compute_priority

EVAL_DIR = Path(__file__).resolve().parent
GOLDEN_PATH = EVAL_DIR / "golden_labels.json"
QUESTIONS_PATH = EVAL_DIR / "qa_questions.json"
RESULTS_PATH = EVAL_DIR / "results.md"
CATEGORIES = ("action_required", "informational", "irrelevant")
SEED_BY_PREFIX = {"hom": "action_required", "mtr": "action_required", "lia": "action_required",
                  "gen": "action_required", "info": "informational", "irr": "irrelevant"}


@dataclass
class Score:
    """How one prompt version did on the golden set."""

    version: str
    correct: int = 0
    total: int = 0
    confusion: Counter[tuple[str, str]] = field(default_factory=Counter)
    misclassified: list[tuple[str, str, TriageResult]] = field(default_factory=list)  # key, golden, result
    missed_actions: list[str] = field(default_factory=list)  # golden action archived or ignored, no review
    over_p1: list[str] = field(default_factory=list)  # P1 but not expected
    under_p1: list[str] = field(default_factory=list)  # expected P1 but not P1
    true_p1: int = 0
    distribution: Counter[str] = field(default_factory=Counter)


def seed_labels(data_path: Path | None = None) -> dict[str, str]:
    """The label implied by each thread's source thread_id prefix, by thread key (eval only)."""
    data_path = data_path or config.DATA_PATH
    raw = json.loads(data_path.read_text(encoding="utf-8"))["emails"]
    threads = load_threads(data_path)  # same order as the file
    return {t.key: SEED_BY_PREFIX[entry["messages"][0]["thread_id"].split("_")[1]]
            for entry, t in zip(raw, threads)}


def results_by_version(db_path: Path | None = None) -> dict[str, dict[str, TriageResult]]:
    """The latest triage result per thread for every prompt version, rebuilt from the audit log."""
    conn = store.connect(db_path)
    rows = conn.execute("SELECT thread_key, detail FROM audit_log "
                        "WHERE event IN ('triage', 'triage_error') ORDER BY id").fetchall()
    conn.close()
    by_version: dict[str, dict[str, TriageResult]] = {}
    for row in rows:
        detail = json.loads(row["detail"])
        by_version.setdefault(detail["prompt_version"], {})[row["thread_key"]] = TriageResult(**detail["result"])
    return by_version


def score(version: str, results: dict[str, TriageResult], golden: dict[str, Any],
          threads: dict[str, Thread], now: date) -> Score:
    """Compare one version's results with the golden labels; priorities come from the current rules."""
    s = Score(version=version, total=len(golden))
    for key, gold in golden.items():
        triage = results[key]
        priority = compute_priority(triage, threads[key], now)
        s.confusion[(gold["category"], triage.category)] += 1
        s.distribution[priority.level if priority.bucket == "act" else priority.bucket] += 1
        if triage.category == gold["category"]:
            s.correct += 1
        else:
            s.misclassified.append((key, gold["category"], triage))
        if gold["category"] == "action_required" and priority.bucket in ("archive", "ignore"):
            s.missed_actions.append(key)
        is_p1 = priority.bucket == "act" and priority.level == "P1"
        s.true_p1 += is_p1 and gold["expected_p1"]
        if is_p1 != gold["expected_p1"]:
            (s.over_p1 if is_p1 else s.under_p1).append(key)
    return s


def pct(part: int, whole: int) -> str:
    """'n/m (p%)', or 'n/a' when there is nothing to divide by."""
    return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "n/a"


def summary_table(scores: list[Score], expected_p1: int) -> list[str]:
    """Markdown rows comparing every prompt version on the headline numbers."""
    lines = ["| Prompt | Category accuracy | Missed actions | P1 precision | P1 recall | Distribution |",
             "|---|---|---|---|---|---|"]
    for s in scores:
        predicted_p1 = s.true_p1 + len(s.over_p1)
        dist = ", ".join(f"{k} {v}" for k, v in sorted(s.distribution.items()))
        lines.append(f"| {s.version} | {pct(s.correct, s.total)} | {len(s.missed_actions)} | "
                     f"{pct(s.true_p1, predicted_p1)} | {pct(s.true_p1, expected_p1)} | {dist} |")
    return lines


def detail_section(s: Score, golden: dict[str, Any]) -> list[str]:
    """Confusion matrix, misclassified threads with the model's reasoning, and P1 differences."""
    lines = [f"## Details for {s.version}", "", "Rows: golden label. Columns: predicted.", "",
             "| | " + " | ".join(CATEGORIES) + " |", "|---" * (len(CATEGORIES) + 1) + "|"]
    for gold in CATEGORIES:
        lines.append(f"| **{gold}** | " + " | ".join(str(s.confusion[(gold, p)]) for p in CATEGORIES) + " |")
    lines += ["", "**Misclassified threads**", ""]
    lines += [f"- `{key}` {golden[key]['subject']}: expected {gold}, got {r.category} "
              f"(confidence {r.confidence:.2f}). Model: {r.reasoning}" for key, gold, r in s.misclassified] or ["- none"]
    lines += ["", "**P1 differences** (expected_p1 vs the rules applied to this version's signals)", ""]
    lines += [f"- Over-prioritised (P1, not expected): `{k}` {golden[k]['subject']}" for k in s.over_p1]
    lines += [f"- Under-prioritised (expected P1): `{k}` {golden[k]['subject']}" for k in s.under_p1]
    if not s.over_p1 and not s.under_p1:
        lines.append("- none")
    return lines


def ask_all(questions: list[dict[str, Any]]) -> None:
    """Ask every eval question through qa.answer: real model calls, each written to the audit log."""
    conn = store.connect()
    try:
        for q in questions:
            result = qa.answer(q["question"], conn)
            print(f"{q['id']}: {'refused' if result.refused else 'answered'}, {len(result.citations)} citation(s)")
    finally:
        conn.close()


def latest_answers(questions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The most recent audited answer to each eval question, by question text."""
    conn = store.connect()
    rows = conn.execute("SELECT detail FROM audit_log WHERE event = 'ask' ORDER BY id").fetchall()
    conn.close()
    wanted = {q["question"] for q in questions}
    latest = {}
    for row in rows:
        detail = json.loads(row["detail"])
        if detail["question"] in wanted:
            latest[detail["question"]] = detail
    return latest


def qa_section(questions: list[dict[str, Any]], latest: dict[str, dict[str, Any]],
               refs_by_key: dict[str, list[str]]) -> list[str]:
    """Markdown for the Q&A results: a check row per question, then every answer in full."""
    prompts = ", ".join(sorted({d["prompt_version"] for d in latest.values() if d.get("prompt_version")})) or "none"
    lines = ["## Q&A", "", f"Model {config.QA_MODEL}, prompt {prompts}, top {config.QA_TOP_K} "
             "threads. Refusal: refused exactly when expected. Refs: expected claim refs among the cited threads. "
             "Words: must-mention words found in the answer. Retrieval settings were tuned on these questions.", "",
             "| # | Question | Refusal | Refs | Words | Seconds |", "|---|---|---|---|---|---|"]
    answers = []
    for q in questions:
        detail = latest.get(q["question"])
        if detail is None:
            lines.append(f"| {q['id']} | {q['question']} | not asked yet | | | |")
            continue
        a = detail["answer"]
        cited = {ref for c in a["citations"] for ref in refs_by_key.get(c["thread_key"], [])}
        words = sum(w.lower() in a["answer"].lower() for w in q["must_mention"])
        ok = "yes" if a["refused"] == q["expect_refusal"] else "**no**"
        lines.append(f"| {q['id']} | {q['question']} | {ok} | {len(cited & set(q['expected_refs']))}/"
                     f"{len(q['expected_refs'])} | {words}/{len(q['must_mention'])} | {detail.get('seconds', '')} |")
        answers.append(f"- **{q['id']}** {'(refused) ' if a['refused'] else ''}{a['answer']} "
                       f"_[{len(a['citations'])} citation(s)]_")
    return [*lines, "", "**Answers**", "", *answers]


def render(scores: list[Score], golden: dict[str, Any], seed_changes: list[str], qa_lines: list[str]) -> str:
    """The whole results.md: headline table, provenance and caveats, per-version details, then Q&A."""
    expected_p1 = sum(g["expected_p1"] for g in golden.values())
    lines = ["# Evaluation results", "",
             f"Written by `run_eval.py` on {store.now_iso()[:10]}; regenerate it, do not edit it. "
             f"Model {config.TRIAGE_MODEL}, rules {config.PRIORITY_RULES_VERSION}, as-of {config.AS_OF_DATE}, "
             f"{len(golden)} threads, {expected_p1} expected P1.", "",
             *summary_table(scores, expected_p1), "",
             "- **Missed actions**: golden action_required threads the system archived or ignored without a "
             "human review — the costliest error.",
             "- **P1 precision / recall**: against `expected_p1`, the hand label for 'act today if every "
             "signal and deadline were read correctly'.",
             f"- **Golden labels**: seeded from thread_id prefixes, then every thread hand-checked: "
             f"{len(seed_changes)} of {len(golden)} seeds changed{': ' + ', '.join(seed_changes) if seed_changes else ''}. "
             "Judgement calls are noted in golden_labels.json.",
             "- **Caveats**: 50 threads; labels by the developer, not independent annotators; a later prompt "
             "version tuned on these same threads scores optimistically.", ""]
    for s in scores:
        lines += [*detail_section(s, golden), ""]
    return "\n".join([*lines, *qa_lines])


def main() -> None:
    """Score every prompt version and the latest Q&A answers (asking afresh with --qa); write results.md."""
    parser = argparse.ArgumentParser(description="Evaluate triage, priority and Q&A.")
    parser.add_argument("--qa", action="store_true", help="ask the Q&A questions again (Sonnet calls)")
    args = parser.parse_args()
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["labels"]
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    threads = {t.key: t for t in load_threads()}
    seeds = seed_labels()
    seed_changes = [key for key, g in golden.items() if g["category"] != seeds[key]]
    complete = {v: r for v, r in sorted(results_by_version().items()) if set(golden) <= set(r)}
    scores = [score(v, r, golden, threads, config.AS_OF_DATE) for v, r in complete.items()]
    if not scores:
        raise SystemExit("No complete triage run in the database: run `python -m app.pipeline` first.")
    if args.qa:
        ask_all(questions)
    qa_lines = qa_section(questions, latest_answers(questions), {k: t.claim_refs for k, t in threads.items()})
    RESULTS_PATH.write_text(render(scores, golden, seed_changes, qa_lines) + "\n", encoding="utf-8")
    print("\n".join(summary_table(scores, sum(g["expected_p1"] for g in golden.values()))))
    print("\n".join(line for line in qa_lines if line.startswith("| q")))
    print(f"Wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
