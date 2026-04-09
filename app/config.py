from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _get_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    service_name: str
    environment: str
    openai_api_key: str | None
    openai_model: str
    openai_temperature: float
    github_token: str | None
    github_api_url: str
    parseable_url: str | None
    parseable_username: str | None
    parseable_password: str | None
    parseable_dataset: str
    request_timeout: float
    log_tail_chars: int

    @property
    def parseable_configured(self) -> bool:
        return all(
            [
                self.parseable_url,
                self.parseable_username,
                self.parseable_password,
                self.parseable_dataset,
            ]
        )

    def missing_analysis_env(self) -> list[str]:
        missing: list[str] = []
        if not self.openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not self.parseable_url:
            missing.append("PARSEABLE_URL")
        if not self.parseable_username:
            missing.append("PARSEABLE_USERNAME")
        if not self.parseable_password:
            missing.append("PARSEABLE_PASSWORD")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("SERVICE_NAME", "github-actions-reader"),
        environment=os.getenv("APP_ENV", "development"),
        openai_api_key=_get_env("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0")),
        github_token=_get_env("GITHUB_TOKEN"),
        github_api_url=os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/"),
        parseable_url=_get_env("PARSEABLE_URL"),
        parseable_username=_get_env("PARSEABLE_USERNAME"),
        parseable_password=_get_env("PARSEABLE_PASSWORD"),
        parseable_dataset=os.getenv("PARSEABLE_DATASET", "agent-traces"),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")),
        log_tail_chars=int(os.getenv("LOG_TAIL_CHARS", "25000")),
    )
