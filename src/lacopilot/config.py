from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LAC_", env_file=".env", extra="ignore")

    workspace: Path = Path("./workspace")
    config_dir: Path = Path("./config")
    ollama_host: str = "http://127.0.0.1:11434"
    fast_model: str = "qwen3.5:9b"
    model: str = "qwen3.5:9b"
    deep_model: str = "gpt-oss:20b"
    model_mode: Literal["fast", "main", "deep"] = "main"
    context_window: int = Field(default=32768, ge=2048, le=262144)
    max_output_tokens: int = Field(default=4096, ge=128, le=32768)
    max_tool_rounds: int = Field(default=10, ge=1, le=30)
    max_tool_result_chars: int = Field(default=30000, ge=1000, le=200000)
    max_history_chars: int = Field(default=50000, ge=2000, le=500000)
    max_chat_chars: int = Field(default=20000, ge=500, le=100000)
    ollama_timeout_seconds: float = Field(default=300.0, ge=5.0, le=1800.0)
    personality: str = "mentor"

    allow_web: bool = False
    allow_remote_ollama: bool = False
    allow_cloud_models: bool = False
    allow_network_bind: bool = False
    bridge_origins: str = (
        "http://127.0.0.1:3000,http://localhost:3000,"
        "tauri://localhost,http://tauri.localhost,https://tauri.localhost"
    )
    require_approval_for_writes: bool = True
    require_approval_for_external: bool = True
    api_token: str = ""
    sql_read_only: bool = True
    max_file_mb: int = Field(default=500, ge=1, le=10000)
    max_excel_uncompressed_mb: int = Field(default=1024, ge=10, le=10000)
    max_excel_archive_entries: int = Field(default=20_000, ge=100, le=100_000)
    max_query_rows: int = Field(default=5000, ge=1, le=50000)

    @property
    def incoming_dir(self) -> Path:
        return self.workspace / "incoming"

    @property
    def outputs_dir(self) -> Path:
        return self.workspace / "outputs"

    @property
    def logs_dir(self) -> Path:
        return self.workspace / "logs"

    @property
    def knowledge_dir(self) -> Path:
        return self.workspace / "knowledge"

    @property
    def working_dir(self) -> Path:
        return self.workspace / "working"

    @property
    def archive_dir(self) -> Path:
        return self.workspace / "archive"

    @property
    def memory_db(self) -> Path:
        return self.workspace / "memory.sqlite3"

    @property
    def knowledge_db(self) -> Path:
        return self.workspace / "knowledge.sqlite3"

    @property
    def conversations_db(self) -> Path:
        return self.workspace / "conversations.sqlite3"

    @property
    def actions_db(self) -> Path:
        return self.workspace / "actions.sqlite3"

    @property
    def analysis_history_db(self) -> Path:
        return self.workspace / "analysis_history.sqlite3"

    @property
    def personalities_path(self) -> Path:
        return self.config_dir / "personalities.yaml"

    @property
    def database_profiles_path(self) -> Path:
        return self.config_dir / "database_profiles.yaml"

    def choose_model(self, mode: str | None = None) -> str:
        selected = (mode or self.model_mode or "main").lower()
        if selected == "fast":
            return self.fast_model
        if selected == "deep":
            return self.deep_model
        if selected != "main":
            raise ValueError("model mode fast/main/deep olmalı")
        return self.model

    def parsed_bridge_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.bridge_origins.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError(
                "LAC_BRIDGE_ORIGINS wildcard (*) kabul etmez; izinli origin'leri açıkça yazın"
            )
        return origins

    def ensure_dirs(self) -> None:
        for path in [
            self.workspace,
            self.incoming_dir,
            self.outputs_dir,
            self.logs_dir,
            self.knowledge_dir,
            self.working_dir,
            self.archive_dir,
            self.config_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        self._ensure_default_config("personalities.yaml", self.personalities_path)
        self._ensure_default_config("database_profiles.yaml", self.database_profiles_path)

    @staticmethod
    def _ensure_default_config(resource_name: str, destination: Path) -> None:
        if destination.exists():
            return
        resource = files("lacopilot").joinpath("resources", resource_name)
        destination.write_text(resource.read_text(encoding="utf-8"), encoding="utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
