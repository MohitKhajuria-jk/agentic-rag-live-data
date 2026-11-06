import asyncio
import json

from fastapi.testclient import TestClient

from app.main import create_app
from app.memory import MemoryStore

from .conftest import ScriptedModel, answer, tool_call


def events(response) -> list[tuple[str, dict]]:
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_status_reports_demo_sources_and_model(settings):
    with TestClient(create_app(settings, ScriptedModel([]))) as client:
        data = client.get("/api/status").json()
    assert data["llm"]["ready"] is True
    assert data["sources"]["gmail"] == {
        "connected": False, "demo": True, "label": "Demo inbox", "can_connect": False,
        "setup_hint": "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env (see the README).", "fixed": False,
    }


def test_full_conversation_streams_steps_and_saves_the_answer(settings):
    model = ScriptedModel([tool_call("search_gmail", {"query": "flight"}), answer("You fly at 06:15 [1].")])
    with TestClient(create_app(settings, model)) as client:
        cid = client.post("/api/conversations").json()["id"]
        r = client.post(f"/api/conversations/{cid}/messages", json={"content": "When is my flight?"})
        assert r.headers["content-type"].startswith("text/event-stream")
        got = events(r)
        assert [e for e, _ in got] == ["user", "step", "step_done", "answer", "done"]
        assert got[3][1]["cited"][0]["title"] == "Booking confirmed: BLR to DEL"
        conv = client.get(f"/api/conversations/{cid}").json()
        assert conv["title"] == "When is my flight?"
        assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
        assert conv["messages"][1]["steps"][0]["summary"] == "Found 1 email"


def test_model_errors_are_reported_and_the_question_is_not_kept(settings):
    from app.llm import LLMError

    async def fail(messages):
        raise LLMError("The model's rate limit was reached.")

    class Failing(ScriptedModel):
        async def chat(self, messages, tools, tool_choice="auto"):
            raise LLMError("The model's rate limit was reached.")

    with TestClient(create_app(settings, Failing([]))) as client:
        cid = client.post("/api/conversations").json()["id"]
        got = events(client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}))
        assert got[-1] == ("error", {"message": "The model's rate limit was reached."})
        assert client.get(f"/api/conversations/{cid}").json()["messages"] == []


def test_missing_api_key_gives_setup_instructions(settings):
    settings.llm_api_key = ""
    with TestClient(create_app(settings)) as client:
        cid = client.post("/api/conversations").json()["id"]
        got = events(client.post(f"/api/conversations/{cid}/messages", json={"content": "hi"}))
    assert got == [("error", {"message": "Add your API key as LLM_API_KEY in backend/.env, then restart the backend."})]


def test_memory_endpoints(settings):
    with TestClient(create_app(settings, ScriptedModel([]))) as client:
        m = client.post("/api/memories", json={"text": "Lives in Bengaluru."}).json()
        assert client.post("/api/memories", json={"text": "lives in bengaluru"}).json()["id"] == m["id"]
        assert [x["text"] for x in client.get("/api/memories").json()] == ["Lives in Bengaluru."]
        assert client.delete(f"/api/memories/{m['id']}").json() == {"ok": True}
        assert client.delete(f"/api/memories/{m['id']}").status_code == 404


def test_connecting_without_oauth_setup_explains_what_to_do(settings):
    with TestClient(create_app(settings, ScriptedModel([])), follow_redirects=False) as client:
        r = client.get("/api/connect/gmail")
    assert r.status_code == 303
    assert "error=Gmail+isn%27t+set+up+yet" in r.headers["location"]


def test_oauth_callback_rejects_unknown_state(settings):
    settings.google_client_id, settings.google_client_secret = "id", "secret"
    with TestClient(create_app(settings, ScriptedModel([])), follow_redirects=False) as client:
        start = client.get("/api/connect/gmail")
        assert start.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "gmail.readonly" in start.headers["location"]
        r = client.get("/api/oauth/google/callback", params={"code": "x", "state": "forged"})
    assert "expired" in r.headers["location"]


def test_tokens_are_encrypted_at_rest(settings):
    app = create_app(settings, ScriptedModel([]))
    core = app.state.core
    core.save_connection("notion", "My workspace", {"access_token": "secret-token-123"})
    raw = core.db.query("select token_enc from connections")[0]["token_enc"]
    assert b"secret-token-123" not in raw
    assert core.connection("notion") == ("My workspace", {"access_token": "secret-token-123"})


def test_memory_recall_ranks_by_relevance(tmp_path):
    from app.db import Database

    store = MemoryStore(Database(tmp_path / "m.db"), None)
    facts = ["Prefers short answers.", "Studies computer science.", "Has a dog named Bruno.", "Interview prep focuses on graphs.",
             "Lives in Bengaluru.", "Uses Notion for notes.", "Likes cricket.", "Final review is in November."]
    for f in facts:
        asyncio.run(store.add(f))
    top = asyncio.run(store.relevant("what is my dog called", k=3))
    assert top[0]["text"] == "Has a dog named Bruno."
