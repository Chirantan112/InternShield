"""Application configuration for InternShield.

Secrets are read from environment variables (normally via a local .env file).
Never commit real credentials or production secret keys.
"""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable without treating 'false' as true."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration shared by local and deployed environments."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(PROJECT_ROOT / 'instance' / 'internshield.sqlite3').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads are stored outside the public static directory.
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(5 * 1024 * 1024)))
    ALLOWED_UPLOAD_EXTENSIONS = {"txt", "pdf"}
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER", str(PROJECT_ROOT / "instance" / "uploads")
    )

    # Session and browser security. HTTPS-only cookies can be enabled on deployment.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True

    # Login throttling: use a shared Redis-compatible store in multi-worker
    # production deployments; memory:// is suitable for local/single-process use.
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True

    # Optional AI provider configuration. The rule engine must work when these
    # values are absent; an API key will be supplied through the local environment
    # later and must never be stored in source control.
    AI_ENABLED = _env_bool("AI_ENABLED", False)
    AI_PROVIDER = os.getenv("AI_PROVIDER", "openai-compatible")
    AI_API_KEY = os.getenv("AI_API_KEY")
    AI_BASE_URL = os.getenv("AI_BASE_URL")
    AI_MODEL = os.getenv("AI_MODEL")

    # Basic application limits.
    MAX_ANALYSIS_CHARACTERS = int(os.getenv("MAX_ANALYSIS_CHARACTERS", "50000"))
    MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "10"))


class DevelopmentConfig(Config):
    DEBUG = _env_bool("FLASK_DEBUG", True)


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"
    SQLALCHEMY_DATABASE_URI = "sqlite://"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
