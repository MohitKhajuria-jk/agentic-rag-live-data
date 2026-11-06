"""Gmail: OAuth 2.0 with the read-only scope, live search, and MIME parsing."""

from __future__ import annotations

import asyncio
import base64
import html
import re
import time
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode

import httpx

from ..retrieval import Document
from .base import SourceError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
# Read-only: the agent can search and read mail but never send, change or delete it.
SCOPES = "https://www.googleapis.com/auth/gmail.readonly"

MAX_BODY = 20_000


# ---------------------------------------------------------------------- OAuth


def auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    return f"{AUTH_URL}?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )


async def exchange_code(http: httpx.AsyncClient, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict[str, Any]:
    r = await http.post(
        TOKEN_URL,
        data={"code": code, "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "grant_type": "authorization_code"},
    )
    if r.status_code != 200:
        raise SourceError(f"Google didn't accept the sign-in ({r.status_code}). Try connecting Gmail again.")
    data = r.json()
    tokens = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
        "scope": data.get("scope", ""),
    }
    if "gmail.readonly" not in tokens["scope"]:
        raise SourceError("Gmail access wasn't granted. Connect again and tick the box that allows reading your email.")
    profile = await http.get(f"{API}/profile", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    tokens["email"] = profile.json().get("emailAddress", "") if profile.status_code == 200 else ""
    return tokens


async def revoke(http: httpx.AsyncClient, tokens: dict[str, Any]) -> None:
    token = tokens.get("refresh_token") or tokens.get("access_token")
    if token:
        try:
            await http.post(REVOKE_URL, data={"token": token})
        except httpx.HTTPError:
            pass


# -------------------------------------------------------------------- parsing


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "head"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(markup: str) -> str:
    parser = _TextExtractor()
    parser.feed(markup)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\n\s*\n\s*", "\n\n", text).strip()


def _decode(data: str) -> str:
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


def strip_quoted(text: str) -> str:
    """Drops quoted earlier messages in replies, which repeat content and confuse retrieval."""
    cut = re.search(r"\n(On .{4,200}wrote:|-{2,} ?Original Message ?-{2,}|From: .+\nSent: )", text)
    if cut and cut.start() > 40:
        text = text[: cut.start()]
    lines = [line for line in text.splitlines() if not line.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def extract_body(payload: dict[str, Any]) -> tuple[str, list[str]]:
    plain: list[str] = []
    rich: list[str] = []
    attachments: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        data = (part.get("body") or {}).get("data")
        if part.get("filename"):
            attachments.append(part["filename"])
        elif mime == "text/plain" and data:
            plain.append(_decode(data))
        elif mime == "text/html" and data:
            rich.append(_decode(data))
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    body = "\n".join(plain) if plain else html_to_text("\n".join(rich))
    return strip_quoted(body)[:MAX_BODY], attachments


def parse_message(msg: dict[str, Any]) -> Document:
    payload = msg.get("payload") or {}
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    subject = headers.get("subject", "").strip() or "(no subject)"
    sender = headers.get("from", "")
    date_iso = None
    try:
        date_iso = parsedate_to_datetime(headers["date"]).isoformat()
    except (KeyError, TypeError, ValueError):
        if msg.get("internalDate"):
            date_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(msg["internalDate"]) / 1000))
    body, attachments = extract_body(payload)
    lines = [f"From: {sender}", f"To: {headers.get('to', '')}", f"Date: {headers.get('date', '')}", f"Subject: {subject}"]
    if attachments:
        lines.append("Attachments: " + ", ".join(attachments))
    thread = msg.get("threadId") or msg.get("id")
    return Document(
        source="gmail",
        item_id=msg["id"],
        title=subject,
        text="\n".join(lines) + "\n\n" + body,
        url=f"https://mail.google.com/mail/u/0/#all/{thread}",
        author=sender,
        date=date_iso,
        snippet=html.unescape(msg.get("snippet", "")),
    )


# --------------------------------------------------------------------- source


class GmailSource:
    name = "gmail"
    demo = False

    def __init__(
        self,
        tokens: dict[str, Any],
        http: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        save_tokens: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ):
        self.tokens = tokens
        self.http = http
        self.client_id = client_id
        self.client_secret = client_secret
        self.save_tokens = save_tokens
        self.label = f"Gmail ({tokens.get('email') or 'connected'})"

    async def _token(self) -> str:
        if time.time() < self.tokens.get("expires_at", 0):
            return self.tokens["access_token"]
        if not self.tokens.get("refresh_token"):
            raise SourceError("Gmail access has expired. Reconnect Gmail in Sources.")
        r = await self.http.post(
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.tokens["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        if r.status_code != 200:
            raise SourceError("Gmail access was revoked or expired. Reconnect Gmail in Sources.")
        data = r.json()
        self.tokens["access_token"] = data["access_token"]
        self.tokens["expires_at"] = time.time() + int(data.get("expires_in", 3600)) - 60
        if self.save_tokens:
            result = self.save_tokens(self.tokens)
            if asyncio.iscoroutine(result):
                await result
        return self.tokens["access_token"]

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self._token()
        r = await self.http.get(f"{API}/{path}", params=params, headers={"Authorization": f"Bearer {token}"})
        if r.status_code in (401, 403):
            raise SourceError("Gmail refused access. Reconnect Gmail in Sources.")
        if r.status_code == 429:
            raise SourceError("Gmail is limiting requests right now. Try again in a minute.")
        r.raise_for_status()
        return r.json()

    async def search(self, query: str, limit: int) -> list[Document]:
        listing = await self._get("messages", {"q": query, "maxResults": max(1, min(limit, 15))})
        ids = [m["id"] for m in listing.get("messages", [])]
        gate = asyncio.Semaphore(5)

        async def fetch(mid: str) -> Document | None:
            async with gate:
                try:
                    return parse_message(await self._get(f"messages/{mid}", {"format": "full"}))
                except httpx.HTTPError:
                    return None

        docs = await asyncio.gather(*(fetch(i) for i in ids))
        return [d for d in docs if d]

    async def read(self, item_id: str) -> Document | None:
        try:
            return parse_message(await self._get(f"messages/{item_id}", {"format": "full"}))
        except httpx.HTTPStatusError:
            return None
