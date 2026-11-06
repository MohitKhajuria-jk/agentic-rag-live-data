import asyncio
import json

from app.agent import Agent, SourceRegistry, extract_citations
from app.db import Database
from app.memory import MemoryStore
from app.retrieval import Document
from app.sources.demo import DemoSource

from .conftest import ScriptedModel, answer, tool_call


def make_agent(tmp_path, model):
    db = Database(tmp_path / "t.db")
    demo = {"gmail": DemoSource("gmail"), "notion": DemoSource("notion")}
    readers = {(k, True): v for k, v in demo.items()}
    agent = Agent(model, demo, readers, MemoryStore(db, None), None, db, max_steps=4)
    conv = db.create_conversation()
    return agent, db, conv["id"]


def run(agent, db, cid, question):
    db.add_message(cid, "user", question)

    async def collect():
        return [e async for e in agent.run(cid, question)]

    events = asyncio.run(collect())
    final = events[-1]
    if final["type"] == "answer":  # saved the same way the API does
        db.add_message(cid, "assistant", final["content"], final["steps"], final["cited"])
    return events


def test_agent_searches_two_sources_and_cites_them(tmp_path):
    model = ScriptedModel([
        tool_call("search_gmail", {"query": "from:northwind interview"}, "c1", signature="sig-abc"),
        tool_call("search_notion", {"query": "interview prep"}, "c2"),
        answer("Your interview is on the date in the email [1]. Revise graphs and DP [2]. Ignore [9]."),
    ])
    agent, db, cid = make_agent(tmp_path, model)
    events = run(agent, db, cid, "When is my Northwind interview and what should I revise?")

    kinds = [e["type"] for e in events]
    assert kinds == ["step", "step_done", "step", "step_done", "answer"]
    assert events[0]["step"]["label"] == "Searching Demo inbox for “from:northwind interview”"
    final = events[-1]
    assert final["content"].endswith("Revise graphs and DP [2]. Ignore.")
    assert [c["title"] for c in final["cited"]] == ["Interview invitation: Software Engineer Intern", "Interview prep: Northwind Labs"]
    assert "text" not in final["cited"][0]

    # The second request sends the first assistant message back unchanged, thought signature included.
    second = model.calls[1]["messages"]
    assistant = next(m for m in second if m["role"] == "assistant")
    assert assistant["tool_calls"][0]["extra_content"] == {"google": {"thought_signature": "sig-abc"}}
    tool_msg = next(m for m in second if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "c1" and tool_msg["name"] == "search_gmail"
    assert '<source n="1">' in tool_msg["content"]


def test_source_numbers_persist_across_turns_and_can_be_reread(tmp_path):
    model = ScriptedModel([
        tool_call("search_gmail", {"query": "invoice"}),
        answer("It's ₹1,248 [1]."),
        tool_call("read_source", {"n": 1}),
        tool_call("search_notion", {"query": "budget"}),
        answer("That's above your ₹1,000 budget [2], based on the invoice [1]."),
    ])
    agent, db, cid = make_agent(tmp_path, model)
    run(agent, db, cid, "How much was my cloud bill?")
    events = run(agent, db, cid, "Is that within my budget?")

    # The follow-up prompt lists sources found earlier, and history includes the first answer.
    system = model.calls[2]["messages"][0]["content"]
    assert "[1] Email: Your Cloudly invoice for last month" in system
    assert any(m["role"] == "assistant" and "₹1,248 [1]" in m["content"] for m in model.calls[2]["messages"])
    read_step = [e for e in events if e["type"] == "step_done"][0]["step"]
    assert read_step["label"] == "Reading [1] Your Cloudly invoice for last month"
    assert [c["n"] for c in events[-1]["cited"]] == [2, 1]
    assert len(SourceRegistry(db, cid).items) == 2


def test_agent_saves_memories_and_uses_them_later(tmp_path):
    model = ScriptedModel([
        tool_call("save_memory", {"fact": "Prefers answers as short bullet points."}),
        answer("Got it."),
        answer("Sure."),
    ])
    agent, db, cid = make_agent(tmp_path, model)
    events = run(agent, db, cid, "Remember that I like short bullet-point answers.")
    assert {"type": "memory_saved", "text": "Prefers answers as short bullet points."} in events
    run(agent, db, cid, "Hi")
    assert "- Prefers answers as short bullet points." in model.calls[-1]["messages"][0]["content"]


def test_agent_stops_after_max_steps_and_asks_for_an_answer(tmp_path):
    looping = [tool_call("search_gmail", {"query": f"q{i}"}, f"c{i}") for i in range(4)]
    model = ScriptedModel(looping + [answer("Here's what I found.")])
    agent, db, cid = make_agent(tmp_path, model)
    events = run(agent, db, cid, "Find everything")
    assert events[-1]["content"] == "Here's what I found."
    assert model.calls[-1]["tool_choice"] == "none"
    assert model.calls[-1]["messages"][-1]["content"].startswith("Stop searching")


def test_tool_arguments_that_are_not_json_do_not_crash(tmp_path):
    bad = {"role": "assistant", "content": None, "tool_calls": [{"id": "x", "type": "function", "function": {"name": "read_source", "arguments": "not json"}}]}
    model = ScriptedModel([bad, answer("Done.")])
    agent, db, cid = make_agent(tmp_path, model)
    events = run(agent, db, cid, "Read it")
    assert events[1]["step"]["summary"] == "No source number"
    assert events[-1]["content"] == "Done."


def test_extract_citations_handles_groups_and_unknown_numbers(tmp_path):
    db = Database(tmp_path / "c.db")
    cid = db.create_conversation()["id"]
    reg = SourceRegistry(db, cid)
    for i in range(3):
        reg.register(Document("gmail", f"id{i}", f"Email {i}", "text"))
    text, cited = extract_citations("A [3, 1]. B [2][7] .", reg)
    assert text == "A [3][1]. B [2]."
    assert [c["n"] for c in cited] == [3, 1, 2]


def test_prompt_marks_demo_sources_and_lists_memories(tmp_path):
    model = ScriptedModel([answer("Hello.")])
    agent, db, cid = make_agent(tmp_path, model)
    asyncio.run(agent.memory.add("Is a final-year computer science student."))
    run(agent, db, cid, "hello")
    system = model.calls[0]["messages"][0]["content"]
    assert "Demo inbox (sample data for trying the app" in system
    assert "- Is a final-year computer science student." in system
    tools = [t["function"]["name"] for t in model.calls[0]["tools"]]
    assert tools == ["search_gmail", "search_notion", "read_source", "save_memory", "search_memory"]
    assert json.dumps(model.calls[0]["tools"])  # schemas are plain JSON
