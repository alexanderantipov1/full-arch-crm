"""HTTP middleware: request ID, structured access logs, exception → JSON."""

from __future__ import annotations

import os
import time
import uuid

import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from packages.core.exceptions import PlatformError

log = structlog.get_logger("api")

# Identifies which Cloud Run service answered. ``X-Service`` + ``X-Commit``
# let an operator (or smoke test) curl any endpoint and see which
# container served it. Cuts diagnostic time when a request lands on the
# wrong service due to routing surprises (ENG-153 post-mortem).
_SERVICE_NAME = "fusion-api"


def _commit_sha() -> str:
    return os.environ.get("APP_COMMIT_SHA", "dev")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id and emit a structured access log per request.

    Also stamps ``X-Service`` + ``X-Commit`` response headers so anyone
    inspecting traffic can immediately tell which container responded
    and which commit it was built from. The frontend mirrors this in
    its own middleware.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id

        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            log.info("http_request", elapsed_ms=elapsed_ms)
            structlog.contextvars.clear_contextvars()

        response.headers["x-request-id"] = request_id
        response.headers["x-service"] = _SERVICE_NAME
        response.headers["x-commit"] = _commit_sha()
        return response


async def platform_error_handler(_request: Request, exc: PlatformError) -> JSONResponse:
    """Translate domain exceptions into a stable JSON error envelope."""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def request_validation_error_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Translate request validation failures without echoing unsafe input."""

    details = {
        "errors": [
            {
                "type": str(error.get("type", "validation_error")),
                "loc": [str(item) for item in error.get("loc", [])],
                "message": str(error.get("msg", "Invalid request.")),
            }
            for error in exc.errors()
        ]
    }
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": details,
            }
        },
    )
