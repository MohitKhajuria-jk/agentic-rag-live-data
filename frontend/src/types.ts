export type SourceName = "gmail" | "notion";

/** An email or page the agent retrieved, numbered for citation within a conversation. */
export interface SourceCard {
  n: number;
  source: SourceName;
  item_id: string;
  title: string;
  url: string | null;
  author: string | null;
  date: string | null;
  snippet: string;
  demo: boolean;
}

export interface Step {
  id: number;
  tool: string;
  label: string;
  status: "running" | "done" | "error";
  summary?: string;
}

export interface Message {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  steps: Step[];
  cited: SourceCard[];
  created_at: number;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

export interface Memory {
  id: string;
  text: string;
  created_at: number;
}

export interface SourceStatus {
  connected: boolean;
  demo: boolean;
  label: string | null;
  can_connect: boolean;
  setup_hint: string | null;
  /** Set by an internal integration token in .env, so it can't be disconnected from the app. */
  fixed: boolean;
}

export interface Status {
  llm: {
    ready: boolean;
    label: string;
    provider?: string;
    model?: string;
    fallback_model?: string | null;
    using_fallback?: boolean;
    reasoning_effort?: string;
    embedding_model?: string | null;
    semantic_search: boolean;
  };
  sources: Record<SourceName, SourceStatus>;
  demo_mode: boolean;
  memories: number;
}

export type StreamEvent =
  | { type: "user"; data: Message }
  | { type: "step"; data: { step: Step } }
  | { type: "step_done"; data: { step: Step } }
  | { type: "memory_saved"; data: { text: string } }
  | { type: "answer"; data: Message }
  | { type: "error"; data: { message: string } }
  | { type: "done"; data: Record<string, never> };
