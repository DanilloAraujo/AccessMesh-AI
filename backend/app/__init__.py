"""
backend/app
───────────
Application package for AccessMesh-AI.

Import create_app directly from backend.app.factory to avoid circular imports:

    from backend.app.factory import create_app
"""

__all__ = ["create_app"]
