"""Rate Limiting Middleware — Evangelista Intelligence Platform.

Bloquea IPs que exceden el umbral de requests por ventana de tiempo.
Aplicable a endpoints sensibles como simulaciones Monte Carlo.
"""
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiter:
    """Token-bucket style rate limiter in-memory."""

    def __init__(self, max_requests: int, window_seconds: int, block_seconds: int = 300):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        # client_ip -> list of timestamps
        self._requests: dict[str, list[float]] = defaultdict(list)
        # client_ip -> blocked until timestamp
        self._blocked: dict[str, float] = {}

    def _cleanup(self, client_ip: str):
        now = time.time()
        # Clear expired blocks
        if client_ip in self._blocked and now >= self._blocked[client_ip]:
            del self._blocked[client_ip]
            self._requests[client_ip] = []
        # Clear old request timestamps
        cutoff = now - self.window_seconds
        self._requests[client_ip] = [
            ts for ts in self._requests[client_ip] if ts > cutoff
        ]

    def is_blocked(self, client_ip: str) -> bool:
        self._cleanup(client_ip)
        return client_ip in self._blocked

    def record(self, client_ip: str) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        self._cleanup(client_ip)
        if self.is_blocked(client_ip):
            return False

        self._requests[client_ip].append(time.time())
        if len(self._requests[client_ip]) > self.max_requests:
            self._blocked[client_ip] = time.time() + self.block_seconds
            return False
        return True


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Applies rate limiting to specific route prefixes."""

    def __init__(
        self,
        app,
        limits: dict[str, tuple[int, int, int]] | None = None,
    ):
        """
        Args:
            app: ASGI app
            limits: {path_prefix: (max_requests, window_seconds, block_seconds)}
        """
        super().__init__(app)
        if limits is None:
            limits = {
                "/api/v1/sentinel": (5, 60, 300),  # 5 req/min, bloqueado 5min
                "/api/v1/monte-carlo": (5, 60, 300),
            }
        self.limits = limits
        self.limiters: dict[str, RateLimiter] = {}
        for prefix, (max_req, window, block) in limits.items():
            self.limiters[prefix] = RateLimiter(max_req, window, block)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Find matching limiter
        for prefix, limiter in self.limiters.items():
            if request.url.path.startswith(prefix):
                if limiter.is_blocked(client_ip):
                    remaining = limiter._blocked.get(client_ip, 0) - time.time()
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "rate_limit_exceeded",
                            "message": f"Demasiadas solicitudes. Reintente en {int(remaining)} segundos.",
                        },
                    )
                if not limiter.record(client_ip):
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "rate_limit_exceeded",
                            "message": "Demasiadas solicitudes. Usted ha sido bloqueado temporalmente.",
                        },
                    )
                break

        return await call_next(request)
