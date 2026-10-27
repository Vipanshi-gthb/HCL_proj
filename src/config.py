"""Configuration management for P_123.

Loads configuration from environment variables and local .env file.
Adheres strictly to the privacy and safety rules in P123_ARCHITECTURE.md section 9.
NEVER logs or displays the API key.
"""

import os
from dataclasses import dataclass, field
from typing import List

# Attempt to load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass


@dataclass
class Settings:
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip())
    gemini_fallback_models: List[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash,gemini-2.0-flash").split(",")
        if m.strip()
    ])
    gemini_timeout_seconds: int = field(default_factory=lambda: int(os.getenv("GEMINI_TIMEOUT_SECONDS", "20")))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "10")))
    max_rows: int = field(default_factory=lambda: int(os.getenv("MAX_ROWS", "200000")))
    max_cols: int = field(default_factory=lambda: int(os.getenv("MAX_COLS", "100")))
    max_question_chars: int = field(default_factory=lambda: int(os.getenv("MAX_QUESTION_CHARS", "500")))
    rate_limit_per_min: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MIN", "10")))

    @property
    def is_gemini_configured(self) -> bool:
        """Returns True if a non-empty GEMINI_API_KEY is present."""
        return bool(self.gemini_api_key and not self.gemini_api_key.startswith("your_gemini_api_key"))


def get_settings() -> Settings:
    """Return a fresh Settings instance."""
    return Settings()
