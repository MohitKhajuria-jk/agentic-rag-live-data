"""Notion: OAuth (public integration) or an internal integration token, live search and page text."""

from __future__ import annotations

import asyncio
import base64
from typing import Any
from urllib.parse import urlencode

import httpx

from ..retrieval import Document
from .base import SourceError

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
MAX_BLOCKS = 300


def auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    return "https://api.notion.com/v1/oauth/authorize?" + urlencode(
        {"client_id": client_id, "response_type": "code", "owner": "user", "redirect_uri": redirect_uri, "state": state}
    )


async def exchange_code(http: httpx.AsyncClient, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict[str, Any]:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = await http.post(
        f"{API}/oauth/token",
        json={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        headers={"Authorization": f"Basic {basic}", "Notion-Version": VERSION},
    )
    if r.status_code != 200:
        raise SourceError(f"Notion didn't accept the sign-in ({r.status_code}). Try connecting Notion again.")
    data = r.json()
    return {"access_token": data["access_token"], "workspace": data.get("workspace_name") or "Notion workspace"}


# -------------------------------------------------------------------- parsing


def rich_text(items: list[dict[str, Any]] | None) -> str:
    return "".join(i.get("plain_text", "") for i in items or [])


def page_title(page: dict[str, Any]) -> str:
    for prop in (page.get("properties") or {}).values():
        if prop.get("type") == "title":
            title = rich_text(prop.get("title"))
            if title.strip():
                return title.strip()
    return "Untitled"


def block_text(block: dict[str, Any]) -> str:
    kind = block.get("type", "")
    body = block.get(kind) or {}
    text = rich_text(body.get("rich_text"))
    if kind.startswith("heading_"):
        return f"\n{'#' * int(kind[-1])} {text}"
    if kind == "bulleted_list_item":
        return f"• {text}"
    if kind == "numbered_list_item":
        return f"- {text}"
    if kind == "to_do":
        return f"[{'x' if body.get('checked') else ' '}] {text}"
    if kind in ("quote", "callout"):
        return f"> {text}"
    if kind == "code":
        return f"```\n{text}\n```"
    if kind == "child_page":
        return f"(subpage: {body.get('title', '')})"
    if kind == "child_database":
        return f"(database: {body.get('title', '')})"
    if kind == "table_row":
        return " | ".join(rich_text(cell) for cell in body.get("cells", []))
    if kind in ("bookmark", "link_preview", "embed"):
        return body.get("url", "")
    if kind == "equation":
        return body.get("expression", "")
    return text


# --------------------------------------------------------------------- source


class NotionSource:
    name = "notion"
    demo = False

    def __init__(self, token: str, http: httpx.AsyncClient, workspace: str = "Notion"):
        self.token = token
        self.http = http
        self.label = f"Notion ({workspace})"
        self._gate = asyncio.Semaphore(3)  # Notion allows about 3 requests a second

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Notion-Version": VERSION, "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        async with self._gate:
            for attempt in range(3):
                r = await self.http.request(method, f"{API}/{path}", headers=self.headers, **kwargs)
                if r.status_code == 429 and attempt < 2:
                    await asyncio.sleep(float(r.headers.get("retry-after", "1")))
                    continue
                break
        if r.status_code == 401:
            raise SourceError("Notion refused access. Reconnect Notion in Sources.")
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()

    async def _blocks(self, block_id: str, depth: int = 0, budget: list[int] | None = None) -> list[str]:
        budget = budget if budget is not None else [MAX_BLOCKS]
        lines: list[str] = []
        cursor: str | None = None
        while budget[0] > 0:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = await self._request("GET", f"blocks/{block_id}/children", params=params)
            for block in data.get("results", []):
                budget[0] -= 1
                line = block_text(block)
                if line.strip():
                    lines.append(("  " * depth) + line)
                if block.get("has_children") and depth < 2 and block.get("type") not in ("child_page", "child_database"):
                    lines.extend(await self._blocks(block["id"], depth + 1, budget))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return lines

    async def _document(self, page: dict[str, Any]) -> Document:
        title = page_title(page)
        lines = await self._blocks(page["id"])
        text = "\n".join(lines).strip()
        return Document(
            source="notion",
            item_id=page["id"],
            title=title,
            text=text or title,
            url=page.get("url"),
            author=None,
            date=page.get("last_edited_time"),
            snippet="",
        )

    async def search(self, query: str, limit: int) -> list[Document]:
        body = {
            "query": query,
            "filter": {"property": "object", "value": "page"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "page_size": max(1, min(limit, 10)),
        }
        pages = (await self._request("POST", "search", json=body)).get("results", [])
        if not pages and query:
            # Notion search mostly matches titles. Fall back to recent pages so their
            # content can be ranked against the question instead.
            body["query"] = ""
            body["page_size"] = 15
            pages = (await self._request("POST", "search", json=body)).get("results", [])
        return list(await asyncio.gather(*(self._document(p) for p in pages)))

    async def read(self, item_id: str) -> Document | None:
        page = await self._request("GET", f"pages/{item_id}")
        return await self._document(page) if page else None
