"""Application configuration.

Loads settings from environment variables with sensible defaults
for local development. In production, set these via a .env file
or your deployment platform's environment configuration.
"""

import os

from dotenv import load_dotenv

# Load .env file if it exists (no error if missing)
load_dotenv()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
APP_ENV: str = os.getenv("APP_ENV", "development")
APP_DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

# ---------------------------------------------------------------------------
# Storage & Database Settings
# ---------------------------------------------------------------------------
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "memory")

DATABASE_URL: str | None = os.getenv("DATABASE_URL", None)
DATABASE_URL_POOLED: str | None = os.getenv("DATABASE_URL_POOLED", None)
TEST_DATABASE_URL: str | None = os.getenv("TEST_DATABASE_URL", None)


def normalize_database_url(url: str) -> str:
    """Normalize a database URL to use Psycopg 3 driver with required SSL.

    Accepts:
    - postgresql://...
    - postgres://...
    - postgresql+psycopg://...

    Converts scheme to postgresql+psycopg://.
    Enforces sslmode=require without duplicating existing query parameters.
    Never logs or exposes the URL or its credentials.
    """
    import urllib.parse

    if not url or not isinstance(url, str) or not url.strip():
        raise ValueError("Invalid database URL: URL must be a non-empty string.")

    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except Exception:
        raise ValueError("Failed to parse database URL.") from None

    scheme = parsed.scheme.lower()
    if scheme in ("postgresql", "postgres", "postgresql+psycopg"):
        new_scheme = "postgresql+psycopg"
    else:
        raise ValueError(
            "Invalid database URL scheme: expected postgresql, postgres, or postgresql+psycopg."
        )

    query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    has_sslmode = any(k.lower() == "sslmode" for k, _ in query_params)
    if not has_sslmode:
        query_params.append(("sslmode", "require"))

    new_query = urllib.parse.urlencode(query_params)
    return urllib.parse.urlunsplit(
        (new_scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
    )


def assert_safe_test_database(url: str) -> None:
    """Validate that the supplied database URL is safe for test execution.

    Safety Rules:
    - Reject if TEST_DATABASE_URL is unset, or if the supplied url does not match
      TEST_DATABASE_URL after normalization.
    - If DATABASE_URL is set, reject if the two URLs are identical or share the same
      host and database name.
    - If DATABASE_URL is unset, allow a valid TEST_DATABASE_URL, provided all other
      checks pass.
    - Never include connection URLs in exception messages.
    """
    import urllib.parse

    test_db_env = os.getenv("TEST_DATABASE_URL")
    if not test_db_env or not test_db_env.strip():
        raise ValueError("Safety check failed: TEST_DATABASE_URL is not configured.")

    try:
        norm_supplied = normalize_database_url(url)
        norm_test = normalize_database_url(test_db_env)
    except Exception:
        raise ValueError("Safety check failed: Unable to normalize test database URL.") from None

    if norm_supplied != norm_test:
        raise ValueError(
            "Safety check failed: Supplied URL does not match configured TEST_DATABASE_URL."
        )

    dev_db_env = os.getenv("DATABASE_URL")
    if dev_db_env and dev_db_env.strip():
        try:
            norm_dev = normalize_database_url(dev_db_env)
        except Exception:
            raise ValueError(
                "Safety check failed: Unable to normalize development DATABASE_URL."
            ) from None

        if norm_supplied == norm_dev:
            raise ValueError(
                "Safety check failed: TEST_DATABASE_URL cannot be identical to DATABASE_URL."
            )

        parsed_dev = urllib.parse.urlsplit(norm_dev)
        parsed_test = urllib.parse.urlsplit(norm_supplied)

        dev_host = (parsed_dev.hostname or "").lower()
        test_host = (parsed_test.hostname or "").lower()
        dev_db = parsed_dev.path.lstrip("/").lower()
        test_db = parsed_test.path.lstrip("/").lower()

        if dev_host and test_host and dev_host == test_host:
            if dev_db and test_db and dev_db == test_db:
                raise ValueError(
                    "Safety check failed: TEST_DATABASE_URL cannot share the same host and database name as DATABASE_URL."
                )


def validate_startup_configuration() -> None:
    """Verify application environment configuration at startup.

    Must be executed during application startup (lifespan), not at module import.
    In production: STORAGE_BACKEND must be 'postgres' and DATABASE_URL must be set.
    In development: STORAGE_BACKEND defaults to 'memory' and logs a warning.
    """
    import logging

    logger = logging.getLogger("app.config")

    env = os.getenv("APP_ENV", APP_ENV).strip().lower()
    storage = os.getenv("STORAGE_BACKEND", STORAGE_BACKEND).strip().lower()
    db_url = os.getenv("DATABASE_URL")

    if env == "production":
        if storage != "postgres":
            raise RuntimeError(
                "Invalid startup configuration: In production, STORAGE_BACKEND must be set to 'postgres'."
            )
        if not db_url or not str(db_url).strip():
            raise RuntimeError(
                "Invalid startup configuration: In production, DATABASE_URL must be configured."
            )
    else:
        if storage == "memory":
            logger.warning(
                "WARNING: Application running in development with STORAGE_BACKEND='memory'. "
                "All data is held in-memory and will be lost on restart."
            )

# ---------------------------------------------------------------------------
# CORS – origins allowed to call the API
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

# ---------------------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------------------
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

# ---------------------------------------------------------------------------
# GitHub Integration
# ---------------------------------------------------------------------------
GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN", None)
GITHUB_API_BASE_URL: str = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com").rstrip("/")
GITHUB_REQUEST_TIMEOUT: float = float(os.getenv("GITHUB_REQUEST_TIMEOUT", "10.0"))
