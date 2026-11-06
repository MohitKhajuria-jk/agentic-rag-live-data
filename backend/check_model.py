"""Checks the connection to the model API and times a few small requests.

Run it from the backend folder:

    .venv\\Scripts\\python check_model.py

It uses the settings in backend/.env and prints how long each step takes,
so you can tell a network problem from a slow model.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.agent import tool_schemas
from app.config import get_settings

TIMEOUT = httpx.Timeout(90.0, connect=15.0)


def line(label: str, result: str) -> None:
    print(f"  {label:<38} {result}")


def error_text(r: httpx.Response) -> str:
    try:
        data = r.json()
        if isinstance(data, list) and data:
            data = data[0]
        return str(data.get("error", {}).get("message") or r.text)[:200]
    except ValueError:
        return r.text[:200]


async def timed(http: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> tuple[float, httpx.Response | None, str]:
    start = time.monotonic()
    try:
        r = await http.request(method, url, timeout=TIMEOUT, **kwargs)
        return time.monotonic() - start, r, ""
    except httpx.ConnectTimeout:
        return time.monotonic() - start, None, "could not connect within 15 s"
    except httpx.TimeoutException:
        return time.monotonic() - start, None, "no reply within 90 s"
    except httpx.HTTPError as err:
        return time.monotonic() - start, None, f"{type(err).__name__}: {err}"


async def chat(http: httpx.AsyncClient, base: str, headers: dict, model: str, effort: str | None, tools: bool) -> tuple[float, str]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Answer in one short sentence."},
            {"role": "user", "content": "hi"},
        ],
    }
    if effort:
        body["reasoning_effort"] = effort
    if tools:
        body["tools"] = tool_schemas({"gmail": None, "notion": None})  # type: ignore[dict-item]
        body["tool_choice"] = "auto"
    seconds, r, err = await timed(http, "POST", f"{base}/chat/completions", json=body, headers=headers)
    if err:
        return seconds, f"FAILED after {seconds:.1f}s: {err}"
    if r.status_code != 200:
        return seconds, f"HTTP {r.status_code} after {seconds:.1f}s: {error_text(r)}"
    message = r.json()["choices"][0]["message"]
    what = "tool call" if message.get("tool_calls") else repr((message.get("content") or "")[:40])
    return seconds, f"OK in {seconds:.1f}s ({what})"


async def main() -> None:
    s = get_settings()
    base = s.resolved_base_url
    model = s.resolved_model
    headers = {"Content-Type": "application/json"}
    if s.llm_api_key:
        headers["Authorization"] = f"Bearer {s.llm_api_key}"

    print("\nSettings")
    line("Provider", s.llm_provider)
    line("Model", model or "(not set)")
    line("Endpoint", base)
    line("API key", f"set ({len(s.llm_api_key)} characters)" if s.llm_api_key else "MISSING: add LLM_API_KEY to .env")
    line("Thinking effort", s.resolved_reasoning_effort or "provider default")

    async with httpx.AsyncClient() as http:
        print("\n1. Connection")
        host = urlparse(base).netloc
        seconds, r, err = await timed(http, "GET", f"{base}/models", headers=headers)
        if err:
            line(f"Reach {host}", f"FAILED after {seconds:.1f}s: {err}")
            print("\nYour computer can't reach the model API. Check your internet connection, VPN,")
            print("antivirus or firewall, or try another network (for example a phone hotspot).")
            return
        line(f"Reach {host}", f"OK in {seconds:.1f}s (HTTP {r.status_code})")
        models: list[str] = []
        if r.status_code == 200:
            models = [m["id"].removeprefix("models/") for m in r.json().get("data", [])]
            flash = [m for m in models if "flash" in m and "embedding" not in m and "image" not in m and "tts" not in m]
            line("Flash models for your key", ", ".join(flash[:8]) or "none found")
        else:
            line("List models", f"HTTP {r.status_code}: {error_text(r)}")

        print(f"\n2. Replies from {model}")
        plain = await chat(http, base, headers, model, None, tools=False)
        line("Plain reply, default thinking", plain[1])
        low = await chat(http, base, headers, model, s.resolved_reasoning_effort or None, tools=False)
        line(f"Plain reply, thinking '{s.resolved_reasoning_effort or 'default'}'", low[1])
        with_tools = await chat(http, base, headers, model, s.resolved_reasoning_effort or None, tools=True)
        line("With the agent's tools", with_tools[1])

        lite = next((m for m in models if "flash-lite" in m and "preview" not in m), None) or next((m for m in models if "flash-lite" in m), None)
        lite_result = None
        if lite and lite != model:
            print(f"\n3. A lighter model: {lite}")
            lite_result = await chat(http, base, headers, lite, s.resolved_reasoning_effort or None, tools=True)
            line("With the agent's tools", lite_result[1])

    print("\nWhat this means")
    slow = with_tools[0] > 30 or not with_tools[1].startswith("OK")
    if not slow:
        print(f"  {model} answers normally. If the app is still slow, paste this output and the backend window's lines.")
    elif lite_result and lite_result[1].startswith("OK") and lite_result[0] < 30:
        print(f"  {model} is slow for your key right now, but {lite} answers quickly.")
        print(f"  To switch, set LLM_MODEL={lite} in backend/.env and restart the backend.")
    elif "api key" in with_tools[1].lower():
        print("  The API key was rejected. Check LLM_API_KEY in backend/.env (no spaces or quotes).")
    elif "HTTP 429" in with_tools[1]:
        print("  You've hit the free tier's rate limit. Wait a minute or two and try again.")
    else:
        print("  Replies are slow or failing. Paste this whole output in the chat so the cause can be pinned down.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
