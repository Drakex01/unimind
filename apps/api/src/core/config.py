"""Application Configuration and Settings."""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    unimind_env: str = "development"
    unimind_app_port: int = 8000
    unimind_app_host: str = "0.0.0.0"
    unimind_secret_key: str = "change-this-in-production-use-a-strong-32-char-random-string"
    unimind_log_level: str = "INFO"
    unimind_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    database_url: str = "sqlite+aiosqlite:///./data/unimind_dev.db"

    gemini_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    plugins_dir: str = str(Path(__file__).resolve().parent.parent.parent.parent.parent / "plugins")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.unimind_allowed_origins.split(",") if origin.strip()]


settings = Settings()
