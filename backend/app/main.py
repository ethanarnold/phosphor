"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health, labs, signals, states
from app.core.audit import AuditLogMiddleware
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.security import AuthenticatedUser, get_current_user

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
    description="AI research tool for labs - Lab State Compressor",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

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
async def set_user_context(request: Request, call_next):
    """Set user context for downstream middleware (audit logging)."""
    # Skip for unauthenticated endpoints
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)

    try:
        # Try to extract user info from JWT
        from fastapi.security import HTTPAuthorizationCredentials

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            from app.core.security import ClerkJWTValidator

            validator = ClerkJWTValidator(settings)
            claims = validator.validate_token(token)
            request.state.user_id = claims.get("sub", "anonymous")
            request.state.org_id = claims.get("org_id")
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
    states.router,
    prefix=f"{settings.api_prefix}/labs",
    tags=["states"],
)
