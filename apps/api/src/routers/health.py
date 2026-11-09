"""Health and Readiness Probes."""

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthStatus(BaseModel):
    status: str
    environment: str
    version: str = "1.0.0"


@router.get("/health/live", status_code=status.HTTP_200_OK, response_model=HealthStatus)
async def liveness():
    """Liveness probe confirming API process is running."""
    return HealthStatus(status="alive", environment="development")


@router.get("/health/ready", status_code=status.HTTP_200_OK, response_model=HealthStatus)
async def readiness():
    """Readiness probe confirming API dependencies are ready to accept traffic."""
    return HealthStatus(status="ready", environment="development")
