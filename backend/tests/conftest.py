import os
import tempfile
from typing import Any, Callable

import pytest

# Keep test databases out of backend/data, even when the app module is imported.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="rag-test-"))

from app.config import Settings  # noqa: E402


class ScriptedModel:
    """Stands in for the LLM: returns prepared replies in order and records every request."""

    label = "Scripted test model"

    def __init__(self, replies: list[dict[str, Any] | Callable[[list[dict[str, Any]]], dict[str, Any]]]):
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], tool_choice: str = "auto") -> dict[str, Any]:
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools, "tool_choice": tool_choice})
        if not self.replies:
            return {"role": "assistant", "content": "No more scripted replies."}
        reply = self.replies.pop(0)
        return reply(messages) if callable(reply) else reply


def tool_call(name: str, args: dict[str, Any], call_id: str = "call_1", signature: str | None = None) -> dict[str, Any]:
    call: dict[str, Any] = {"id": call_id, "type": "function", "function": {"name": name, "arguments": __import__("json").dumps(args)}}
    if signature:
        call["extra_content"] = {"google": {"thought_signature": signature}}
    return {"role": "assistant", "content": None, "tool_calls": [call]}


def answer(text: str) -> dict[str, Any]:
    return {"role": "assistant", "content": text}


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        llm_provider="gemini",
        llm_api_key="test-key",
        embedding_model="none",
        demo_mode=True,
        google_client_id="",
        google_client_secret="",
        notion_token="",
        notion_client_id="",
        notion_client_secret="",
    )
