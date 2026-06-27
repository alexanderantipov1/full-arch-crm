"""Domain-agnostic exception hierarchy.

Each layer of the platform raises strongly typed exceptions. The API layer
translates them into HTTP responses; the worker layer logs and retries.
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base for all platform errors. Never raise this directly."""

    code: str = "platform_error"
    http_status: int = 500

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(PlatformError):
    code = "not_found"
    http_status = 404


class ConflictError(PlatformError):
    code = "conflict"
    http_status = 409


class ValidationError(PlatformError):
    code = "validation_error"
    http_status = 422


class AuthorizationError(PlatformError):
    """Raised when a caller is not allowed to perform an action."""

    code = "forbidden"
    http_status = 403


class PHIAccessDeniedError(AuthorizationError):
    """Specific subclass for PHI access violations — must be auditable."""

    code = "phi_access_denied"


class IntegrationError(PlatformError):
    """External system failure (Salesforce, CareStack, GCS, ...)."""

    code = "integration_error"
    http_status = 502
