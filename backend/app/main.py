"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import (
    agents,
    documents,
    experiments,
    feedback,
    health,
    imports,
    labs,
    literature,
    matching,
    metrics,
    opportunities,
    search,
    signals,
    states,
)
from app.api.routes import api_keys as api_keys_routes
from app.core.audit import AuditLogMiddleware
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.rate_limit import limiter

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="Phosphor API",
    description="AI research tool for labs - Lab State Compressor & Opportunity Extraction",
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# CORS middleware - locked to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Audit logging middleware
app.add_middleware(AuditLogMiddleware)


@app.middleware("http")
async def set_user_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Set user context for downstream middleware (audit logging)."""
    # Skip for unauthenticated endpoints
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)

    try:
        # Try to extract user info from JWT
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            from app.core.security import ClerkJWTValidator

            validator = ClerkJWTValidator(settings)
            claims = validator.validate_token(token)
            request.state.user_id = claims.get("sub", "anonymous")
            request.state.org_id = claims.get("org_id")
        elif request.headers.get("X-API-Key"):
            # API key auth - set basic context for audit logging
            api_key_val = request.headers["X-API-Key"]
            request.state.user_id = f"apikey:{api_key_val[:8]}"
            request.state.org_id = None  # resolved later in auth dependency
    except Exception:
        request.state.user_id = "anonymous"
        request.state.org_id = None

    return await call_next(request)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    # In production, don't expose internal error details
    if settings.environment == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


# Include routers
app.include_router(health.router)
app.include_router(
    labs.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["labs"],
)
app.include_router(
    signals.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["signals"],
)
app.include_router(
    experiments.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["experiments"],
)
app.include_router(
    documents.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["documents"],
)
app.include_router(
    feedback.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["feedback"],
)
app.include_router(
    search.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["search"],
)
app.include_router(
    metrics.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["metrics"],
)
app.include_router(
    states.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["states"],
)
app.include_router(
    literature.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["literature"],
)
# `matching` must be registered before `opportunities`: both mount under
# /api/v1/labs, and matching's `/{lab_id}/opportunities/ranked` would
# otherwise be shadowed by opportunities' `/{lab_id}/opportunities/{opp_id:UUID}`
# (FastAPI uses first-match, not longest-prefix, routing).
app.include_router(
    matching.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["matching"],
)
app.include_router(
    opportunities.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["opportunities"],
)
app.include_router(
    api_keys_routes.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["api-keys"],
)
app.include_router(
    agents.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["agents"],
)
app.include_router(
    imports.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["imports"],
)
