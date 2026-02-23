"""Tests for health check endpoint."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Health check should return 200 and status."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_health_check_no_auth_required(client: TestClient) -> None:
    """Health check should work without authentication."""
    # Remove auth override to test unauthenticated access
    from app.main import app
    from app.core.security import get_current_user

    # Clear overrides temporarily
    original_override = app.dependency_overrides.get(get_current_user)
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]

    response = client.get("/health")
    assert response.status_code == 200

    # Restore override
    if original_override:
        app.dependency_overrides[get_current_user] = original_override
