// Mirrors the backend's Pydantic models (backend/app/models.py) and the API's response shapes.

export type Level = "P1" | "P2" | "P3" | "P4";
export type Bucket = "act" | "review" | "archive" | "ignore";
export type LineOfBusiness = "home" | "motor" | "liability" | "unknown";
export type Category = "action_required" | "informational" | "irrelevant";

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
  action_type: string;
  action_summary: string;
  claim_ref: string | null;
  line_of_business: LineOfBusiness;
  sender_type: string;
  urgency: "high" | "medium" | "low";
  importance: "high" | "medium" | "low";
  deadline_mentioned: string | null;
  signals: string[];
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
}

export interface ThreadRow {
  key: string;
  subject: string;
  sender: string;
  message_count: number;
  first_date: string;
  last_date: string;
  age_days: number;
  claim_ref: string | null;
  category: Category | null;
  sender_type: string | null;
  line_of_business: LineOfBusiness | null;
  action_summary: string;
  level: Level | null;
  bucket: Bucket | null;
  explanation: string;
  rules_fired: string[];
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

export interface Summary {
  total_threads: number;
  counts: Record<string, number>; // P1, P2, P3 (act bucket), review, archive (= P4), ignore, untriaged
  last_run: string | null;
  models: string[];
  prompt_versions: string[];
  rules_version: string;
  as_of: string;
}

export interface Citation {
  thread_key: string;
  message_id: string;
  subject: string;
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

export interface Filters {
  bucket?: Bucket;
  level?: Level;
  lob?: LineOfBusiness;
}
