"""FastAPI application entry point.

Initializes the application, configures CORS middleware, and
registers routers. Additional routers will be mounted here
as features are implemented.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints.ingestion import router as ingestion_router
from app.api.endpoints.ranking import router as ranking_router
from app.api.endpoints.rules import router as rules_router
from app.api.endpoints.scoring import router as scoring_router
from app.api.endpoints.signals import router as signals_router
from app.config import APP_ENV, CORS_ORIGINS, STORAGE_BACKEND, validate_startup_configuration
from app.db.errors import register_database_error_handlers
from app.db.seeding import seed_database_presets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate environment configuration and seed presets in PostgreSQL mode at startup."""
    validate_startup_configuration()
    storage_backend = os.getenv("STORAGE_BACKEND", STORAGE_BACKEND).strip().lower()
    if storage_backend == "postgres":
        seed_database_presets()
    yield


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Team Recruitment Automation Tool",
    description=(
        "Helps hackathon organizers shortlist the top teams from "
        "registration data using configurable eligibility rules "
        "and weighted scoring."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Register centralized database error handlers
register_database_error_handlers(app)

# ---------------------------------------------------------------------------
# CORS middleware – allow frontend origins, expose Content-Disposition
# ---------------------------------------------------------------------------
_cors_origins = CORS_ORIGINS
_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(ingestion_router)
app.include_router(signals_router)
app.include_router(rules_router)
app.include_router(scoring_router)
app.include_router(ranking_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Return a simple status indicating the backend is running."""
    return {
        "status": "healthy",
        "environment": os.getenv("APP_ENV", APP_ENV),
        "version": app.version,
        "storage_backend": os.getenv("STORAGE_BACKEND", STORAGE_BACKEND),
    }

