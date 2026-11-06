import asyncio
import base64
import json
import time

import httpx
import pytest

from app.sources import gmail, notion
from app.sources.base import SourceError
from app.sources.demo import DemoSource


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


MESSAGE = {
    "id": "m1",
    "threadId": "t1",
    "snippet": "Your invoice &amp; usage",
    "payload": {
        "mimeType": "multipart/mixed",
        "headers": [
            {"name": "Subject", "value": "October invoice"},
            {"name": "From", "value": "Billing <billing@example.com>"},
            {"name": "To", "value": "me@example.com"},
            {"name": "Date", "value": "Mon, 02 Nov 2026 09:15:00 +0530"},
        ],
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": b64("Amount due: Rs 1,248\n\nOn Sun, 1 Nov 2026 someone wrote:\n> old quoted text")}},
                    {"mimeType": "text/html", "body": {"data": b64("<p>Amount due: <b>Rs 1,248</b></p>")}},
                ],
            },
            {"mimeType": "application/pdf", "filename": "invoice.pdf", "body": {"attachmentId": "a1"}},
        ],
    },
}


def test_parse_message_prefers_plain_text_and_drops_quotes():
    doc = gmail.parse_message(MESSAGE)
    assert doc.title == "October invoice"
    assert doc.author == "Billing <billing@example.com>"
    assert doc.date.startswith("2026-11-02T09:15:00")
    assert "Amount due: Rs 1,248" in doc.text
    assert "old quoted text" not in doc.text
    assert "Attachments: invoice.pdf" in doc.text
    assert doc.snippet == "Your invoice & usage"
    assert doc.url == "https://mail.google.com/mail/u/0/#all/t1"


def test_html_only_email_is_converted_to_text():
    msg = {"id": "m2", "payload": {"mimeType": "text/html", "headers": [], "body": {"data": b64("<style>p{}</style><p>Hello</p><p>World&nbsp;!</p>")}}}
    doc = gmail.parse_message(msg)
    assert doc.title == "(no subject)"
    assert doc.text.endswith("Hello\n\nWorld !")


def test_gmail_search_refreshes_expired_tokens_and_fetches_messages():
    saved = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer fresh"
        if request.url.path.endswith("/messages"):
            assert request.url.params["q"] == "from:billing invoice"
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        return httpx.Response(200, json=MESSAGE)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = gmail.GmailSource(
                {"access_token": "old", "refresh_token": "r", "expires_at": time.time() - 10, "email": "me@example.com"},
                http, "cid", "secret", save_tokens=lambda t: saved.update(t),
            )
            return await source.search("from:billing invoice", 5)

    docs = asyncio.run(run())
    assert [d.item_id for d in docs] == ["m1"]
    assert saved["access_token"] == "fresh"


def test_gmail_sign_in_without_read_permission_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "a", "expires_in": 3600, "scope": "openid email"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            await gmail.exchange_code(http, "id", "secret", "http://localhost/cb", "code")

    with pytest.raises(SourceError, match="tick the box"):
        asyncio.run(run())


def test_notion_block_text_formats_common_blocks():
    rt = lambda t: [{"plain_text": t}]  # noqa: E731
    assert notion.block_text({"type": "heading_2", "heading_2": {"rich_text": rt("Goals")}}) == "\n## Goals"
    assert notion.block_text({"type": "to_do", "to_do": {"rich_text": rt("Slides"), "checked": True}}) == "[x] Slides"
    assert notion.block_text({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("Graphs")}}) == "• Graphs"
    assert notion.block_text({"type": "table_row", "table_row": {"cells": [rt("Rent"), rt("₹4,500")]}}) == "Rent | ₹4,500"


def test_notion_search_falls_back_to_recent_pages_and_reads_nested_blocks():
    searches = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Notion-Version"] == notion.VERSION
        if request.url.path == "/v1/search":
            body = json.loads(request.content)
            searches.append(body["query"])
            if body["query"]:
                return httpx.Response(200, json={"results": []})
            return httpx.Response(200, json={"results": [{"id": "p1", "url": "https://notion.so/p1", "last_edited_time": "2026-11-01T10:00:00Z",
                                                          "properties": {"Name": {"type": "title", "title": [{"plain_text": "Budget"}]}}}]})
        if request.url.path == "/v1/blocks/p1/children":
            return httpx.Response(200, json={"results": [
                {"id": "b1", "type": "paragraph", "has_children": True, "paragraph": {"rich_text": [{"plain_text": "Fixed costs"}]}},
            ], "has_more": False})
        if request.url.path == "/v1/blocks/b1/children":
            return httpx.Response(200, json={"results": [
                {"id": "b2", "type": "bulleted_list_item", "has_children": False, "bulleted_list_item": {"rich_text": [{"plain_text": "Cloud: ₹1,000"}]}},
            ], "has_more": False})
        return httpx.Response(404, json={})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await notion.NotionSource("secret", http).search("cloud spending", 5)

    docs = asyncio.run(run())
    assert searches == ["cloud spending", ""]
    assert docs[0].title == "Budget"
    assert docs[0].text == "Fixed costs\n  • Cloud: ₹1,000"


def test_demo_inbox_search_handles_gmail_operators():
    async def run():
        src = DemoSource("gmail")
        return await src.search("from:northwind interview", 5), await src.search("newer_than:30d invoice", 5)

    interview, invoice = asyncio.run(run())
    assert [d.item_id for d in interview] == ["demo-mail-1"]
    assert invoice[0].item_id == "demo-mail-2"
