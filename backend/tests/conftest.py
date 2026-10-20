"""Global pytest configuration and root fixtures.

Guarantees that STORAGE_BACKEND is forced to 'memory' and APP_ENV defaults to 'development'
before application modules and routers are loaded.
"""

from __future__ import annotations

import os

# Force in-memory storage backend for unit test suite execution
os.environ["STORAGE_BACKEND"] = "memory"
os.environ["AUTH_ENABLED"] = "false"
if "APP_ENV" not in os.environ:
    os.environ["APP_ENV"] = "development"

import pytest
from app.storage import default_storage_factory


@pytest.fixture(autouse=True)
def ensure_memory_storage_backend():
    """Ensure every test begins and ends with storage factory set to memory."""
    default_storage_factory.configure(backend="memory")
    yield
    default_storage_factory.configure(backend="memory")

