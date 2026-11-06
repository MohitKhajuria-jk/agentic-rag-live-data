from __future__ import annotations

from typing import Protocol

from ..retrieval import Document


class Source(Protocol):
    """A place the agent can search live: Gmail, Notion, or demo data standing in for them."""

    name: str  # "gmail" | "notion"
    label: str  # shown to the user, e.g. "Gmail (you@example.com)"
    demo: bool

    async def search(self, query: str, limit: int) -> list[Document]: ...

    async def read(self, item_id: str) -> Document | None: ...


class SourceError(Exception):
    """A source failed in a way the user can fix (expired access, missing permission)."""
