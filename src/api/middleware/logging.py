"""Middleware de logging para requests y responses."""
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Loguea cada request con método, path, status y tiempo de respuesta."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()

        response = await call_next(request)

        duration_ms = int((time.time() - start) * 1000)
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else "unknown",
        )
        return response
