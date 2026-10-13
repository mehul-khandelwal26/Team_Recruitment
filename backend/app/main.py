"""FastAPI application entry point.

Initializes the application, configures CORS middleware, and
registers routers. Additional routers will be mounted here
as features are implemented.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints.ingestion import router as ingestion_router
from app.api.endpoints.signals import router as signals_router
from app.config import APP_ENV, CORS_ORIGINS

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


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Return a simple status indicating the backend is running."""
    return {
        "status": "healthy",
        "environment": APP_ENV,
        "version": app.version,
    }

