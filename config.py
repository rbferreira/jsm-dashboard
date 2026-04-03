"""Centralized configuration for the SD Dashboard project.

All environment variables are loaded from a .env file via python-dotenv.
A single `settings` singleton is exposed for use across the application.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Return the value of an env var or raise a clear error if missing."""
    value = os.getenv(name, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            "Check your .env file or container env configuration."
        )
    return value


def _optional(name: str, default: str = "") -> str:
    """Return the value of an optional env var, falling back to *default*."""
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # Jira
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    jira_project: str

    # Anthropic (optional — only needed for catalog_generator.py)
    anthropic_api_key: str

    # Derived
    jira_api_base: str = field(init=False)

    def __post_init__(self) -> None:
        # frozen=True prevents direct attribute assignment, so we use
        # object.__setattr__ for derived fields.
        object.__setattr__(
            self,
            "jira_api_base",
            f"{self.jira_base_url}/rest/api/3",
        )


def _load_settings() -> Settings:
    return Settings(
        jira_base_url=_require("JIRA_BASE_URL").rstrip("/"),
        jira_email=_require("JIRA_EMAIL"),
        jira_api_token=_require("JIRA_API_TOKEN"),
        jira_project=_require("JIRA_PROJECT"),
        anthropic_api_key=_optional("ANTHROPIC_API_KEY"),
    )


settings: Settings = _load_settings()
