// Mirrors the backend's domain models (backend/app/models.py) the API's response shapes (backend/app/schemas.py)
// and the pipeline's run report (backend/app/pipeline.py, RunSummary).

export type Level = "P1" | "P2" | "P3" | "P4";
export type Bucket = "act" | "review" | "archive" | "ignore";
export type LineOfBusiness = "home" | "motor" | "liability" | "unknown";
export type Category = "action_required" | "informational" | "irrelevant";
export type Rating = "high" | "medium" | "low";
export type ActionType =
  | "respond" | "approve_authorise" | "investigate" | "chase_third_party"
  | "open_new_claim" | "review_document" | "escalate" | "none";
export type SenderType =
  | "customer" | "broker" | "repairer_supplier" | "solicitor" | "loss_adjuster" | "internal" | "automated" | "unknown";
export type Signal =
  | "fnol" | "injury" | "make_safe_urgent" | "complaint" | "legal_threat" | "regulatory" | "fraud_flag"
  | "vulnerable_customer" | "repeat_chase" | "payment_or_authority_pending" | "already_resolved"
  | "parse_error"; // set by the code when the model's reply was unusable or the call failed
/** The dashboard card a thread counts towards; the API decides it (one definition with /summary). */
export type Card = "P1" | "P2" | "P3" | "review" | "archive" | "ignore" | "untriaged";

export interface Attachment {
  filename: string;
  filesize: number;
  filetype: string;
}

export interface Message {
  message_id: string;
  sent_from: string;
  sent_to: string[];
  sent_cc: string[];
  date_sent: string;
  subject: string;
  body: string;
  attachments: Attachment[];
  importance_flag: string | null;
  from_internal: boolean; // sent by Pinnacle staff
}

export interface TriageResult {
  category: Category;
  action_type: ActionType;
  action_summary: string;
  claim_ref: string | null;
  line_of_business: LineOfBusiness;
  sender_type: SenderType;
  urgency: Rating;
  importance: Rating;
  deadline_mentioned: string | null;
  signals: Signal[];
  confidence: number;
  reasoning: string;
}

export interface TriageRecord {
  result: TriageResult;
  raw_response: string;
  model: string;
  prompt_version: string;
  request_id: string | null;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
  created_at: string | null;
}

export interface PriorityResult {
  level: Level | null;
  bucket: Bucket;
  rules_fired: string[];
  explanation: string;
  waiting_days: number; // working days the latest outside sender has waited on us; 0 when we wrote last
}

/** One entry of rules_fired split for display; sets_level marks the rules behind the level (decided in Python). */
export interface Reason {
  rule: string;
  detail: string; // "" when the entry has no detail
  sets_level: boolean;
}

export interface ThreadRow {
  key: string;
  subject: string;
  sender: string;
  message_count: number;
  first_date: string;
  last_date: string;
  age_days: number;
  waiting_days: number; // from the stored priority; 0 before the first priority
  claim_ref: string | null;
  category: Category | null;
  sender_type: SenderType | null;
  line_of_business: LineOfBusiness | null;
  action_summary: string;
  level: Level | null;
  bucket: Bucket | null;
  card: Card;
  explanation: string;
  rules_fired: string[];
  reasons: Reason[];
}

export interface AuditEntry {
  id: number;
  created_at: string;
  event: string;
  detail: Record<string, unknown>;
}

export interface ThreadDetail {
  thread: ThreadRow;
  messages: Message[];
  triage: TriageRecord | null;
  priority: PriorityResult | null;
  audit: AuditEntry[];
}

/** The priority rules' thresholds, from backend config, so help text never copies them. */
export interface Policy {
  confidence_threshold: number;
  p1_deadline_days: number;
  p2_deadline_days: number;
  unanswered_working_days: number;
}

export interface Summary {
  total_threads: number;
  counts: Record<string, number>; // P1, P2, P3 (act bucket), review, archive (= P4), ignore, untriaged
  last_run: string | null;
  models: string[];
  prompt_versions: string[];
  rules_versions: string[]; // rules behind the stored priorities
  as_of: string;
  policy: Policy;
}

export interface Citation {
  thread_key: string;
  message_id: string;
  subject: string;
  sent_from: string;
  date_sent: string;
}

export interface RetrievedThread {
  thread_key: string;
  subject: string;
  score: number;
  reasons: string[];
}

export interface QAAnswer {
  answer: string;
  citations: Citation[];
  confidence: number;
  refused: boolean;
  retrieved: RetrievedThread[];
}

export interface RunSummary {
  threads: number;
  triaged: number;
  skipped: number;
  fallbacks: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  priorities: Record<string, number>;
}
