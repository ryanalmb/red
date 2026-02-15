"""Health endpoint for API server (Story 14.1).

GET /health — Returns server status, uptime, and version.
No authentication required (for load balancer health checks).
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from pydantic import BaseModel

import cyberred

router = APIRouter()

# Module-level start time, set when lifespan starts
_start_time: float | None = None


def set_start_time(t: float) -> None:
    """Set the server start time (called from lifespan)."""
    global _start_time
    _start_time = t


def reset_start_time() -> None:
    """Reset the server start time to None (called on shutdown).

    Prevents stale uptime reporting after server stop.
    """
    global _start_time
    _start_time = None


def get_uptime() -> float:
    """Get server uptime in seconds."""
    if _start_time is None:
        return 0.0
    return time.time() - _start_time


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    uptime: float
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return server health status.

    This endpoint does NOT require authentication,
    allowing load balancers and monitoring systems to check server health.

    Returns:
        HealthResponse with status, uptime seconds, and version string.
    """
    return HealthResponse(
        status="ok",
        uptime=get_uptime(),
        version=cyberred.__version__,
    )
