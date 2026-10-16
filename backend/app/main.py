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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate environment configuration at application startup."""
    validate_startup_configuration()
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

# ---------------------------------------------------------------------------
# CORS middleware – allow the Vite dev server during development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

