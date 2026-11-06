import { useEffect } from "react";
import { Brain, FileText, Mail } from "lucide-react";
import type { SourceName } from "../types";

export const SOURCE_META: Record<SourceName, { name: string; Icon: typeof Mail; text: string; soft: string }> = {
  gmail: { name: "Gmail", Icon: Mail, text: "text-gmail", soft: "bg-gmail-soft" },
  notion: { name: "Notion", Icon: FileText, text: "text-notion", soft: "bg-notion-soft" },
};

export function SourceIcon({ source, size = 16 }: { source: SourceName | "memory"; size?: number }) {
  if (source === "memory") return <Brain size={size} className="text-memory" aria-hidden />;
  const { Icon, text } = SOURCE_META[source];
  return <Icon size={size} className={text} aria-hidden />;
}

/** SVG gradients that icons can use as their stroke colour, e.g. color="url(#brand)". */
export function GradientDefs() {
  return (
    <svg width="0" height="0" className="absolute" aria-hidden focusable="false">
      <defs>
        {/* userSpaceOnUse: works for straight-line icons too (24×24 icon grid) */}
        <linearGradient id="brand" gradientUnits="userSpaceOnUse" x1="2" y1="2" x2="22" y2="22">
          <stop offset="0" stopColor="#b07bff" />
          <stop offset="0.5" stopColor="#6d7cff" />
          <stop offset="1" stopColor="#3fdcf0" />
        </linearGradient>
        <linearGradient id="spark" gradientUnits="userSpaceOnUse" x1="2" y1="2" x2="22" y2="22">
          <stop offset="0" stopColor="#c4b5fd" />
          <stop offset="1" stopColor="#60a5fa" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function Toast({ message, tone, onDone }: { message: string; tone: "info" | "error"; onDone: () => void }) {
  useEffect(() => {
    const id = setTimeout(onDone, tone === "error" ? 8000 : 3500);
    return () => clearTimeout(id);
  }, [message, tone, onDone]);
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`fixed bottom-6 left-1/2 z-50 w-max max-w-[calc(100%-2rem)] -translate-x-1/2 rounded-xl px-4 py-3 text-sm font-semibold shadow-glow [animation:rise_180ms_ease-out] ${
        tone === "error" ? "bg-red text-[#2a0707]" : "bg-ink text-bg"
      }`}
    >
      {message}
    </div>
  );
}

export function formatWhen(value: string | number | null): string {
  if (value === null || value === "") return "";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const days = Math.round((Date.now() - date.getTime()) / 86_400_000);
  if (days === 0 && date.toDateString() === new Date().toDateString()) {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  if (days < 7 && days > 0) return date.toLocaleDateString([], { weekday: "short" });
  return date.toLocaleDateString([], { day: "numeric", month: "short", year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
}
