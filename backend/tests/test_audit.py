"""Tests for audit logging utilities."""

from unittest.mock import MagicMock

import pytest

from app.core.audit import AuditLogMiddleware


class TestAuditMiddleware:
    """Tests for AuditLogMiddleware helper methods."""

    @pytest.fixture
    def middleware(self) -> AuditLogMiddleware:
        """Create middleware instance."""
        return AuditLogMiddleware(app=MagicMock())

    def test_get_client_ip_direct(self, middleware: AuditLogMiddleware) -> None:
        """Test IP extraction from direct connection."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "192.168.1.1"

        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_forwarded(self, middleware: AuditLogMiddleware) -> None:
        """Test IP extraction from X-Forwarded-For header."""
        request = MagicMock()
        request.headers.get.return_value = "10.0.0.1, 10.0.0.2"

        ip = middleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_get_client_ip_no_client(self, middleware: AuditLogMiddleware) -> None:
        """Test IP extraction when client is None."""
        request = MagicMock()
        request.headers.get.return_value = None
        request.client = None

        ip = middleware._get_client_ip(request)
        assert ip == "unknown"

    def test_extract_resource_type_labs(self, middleware: AuditLogMiddleware) -> None:
        """Test resource type extraction for labs endpoint."""
        result = middleware._extract_resource_type("/api/v1/labs/123")
        assert result == "labs"

    def test_extract_resource_type_signals(self, middleware: AuditLogMiddleware) -> None:
        """Test resource type extraction for signals endpoint."""
        result = middleware._extract_resource_type("/api/v1/labs/uuid-here/signals")
        assert result == "labs"

    def test_extract_resource_type_unknown(self, middleware: AuditLogMiddleware) -> None:
        """Test resource type extraction returns unknown for unrecognized paths."""
        result = middleware._extract_resource_type("/api/v1")
        assert result == "unknown"

    def test_extract_resource_id_valid_uuid(self, middleware: AuditLogMiddleware) -> None:
        """Test UUID extraction from path."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        result = middleware._extract_resource_id(f"/api/v1/labs/{uuid_str}")
        assert result == uuid_str

    def test_extract_resource_id_no_uuid(self, middleware: AuditLogMiddleware) -> None:
        """Test UUID extraction when no UUID in path."""
        result = middleware._extract_resource_id("/api/v1/labs")
        assert result is None

    def test_extract_resource_id_invalid_uuid(self, middleware: AuditLogMiddleware) -> None:
        """Test UUID extraction with invalid UUID format."""
        result = middleware._extract_resource_id("/api/v1/labs/not-a-uuid")
        assert result is None
