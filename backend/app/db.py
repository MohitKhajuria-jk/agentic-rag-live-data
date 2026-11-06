"""SQLite storage: conversations, messages, cited sources, memories and connections."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA = """
create table if not exists connections (
  source text primary key,
  account text not null,
  token_enc blob not null,
  updated_at real not null
);
create table if not exists oauth_states (
  state text primary key,
  source text not null,
  created_at real not null
);
create table if not exists conversations (
  id text primary key,
  title text not null,
  created_at real not null,
  updated_at real not null
);
create table if not exists messages (
  id integer primary key autoincrement,
  conversation_id text not null references conversations(id) on delete cascade,
  role text not null,
  content text not null,
  steps_json text not null default '[]',
  cited_json text not null default '[]',
  created_at real not null
);
-- Every item the agent has retrieved in a conversation, numbered [1], [2], ... so
-- follow-up questions can refer back to them.
create table if not exists conversation_sources (
  conversation_id text not null references conversations(id) on delete cascade,
  n integer not null,
  source text not null,
  item_id text not null,
  data_json text not null,
  primary key (conversation_id, n)
);
create table if not exists memories (
  id text primary key,
  text text not null,
  embedding_json text,
  created_at real not null
);
"""


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("pragma foreign_keys = on")
        self._conn.execute("pragma journal_mode = wal")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self._lock, self._conn:
            return self._conn.execute(sql, params)

    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        self._conn.close()

    # ---------------------------------------------------------------- conversations

    def create_conversation(self, title: str = "New chat") -> dict[str, Any]:
        cid = uuid.uuid4().hex
        now = time.time()
        self.execute("insert into conversations values (?, ?, ?, ?)", (cid, title, now, now))
        return {"id": cid, "title": title, "created_at": now, "updated_at": now}

    def list_conversations(self) -> list[dict[str, Any]]:
        rows = self.query("select * from conversations order by updated_at desc limit 200")
        return [dict(r) for r in rows]

    def get_conversation(self, cid: str) -> dict[str, Any] | None:
        rows = self.query("select * from conversations where id = ?", (cid,))
        return dict(rows[0]) if rows else None

    def rename_conversation(self, cid: str, title: str) -> None:
        self.execute("update conversations set title = ? where id = ?", (title, cid))

    def touch_conversation(self, cid: str) -> None:
        self.execute("update conversations set updated_at = ? where id = ?", (time.time(), cid))

    def delete_conversation(self, cid: str) -> None:
        self.execute("delete from conversations where id = ?", (cid,))

    def add_message(self, cid: str, role: str, content: str, steps: list | None = None, cited: list | None = None) -> dict[str, Any]:
        now = time.time()
        cur = self.execute(
            "insert into messages (conversation_id, role, content, steps_json, cited_json, created_at) values (?, ?, ?, ?, ?, ?)",
            (cid, role, content, json.dumps(steps or []), json.dumps(cited or []), now),
        )
        self.touch_conversation(cid)
        return {"id": cur.lastrowid, "role": role, "content": content, "steps": steps or [], "cited": cited or [], "created_at": now}

    def delete_message(self, message_id: int) -> None:
        self.execute("delete from messages where id = ?", (message_id,))

    def list_messages(self, cid: str) -> list[dict[str, Any]]:
        rows = self.query("select * from messages where conversation_id = ? order by id", (cid,))
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "steps": json.loads(r["steps_json"]),
                "cited": json.loads(r["cited_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def load_sources(self, cid: str) -> list[dict[str, Any]]:
        rows = self.query("select data_json from conversation_sources where conversation_id = ? order by n", (cid,))
        return [json.loads(r["data_json"]) for r in rows]

    def save_source(self, cid: str, item: dict[str, Any]) -> None:
        self.execute(
            "insert or replace into conversation_sources values (?, ?, ?, ?, ?)",
            (cid, item["n"], item["source"], item["item_id"], json.dumps(item)),
        )

    # -------------------------------------------------------------------- oauth

    def save_oauth_state(self, state: str, source: str) -> None:
        self.execute("delete from oauth_states where created_at < ?", (time.time() - 900,))
        self.execute("insert into oauth_states values (?, ?, ?)", (state, source, time.time()))

    def pop_oauth_state(self, state: str, source: str) -> bool:
        rows = self.query("select created_at from oauth_states where state = ? and source = ?", (state, source))
        self.execute("delete from oauth_states where state = ?", (state,))
        return bool(rows) and time.time() - rows[0]["created_at"] < 900
