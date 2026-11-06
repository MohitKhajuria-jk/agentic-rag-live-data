import { useEffect, useMemo, useRef, type FormEvent, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Brain, BrainCircuit, MessageSquareMore, Plus, Send, Sparkle } from "lucide-react";
import type { Message, Status } from "../types";
import { citationNumber, linkCitations } from "../lib/citations";
import { SOURCE_META } from "./ui";

export const STARTERS = [
  { label: "Search my emails", prompt: "Search my emails for " },
  { label: "Find something in Notion", prompt: "Find in my Notion pages: " },
  { label: "Remember this for later", prompt: "Remember that " },
];

function Answer({ message, onCite }: { message: Message; onCite: (n: number) => void }) {
  const bySource = useMemo(() => new Map(message.cited.map((c) => [c.n, c])), [message.cited]);
  const markdown = useMemo(() => linkCitations(message.content, new Set(bySource.keys())), [message.content, bySource]);
  return (
    <div className="answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const n = citationNumber(href);
            const card = n !== null ? bySource.get(n) : undefined;
            if (card) {
              return (
                <button
                  type="button"
                  className={`cite cite-${card.source}`}
                  title={`${SOURCE_META[card.source].name}: ${card.title}`}
                  aria-label={`Source ${card.n}: ${card.title}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onCite(card.n);
                  }}
                >
                  {card.n}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

function Avatar() {
  return (
    <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-line-strong bg-bg-2">
      <BrainCircuit size={20} color="url(#brand)" aria-hidden />
    </span>
  );
}

export function MessageView({ message, selected, onSelect, onCite }: { message: Message; selected: boolean; onSelect: () => void; onCite: (n: number) => void }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end [animation:rise_160ms_ease-out]">
        <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-[linear-gradient(135deg,#7c3aed,#4f46e5)] px-4 py-2.5 text-white shadow-[0_10px_30px_-14px_rgb(124_58_237/0.9)]">
          {message.content}
        </p>
      </div>
    );
  }
  const sources = message.cited.length;
  return (
    <article className="flex min-w-0 gap-3 [animation:rise_160ms_ease-out]">
      <Avatar />
      <div
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && e.target === e.currentTarget && (e.preventDefault(), onSelect())}
        aria-pressed={selected}
        aria-label="Show how this answer was found"
        className={`min-w-0 flex-1 cursor-pointer rounded-2xl rounded-tl-md border px-4 py-3 transition-colors ${
          selected ? "border-violet/60 bg-panel-2" : "border-line bg-bg-2/60 hover:border-line-strong"
        }`}
      >
        <Answer message={message} onCite={onCite} />
        {(sources > 0 || message.steps.length > 0) && (
          <p className="mt-2 text-xs font-medium text-faint">
            {sources ? `${sources} ${sources === 1 ? "source" : "sources"} cited` : "No sources needed"}
            {message.steps.length ? ` · ${message.steps.length} ${message.steps.length === 1 ? "step" : "steps"}` : ""}
            {selected ? " · shown in the trace" : " · click to see the trace"}
          </p>
        )}
      </div>
    </article>
  );
}

export function ChatPanel(props: {
  status: Status | null;
  messages: Message[];
  running: boolean;
  liveText: string | null;
  memoryNotes: string[];
  selectedId: Message["id"] | null;
  onSelect: (id: Message["id"]) => void;
  onCite: (messageId: Message["id"], n: number) => void;
  draft: string;
  onDraft: (v: string) => void;
  onSend: (text: string) => void;
  onNewChat: () => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const empty = !props.messages.length && !props.running;
  const online = props.status?.llm.ready;

  // Keep the newest message in view by scrolling only the chat list (never the whole page).
  useEffect(() => {
    const el = scroller.current;
    if (!el || empty) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [props.messages.length, props.running, props.memoryNotes.length, empty]);

  useEffect(() => {
    const el = props.inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [props.draft, props.inputRef]);

  function submit(e: FormEvent) {
    e.preventDefault();
    props.onSend(props.draft);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      props.onSend(props.draft);
    }
  }

  function applyStarter(prompt: string) {
    props.onDraft(prompt);
    requestAnimationFrame(() => {
      const el = props.inputRef.current;
      el?.focus();
      el?.setSelectionRange(prompt.length, prompt.length);
    });
  }

  return (
    <section className="panel flex min-h-[32rem] min-w-0 flex-col lg:min-h-0" aria-label="AI chat">
      <header className="flex items-center gap-3 border-b border-line px-5 py-4">
        <span className="grid size-10 place-items-center rounded-xl bg-[linear-gradient(135deg,#8b5cf6,#6366f1)]">
          <MessageSquareMore size={22} className="text-white" aria-hidden />
        </span>
        <h2 className="whitespace-nowrap text-lg font-bold">AI Chat</h2>
        <div className="ml-auto flex items-center gap-2">
          {props.messages.length > 0 && (
            <button className="btn btn-ghost min-h-0 whitespace-nowrap px-3 py-1.5 text-sm" onClick={props.onNewChat} aria-label="New chat" title="New chat">
              <Plus size={16} aria-hidden />
              <span className="hidden min-[420px]:inline">New chat</span>
            </button>
          )}
          <span className={`pill ${online ? "bg-green-soft text-green" : "bg-red-soft text-red"}`} title={props.status?.llm.label}>
            <span className="pill-dot" aria-hidden />
            {props.status ? (online ? "Online" : "Setup needed") : "Connecting"}
          </span>
        </div>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        {empty ? (
          <div className="flex min-h-full flex-col items-center justify-center-safe py-6 text-center">
            <span className="relative grid size-24 place-items-center">
              <span className="absolute inset-2 rounded-full bg-indigo/25 blur-xl" aria-hidden />
              <BrainCircuit size={76} strokeWidth={1.5} color="url(#brand)" className="relative" aria-hidden />
            </span>
            <h3 className="mt-4 text-2xl font-bold sm:text-[1.7rem]">Welcome to Agentic RAG!</h3>
            <p className="mt-2 max-w-md text-muted sm:text-[1.05rem]">Ask anything about your data. I'll find it, reason about it and answer with sources.</p>
            {props.status && !props.status.llm.ready && (
              <p className="mt-4 max-w-md rounded-xl bg-red-soft px-4 py-3 text-sm text-red">
                Add your Gemini API key as <code className="font-mono">LLM_API_KEY</code> in <code className="font-mono">backend/.env</code>, then restart the backend.
              </p>
            )}
            <ul className="mt-7 flex flex-wrap justify-center gap-2.5">
              {STARTERS.map((s) => (
                <li key={s.label}>
                  <button
                    onClick={() => applyStarter(s.prompt)}
                    className="flex items-center gap-2 rounded-full border border-line-strong bg-panel-2/80 px-4 py-2.5 text-sm font-semibold transition-colors hover:border-violet hover:bg-panel-2"
                  >
                    <Sparkle size={16} color="url(#spark)" fill="url(#spark)" aria-hidden />
                    {s.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-5">
            {props.messages.map((m) => (
              <MessageView
                key={m.id}
                message={m}
                selected={m.id === props.selectedId}
                onSelect={() => props.onSelect(m.id)}
                onCite={(n) => props.onCite(m.id, n)}
              />
            ))}
            {props.memoryNotes.map((t) => (
              <p key={t} className="ml-12 flex items-center gap-2 rounded-xl bg-memory-soft px-3 py-2 text-sm font-medium text-memory">
                <Brain size={15} aria-hidden /> Remembered: {t}
              </p>
            ))}
            {props.running && (
              <div className="flex items-center gap-3" aria-live="polite">
                <Avatar />
                <span className="flex items-center gap-2 rounded-2xl rounded-tl-md border border-line bg-bg-2/60 px-4 py-3 text-sm text-muted">
                  <span className="flex gap-1" aria-hidden>
                    {[0, 1, 2].map((i) => (
                      <span key={i} className="size-1.5 rounded-full bg-violet [animation:pulse-dot_1s_ease-in-out_infinite]" style={{ animationDelay: `${i * 150}ms` }} />
                    ))}
                  </span>
                  {props.liveText ?? "Thinking…"}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      <form onSubmit={submit} className="border-t border-line p-3 sm:p-4">
        <div className="flex items-end gap-2 rounded-2xl border border-line-strong bg-bg-2/80 p-2 pl-4 transition-colors focus-within:border-violet focus-within:shadow-glow">
          <label htmlFor="composer" className="sr-only">
            Ask a question
          </label>
          <textarea
            id="composer"
            ref={props.inputRef}
            rows={1}
            value={props.draft}
            onChange={(e) => props.onDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question…"
            className="max-h-[180px] min-h-11 flex-1 resize-none bg-transparent py-2.5 placeholder:text-faint focus:outline-none"
          />
          <button
            type="submit"
            className="grid size-11 shrink-0 place-items-center rounded-xl bg-[linear-gradient(135deg,#a855f7,#6366f1)] text-white shadow-[0_8px_24px_-10px_rgb(168_85_247/0.9)] transition hover:brightness-110 disabled:opacity-40"
            disabled={!props.draft.trim() || props.running}
            aria-label="Send"
          >
            <Send size={19} className="-translate-x-px translate-y-px" aria-hidden />
          </button>
        </div>
        <p className="mt-1.5 px-1 text-xs text-faint">Enter to send · Shift+Enter for a new line · read-only access to your sources</p>
      </form>
    </section>
  );
}
