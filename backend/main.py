"""Compatibility entry point for ``uvicorn main:app``.

The application implementation lives in ``app.main``.
"""

from app.main import app, create_app

__all__ = ["app", "create_app"]
