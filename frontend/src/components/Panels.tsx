import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  AudioLines, Brain, Check, CircleAlert, Cpu, ExternalLink, FileSearch, FileText, Info, LoaderCircle, Play, Plug, Plus, Search, Settings2, ShieldCheck, Trash2,
} from "lucide-react";
import type { Memory, Message, SourceCard, SourceName, Status, Step } from "../types";
import { api } from "../lib/api";
import { SOURCE_META, SourceIcon, formatWhen } from "./ui";

/* ------------------------------------------------------------------ trace */

type PhaseState = "waiting" | "active" | "done" | "skipped";

interface Phase {
  title: string;
  detail: string;
  state: PhaseState;
  Icon: typeof Search;
  steps: Step[];
}

function useTicker(active: boolean, resetKey: string): number {
  const since = useRef(Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    since.current = Date.now();
    setNow(Date.now());
  }, [resetKey]);
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return Math.max(0, Math.floor((now - since.current) / 1000));
}

function buildPhases(steps: Step[], running: boolean, answered: boolean, waited: number, seconds: number | null, cited: number): Phase[] {
  const searches = steps.filter((s) => s.tool === "search_gmail" || s.tool === "search_notion");
  const reads = steps.filter((s) => s.tool === "read_source" || s.tool === "search_memory");
  const saves = steps.filter((s) => s.tool === "save_memory");
  const anyRunning = steps.some((s) => s.status === "running");
  const idle = !running && !answered;
  const wait = waited >= 3 ? ` ${waited}s` : "";

  const p0: PhaseState = idle ? "active" : steps.length || answered ? "done" : "active";
  let p1: PhaseState = "waiting";
  if (searches.length) p1 = searches.some((s) => s.status === "running") ? "active" : "done";
  else if (answered) p1 = "skipped";
  let p2: PhaseState = "waiting";
  if (reads.some((s) => s.status === "running")) p2 = "active";
  else if (reads.length || (searches.length && !searches.some((s) => s.status === "running"))) p2 = "done";
  else if (answered) p2 = "skipped";
  let p3: PhaseState = "waiting";
  if (answered) p3 = "done";
  else if (running && steps.length && !anyRunning) p3 = "active";
  const p4: PhaseState = answered ? "done" : "waiting";

  return [
    {
      title: "Ready to process your question",
      detail: idle ? "Ask something to start" : p0 === "active" ? `Agent is thinking…${wait}` : "Planned where to look",
      state: p0,
      Icon: Play,
      steps: [],
    },
    {
      title: "Searching your sources",
      detail: p1 === "skipped" ? "Not needed for this question" : searches.length ? `${searches.length} live ${searches.length === 1 ? "search" : "searches"}` : "Gmail and Notion, live",
      state: p1,
      Icon: Search,
      steps: searches,
    },
    {
      title: "Retrieving relevant information",
      detail: p2 === "skipped" ? "Not needed for this question" : reads.length ? "Ranked passages and read sources" : p2 === "done" ? "Ranked the most relevant passages" : "Ranking passages by relevance",
      state: p2,
      Icon: FileSearch,
      steps: reads,
    },
    {
      title: "Generating response",
      detail: p3 === "active" ? `Writing a grounded answer…${wait}` : p3 === "done" ? "Answer written from the sources" : "Grounded in what was found",
      state: p3,
      Icon: Settings2,
      steps: [],
    },
    {
      title: "Finalizing answer",
      detail: answered ? [seconds !== null ? `Done in ${seconds.toFixed(1)}s` : "Done", `${cited} ${cited === 1 ? "source" : "sources"} cited`].join(" · ") : "Checking citations",
      state: p4,
      Icon: Check,
      steps: saves,
    },
  ];
}

const DOT: Record<PhaseState, string> = {
  active: "bg-[linear-gradient(135deg,#a855f7,#6366f1)] text-white shadow-[0_0_0_4px_rgb(139_92_246/0.25)]",
  done: "bg-[#2b3570] text-[#c7d0ff]",
  waiting: "bg-panel-2 text-faint",
  skipped: "bg-panel-2 text-faint",
};

