"""App settings, read from environment variables or backend/.env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Preset endpoints for OpenAI-compatible chat APIs. Any of them can be overridden with LLM_BASE_URL.
PROVIDERS: dict[str, dict[str, str]] = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-3.5-flash",
        # Used automatically while the main model is overloaded or rate-limited.
        "fallback_model": "gemini-3.1-flash-lite",
        "embedding_model": "gemini-embedding-001",
        "label": "Google Gemini",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "",
        "embedding_model": "text-embedding-3-small",
        "label": "OpenAI",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "",
        "embedding_model": "",
        "label": "Anthropic Claude",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.1",
        "embedding_model": "nomic-embed-text",
        "label": "Ollama (local)",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    # Language model
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    # Backup model for when the main one is busy ("none" turns this off).
    llm_fallback_model: str = ""
    # How long the model may think before answering: low | medium | high, or "default" for the provider's own.
    # Empty means "low" on Gemini (fast, and plenty for searching and summarising) and the provider default elsewhere.
    llm_reasoning_effort: str = ""
    # Seconds to wait for one model reply.
    llm_timeout_seconds: float = 150
    # Embeddings for semantic search. Set to "none" to use keyword (BM25) ranking only.
    embedding_model: str = ""
    max_agent_steps: int = 6

    # Google (Gmail) OAuth client from Google Cloud Console
    google_client_id: str = ""
    google_client_secret: str = ""

    # Notion: either an internal integration token, or a public integration's OAuth client
    notion_token: str = ""
    notion_client_id: str = ""
    notion_client_secret: str = ""

    # Sample emails and Notion pages, used for any source that isn't connected
    demo_mode: bool = True

    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    # Encrypts stored OAuth tokens. Generated into data/.secret if not set.
    app_secret: str = ""
    data_dir: Path = BACKEND_DIR / "data"

    @property
    def provider(self) -> dict[str, str]:
        return PROVIDERS.get(self.llm_provider.lower(), PROVIDERS["gemini"])

    @property
    def resolved_base_url(self) -> str:
        return (self.llm_base_url or self.provider["base_url"]).rstrip("/")

    @property
    def resolved_model(self) -> str:
        return self.llm_model or self.provider["model"]

    @property
    def resolved_fallback_model(self) -> str:
        if self.llm_fallback_model.strip().lower() == "none":
            return ""
        fallback = self.llm_fallback_model.strip() or self.provider.get("fallback_model", "")
        return "" if fallback == self.resolved_model else fallback

    @property
    def resolved_reasoning_effort(self) -> str:
        value = self.llm_reasoning_effort.strip().lower()
        if value in ("none", "off", "default"):
            return ""
        if value:
            return value
        return "low" if self.llm_provider.lower() == "gemini" else ""

    @property
    def resolved_embedding_model(self) -> str:
        if self.embedding_model.lower() == "none":
            return ""
        return self.embedding_model or self.provider["embedding_model"]

    @property
    def llm_ready(self) -> bool:
        needs_key = self.llm_provider.lower() != "ollama"
        return bool(self.resolved_model) and (bool(self.llm_api_key) or not needs_key)

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def notion_oauth_configured(self) -> bool:
        return bool(self.notion_client_id and self.notion_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
