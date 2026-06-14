from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    groq_api_key: str
    groq_model: str
    anthropic_api_key: str
    anthropic_model: str
    cors_origins: list[str]
    chunk_max_chars: int

    def __init__(self) -> None:
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "")
        self.groq_model = os.environ.get(
            "GROQ_MODEL", "llama-3.3-70b-versatile"
        )
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.anthropic_model = os.environ.get(
            "ANTHROPIC_MODEL", "claude-haiku-4-5"
        )
        raw_origins = os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
        )
        self.cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        self.chunk_max_chars = int(os.environ.get("CHUNK_MAX_CHARS", "1000"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
