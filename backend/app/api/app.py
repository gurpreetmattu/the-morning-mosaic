"""The FastAPI application.

Routes are synchronous where they touch the database, so Starlette runs them
in its threadpool (see docs/adr/0001). Only the signup route is async, because
the Turnstile check is an outbound HTTP call.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import account, archive, public
from app.api.security import SecurityHeadersMiddleware
from app.api.session import CSRF_HEADER
from app.config.settings import Settings, get_settings
from app.render.email import BRAND


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    app = FastAPI(
        title=f"{BRAND} API",
        # The API is for the project's own frontend and the links in its
        # emails; there is nothing here for third parties to explore.
        docs_url="/docs" if not config.is_prod else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not config.is_prod else None,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        # Only the project's own frontend calls this, and it is served from
        # the same origin, so the allowance is exact rather than a wildcard.
        allow_origins=[str(config.base_url).rstrip("/")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", CSRF_HEADER],
    )

    app.include_router(public.router)
    app.include_router(archive.router)
    app.include_router(account.router)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
