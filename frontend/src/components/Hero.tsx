import type { ReactNode } from "react";
import { ChevronRight, Database, FileText, Mail, Sparkle, Zap } from "lucide-react";
import type { SourceName, Status } from "../types";

/** A friendly assistant robot, waving. Drawn here so it needs no image file. */
export function Robot({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 230 210" className={className} aria-hidden>
      <defs>
        <linearGradient id="shell" x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#c9d3ff" />
        </linearGradient>
        <linearGradient id="visor" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#101a52" />
          <stop offset="1" stopColor="#070c2c" />
        </linearGradient>
        <radialGradient id="halo" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#7c8cff" stopOpacity="0.55" />
          <stop offset="1" stopColor="#7c8cff" stopOpacity="0" />
        </radialGradient>
        <filter id="eye-glow" x="-1" y="-1" width="3" height="3">
          <feGaussianBlur stdDeviation="3" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <ellipse cx="138" cy="100" rx="100" ry="96" fill="url(#halo)" />
      {/* body */}
      <rect x="86" y="146" width="108" height="90" rx="40" fill="url(#shell)" />
      <circle cx="140" cy="182" r="11" fill="#4f7cff" />
      <circle cx="140" cy="182" r="5" fill="#a5f3fc" />
      {/* waving arm */}
      <g className="origin-[96px_160px] [transform-box:view-box] [animation:wave_3.2s_ease-in-out_infinite]">
        <path d="M96 160 C 74 150, 58 132, 52 110" stroke="#dfe5ff" strokeWidth="16" strokeLinecap="round" fill="none" />
        <g transform="translate(30 66)">
          <rect x="6" y="22" width="34" height="34" rx="14" fill="url(#shell)" />
          <rect x="8" y="2" width="8" height="26" rx="4" fill="url(#shell)" />
          <rect x="17" y="0" width="8" height="26" rx="4" fill="url(#shell)" />
          <rect x="26" y="3" width="8" height="24" rx="4" fill="url(#shell)" />
          <rect x="35" y="10" width="7" height="20" rx="3.5" fill="url(#shell)" />
          <rect x="-4" y="30" width="16" height="9" rx="4.5" fill="url(#shell)" transform="rotate(-25 4 34)" />
        </g>
      </g>
      {/* head */}
      <g className="[animation:float_5s_ease-in-out_infinite]">
        <circle cx="74" cy="92" r="20" fill="#3b6cff" />
        <circle cx="74" cy="92" r="11" fill="#7aa2ff" />
        <circle cx="206" cy="92" r="20" fill="#3b6cff" />
        <circle cx="206" cy="92" r="11" fill="#7aa2ff" />
        <rect x="80" y="26" width="120" height="132" rx="56" fill="url(#shell)" />
        <rect x="94" y="54" width="92" height="74" rx="34" fill="url(#visor)" stroke="#27358a" strokeWidth="2" />
        <g filter="url(#eye-glow)" fill="#39c8ff">
          <rect x="118" y="72" width="13" height="22" rx="6.5" />
          <rect x="149" y="72" width="13" height="22" rx="6.5" />
        </g>
        <path d="M126 106 Q 140 117 154 106" stroke="#39c8ff" strokeWidth="5" strokeLinecap="round" fill="none" filter="url(#eye-glow)" />
        <ellipse cx="116" cy="40" rx="18" ry="6" fill="#ffffff" opacity="0.8" />
      </g>
    </svg>
  );
}

function AppTile({ children, tilt, compact }: { children: ReactNode; tilt: string; compact: boolean }) {
  return (
    <span className={`grid place-items-center rounded-2xl bg-white shadow-[0_12px_30px_-8px_rgb(0_0_0/0.6)] ${compact ? "size-12" : "size-16"} ${tilt}`}>
      {children}
    </span>
  );
}

