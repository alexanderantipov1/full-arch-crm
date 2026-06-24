"""GCP Secret Manager URL resolver for env-driven settings.

Any setting whose env value matches the form

    gcp-secret://<project>/<name>[/<version>]

is replaced by the underlying secret payload at startup. Plain values
pass through unchanged, so dev `.env` files keep working without GCP
credentials.

The resolver is invoked from `packages.core.config.Settings` via a
pre-validator. It MUST stay side-effect-free at import time (the
google-cloud-secret-manager dependency is optional via the `[secrets]`
extra and may not be installed in dev).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from google.cloud.secretmanager_v1 import SecretManagerServiceClient

SCHEME = "gcp-secret"
DEFAULT_VERSION = "latest"


def is_secret_url(value: object) -> bool:
    """True iff value is a string carrying a Secret Manager URL."""
    return isinstance(value, str) and value.startswith(f"{SCHEME}://")


def resolve(value: str) -> str:
    """Resolve a single ``gcp-secret://...`` URL to its payload.

    Format: ``gcp-secret://<project>/<name>[/<version>]``.
    Version defaults to ``latest`` when omitted.

    Raises:
        ValueError: malformed URL.
        RuntimeError: google-cloud-secret-manager not installed.
    """
    parsed = urlparse(value)
    if parsed.scheme != SCHEME:
        raise ValueError(f"Not a {SCHEME}:// URL: {value}")

    project = parsed.netloc
    parts = [p for p in parsed.path.split("/") if p]
    if not project or not parts:
        raise ValueError(
            f"Malformed {SCHEME}:// URL — expected "
            f"{SCHEME}://<project>/<name>[/<version>], got {value}"
        )
    name = parts[0]
    version = parts[1] if len(parts) > 1 else DEFAULT_VERSION

    client = _client()
    resource = f"projects/{project}/secrets/{name}/versions/{version}"
    response = client.access_secret_version(request={"name": resource})
    return response.payload.data.decode("utf-8")


def resolve_mapping(values: dict[str, object]) -> dict[str, object]:
    """Walk a settings input dict and resolve any secret URLs in place."""
    for key, value in list(values.items()):
        if is_secret_url(value):
            assert isinstance(value, str)  # narrowed by is_secret_url
            values[key] = resolve(value)
    return values


@lru_cache(maxsize=1)
def _client() -> SecretManagerServiceClient:
    """Lazy, cached client. Import is deferred so dev installs without
    the [secrets] extra do not need google-cloud-secret-manager."""
    try:
        from google.cloud.secretmanager_v1 import SecretManagerServiceClient
    except ImportError as exc:  # pragma: no cover — import-time failure
        raise RuntimeError(
            "google-cloud-secret-manager is not installed. "
            "Install with: pip install '.[secrets]'"
        ) from exc
    return SecretManagerServiceClient()
