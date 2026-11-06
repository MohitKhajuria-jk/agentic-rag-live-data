import asyncio
import json

import httpx
import pytest

from app.llm import Embeddings, LLMError, OpenAICompatibleClient


def client_with(settings, handler):
    return OpenAICompatibleClient(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_chat_request_matches_the_openai_format_gemini_expects(settings):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Hi"}}]})

    tools = [{"type": "function", "function": {"name": "search_gmail", "parameters": {"type": "object"}}}]
    reply = asyncio.run(client_with(settings, handler).chat([{"role": "user", "content": "hello"}], tools))
    assert reply == {"role": "assistant", "content": "Hi"}
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "gemini-3.5-flash"
    assert seen["body"]["reasoning_effort"] == "low"
    assert seen["body"]["tool_choice"] == "auto" and seen["body"]["tools"] == tools


def test_a_busy_model_switches_to_the_backup_and_stays_there(settings, monkeypatch):
    models = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        models.append(model)
        if model == "gemini-3.5-flash":
            return httpx.Response(503, json=[{"error": {"message": "This model is currently experiencing high demand."}}])
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = client_with(settings, handler)
    assert asyncio.run(client.chat([], []))["content"] == "ok"
    assert asyncio.run(client.chat([], []))["content"] == "ok"
    assert models == ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.1-flash-lite"]
    assert client.label == "Google Gemini · gemini-3.1-flash-lite (backup while gemini-3.5-flash is busy)"


def test_overload_on_both_models_is_explained(settings, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    busy = lambda r: httpx.Response(503, json={"error": {"message": "high demand"}})  # noqa: E731
    with pytest.raises(LLMError, match="high demand for gemini-3.1-flash-lite"):
        asyncio.run(client_with(settings, busy).chat([], []))


def test_backup_model_can_be_turned_off(settings):
    settings.llm_fallback_model = "none"
    assert settings.resolved_fallback_model == ""
    settings.llm_fallback_model = ""
    settings.llm_model = "gemini-3.1-flash-lite"
    assert settings.resolved_fallback_model == ""  # never the same as the main model


def test_rate_limits_are_retried_then_explained(settings, monkeypatch):
    settings.llm_fallback_model = "none"
    calls = []

    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "1"}, json={"error": "quota"})

    with pytest.raises(LLMError, match="rate limit"):
        asyncio.run(client_with(settings, handler).chat([], []))
    assert len(calls) == 3


def test_a_temporary_error_recovers_on_retry(settings, monkeypatch):
    settings.llm_fallback_model = "none"
    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    responses = [httpx.Response(503), httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})]
    reply = asyncio.run(client_with(settings, lambda r: responses.pop(0)).chat([], []))
    assert reply["content"] == "ok"


@pytest.mark.parametrize(
    "status, message",
    [(401, "rejected the API key"), (404, "wasn't found"), (400, "returned an error \\(400\\)")],
)
def test_errors_tell_the_user_what_to_fix(settings, status, message):
    with pytest.raises(LLMError, match=message):
        asyncio.run(client_with(settings, lambda r: httpx.Response(status, text="bad")).chat([], []))


def test_gemini_bad_key_400_is_explained(settings):
    body = [{"error": {"code": 400, "message": "Please pass a valid API key", "status": "INVALID_ARGUMENT"}}]
    with pytest.raises(LLMError, match="rejected the API key"):
        asyncio.run(client_with(settings, lambda r: httpx.Response(400, json=body)).chat([], []))


def test_other_errors_show_the_api_message_not_raw_json(settings):
    body = {"error": {"message": "Request contains an invalid argument."}}
    with pytest.raises(LLMError, match=r"\(400\): Request contains an invalid argument\.$"):
        asyncio.run(client_with(settings, lambda r: httpx.Response(400, json=body)).chat([], []))


def test_embeddings_cache_and_fall_back_when_unavailable(settings):
    settings.embedding_model = "gemini-embedding-001"
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body["input"])
        return httpx.Response(200, json={"data": [{"index": i, "embedding": [float(i), 1.0]} for i in range(len(body["input"]))]})

    emb = Embeddings(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    first = asyncio.run(emb.embed(["a", "b"]))
    second = asyncio.run(emb.embed(["b", "c"]))
    assert first == [[0.0, 1.0], [1.0, 1.0]]
    assert second[0] == [1.0, 1.0]
    assert requests == [["a", "b"], ["c"]]  # "b" came from the cache

    broken = Embeddings(settings, httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(429))))
    assert asyncio.run(broken.embed(["x"])) is None
    assert broken.available is False  # keyword ranking takes over for a while


def test_reasoning_effort_is_only_set_by_default_on_gemini(settings):
    assert settings.resolved_reasoning_effort == "low"
    settings.llm_reasoning_effort = "none"
    assert settings.resolved_reasoning_effort == ""
    settings.llm_reasoning_effort = ""
    settings.llm_provider = "openai"
    assert settings.resolved_reasoning_effort == ""


def test_timeouts_are_not_retried_and_explain_the_wait(settings):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.extensions["timeout"]["read"])
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError, match="didn't answer within 150 seconds"):
        asyncio.run(client_with(settings, handler).chat([], []))
    assert calls == [150]


def test_a_dropped_connection_is_retried_once(settings, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.RemoteProtocolError("connection reset", request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    assert asyncio.run(client_with(settings, handler).chat([], []))["content"] == "ok"
    assert len(attempts) == 2


def test_embeddings_without_index_fields_keep_their_order(settings):
    """Gemini's OpenAI-compatible embeddings omit "index"."""
    settings.embedding_model = "gemini-embedding-001"

    def handler(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        return httpx.Response(200, json={"object": "list", "data": [{"object": "embedding", "embedding": [float(len(t))]} for t in texts]})

    emb = Embeddings(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert asyncio.run(emb.embed(["a", "bbb", "cc"])) == [[1.0], [3.0], [2.0]]
    assert emb.available is True
