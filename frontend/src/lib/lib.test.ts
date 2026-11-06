import { describe, expect, it } from "vitest";
import { citationNumber, linkCitations } from "./citations";
import { SseParser } from "./sse";

describe("SseParser", () => {
  it("parses events split across chunks", () => {
    const p = new SseParser();
    expect(p.push('event: step\ndata: {"step":{"id":1}}\n\nevent: ans')).toEqual([{ event: "step", data: { step: { id: 1 } } }]);
    expect(p.push('wer\ndata: {"content":"Hi [1]"}\n\n')).toEqual([{ event: "answer", data: { content: "Hi [1]" } }]);
  });

  it("handles Windows line endings and ignores blocks without data", () => {
    const p = new SseParser();
    expect(p.push(": keep-alive\r\n\r\nevent: done\r\ndata: {}\r\n\r\n")).toEqual([{ event: "done", data: {} }]);
  });
});

describe("linkCitations", () => {
  const known = new Set([1, 2, 3]);

  it("links known citation numbers only", () => {
    expect(linkCitations("Due ₹1,248 [1][2], see [7].", known)).toBe("Due ₹1,248 [1](#cite-1)[2](#cite-2), see [7].");
  });

  it("leaves code, links and checkboxes alone", () => {
    expect(linkCitations("`arr[1]` and [1](http://x) and [x] done [3]", known)).toBe("`arr[1]` and [1](http://x) and [x] done [3](#cite-3)");
  });

  it("reads numbers back from links", () => {
    expect(citationNumber("#cite-12")).toBe(12);
    expect(citationNumber("https://example.com")).toBeNull();
  });
});
