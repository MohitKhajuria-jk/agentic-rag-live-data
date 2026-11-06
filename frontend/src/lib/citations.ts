/**
 * Turns citation markers like [3] into Markdown links (#cite-3) so the
 * Markdown renderer can draw them as chips. Leaves code, real links and
 * checkboxes ("[x]") alone.
 */
export function linkCitations(markdown: string, known: Set<number>): string {
  const parts = markdown.split(/(```[\s\S]*?```|`[^`\n]*`)/g);
  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part; // code
      return part.replace(/\[(\d{1,3})\](?!\()/g, (whole, num: string) => {
        const n = Number(num);
        return known.has(n) ? `[${n}](#cite-${n})` : whole;
      });
    })
    .join("");
}

export function citationNumber(href: string | undefined): number | null {
  const m = href?.match(/^#cite-(\d+)$/);
  return m ? Number(m[1]) : null;
}
