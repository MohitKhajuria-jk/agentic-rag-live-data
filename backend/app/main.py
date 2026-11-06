"""HTTP API: connections (OAuth), conversations with a streaming agent, and memory."""

from __future__ import annotations

import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import Agent
from .config import BACKEND_DIR, Settings, get_settings
from .db import Database
from .llm import ChatModel, Embeddings, OpenAICompatibleClient
from .memory import MemoryStore
from .security import TokenVault, load_or_create_secret
from .sources import gmail, notion
from .sources.base import Source, SourceError
from .sources.demo import DemoSource

log = logging.getLogger("app")


class AskBody(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MemoryBody(BaseModel):
    text: str = Field(min_length=1, max_length=300)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class AppState:
    def __init__(self, settings: Settings, model: ChatModel | None, http: httpx.AsyncClient):
        self.settings = settings
        self.http = http
        self.db = Database(settings.data_dir / "app.db")
        self.vault = TokenVault(load_or_create_secret(settings.app_secret, settings.data_dir))
        self.embedder = Embeddings(settings, http) if settings.resolved_embedding_model and settings.llm_ready else None
        self.memory = MemoryStore(self.db, self.embedder)
        self.model = model if model is not None else (OpenAICompatibleClient(settings, http) if settings.llm_ready else None)
        self.demo = {"gmail": DemoSource("gmail"), "notion": DemoSource("notion")}

    # ----------------------------------------------------------- connections

    def connection(self, source: str) -> tuple[str, dict[str, Any]] | None:
        rows = self.db.query("select account, token_enc from connections where source = ?", (source,))
        if not rows:
            return None
        tokens = self.vault.open(rows[0]["token_enc"])
        return (rows[0]["account"], tokens) if tokens else None

    def save_connection(self, source: str, account: str, tokens: dict[str, Any]) -> None:
        self.db.execute(
            "insert or replace into connections values (?, ?, ?, ?)",
            (source, account, self.vault.seal(tokens), time.time()),
        )

    def sources(self) -> tuple[dict[str, Source], dict[tuple[str, bool], Source]]:
        s = self.settings
        live: dict[str, Source] = {}
        readers: dict[tuple[str, bool], Source] = {(name, True): src for name, src in self.demo.items()}
        gm = self.connection("gmail")
        if gm and s.google_configured:
            account, tokens = gm
            source = gmail.GmailSource(
                tokens, self.http, s.google_client_id, s.google_client_secret,
                save_tokens=lambda t, a=account: self.save_connection("gmail", a, t),
            )
            live["gmail"] = readers[("gmail", False)] = source
        elif s.demo_mode:
            live["gmail"] = self.demo["gmail"]
        no = self.connection("notion")
        if s.notion_token:
            live["notion"] = readers[("notion", False)] = notion.NotionSource(s.notion_token, self.http, "internal integration")
        elif no:
            account, tokens = no
            live["notion"] = readers[("notion", False)] = notion.NotionSource(tokens["access_token"], self.http, account)
        elif s.demo_mode:
            live["notion"] = self.demo["notion"]
        return live, readers

    def status(self) -> dict[str, Any]:
        s = self.settings
        live, _ = self.sources()

        def describe(name: str, can_connect: bool, how: str) -> dict[str, Any]:
            src = live.get(name)
            return {
                "connected": bool(src) and not src.demo,
                "demo": bool(src) and src.demo,
                "label": src.label if src else None,
                "can_connect": can_connect,
                "setup_hint": None if can_connect else how,
                "fixed": name == "notion" and bool(s.notion_token),
            }

        return {
            "llm": {
                "ready": self.model is not None,
                "label": getattr(self.model, "label", None) or f"{s.provider['label']} · {s.resolved_model or 'no model set'}",
                "provider": s.provider["label"],
                "model": s.resolved_model,
                "fallback_model": s.resolved_fallback_model or None,
                "using_fallback": bool(getattr(self.model, "using_fallback", False)),
                "reasoning_effort": s.resolved_reasoning_effort or "provider default",
                "embedding_model": s.resolved_embedding_model or None,
                "semantic_search": bool(self.embedder and self.embedder.available),
            },
            "sources": {
                "gmail": describe("gmail", s.google_configured, "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env (see the README)."),
                "notion": describe(
                    "notion",
                    s.notion_oauth_configured,
                    "Add NOTION_TOKEN (internal integration) or NOTION_CLIENT_ID and NOTION_CLIENT_SECRET to backend/.env (see the README).",
                ),
            },
            "demo_mode": s.demo_mode,
            "memories": len(self.memory.list()),
        }


def create_app(settings: Settings | None = None, model: ChatModel | None = None, http: httpx.AsyncClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    client = http or httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0), follow_redirects=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await client.aclose()
        state.db.close()

    app = FastAPI(title="Agentic RAG over Live Data and Memory", lifespan=lifespan)
    state = AppState(settings, model, client)
    app.state.core = state

    def redirect_uri(source: str) -> str:
        return f"{settings.backend_url.rstrip('/')}/api/oauth/{'google' if source == 'gmail' else 'notion'}/callback"

    def back_to_app(**params: str) -> RedirectResponse:
        return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/?{urlencode(params)}", status_code=303)

    # -------------------------------------------------------------- status

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return state.status()

    # ---------------------------------------------------------------- OAuth

    @app.get("/api/connect/{source}")
    async def connect(source: str) -> RedirectResponse:
        state_token = secrets.token_urlsafe(24)
        if source == "gmail":
            if not settings.google_configured:
                return back_to_app(error="Gmail isn't set up yet. Add your Google OAuth client to backend/.env (see the README).")
            state.db.save_oauth_state(state_token, "gmail")
            return RedirectResponse(gmail.auth_url(settings.google_client_id, redirect_uri("gmail"), state_token))
        if source == "notion":
            if not settings.notion_oauth_configured:
                return back_to_app(error="Notion OAuth isn't set up. Add NOTION_TOKEN or a Notion OAuth client to backend/.env (see the README).")
            state.db.save_oauth_state(state_token, "notion")
            return RedirectResponse(notion.auth_url(settings.notion_client_id, redirect_uri("notion"), state_token))
        raise HTTPException(404, "Unknown source")

    @app.get("/api/oauth/google/callback")
    async def google_callback(request: Request, code: str = "", error: str = "") -> RedirectResponse:
        if error:
            return back_to_app(error="Gmail wasn't connected because access was declined.")
        if not state.db.pop_oauth_state(request.query_params.get("state", ""), "gmail"):
            return back_to_app(error="That sign-in link expired. Click Connect Gmail again.")
        try:
            tokens = await gmail.exchange_code(client, settings.google_client_id, settings.google_client_secret, redirect_uri("gmail"), code)
        except SourceError as err:
            return back_to_app(error=str(err))
        state.save_connection("gmail", tokens.get("email") or "Gmail", tokens)
        return back_to_app(connected="gmail")

    @app.get("/api/oauth/notion/callback")
    async def notion_callback(request: Request, code: str = "", error: str = "") -> RedirectResponse:
        if error:
            return back_to_app(error="Notion wasn't connected because access was declined.")
        if not state.db.pop_oauth_state(request.query_params.get("state", ""), "notion"):
            return back_to_app(error="That sign-in link expired. Click Connect Notion again.")
        try:
            tokens = await notion.exchange_code(client, settings.notion_client_id, settings.notion_client_secret, redirect_uri("notion"), code)
        except SourceError as err:
            return back_to_app(error=str(err))
        state.save_connection("notion", tokens["workspace"], tokens)
        return back_to_app(connected="notion")

    @app.delete("/api/connections/{source}")
    async def disconnect(source: str) -> dict[str, Any]:
        conn = state.connection(source)
        if conn and source == "gmail":
            await gmail.revoke(client, conn[1])
        state.db.execute("delete from connections where source = ?", (source,))
        return state.status()

    # -------------------------------------------------------- conversations

    @app.get("/api/conversations")
    async def conversations() -> list[dict[str, Any]]:
        return state.db.list_conversations()

    @app.post("/api/conversations")
    async def new_conversation() -> dict[str, Any]:
        return state.db.create_conversation()

    @app.get("/api/conversations/{cid}")
    async def conversation(cid: str) -> dict[str, Any]:
        conv = state.db.get_conversation(cid)
        if not conv:
            raise HTTPException(404, "This conversation doesn't exist.")
        return {**conv, "messages": state.db.list_messages(cid)}

    @app.delete("/api/conversations/{cid}")
    async def delete_conversation(cid: str) -> dict[str, bool]:
        state.db.delete_conversation(cid)
        return {"ok": True}

    @app.post("/api/conversations/{cid}/messages")
    async def ask(cid: str, body: AskBody) -> StreamingResponse:
        conv = state.db.get_conversation(cid)
        if not conv:
            raise HTTPException(404, "This conversation doesn't exist.")
        question = body.content.strip()

        async def stream() -> AsyncIterator[str]:
            if state.model is None:
                yield sse("error", {"message": "Add your API key as LLM_API_KEY in backend/.env, then restart the backend."})
                return
            user_msg = state.db.add_message(cid, "user", question)
            yield sse("user", user_msg)
            live, readers = state.sources()
            agent = Agent(state.model, live, readers, state.memory, state.embedder, state.db, settings.max_agent_steps)
            try:
                async for event in agent.run(cid, question):
                    if event["type"] == "answer":
                        saved = state.db.add_message(cid, "assistant", event["content"], event["steps"], event["cited"])
                        if conv["title"] == "New chat":
                            title = question if len(question) <= 60 else question[:57].rsplit(" ", 1)[0] + "…"
                            state.db.rename_conversation(cid, title)
                        yield sse("answer", saved)
                    elif event["type"] == "error":
                        state.db.delete_message(user_msg["id"])
                        yield sse("error", {"message": event["message"]})
                        return
                    else:
                        yield sse(event["type"], event)
            except Exception:  # noqa: BLE001 - report any failure to the user instead of a broken stream
                log.exception("Agent failed")
                state.db.delete_message(user_msg["id"])
                yield sse("error", {"message": "Something went wrong while answering. Check the backend terminal for details."})
                return
            yield sse("done", {})

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # --------------------------------------------------------------- memory

    @app.get("/api/memories")
    async def memories() -> list[dict[str, Any]]:
        return state.memory.list()

    @app.post("/api/memories")
    async def add_memory(body: MemoryBody) -> dict[str, Any]:
        memory, _ = await state.memory.add(body.text)
        return memory

    @app.delete("/api/memories/{memory_id}")
    async def delete_memory(memory_id: str) -> dict[str, bool]:
        if not state.memory.delete(memory_id):
            raise HTTPException(404, "That memory doesn't exist.")
        return {"ok": True}

    @app.exception_handler(SourceError)
    async def source_error(_: Request, exc: SourceError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    # ------------------------------------------------- built frontend (optional)

    dist = Path(BACKEND_DIR).parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> FileResponse:
            target = dist / path
            if path and target.is_file() and dist in target.resolve().parents:
                return FileResponse(target)
            return FileResponse(dist / "index.html")

    return app


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()
