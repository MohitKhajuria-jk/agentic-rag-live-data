"""Long-term memory: lasting facts and preferences the user tells the agent.

Memories are stored in SQLite with their embedding (when available) and
recalled by relevance at the start of each answer.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from .db import Database
from .llm import Embeddings
from .retrieval import Chunk, Document, bm25_scores, cosine, tokenize

MAX_MEMORY_CHARS = 300


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


class MemoryStore:
    def __init__(self, db: Database, embedder: Embeddings | None):
        self.db = db
        self.embedder = embedder

    def list(self) -> list[dict[str, Any]]:
        rows = self.db.query("select id, text, created_at from memories order by created_at desc")
        return [dict(r) for r in rows]

    def delete(self, memory_id: str) -> bool:
        return self.db.execute("delete from memories where id = ?", (memory_id,)).rowcount > 0

    async def add(self, text: str) -> tuple[dict[str, Any], bool]:
        """Saves a memory. Returns (memory, created); an existing near-identical memory is returned unchanged."""
        text = re.sub(r"\s+", " ", text).strip()[:MAX_MEMORY_CHARS]
        if not text:
            raise ValueError("A memory can't be empty.")
        key = _normalize(text)
        for m in self.list():
            if _normalize(m["text"]) == key:
                return m, False
        vector = None
        if self.embedder:
            vectors = await self.embedder.embed([text])
            vector = vectors[0] if vectors else None
            if vector:
                for row in self.db.query("select id, text, created_at, embedding_json from memories where embedding_json is not null"):
                    if cosine(vector, json.loads(row["embedding_json"])) > 0.95:
                        return {"id": row["id"], "text": row["text"], "created_at": row["created_at"]}, False
        memory = {"id": uuid.uuid4().hex, "text": text, "created_at": time.time()}
        self.db.execute(
            "insert into memories values (?, ?, ?, ?)",
            (memory["id"], text, json.dumps(vector) if vector else None, memory["created_at"]),
        )
        return memory, True

    async def relevant(self, query: str, k: int = 6) -> list[dict[str, Any]]:
        rows = self.db.query("select id, text, created_at, embedding_json from memories order by created_at desc")
        if len(rows) <= k:
            return [{"id": r["id"], "text": r["text"], "created_at": r["created_at"]} for r in rows]
        chunks = [
            Chunk(doc=Document(source="memory", item_id=r["id"], title="", text=r["text"]), index=0, text=r["text"], tokens=tokenize(r["text"]))
            for r in rows
        ]
        keyword = bm25_scores(query, chunks)
        top = max(keyword) or 1.0
        scores = [s / top for s in keyword]
        if self.embedder:
            q = await self.embedder.embed([query])
            if q:
                for i, r in enumerate(rows):
                    if r["embedding_json"]:
                        scores[i] = 0.4 * scores[i] + 0.6 * max(0.0, cosine(q[0], json.loads(r["embedding_json"])))
        best = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)[:k]
        return [{"id": rows[i]["id"], "text": rows[i]["text"], "created_at": rows[i]["created_at"]} for i in best]
