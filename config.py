"""Central configuration for Goii Music Bot.

Secrets are read from environment variables (or an optional local ``.env``
file). Nothing sensitive is hard-coded in the source code any more.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    """Tiny dependency-free ``.env`` loader for local development.

    Real environment variables always win over values from the file.
    """
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name, str(default)))
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(_get(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """All runtime settings in one immutable place."""

    bot_token: str = ""
    bot_username: str = ""  # @username from @BotFather (no @ needed)
    ai_provider: str = "auto"
    ai_api_key: str = ""
    ai_key_hint: str = ""  # which provider-specific env var supplied the key
    ai_model: str = ""
    ai_base_url: str = ""
    ai_timeout: float = 12.0
    max_results: int = 5
    audio_quality: str = "96"
    max_file_mb: int = 12
    download_dir: str = "downloads"
    port: int = 8080

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        key, hint = "", ""
        for var, provider in (
            ("AI_API_KEY", ""),
            ("GEMINI_API_KEY", "gemini"),
            ("GROQ_API_KEY", "groq"),
            ("OPENAI_API_KEY", "openai"),
        ):
            value = _get(var)
            if value:
                key, hint = value, provider
                break

        return cls(
            bot_token=_get("BOT_TOKEN") or _get("TELEGRAM_BOT_TOKEN"),
            bot_username=_get("BOT_USERNAME").lstrip("@"),
            ai_provider=(_get("AI_PROVIDER", "auto") or "auto").lower(),
            ai_api_key=key,
            ai_key_hint=hint,
            ai_model=_get("AI_MODEL"),
            ai_base_url=_get("AI_BASE_URL"),
            ai_timeout=_get_float("AI_TIMEOUT", 12.0),
            max_results=max(1, min(_get_int("MAX_SEARCH_RESULTS", 5), 8)),
            audio_quality=_get("AUDIO_QUALITY", "96"),
            max_file_mb=_get_int("MAX_FILE_MB", 12),
            download_dir=_get("DOWNLOAD_DIR", "downloads"),
            port=_get_int("PORT", 8080),
        )

    @property
    def bot_link(self) -> str:
        """Public Telegram link, e.g. https://t.me/GoiiMusicBot."""
        return f"https://t.me/{self.bot_username}" if self.bot_username else ""

    @property
    def bot_id(self) -> str:
        """Numeric bot id (the part before ':' in the token). Not a secret."""
        head = self.bot_token.split(":", 1)[0]
        return head if head.isdigit() else ""

    def resolved_provider(self) -> str:
        """Work out which AI engine to actually use.

        Returns one of: local, gemini, groq, openai, openrouter, custom.
        A missing key (or ``AI_PROVIDER=local``) always means local mode, so
        the bot keeps working with zero configuration.
        """
        provider = self.ai_provider
        if provider in {"local", "off", "none", "false", "0", "disabled"}:
            return "local"
        if not self.ai_api_key:
            return "local"
        if provider == "auto":
            if self.ai_key_hint in {"gemini", "groq", "openai"}:
                return self.ai_key_hint
            return (_get("AI_AUTO_PROVIDER", "gemini") or "gemini").lower()
        if provider in {"gemini", "google", "googleai"}:
            return "gemini"
        if provider in {"groq"}:
            return "groq"
        if provider in {"openai"}:
            return "openai"
        if provider in {"openrouter"}:
            return "openrouter"
        return "custom"  # any OpenAI-compatible endpoint via AI_BASE_URL
