"""Every setting the backend depends on, in one place.

Why: model names, prompt versions, thresholds and paths are policy and
operational choices. Keeping them together makes them easy to review and
change, and the audit trail quotes them (each stored LLM result records the
model and prompt version taken from here).
"""

from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# --- Paths -------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATA_PATH = REPO_ROOT / "data" / "emails_candidate.json"
DB_PATH = BACKEND_DIR / "triage.db"  # SQLite file; rebuilt by the pipeline, gitignored
PROMPTS_DIR = BACKEND_DIR / "app" / "prompts"

# --- Secrets -----------------------------------------------------------------
# The Anthropic SDK reads ANTHROPIC_API_KEY from the environment. Load it from
# the repo-root .env file; a variable already set in the shell wins.
load_dotenv(REPO_ROOT / ".env")

# --- Models ------------------------------------------------------------------
TRIAGE_MODEL = "claude-haiku-4-5"  # one call per thread: small, fast, cheap
QA_MODEL = "claude-sonnet-5-5"  # free-text questions: reasons across threads, cites sources
TRIAGE_MAX_TOKENS = 1024  # the JSON reply is ~300 tokens
# Temperature 0 for repeatable judgements (D-18). SDK 1.x dropped the `temperature` argument, but
# Haiku 4.5 still honours the field, so it goes into the raw request body.
TRIAGE_OPTIONS = {"extra_body": {"temperature": 0}}
QA_MAX_TOKENS = 16000  # Sonnet 5.5 always thinks; thinking counts towards this limit
QA_OPTIONS = {"output_config": {"effort": "medium"}}  # thinking depth: a balance of answer quality and speed
QA_TOP_K = 12  # most threads handed to the Q&A model
QA_MIN_RELATIVE_SCORE = 0.1  # drop threads scoring under a tenth of the best match
# USD per million tokens (input, output), for the cost estimate printed by the pipeline.
PRICE_PER_MTOK = {"claude-haiku-4-5": (1.00, 5.00), "claude-sonnet-5-5": (2.00, 10.00)}

# --- Prompt versions (files in app/prompts/) ----------------------------------
TRIAGE_PROMPT_VERSION = "triage_v2"  # v1 kept for comparison (backend/eval/results.md)
QA_PROMPT_VERSION = "qa_v3"  # v3: "what to focus on" names the top 3 (D-52); v2 adds the workload (D-47)

# --- Priority policy (the rules themselves are in app/priority.py) ----------
PRIORITY_RULES_VERSION = "rules_v2"  # bump when a rule changes; stored with every priority
CONFIDENCE_THRESHOLD = 0.6  # below this a human reviews the item (bucket "review")
P1_DEADLINE_DAYS = 2  # a deadline overdue or due within this many days -> P1
P2_DEADLINE_DAYS = 7  # due within this many days -> P2
UNANSWERED_WORKING_DAYS = 5  # latest message from outside, waiting on us longer than this -> P2
# "Today" for waiting times and deadlines. The dataset ends on 2026-02-20, so
# both are measured from there. In production this would be date.today().
AS_OF_DATE = date(2026, 2, 20)
INTERNAL_DOMAIN = "pinnacle-insurance.co.uk"  # senders on this domain are "us"

# --- API -----------------------------------------------------------------------
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # Vite dev server, allowed by CORS
