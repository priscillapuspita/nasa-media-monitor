"""Centralized environment loading and validation."""

from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MENTION_QUERY = 'NASA OR Artemis OR "James Webb" OR "Kennedy Space Center" OR JPL'
DEFAULT_REDDIT_USER_AGENT = "nasa-media-monitor/0.1 by personal-project"
REQUIRED_ENV_VARS = (
    "DATABASE_URL",
    "NEWSAPI_KEY",
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


class ConfigError(RuntimeError):
    pass


def load_environment(env_path: str | Path = ".env") -> None:
    path = Path(env_path)
    try:
        from dotenv import load_dotenv

        load_dotenv(path)
        return
    except ModuleNotFoundError:
        pass

    if not path.exists():
        return

    with path.open("r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue

            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_secret(name: str) -> str | None:
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return None

    try:
        value = st.secrets.get(name)
    except Exception:
        return None

    if value is None:
        return None

    return str(value)


def get_config_value(name: str, default: str | None = None) -> str | None:
    load_environment()
    return get_secret(name) or os.environ.get(name) or default


def require_config_value(name: str) -> str:
    value = get_config_value(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def require_env(*names: str) -> dict[str, str]:
    values = {name: get_config_value(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

    return {name: values[name] for name in names if values[name] is not None}


def get_env(name: str, default: str | None = None) -> str | None:
    return get_config_value(name, default)


def get_required_database_url() -> str:
    return require_env("DATABASE_URL")["DATABASE_URL"]


DATABASE_URL = get_config_value("DATABASE_URL")
NEWSAPI_KEY = get_config_value("NEWSAPI_KEY")
REDDIT_CLIENT_ID = get_config_value("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = get_config_value("REDDIT_CLIENT_SECRET")
TELEGRAM_BOT_TOKEN = get_config_value("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = get_config_value("TELEGRAM_CHAT_ID")
HUGGINGFACE_API_TOKEN = get_config_value("HUGGINGFACE_API_TOKEN")
REDDIT_USER_AGENT = get_config_value("REDDIT_USER_AGENT", DEFAULT_REDDIT_USER_AGENT)
MENTION_QUERY = get_config_value("MENTION_QUERY", DEFAULT_MENTION_QUERY)
