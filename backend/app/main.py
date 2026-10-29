import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.deps import limiter
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.mongo import close_database, initialize_database
from app.workers.analysis_worker import run_worker

logger = logging.getLogger("clinic-api")


def _init_sentry() -> None:
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.sentry_environment,
            traces_sample_rate=0.1,
        )
    except Exception:
        logger.exception("Could not initialise Sentry")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    await initialize_database()

    worker_task = None
    if settings.analysis_worker_enabled:
        worker_task = asyncio.create_task(
            run_worker(), name="analysis-worker"
        )

    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task
        await close_database()


def create_app() -> FastAPI:
    configure_logging("clinic-api", settings.log_level)
    _init_sentry()

    app = FastAPI(
        title="Clinic Voice Agent API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    register_error_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(settings.trusted_hosts),
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(api_router, prefix="/api")
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
