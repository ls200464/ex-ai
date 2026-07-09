from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env relative to this file or current directory
_env_paths = [
    os.path.join(os.path.dirname(__file__), "..", ".env"),  # backend/.env from config.py
    ".env",
    os.path.join(os.getcwd(), "backend", ".env"),
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[p for p in _env_paths if os.path.exists(p)] or _env_paths[0],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./exskill.db"

    # LLM
    LLM_PROVIDER: str = "claude"
    LLM_MODEL: str = "claude-fable-5"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096

    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    # Embeddings
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VOYAGE_API_KEY: str = ""

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production-use-a-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000"


settings = Settings()
