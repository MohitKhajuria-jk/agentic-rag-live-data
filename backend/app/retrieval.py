"""Retrieval: split documents into chunks and rank them against a question.

Ranking combines BM25 keyword scores with embedding (semantic) similarity
when an embedding model is available, and falls back to BM25 alone.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Protocol


@dataclass
class Document:
    """One item from a source: an email, a Notion page, or a memory."""

    source: str  # "gmail" | "notion"
    item_id: str
    title: str
    text: str
    url: str | None = None
    author: str | None = None
    date: str | None = None  # ISO 8601
    snippet: str = ""
    demo: bool = False

    def card(self) -> dict:
        """The metadata shown to the user for a cited source (no full text)."""
        data = asdict(self)
        data.pop("text")
        # Card previews drop Markdown-style heading marks and bullets from page text.
        plain = re.sub(r"(?m)^\s*(#+|•|-|\[[ x]\])\s*", "", self.text)
        data["snippet"] = self.snippet or excerpt(plain, 240)
        return data


@dataclass
class Chunk:
    doc: Document
    index: int
    text: str
    score: float = 0.0
    tokens: list[str] = field(default_factory=list, repr=False)


STOPWORDS = set(
    """a an and are as at be been but by can could did do does for from had has have he her his how i if in into is it its
    me my of on or our she so than that the their them then there these they this to too us was we were what when where
    which who whom why will with would you your about any all also am just more most no not only other over same some such
    up very via per tell show find give please""".split()
)


def stem(word: str) -> str:
    """Light stemming so "invoices" matches "invoice" and "meetings" matches "meeting"."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())
    out = []
    for w in words:
        if w in STOPWORDS or len(w) < 2:
            continue
        out.append(stem(w))
    return out


def excerpt(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= limit:
        return clean
    cut = clean[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    """Splits text into roughly `size`-character chunks along paragraph and sentence breaks."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []
    if len(text) <= size:
        return [text]
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            pieces.append(para)
        else:
            pieces.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip())
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        while len(piece) > size:  # a single very long sentence
            chunks.append(piece[:size])
            piece = piece[size - overlap :]
        if current and len(current) + len(piece) + 1 > size:
            chunks.append(current)
            tail = current[-overlap:]
            current = (tail.split(" ", 1)[-1] + " " + piece).strip()
        else:
            current = f"{current}\n{piece}".strip() if current else piece
    if current:
        chunks.append(current)
    return chunks


def chunk_documents(docs: list[Document], size: int = 900) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        header = f"{doc.title}\n" if doc.title else ""
        for i, part in enumerate(chunk_text(doc.text, size) or [doc.snippet or doc.title]):
            # The title goes into every chunk so a chunk can match on what the item is about.
            chunks.append(Chunk(doc=doc, index=i, text=part, tokens=tokenize(header + part)))
    return chunks


def bm25_scores(query: str, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> list[float]:
    q = tokenize(query)
    if not q or not chunks:
        return [0.0] * len(chunks)
    n = len(chunks)
    avg_len = sum(len(c.tokens) for c in chunks) / n or 1
    df: Counter[str] = Counter()
    for c in chunks:
        df.update(set(c.tokens))
    scores = []
    for c in chunks:
        tf = Counter(c.tokens)
        length = len(c.tokens) or 1
        s = 0.0
        for term in set(q):
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            s += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * length / avg_len))
        scores.append(s)
    return scores


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]] | None: ...


async def rank_chunks(query: str, chunks: list[Chunk], embedder: Embedder | None = None) -> list[Chunk]:
    """Scores chunks against the query, best first. Hybrid BM25 + embeddings when available."""
    if not chunks:
        return []
    keyword = bm25_scores(query, chunks)
    top = max(keyword) or 1.0
    keyword = [s / top for s in keyword]
    semantic: list[float] | None = None
    if embedder is not None:
        vectors = await embedder.embed([query] + [c.text for c in chunks])
        if vectors and len(vectors) == len(chunks) + 1:
            q = vectors[0]
            semantic = [max(0.0, cosine(q, v)) for v in vectors[1:]]
    for i, c in enumerate(chunks):
        c.score = 0.45 * keyword[i] + 0.55 * semantic[i] if semantic else keyword[i]
    return sorted(chunks, key=lambda c: c.score, reverse=True)


def best_chunk_per_document(ranked: list[Chunk]) -> dict[str, Chunk]:
    best: dict[str, Chunk] = {}
    for c in ranked:
        key = f"{c.doc.source}:{c.doc.item_id}"
        if key not in best:
            best[key] = c
    return best
