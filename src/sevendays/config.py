"""Runtime configuration, entirely environment-driven (12-factor)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# Default model per provider. Anthropic IDs per the claude-api reference.
# For openai, set MODEL explicitly to whatever your account has access to.
_DEFAULT_MODEL = {
    "anthropic": "claude-sonnet-4-6",
    "mistral": "mistral-large-latest",
    "openai": "gpt-4o",
    "stub": "stub",
}


@dataclass(frozen=True)
class Config:
    provider: str          # "stub" | "anthropic" | "mistral"
    model: str
    api_key: str | None
    content_dir: Path      # working tree the artifacts live in
    total_days: int
    day_override: int | None
    base_url: str          # public site, used for notification links
    max_html_bytes: int

    ntfy_url: str
    ntfy_topic: str | None

    git_push: bool
    content_repo: str | None
    content_branch: str
    git_token: str | None
    git_author_name: str
    git_author_email: str

    @classmethod
    def from_env(cls) -> "Config":
        provider = os.getenv("LLM_PROVIDER", "stub").lower()
        return cls(
            provider=provider,
            model=os.getenv("MODEL", _DEFAULT_MODEL.get(provider, "claude-sonnet-4-6")),
            api_key=(
                os.getenv("LLM_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("MISTRAL_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            ),
            content_dir=Path(os.getenv("CONTENT_DIR", "./content")).resolve(),
            total_days=int(os.getenv("TOTAL_DAYS", "7")),
            day_override=int(os.environ["DAY"]) if os.getenv("DAY") else None,
            base_url=os.getenv("BASE_URL", "https://genesis.hoyos.dev").rstrip("/"),
            max_html_bytes=int(os.getenv("MAX_HTML_BYTES", "250000")),
            ntfy_url=os.getenv("NTFY_URL", "https://ntfy.sh").rstrip("/"),
            ntfy_topic=os.getenv("NTFY_TOPIC"),
            git_push=_bool(os.getenv("GIT_PUSH"), False),
            content_repo=os.getenv("CONTENT_REPO"),
            content_branch=os.getenv("CONTENT_BRANCH", "content"),
            git_token=os.getenv("GIT_TOKEN"),
            git_author_name=os.getenv("GIT_AUTHOR_NAME", "Seven Days"),
            git_author_email=os.getenv("GIT_AUTHOR_EMAIL", "seven-days@hoyos.dev"),
        )