export function TracePanel({ steps, running, answered, seconds, cited }: { steps: Step[]; running: boolean; answered: boolean; seconds: number | null; cited: number }) {
  const waited = useTicker(running, `${running}:${steps.map((s) => s.id + s.status).join(",")}`);
  const phases = buildPhases(steps, running, answered, waited, seconds, cited);
  return (
    <section className="panel min-w-0" aria-label="Agent execution trace">
      <header className="flex items-center gap-3 border-b border-line px-5 py-4">
        <AudioLines size={24} color="url(#brand)" aria-hidden />
        <h2 className="font-bold">Agent Execution Trace</h2>
        <span className={`pill ml-auto ${running ? "bg-green-soft text-green" : "bg-panel-2 text-muted"}`}>
          <span className={`pill-dot ${running ? "[animation:pulse-dot_1s_ease-in-out_infinite]" : ""}`} aria-hidden />
          {running ? "Live" : answered ? "Last answer" : "Idle"}
        </span>
      </header>
      <ol className="px-5 py-4" aria-live={running ? "polite" : undefined}>
        {phases.map((p, i) => (
          <li key={p.title} className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-3 pb-4 last:pb-0">
            {i < phases.length - 1 && <span className={`absolute left-[0.95rem] top-9 bottom-0 w-0.5 ${p.state === "done" ? "bg-[#3b4790]" : "bg-line"}`} aria-hidden />}
            <span className={`relative z-10 grid size-8 place-items-center rounded-full ${DOT[p.state]}`}>
              {p.state === "active" && i > 0 ? <LoaderCircle size={16} className="animate-spin" aria-hidden /> : <p.Icon size={15} fill={p.Icon === Play ? "currentColor" : "none"} aria-hidden />}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className={`font-semibold leading-snug ${p.state === "waiting" || p.state === "skipped" ? "text-muted" : "text-ink"}`}>{p.title}</p>
              <p className={`text-sm ${p.state === "active" ? "text-indigo-200" : "text-faint"}`}>{p.detail}</p>
              {p.steps.length > 0 && (
                <ul className="mt-1.5 grid gap-1">
                  {p.steps.map((s) => (
                    <li key={s.id} className="flex items-start gap-1.5 text-xs text-muted">
                      <span className="mt-0.5 shrink-0">
                        {s.status === "running" ? (
                          <LoaderCircle size={12} className="animate-spin text-violet" aria-label="Working" />
                        ) : s.status === "error" ? (
                          <CircleAlert size={12} className="text-red" aria-label="Failed" />
                        ) : s.tool === "search_gmail" ? (
                          <SourceIcon source="gmail" size={12} />
                        ) : s.tool === "search_notion" ? (
                          <SourceIcon source="notion" size={12} />
                        ) : s.tool.includes("memory") ? (
                          <SourceIcon source="memory" size={12} />
                        ) : (
                          <Check size={12} className="text-cyan" aria-hidden />
                        )}
                      </span>
                      <span className="min-w-0 break-words">
                        {s.label}
                        {s.summary && <span className={s.status === "error" ? "text-red" : "text-faint"}> → {s.summary}</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/* ---------------------------------------------------------------- sources */

export function SourcesCard({ messageId, cited, flash }: { messageId: Message["id"] | null; cited: SourceCard[]; flash: { n: number; at: number } | null }) {
  const [all, setAll] = useState(false);
  useEffect(() => setAll(false), [messageId]);
  useEffect(() => {
    if (flash === null) return;
    if (cited.findIndex((c) => c.n === flash.n) >= 3) setAll(true);
    requestAnimationFrame(() => {
      const el = document.getElementById(`source-${flash.n}`);
      el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      el?.classList.remove("source-flash");
      void el?.offsetWidth;
      el?.classList.add("source-flash");
    });
  }, [flash]);
  const shown = all ? cited : cited.slice(0, 3);
  return (
    <section className="panel flex min-h-0 min-w-0 flex-col" aria-label="Sources">
      <header className="flex items-center gap-3 px-5 pb-2 pt-4">
        <ShieldCheck size={24} className="text-cyan" fill="rgb(34 211 238 / 0.15)" aria-hidden />
        <h2 className="font-bold">Sources</h2>
        {cited.length > 3 && (
          <button className="ml-auto text-sm font-semibold text-[#7aa2ff] hover:text-cyan" onClick={() => setAll((v) => !v)}>
            {all ? "Show fewer" : `View all ${cited.length} →`}
          </button>
        )}
      </header>
      {cited.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center px-6 pb-6 pt-2 text-center">
          <span className="relative mb-3 grid h-16 w-24 place-items-center" aria-hidden>
            <span className="absolute left-1 top-3 h-12 w-16 -rotate-6 rounded-lg bg-[#2b3570]" />
            <span className="absolute right-1 top-3 h-12 w-16 rotate-6 rounded-lg bg-[#2b3570]" />
            <span className="relative grid h-14 w-20 place-items-center rounded-lg bg-[linear-gradient(160deg,#4f62c9,#34428f)]">
              <span className="grid w-12 gap-1.5">
                <span className="h-1 rounded bg-white/60" />
                <span className="h-1 w-9 rounded bg-white/40" />
                <span className="h-1 rounded bg-white/40" />
              </span>
            </span>
          </span>
          <p className="text-sm text-muted">Sources will appear here with citations</p>
        </div>
      ) : (
        <ul className="grid min-h-0 gap-2 overflow-y-auto px-4 pb-4">
          {shown.map((c) => {
            const detail = [c.author?.replace(/<.*?>/, "").trim(), formatWhen(c.date)].filter(Boolean).join(" · ");
            return (
              <li key={c.n} id={`source-${c.n}`} className="rounded-xl border border-line bg-bg-2/70 p-3">
                <div className="flex items-start gap-2.5">
                  <span className={`cite cite-${c.source} mt-0.5 shrink-0`} aria-hidden>
                    {c.n}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-1.5 text-sm font-semibold leading-snug">
                      <SourceIcon source={c.source} size={14} />
                      <span className="truncate">{c.title}</span>
                    </p>
                    {detail && <p className="truncate text-xs text-faint">{detail}</p>}
                    {c.snippet && <p className="mt-1 line-clamp-2 text-xs text-muted">{c.snippet}</p>}
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      {c.demo && <span className="rounded bg-amber-soft px-1.5 text-xs font-semibold text-amber">demo data</span>}
                      {c.url && (
                        <a href={c.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold text-[#7aa2ff] hover:text-cyan">
                          Open in {SOURCE_META[c.source].name} <ExternalLink size={12} aria-hidden />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ pages */

function Page({ title, intro, Icon, children }: { title: string; intro: string; Icon: typeof Search; children: ReactNode }) {
  return (
    <section className="panel min-w-0 p-6 sm:p-8 [animation:rise_180ms_ease-out]">
      <div className="flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-xl bg-[linear-gradient(135deg,#8b5cf6,#6366f1)]">
          <Icon size={22} className="text-white" aria-hidden />
        </span>
        <h1 className="text-2xl font-bold">{title}</h1>
      </div>
      <p className="mt-3 max-w-2xl text-muted">{intro}</p>
      <div className="mt-6 grid gap-4">{children}</div>
    </section>
  );
}

const DESCRIPTIONS: Record<SourceName, string> = {
  gmail: "Searches and reads your email with Gmail's own search, including operators like from: and newer_than:. Read-only.",
  notion: "Searches your Notion pages and reads their content, including nested blocks. Only pages shared with your integration are visible.",
};

export function IntegrationsPage({ status, onStatus, notify }: { status: Status; onStatus: (s: Status) => void; notify: (m: string, tone?: "info" | "error") => void }) {
  const [busy, setBusy] = useState<SourceName | null>(null);
  async function disconnect(name: SourceName) {
    setBusy(name);
    try {
      onStatus(await api.disconnect(name));
      notify(`Disconnected ${SOURCE_META[name].name}`);
    } catch (err) {
      notify((err as Error).message, "error");
    } finally {
      setBusy(null);
    }
  }
  return (
    <Page title="Integrations" Icon={Plug} intro="Connect the places the agent can search. It reads them live for every question, so answers reflect what's there right now.">
      <div className="grid gap-4 md:grid-cols-2">
        {(Object.keys(status.sources) as SourceName[]).map((name) => {
          const s = status.sources[name];
          const meta = SOURCE_META[name];
          const state = s.connected ? { text: "Connected", tone: "bg-green-soft text-green" } : s.demo ? { text: "Demo data", tone: "bg-amber-soft text-amber" } : { text: "Not connected", tone: "bg-panel-2 text-muted" };
          return (
            <div key={name} className="rounded-2xl border border-line bg-bg-2/60 p-5">
              <div className="flex items-center gap-3">
                <span className="grid size-12 place-items-center rounded-xl bg-white">
                  <meta.Icon size={26} className={name === "gmail" ? "text-[#ea4335]" : "text-[#111]"} strokeWidth={2.4} aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="font-bold">{meta.name}</h2>
                  <p className="truncate text-sm text-faint">{s.connected ? s.label : s.demo ? "Using a sample for now" : "Not set up"}</p>
                </div>
                <span className={`pill ${state.tone}`}>
                  <span className="pill-dot" aria-hidden />
                  {state.text}
                </span>
              </div>
              <p className="mt-3 text-sm text-muted">{DESCRIPTIONS[name]}</p>
              <div className="mt-4">
                {s.connected ? (
                  s.fixed ? (
                    <p className="text-sm text-faint">Connected with NOTION_TOKEN in backend/.env. Remove it there to disconnect.</p>
                  ) : (
                    <button className="btn btn-secondary" onClick={() => disconnect(name)} disabled={busy === name}>
                      {busy === name ? "Disconnecting…" : `Disconnect ${meta.name}`}
                    </button>
                  )
                ) : s.can_connect ? (
                  <a className="btn btn-primary" href={api.connectUrl(name)}>
                    Connect {meta.name}
                  </a>
                ) : (
                  <p className="rounded-xl bg-panel-2 px-3 py-2 text-sm">
                    <span className="font-semibold">To connect your own {meta.name}: </span>
                    {s.setup_hint}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="flex items-start gap-2 rounded-2xl bg-panel-2/70 p-4 text-sm">
        <ShieldCheck size={18} className="mt-0.5 shrink-0 text-cyan" aria-hidden />
        <span>
          <span className="font-semibold">Read-only and private.</span> The agent can search and read, and can never send, edit or delete anything. Sign-in tokens are encrypted on this computer, and text inside emails is never treated as instructions.
        </span>
      </p>
    </Page>
  );
}

export function MemoryPage({ onCount, notify }: { onCount: (n: number) => void; notify: (m: string, tone?: "info" | "error") => void }) {
  const [items, setItems] = useState<Memory[] | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.memories().then(setItems, (err) => setError((err as Error).message));
  }, []);
  useEffect(() => {
    if (items) onCount(items.length);
  }, [items, onCount]);

  async function add(e: FormEvent) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    try {
      const m = await api.addMemory(value);
      setItems((prev) => (prev?.some((p) => p.id === m.id) ? prev : [m, ...(prev ?? [])]));
      setText("");
    } catch (err) {
      notify((err as Error).message, "error");
    }
  }

  async function remove(m: Memory) {
    try {
      await api.deleteMemory(m.id);
      setItems((prev) => prev?.filter((p) => p.id !== m.id) ?? null);
      notify("Forgot that");
    } catch (err) {
      notify((err as Error).message, "error");
    }
  }

  return (
    <Page title="Memory" Icon={Brain} intro="Lasting facts you tell the agent, like your role or how you like answers. It recalls the relevant ones in every chat. Delete anything you don't want kept.">
      <form onSubmit={add} className="flex max-w-2xl gap-2">
        <label htmlFor="memory-input" className="sr-only">
          Add a memory
        </label>
        <input
          id="memory-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={300}
          placeholder="e.g. My project review is in Room 304"
          className="min-w-0 flex-1 rounded-xl border border-line-strong bg-bg-2 px-4 py-2.5 placeholder:text-faint focus:border-violet focus:outline-none"
        />
        <button className="btn btn-primary" type="submit" disabled={!text.trim()}>
          <Plus size={18} aria-hidden /> Add
        </button>
      </form>
      {error && <p className="rounded-xl bg-red-soft px-4 py-3 text-sm font-semibold text-red">{error}</p>}
      {items && !items.length && (
        <p className="max-w-2xl rounded-2xl border border-dashed border-line-strong px-4 py-8 text-center text-muted">
          Nothing remembered yet. Tell the agent something like “Remember that I prefer short answers.”
        </p>
      )}
      <ul className="grid max-w-2xl gap-2">
        {items?.map((m) => (
          <li key={m.id} className="flex items-start gap-3 rounded-xl border border-line bg-bg-2/60 px-4 py-3">
            <Brain size={18} className="mt-0.5 shrink-0 text-memory" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="break-words">{m.text}</p>
              <p className="text-xs text-faint">{formatWhen(m.created_at)}</p>
            </div>
            <button className="grid size-8 shrink-0 place-items-center rounded-lg text-faint hover:bg-red-soft hover:text-red" onClick={() => remove(m)} aria-label={`Forget: ${m.text}`}>
              <Trash2 size={16} />
            </button>
          </li>
        ))}
      </ul>
    </Page>
  );
}

function Row({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="grid gap-1 border-b border-line py-3 last:border-0 sm:grid-cols-[14rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm font-semibold text-muted">{label}</dt>
      <dd className="min-w-0">
        <span className="break-words font-medium">{value}</span>
        {hint && <span className="block text-sm text-faint">{hint}</span>}
      </dd>
    </div>
  );
}

export function SettingsPage({ status }: { status: Status }) {
  const llm = status.llm;
  return (
    <Page title="Settings" Icon={Cpu} intro="How the agent is configured. To change anything, edit backend/.env and restart the backend.">
      <dl className="max-w-3xl rounded-2xl border border-line bg-bg-2/60 px-5 py-2">
        <Row label="Model" value={`${llm.provider ?? ""} · ${llm.model ?? "not set"}`} hint="LLM_PROVIDER and LLM_MODEL" />
        <Row
          label="Backup model"
          value={llm.fallback_model ? `${llm.fallback_model}${llm.using_fallback ? " (in use now)" : ""}` : "None"}
          hint="Used automatically for 10 minutes when the main model is overloaded or rate-limited. LLM_FALLBACK_MODEL"
        />
        <Row label="Thinking effort" value={llm.reasoning_effort ?? "provider default"} hint="Low keeps answers fast. LLM_REASONING_EFFORT" />
        <Row
          label="Ranking"
          value={llm.semantic_search ? `Semantic + keyword (${llm.embedding_model})` : "Keyword (BM25)"}
          hint="How retrieved passages are ranked against your question. EMBEDDING_MODEL"
        />
        <Row label="Demo data" value={status.demo_mode ? "On for sources that aren't connected" : "Off"} hint="DEMO_MODE" />
        <Row label="Memories saved" value={String(status.memories)} />
      </dl>
    </Page>
  );
}

export function AboutPage() {
  const steps = [
    ["Plan", "Gemini reads your question and decides what to search, choosing Gmail, Notion or both, and writes the queries."],
    ["Search live", "The Gmail and Notion APIs are queried at question time, so answers reflect what's there right now."],
    ["Retrieve", "Emails and pages are split into passages and ranked against your question with keyword (BM25) and semantic (embedding) search."],
    ["Answer", "The model writes an answer grounded only in those passages, and every fact cites its numbered source."],
    ["Remember", "Lasting facts you share are saved to long-term memory and recalled in later chats."],
  ];
  return (
    <Page title="About Agentic RAG" Icon={Info} intro="An AI agent that answers questions from your live Gmail and Notion data rather than static documents, with long-term memory and cited sources.">
      <ol className="grid max-w-3xl gap-3">
        {steps.map(([title, text], i) => (
          <li key={title} className="flex gap-4 rounded-2xl border border-line bg-bg-2/60 p-4">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,#a855f7,#6366f1)] font-bold text-white">{i + 1}</span>
            <div>
              <h2 className="font-bold">{title}</h2>
              <p className="text-sm text-muted">{text}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="max-w-3xl text-sm text-muted">
        <span className="font-semibold text-ink">Built with</span> Python, FastAPI, Google Gemini (tool calling and embeddings), the Gmail and Notion APIs with OAuth 2.0, SQLite, React, TypeScript and Tailwind CSS.
      </p>
      <p className="flex max-w-3xl items-start gap-2 text-sm text-muted">
        <FileText size={16} className="mt-0.5 shrink-0" aria-hidden />
        Setup steps and architecture details are in the project's README.
      </p>
    </Page>
  );
}
