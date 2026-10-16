"""Global pytest configuration and root fixtures.

Guarantees that STORAGE_BACKEND is forced to 'memory' and APP_ENV defaults to 'development'
before application modules and routers are loaded.
"""

from __future__ import annotations

import os

# Force in-memory storage backend for unit test suite execution
os.environ["STORAGE_BACKEND"] = "memory"
if "APP_ENV" not in os.environ:
    os.environ["APP_ENV"] = "development"
