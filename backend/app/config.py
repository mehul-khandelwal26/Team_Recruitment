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
# Database (placeholder – not yet connected)
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/team_recruitment_db",
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
