import type { Conversation, Memory, Message, Status, StreamEvent } from "../types";
import { SseParser } from "./sse";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  } catch {
    throw new Error("Can't reach the backend. Make sure it's running (see the README), then try again.");
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  status: () => request<Status>("/status"),
  conversations: () => request<Conversation[]>("/conversations"),
  createConversation: () => request<Conversation>("/conversations", { method: "POST" }),
  conversation: (id: string) => request<Conversation & { messages: Message[] }>(`/conversations/${id}`),
  deleteConversation: (id: string) => request<{ ok: boolean }>(`/conversations/${id}`, { method: "DELETE" }),
  memories: () => request<Memory[]>("/memories"),
  addMemory: (text: string) => request<Memory>("/memories", { method: "POST", body: JSON.stringify({ text }) }),
  deleteMemory: (id: string) => request<{ ok: boolean }>(`/memories/${id}`, { method: "DELETE" }),
  disconnect: (source: string) => request<Status>(`/connections/${source}`, { method: "DELETE" }),
  connectUrl: (source: string) => `/api/connect/${source}`,
};

/** Sends a question and calls `onEvent` for each step of the agent's work as it streams in. */
export async function ask(conversationId: string, content: string, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    throw new Error("Can't reach the backend. Make sure it's running, then try again.");
  }
  if (!res.ok || !res.body) throw new Error(`The question wasn't sent (${res.status}).`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const { event, data } of parser.push(decoder.decode(value, { stream: true }))) {
      onEvent({ type: event, data } as StreamEvent);
    }
  }
}
