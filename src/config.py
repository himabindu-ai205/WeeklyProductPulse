"""Load config.yaml and environment variables. Fail fast on missing required keys."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

# Project root: .../M3-9 (parent of src/)
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


class WindowsConfig(BaseModel):
    corpus_weeks: int = Field(ge=1)
    reporting_days: int = Field(ge=1)
    min_week_reviews: int = Field(ge=0)
    fallback_days: int = Field(ge=1)


class ThemeSeed(BaseModel):
    id: str
    label: str


class ThemesConfig(BaseModel):
    max_total: int = Field(ge=1, le=5)
    highlight: int = Field(ge=1)
    seeds: list[ThemeSeed]


class NoteConfig(BaseModel):
    max_words: int = Field(ge=1)
    quote_count: int = Field(ge=1)
    action_count: int = Field(ge=1)
    quote_min_chars: int = Field(ge=1)
    quote_max_chars: int = Field(ge=1)


class DeliveryConfig(BaseModel):
    recipient: str
    doc_title: str
    email_subject: str
    email_body_mode: Literal["full_note_plus_link", "link_only"]


class LimitsConfig(BaseModel):
    cluster_batch_size: int = Field(ge=1)
    cluster_max_attempts: int = Field(ge=1)
    generate_max_attempts: int = Field(ge=1)
    # Groq free tier: ~30 RPM → default 2.5s between calls
    llm_request_interval_seconds: float = Field(default=2.5, ge=0)


class ScheduleConfig(BaseModel):
    """Ops knobs for Phase 7 weekly runs (GitHub Actions / Task Scheduler / cron)."""

    enabled: bool = False
    day_of_week: str = "monday"
    hour_local: int = Field(default=9, ge=0, le=23)
    timezone: str = "Asia/Kolkata"
    fetch_before_run: bool = True
    export_path: str = "data/exports/groww_play_reviews.csv"
    scrape_count: int = Field(default=2000, ge=100)
    once_per_week: bool = False


class AppConfig(BaseModel):
    """Behavioural knobs from config.yaml (no secrets)."""

    product_name: str
    package_id: str = "com.nextbillion.groww"
    play_store_url: str = (
        "https://play.google.com/store/apps/details?id=com.nextbillion.groww&hl=en_IN"
    )
    windows: WindowsConfig
    themes: ThemesConfig
    note: NoteConfig
    delivery: DeliveryConfig
    limits: LimitsConfig
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)


class EnvSettings(BaseModel):
    """Secrets and runtime env. API keys optional at scaffold."""

    groq_api_key: str | None = None
    pulse_model: str = "openai/gpt-oss-120b"
    # Railway Google Workspace MCP (Streamable HTTP)
    mcp_server_url: str = "https://mcp-server-production-f0ca.up.railway.app"
    mcp_http_token: str | None = None
    # Existing Google Doc id for append_to_google_doc (server cannot create Docs)
    google_doc_id: str | None = None
    docs_mcp_server: str = "google-workspace"
    gmail_mcp_server: str = "google-workspace"
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None


class Settings(BaseModel):
    app: AppConfig
    env: EnvSettings
    root: Path = ROOT


def _require_mapping(data: Any, path: Path) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"Config at {path} must be a YAML mapping, got {type(data).__name__}")
    return data


def load_app_config(config_path: Path | None = None) -> AppConfig:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Missing required config file: {path}")

    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    data = _require_mapping(raw, path)
    required_top = ("product_name", "windows", "themes", "note", "delivery", "limits")
    missing = [k for k in required_top if k not in data]
    if missing:
        raise ValueError(f"config.yaml missing required keys: {', '.join(missing)}")

    try:
        return AppConfig.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Invalid config.yaml: {e}") from e


def load_env_settings(dotenv_path: Path | None = None) -> EnvSettings:
    """Load .env if present. Does not require secrets at scaffold time."""
    load_dotenv(dotenv_path or (ROOT / ".env"), override=False)

    tracing_raw = os.getenv("LANGSMITH_TRACING", "false").strip().lower()
    tracing = tracing_raw in ("1", "true", "yes", "on")

    return EnvSettings(
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        pulse_model=os.getenv("PULSE_MODEL", "openai/gpt-oss-120b"),
        mcp_server_url=os.getenv(
            "MCP_SERVER_URL", "https://mcp-server-production-f0ca.up.railway.app"
        ).rstrip("/"),
        mcp_http_token=os.getenv("MCP_HTTP_TOKEN") or None,
        google_doc_id=os.getenv("GOOGLE_DOC_ID") or None,
        docs_mcp_server=os.getenv("DOCS_MCP_SERVER", "google-workspace"),
        gmail_mcp_server=os.getenv("GMAIL_MCP_SERVER", "google-workspace"),
        langsmith_tracing=tracing,
        langsmith_api_key=os.getenv("LANGSMITH_API_KEY") or None,
    )


def load_settings(config_path: Path | None = None) -> Settings:
    return Settings(app=load_app_config(config_path), env=load_env_settings(), root=ROOT)
