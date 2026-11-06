import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BrainCircuit, Menu } from "lucide-react";
import type { Conversation, Message, SourceName, Status, Step } from "./types";
import { api, ask } from "./lib/api";
import { ChatPanel } from "./components/Thread";
import { AboutPage, IntegrationsPage, MemoryPage, SettingsPage, SourcesCard, TracePanel } from "./components/Panels";
import { Hero, StatusCards } from "./components/Hero";
import { Sidebar, type View } from "./components/Sidebar";
import { GradientDefs, SOURCE_META, Toast } from "./components/ui";

interface Pending {
  question: string;
  steps: Step[];
  memories: string[];
  startedAt: number;
}

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState<Pending | null>(null);
  const [selectedId, setSelectedId] = useState<Message["id"] | null>(null);
  const [durations, setDurations] = useState<Record<string, number>>({});
  const [flash, setFlash] = useState<{ n: number; at: number } | null>(null);
  const [draft, setDraft] = useState("");
  const [view, setView] = useState<View>("chat");
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; tone: "info" | "error" } | null>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  const notify = useCallback((message: string, tone: "info" | "error" = "info") => setToast({ message, tone }), []);
  const refreshStatus = useCallback(() => api.status().then(setStatus, (e) => notify((e as Error).message, "error")), [notify]);
  const refreshConversations = useCallback(() => api.conversations().then(setConversations, () => undefined), []);
  const setMemoryCount = useCallback((n: number) => setStatus((s) => (s && s.memories !== n ? { ...s, memories: n } : s)), []);

  useEffect(() => {
    void refreshStatus();
    void refreshConversations();
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const error = params.get("error");
    if (connected) notify(`${SOURCE_META[connected as SourceName]?.name ?? connected} is connected. The agent will search it live from now on.`);
    if (error) notify(error, "error");
    if (connected || error) history.replaceState(null, "", window.location.pathname);
  }, [refreshStatus, refreshConversations, notify]);

  function go(v: View) {
    setView(v);
    setMenuOpen(false);
  }

  async function openConversation(id: string) {
    go("chat");
    if (id === activeId) return;
    setActiveId(id);
    setMessages([]);
    setSelectedId(null);
    try {
      const conv = await api.conversation(id);
      setMessages(conv.messages);
      const last = [...conv.messages].reverse().find((m) => m.role === "assistant");
      setSelectedId(last?.id ?? null);
    } catch (err) {
      notify((err as Error).message, "error");
    }
  }

  function newChat() {
    go("chat");
    setActiveId(null);
    setMessages([]);
    setSelectedId(null);
    setTimeout(() => input.current?.focus(), 0);
  }

  async function removeConversation(id: string) {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (id === activeId) newChat();
    } catch (err) {
      notify((err as Error).message, "error");
    }
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || pending) return;
    setDraft("");
    let cid = activeId;
    try {
      if (!cid) {
        const conv = await api.createConversation();
        cid = conv.id;
        setActiveId(cid);
        setConversations((prev) => [conv, ...prev]);
      }
    } catch (err) {
      setDraft(question);
      notify((err as Error).message, "error");
      return;
    }
    const startedAt = Date.now();
    setPending({ question, steps: [], memories: [], startedAt });
    let failed = false;
    try {
      await ask(cid, question, (event) => {
        switch (event.type) {
          case "user":
            setMessages((prev) => [...prev, event.data]);
            break;
          case "step":
          case "step_done":
            setPending((p) => {
              if (!p) return p;
              const others = p.steps.filter((s) => s.id !== event.data.step.id);
              return { ...p, steps: [...others, event.data.step].sort((a, b) => a.id - b.id) };
            });
            break;
          case "memory_saved":
            setPending((p) => (p ? { ...p, memories: [...p.memories, event.data.text] } : p));
            break;
          case "answer":
            setMessages((prev) => [...prev, event.data]);
            setSelectedId(event.data.id);
            setDurations((d) => ({ ...d, [String(event.data.id)]: (Date.now() - startedAt) / 1000 }));
            break;
          case "error":
            failed = true;
            setMessages((prev) => (prev.length && prev[prev.length - 1].role === "user" && prev[prev.length - 1].content === question ? prev.slice(0, -1) : prev));
            setDraft(question);
            notify(event.data.message, "error");
            break;
        }
      });
    } catch (err) {
      failed = true;
      setDraft(question);
      notify((err as Error).message, "error");
    } finally {
      setPending(null);
      void refreshConversations();
      if (!failed) void refreshStatus();
    }
  }

  const selected = useMemo(() => messages.find((m) => m.id === selectedId && m.role === "assistant") ?? null, [messages, selectedId]);
  const running = pending !== null;
  const traceSteps = running ? pending.steps : selected?.steps ?? [];
  const liveText = useMemo(() => {
    if (!pending) return null;
    const active = [...pending.steps].reverse().find((s) => s.status === "running");
    if (active) return `${active.label}…`;
    return pending.steps.length ? "Writing the answer from what it found…" : "Planning where to look…";
  }, [pending]);

  const sidebarProps = {
    view,
    onView: go,
    status,
    conversations,
    activeId,
    onOpenConversation: openConversation,
    onDeleteConversation: removeConversation,
  };

  return (
    <div className="flex h-dvh overflow-hidden">
      <GradientDefs />
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ink focus:px-3 focus:py-2 focus:text-bg">
        Skip to content
      </a>
      <aside className="hidden w-[15.5rem] shrink-0 border-r border-line lg:block">
        <Sidebar {...sidebarProps} />
      </aside>
      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMenuOpen(false)} aria-hidden />
          <aside className="absolute inset-y-0 left-0 w-[min(17rem,85vw)] border-r border-line shadow-glow">
            <Sidebar {...sidebarProps} onClose={() => setMenuOpen(false)} />
          </aside>
        </div>
      )}

      <main id="main" className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-3 sm:p-5 lg:overflow-hidden">
        <div className="flex items-center gap-3 lg:hidden">
          <button className="grid size-10 place-items-center rounded-xl border border-line bg-panel" onClick={() => setMenuOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <BrainCircuit size={26} color="url(#brand)" aria-hidden />
          <span className="font-extrabold">Agentic RAG</span>
        </div>

        {view === "chat" ? (
          <>
            <Hero compact={messages.length > 0 || running} />
            <StatusCards status={status} onOpen={(v) => go(v)} />
            <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] xl:grid-cols-[minmax(0,1fr)_25rem]">
              <ChatPanel
                status={status}
                messages={messages}
                running={running}
                liveText={liveText}
                memoryNotes={pending?.memories ?? []}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onCite={(id, n) => {
                  setSelectedId(id);
                  setFlash({ n, at: Date.now() });
                }}
                draft={draft}
                onDraft={setDraft}
                onSend={send}
                onNewChat={newChat}
                inputRef={input}
              />
              <div className="grid min-h-0 min-w-0 content-start gap-4 lg:grid-rows-[auto_minmax(0,1fr)] lg:overflow-y-auto">
                <TracePanel
                  steps={traceSteps}
                  running={running}
                  answered={!running && selected !== null}
                  seconds={selected && !running ? durations[String(selected.id)] ?? null : null}
                  cited={selected?.cited.length ?? 0}
                />
                <SourcesCard messageId={running ? null : selected?.id ?? null} cited={running ? [] : selected?.cited ?? []} flash={flash} />
              </div>
            </div>
          </>
        ) : !status ? (
          <p className="panel p-6 text-muted">Loading…</p>
        ) : view === "integrations" ? (
          <IntegrationsPage status={status} onStatus={setStatus} notify={notify} />
        ) : view === "memory" ? (
          <MemoryPage onCount={setMemoryCount} notify={notify} />
        ) : view === "settings" ? (
          <SettingsPage status={status} />
        ) : (
          <AboutPage />
        )}
      </main>
      {toast && <Toast message={toast.message} tone={toast.tone} onDone={() => setToast(null)} />}
    </div>
  );
}
