"""Health check endpoint - unauthenticated."""

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["health"],
)
async def health_check() -> HealthResponse:
    """Check API health.

    This endpoint is unauthenticated and used for load balancer health checks.
    """
    return HealthResponse(status="healthy", version="0.1.0")
