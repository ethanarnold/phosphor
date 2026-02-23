"""Audit logging middleware and utilities."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.database import AsyncSessionLocal


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all write operations to audit_logs table."""

    # HTTP methods that modify data
    AUDIT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Paths to exclude from audit logging
    EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and log write operations."""
        # Skip non-write methods and excluded paths
        if request.method not in self.AUDIT_METHODS:
            return await call_next(request)

        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)

        # Capture request details before processing
        user_id = getattr(request.state, "user_id", "anonymous")
        org_id = getattr(request.state, "org_id", None)
        ip_address = self._get_client_ip(request)

        # Process the request
        response = await call_next(request)

        # Log successful write operations (2xx status codes)
        if 200 <= response.status_code < 300:
            await self._log_audit_entry(
                user_id=user_id,
                org_id=org_id,
                action=request.method,
                resource_type=self._extract_resource_type(request.url.path),
                resource_id=self._extract_resource_id(request.url.path),
                ip_address=ip_address,
                path=request.url.path,
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _extract_resource_type(self, path: str) -> str:
        """Extract resource type from URL path."""
        # Remove API prefix and split
        parts = path.strip("/").split("/")
        # Find the resource type (usually after 'api/v1')
        for i, part in enumerate(parts):
            if part in ("v1", "api"):
                continue
            # Skip UUIDs
            try:
                uuid.UUID(part)
                continue
            except ValueError:
                return part
        return "unknown"

    def _extract_resource_id(self, path: str) -> str | None:
        """Extract resource ID (UUID) from URL path."""
        parts = path.strip("/").split("/")
        for part in parts:
            try:
                uuid.UUID(part)
                return part
            except ValueError:
                continue
        return None

    async def _log_audit_entry(
        self,
        user_id: str,
        org_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        ip_address: str,
        path: str,
    ) -> None:
        """Write audit log entry to database."""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""
                        INSERT INTO audit_logs
                        (id, lab_id, user_id, action, resource_type, resource_id, details, ip_address, created_at)
                        VALUES (
                            gen_random_uuid(),
                            (SELECT id FROM labs WHERE clerk_org_id = :org_id LIMIT 1),
                            :user_id,
                            :action,
                            :resource_type,
                            :resource_id,
                            :details,
                            :ip_address::inet,
                            :created_at
                        )
                    """),
                    {
                        "org_id": org_id,
                        "user_id": user_id,
                        "action": action,
                        "resource_type": resource_type,
                        "resource_id": uuid.UUID(resource_id) if resource_id else None,
                        "details": json.dumps({"path": path}),
                        "ip_address": ip_address,
                        "created_at": datetime.now(UTC),
                    },
                )
                await session.commit()
        except Exception:
            # Don't fail requests due to audit logging errors
            # In production, this should log to a fallback location
            pass


async def log_audit_event(
    session: AsyncSession,
    user_id: str,
    lab_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str = "internal",
) -> None:
    """Manually log an audit event.

    Use this for business-logic level auditing beyond HTTP operations.
    """
    await session.execute(
        text("""
            INSERT INTO audit_logs
            (id, lab_id, user_id, action, resource_type, resource_id, details, ip_address, created_at)
            VALUES (
                gen_random_uuid(),
                :lab_id,
                :user_id,
                :action,
                :resource_type,
                :resource_id,
                :details,
                :ip_address::inet,
                :created_at
            )
        """),
        {
            "lab_id": lab_id,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": json.dumps(details) if details else None,
            "ip_address": ip_address,
            "created_at": datetime.now(UTC),
        },
    )