export function Hero({ compact }: { compact: boolean }) {
  return (
    <section
      className={`relative isolate overflow-hidden rounded-[1.4rem] border border-[#3a3f8f]/60 ${compact ? "py-5" : "py-7 sm:py-9"} px-6 sm:px-10`}
      style={{
        background:
          "radial-gradient(40rem 18rem at 78% 50%, rgb(66 99 255 / 0.55), transparent 65%), linear-gradient(115deg, #24135e 0%, #1c1f73 40%, #1a3aa8 72%, #3554e6 100%)",
      }}
    >
      {/* sweeping light behind the robot */}
      <div className="pointer-events-none absolute -right-24 -top-24 h-[150%] w-[55%] rotate-12 rounded-[45%] bg-[linear-gradient(160deg,rgb(129_140_248/0.35),rgb(59_130_246/0.05))] blur-[2px]" aria-hidden />
      <Sparkle className="absolute right-[24%] top-5 text-white/90 [animation:twinkle_3s_ease-in-out_infinite]" size={30} fill="currentColor" aria-hidden />
      <Sparkle className="absolute bottom-6 right-[30%] text-white/70 [animation:twinkle_4s_ease-in-out_infinite]" size={16} fill="currentColor" aria-hidden />
      <Sparkle className="absolute bottom-5 left-[52%] hidden text-indigo-300/60 md:block" size={18} fill="currentColor" aria-hidden />
      <div className="relative z-10 max-w-[46rem] md:pr-[22rem] xl:pr-0">
        <h1 className={`text-gradient font-extrabold tracking-tight ${compact ? "text-3xl sm:text-[2.4rem]" : "text-4xl sm:text-5xl xl:text-[3.5rem]"}`}>
          Ask. Search. Remember.
        </h1>
        <p className="mt-2 text-base text-indigo-100/90 sm:text-xl">Your AI agent over Gmail, Notion and more.</p>
      </div>
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 hidden items-center gap-4 pr-4 md:flex lg:pr-8" aria-hidden>
        <div className={`flex items-end gap-4 ${compact ? "" : "pb-6"}`}>
          <AppTile compact={compact} tilt={compact ? "-rotate-6" : "-rotate-6 translate-y-3"}>
            <Mail size={compact ? 24 : 30} className="text-[#ea4335]" strokeWidth={2.4} />
          </AppTile>
          <AppTile compact={compact} tilt={compact ? "rotate-6" : "rotate-6 -translate-y-4"}>
            <FileText size={compact ? 24 : 30} className="text-[#111]" strokeWidth={2.4} />
          </AppTile>
        </div>
        <Robot className={`${compact ? "h-32 translate-y-4" : "h-44 translate-y-3 lg:h-52"} w-auto`} />
      </div>
    </section>
  );
}

function CardShell({ onClick, children, highlight = false, label }: { onClick: () => void; children: ReactNode; highlight?: boolean; label: string }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      className={`group flex min-w-0 items-center gap-4 rounded-2xl border px-4 py-3.5 text-left transition-colors sm:px-5 sm:py-4 ${
        highlight
          ? "border-violet/50 bg-[linear-gradient(120deg,#3a1d7a,#2a1f6e_55%,#24246e)] hover:border-violet"
          : "border-line bg-panel/80 hover:border-line-strong hover:bg-panel-2"
      }`}
    >
      {children}
      <ChevronRight size={20} className="ml-auto shrink-0 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
    </button>
  );
}

function sourceState(status: Status | null, name: SourceName): { text: string; tone: string } {
  const s = status?.sources[name];
  if (!s) return { text: "Checking…", tone: "text-muted" };
  if (s.connected) return { text: "Connected", tone: "text-green" };
  if (s.demo) return { text: "Demo data", tone: "text-amber" };
  return { text: "Not connected", tone: "text-muted" };
}

export function StatusCards({ status, onOpen }: { status: Status | null; onOpen: (view: "integrations" | "memory" | "about") => void }) {
  const gmail = sourceState(status, "gmail");
  const notion = sourceState(status, "notion");
  const memories = status?.memories ?? 0;
  return (
    <div className="grid grid-cols-1 gap-3 min-[520px]:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1.15fr] lg:gap-4">
      <CardShell onClick={() => onOpen("integrations")} label={`Gmail: ${gmail.text}. Open integrations`}>
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-white">
          <Mail size={26} className="text-[#ea4335]" strokeWidth={2.4} aria-hidden />
        </span>
        <span className="min-w-0">
          <span className="block font-bold">Gmail</span>
          <span className={`block truncate text-sm font-medium ${gmail.tone}`}>{gmail.text}</span>
        </span>
      </CardShell>
      <CardShell onClick={() => onOpen("integrations")} label={`Notion: ${notion.text}. Open integrations`}>
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-white">
          <FileText size={26} className="text-[#111]" strokeWidth={2.4} aria-hidden />
        </span>
        <span className="min-w-0">
          <span className="block font-bold">Notion</span>
          <span className={`block truncate text-sm font-medium ${notion.tone}`}>{notion.text}</span>
        </span>
      </CardShell>
      <CardShell onClick={() => onOpen("memory")} label={`Memory: ${memories} saved. Open memory`}>
        <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-[linear-gradient(160deg,#7c8cff,#4f46e5)]">
          <Database size={26} className="text-white" aria-hidden />
        </span>
        <span className="min-w-0">
          <span className="block font-bold">Memory</span>
          <span className="block truncate text-sm font-semibold text-green">{memories ? `Ready · ${memories} saved` : "Ready"}</span>
        </span>
      </CardShell>
      <CardShell onClick={() => onOpen("about")} highlight label="Learn more about Agentic RAG">
        <Zap size={32} className="shrink-0 text-[#c084fc]" fill="currentColor" aria-hidden />
        <span className="min-w-0">
          <span className="block font-bold">Learn More</span>
          <span className="block truncate text-sm text-indigo-100/80">Discover the power of Agentic RAG</span>
        </span>
      </CardShell>
    </div>
  );
}
