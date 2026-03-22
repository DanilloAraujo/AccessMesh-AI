"""
backend/main.py
───────────────
Main entry point for the AccessMesh-AI FastAPI application.

The application is assembled by the factory in backend/app/factory.py.
This module keeps the `app` object at the package root so that Uvicorn
can be pointed at `backend.main:app`.

Responsibilities delegated to factory.py:
  - Load configuration (backend/app/config.py)
  - Initialise Azure services (Web PubSub, Speech, Gesture)
  - Wire HubManager, RealtimeDispatcher, MessageRouter
  - Register all routers (app/routes/ + legacy backend/routers/)
  - Configure CORS and logging middleware
"""

from __future__ import annotations

import uvicorn

from shared.config import settings
from backend.app.factory import create_app

# `app` is the FastAPI instance consumed by Uvicorn: `backend.main:app`
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
        log_level="info",
    )
