import { useState } from "react";
import { BrainCircuit, Database, Info, MessageSquareMore, Plug, Settings, Sparkle, Trash2, X } from "lucide-react";
import type { Conversation, Status } from "../types";
import { formatWhen } from "./ui";

export type View = "chat" | "integrations" | "memory" | "settings" | "about";

const NAV: Array<{ view: View; label: string; Icon: typeof BrainCircuit }> = [
  { view: "chat", label: "Chat", Icon: MessageSquareMore },
  { view: "integrations", label: "Integrations", Icon: Plug },
  { view: "memory", label: "Memory", Icon: Database },
  { view: "settings", label: "Settings", Icon: Settings },
  { view: "about", label: "About", Icon: Info },
];

export function Sidebar(props: {
  view: View;
  onView: (v: View) => void;
  status: Status | null;
  conversations: Conversation[];
  activeId: string | null;
  onOpenConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onClose?: () => void;
}) {
  const [confirm, setConfirm] = useState<string | null>(null);
  const provider = (props.status?.llm.provider ?? "Gemini").replace(/^Google\s+/, "");
  const model = props.status?.llm.using_fallback ? props.status.llm.fallback_model : props.status?.llm.model;

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-[linear-gradient(180deg,#0e1434,#0b1029)] px-4 pb-4 pt-6">
      {props.onClose && (
        <button className="absolute right-3 top-3 grid size-9 place-items-center rounded-lg text-muted hover:bg-panel-2" onClick={props.onClose} aria-label="Close menu">
          <X size={20} />
        </button>
      )}
      <div className="px-3">
        <span className="relative mx-auto mb-3 grid size-20 place-items-center">
          <span className="absolute inset-2 rounded-full bg-violet/30 blur-xl" aria-hidden />
          <BrainCircuit size={70} strokeWidth={1.6} color="url(#brand)" className="relative" aria-hidden />
        </span>
        <p className="text-2xl font-extrabold tracking-tight">Agentic RAG</p>
        <p className="mt-0.5 text-sm leading-snug text-muted">Your Personal Knowledge Assistant</p>
      </div>

      <nav aria-label="Main" className="mt-7 grid gap-1.5">
        {NAV.map(({ view, label, Icon }) => {
          const active = props.view === view;
          return (
            <button
              key={view}
              onClick={() => props.onView(view)}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3.5 rounded-2xl px-4 py-3 text-[0.98rem] font-semibold transition-colors ${
                active
                  ? "border border-violet/50 bg-[linear-gradient(120deg,#4c2ea8,#3b2a8f_60%,#2f2a7a)] text-white shadow-[0_10px_30px_-14px_rgb(139_92_246/0.9)]"
                  : "border border-transparent text-muted hover:bg-panel hover:text-ink"
              }`}
            >
              <Icon size={22} className={active ? "text-[#c4b5fd]" : ""} aria-hidden />
              {label}
            </button>
          );
        })}
      </nav>

      <div className="mt-6 flex min-h-0 flex-1 flex-col">
        <p className="px-4 text-xs font-bold tracking-wide text-faint">Recent chats</p>
        <ul className="mt-2 grid min-h-0 grid-cols-[minmax(0,1fr)] content-start gap-0.5 overflow-y-auto" aria-label="Recent chats">
          {props.conversations.length === 0 && <li className="px-4 text-sm text-faint">Your chats will appear here.</li>}
          {props.conversations.slice(0, 30).map((c) => (
            <li key={c.id} className="group relative">
              {confirm === c.id ? (
                <div className="flex items-center gap-1 rounded-xl bg-red-soft px-3 py-1.5 text-sm">
                  <span className="min-w-0 flex-1 truncate font-semibold text-red">Delete chat?</span>
                  <button className="rounded px-2 py-1 font-semibold text-red hover:bg-red hover:text-[#2a0707]" onClick={() => (setConfirm(null), props.onDeleteConversation(c.id))}>
                    Delete
                  </button>
                  <button className="rounded px-2 py-1 hover:bg-panel-2" onClick={() => setConfirm(null)}>
                    Keep
                  </button>
                </div>
              ) : (
                <>
                  <button
                    onClick={() => props.onOpenConversation(c.id)}
                    aria-current={c.id === props.activeId && props.view === "chat" ? "true" : undefined}
                    className={`w-full rounded-xl px-4 py-2 pr-10 text-left text-sm ${c.id === props.activeId ? "bg-panel-2 text-ink" : "text-muted hover:bg-panel hover:text-ink"}`}
                  >
                    <span className="block truncate font-medium">{c.title}</span>
                    <span className="block text-xs text-faint">{formatWhen(c.updated_at)}</span>
                  </button>
                  <button
                    className="absolute right-2 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-md text-faint opacity-0 hover:text-red focus:opacity-100 group-hover:opacity-100"
                    onClick={() => setConfirm(c.id)}
                    aria-label={`Delete chat: ${c.title}`}
                  >
                    <Trash2 size={15} />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="relative z-10 mt-4 flex items-center gap-3 rounded-2xl border border-[#3b4aa8]/70 bg-[linear-gradient(135deg,#1d2a7a,#18205a)] px-4 py-3.5" title={props.status?.llm.label}>
        <Sparkle size={28} color="url(#spark)" fill="url(#spark)" className="shrink-0" aria-hidden />
        <div className="min-w-0 leading-tight">
          <p className="text-sm text-indigo-100/80">Powered by</p>
          <p className="text-lg font-bold">{provider}</p>
          {model && <p className="truncate text-xs text-indigo-200/70">{model}</p>}
        </div>
      </div>
      <svg className="pointer-events-none absolute -bottom-2 left-0 h-28 w-full" viewBox="0 0 250 110" preserveAspectRatio="none" aria-hidden>
        <defs>
          <linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#7c3aed" stopOpacity="0.55" />
            <stop offset="1" stopColor="#3b82f6" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        <path d="M0 40 C 60 10, 120 70, 250 50 L250 110 L0 110 Z" fill="url(#wave)" />
        <path d="M0 70 C 70 40, 140 95, 250 75 L250 110 L0 110 Z" fill="#6d28d9" opacity="0.35" />
      </svg>
    </div>
  );
}
