"""CareStack REST client (password grant, read-only).

Phase 1: credentials are read from env (mirrors the TypeScript flow in
``apps/web/lib/cs/auth.ts``). Each ``CareStackClient`` instance owns one
``httpx.AsyncClient`` (unless one is injected) and one cached
``CareStackTokens`` row.

ENG-125 will move credential storage to ``tenant.integration_credential``;
the public surface here (``get`` / ``list``) does not change — only the
factory that produces ``CareStackTokens`` does.

Parity with the TS client (``apps/web/lib/cs/client.ts``):

* Identical request headers (``Authorization``, ``VendorKey``,
  ``AccountKey``, ``AccountId``, ``Accept``).
* Identical token endpoint shape (POST form-urlencoded password grant
  to ``{idp_base}/connect/token``).
* On 401 → re-grant once → retry the original call.
* No persistence of the access token (it is in-memory per process,
  re-issued on demand). This is intentional for ENG-124 — DB-backed
  storage lands in ENG-125.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from packages.core.config import get_settings
from packages.core.logging import get_logger

from .exceptions import CareStackApiError, CareStackNotConnectedError

log = get_logger("integrations.carestack.client")

_DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
# Re-grant a token if it is within this many seconds of expiring.
_TOKEN_REFRESH_SKEW_SECONDS = 30


def _iso_utc(dt: datetime) -> str:
    """Render ``dt`` as the ISO-8601 UTC string CareStack accepts.

    Always emits seconds precision and a trailing ``Z``. Strips sub-second
    precision because the Sync APIs are documented at second granularity
    and some CareStack tenants reject fractional seconds.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


@dataclass(frozen=True)
class CareStackTokens:
    """A live CareStack access token + the AccountId header value.

    No ``refresh_token`` field: CareStack's password grant does not
    issue one. When ``expires_at`` is reached the client re-runs the
    password grant with the same credentials.
    """

    access_token: str
    token_type: str
    expires_at: datetime
    account_id: str


class CareStackClient:
    """Async CareStack REST client. One instance per request/job.

    Construct with ``CareStackClient.from_env()`` — the recommended
    factory in Phase 1. Tests inject ``http=`` and ``tokens=`` directly
    to avoid hitting the real network.
    """

    def __init__(
        self,
        *,
        idp_base_url: str,
        api_base_url: str,
        client_id: str,
        client_secret: str,
        vendor_key: str,
        account_key: str,
        account_id: str,
        http: httpx.AsyncClient | None = None,
        tokens: CareStackTokens | None = None,
    ) -> None:
        self._idp_base_url = idp_base_url.rstrip("/")
        self._api_base_url = api_base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._vendor_key = vendor_key
        self._account_key = account_key
        self._account_id = account_id
        self._http = http if http is not None else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        self._owns_http = http is None
        self._tokens: CareStackTokens | None = tokens

    # ------------------------------------------------------------------ factories

    @classmethod
    def from_credential(
        cls,
        payload: dict[str, Any],
        http: httpx.AsyncClient | None = None,
    ) -> CareStackClient:
        """Build from the decrypted credential payload (DB-backed).

        Expects the payload shape written by the
        ``tenant_credentials_seed`` migration / ``IntegrationCredentialService``
        upserts:

        .. code-block:: json

            {
              "client_id": "...",
              "client_secret": "...",
              "vendor_key": "...",
              "account_key": "...",
              "account_id": "...",
              "idp_base_url": "https://identity.carestack.com",
              "api_base_url": "https://api.carestack.com"
            }

        Optional ``api_version`` is currently ignored (the client hard-codes
        ``v1.0`` in resource paths). Raises ``CareStackNotConnectedError``
        if any required field is missing or empty so the FastAPI route
        translates to a 409 with a useful ``missing`` detail.
        """
        required = (
            "idp_base_url",
            "api_base_url",
            "client_id",
            "client_secret",
            "vendor_key",
            "account_key",
            "account_id",
        )
        missing = [k for k in required if not payload.get(k)]
        if missing:
            raise CareStackNotConnectedError(
                "carestack credential payload missing required fields",
                details={"missing": missing},
            )

        return cls(
            idp_base_url=str(payload["idp_base_url"]),
            api_base_url=str(payload["api_base_url"]),
            client_id=str(payload["client_id"]),
            client_secret=str(payload["client_secret"]),
            vendor_key=str(payload["vendor_key"]),
            account_key=str(payload["account_key"]),
            account_id=str(payload["account_id"]),
            http=http,
        )

    @classmethod
    def from_env(cls, http: httpx.AsyncClient | None = None) -> CareStackClient:
        """Build from ``Settings`` — the Phase 1 default.

        Raises ``CareStackNotConnectedError`` if any required env var
        is missing.
        """
        settings = get_settings()
        missing: list[str] = []

        def _need(value: str | None, env_name: str) -> str:
            if not value:
                missing.append(env_name)
                return ""
            return value

        def _need_secret(value: object, env_name: str) -> str:
            if value is None:
                missing.append(env_name)
                return ""
            secret = value.get_secret_value() if hasattr(value, "get_secret_value") else value
            if not secret:
                missing.append(env_name)
                return ""
            return str(secret)

        idp = _need(settings.carestack_idp_base_url, "CARESTACK_IDP_BASE_URL")
        api = _need(settings.carestack_api_base_url, "CARESTACK_API_BASE_URL")
        cid = _need(settings.carestack_client_id, "CARESTACK_CLIENT_ID")
        csec = _need_secret(settings.carestack_client_secret, "CARESTACK_CLIENT_SECRET")
        vkey = _need_secret(settings.carestack_vendor_key, "CARESTACK_VENDOR_KEY")
        akey = _need_secret(settings.carestack_account_key, "CARESTACK_ACCOUNT_KEY")
        aid = _need(settings.carestack_account_id, "CARESTACK_ACCOUNT_ID")

        if missing:
            raise CareStackNotConnectedError(
                "carestack credentials missing in environment",
                details={"missing_env": missing},
            )

        return cls(
            idp_base_url=idp,
            api_base_url=api,
            client_id=cid,
            client_secret=csec,
            vendor_key=vkey,
            account_key=akey,
            account_id=aid,
            http=http,
        )

    # ------------------------------------------------------------------ public

    async def get(
        self,
        path: str,
        query: dict[str, str | int] | None = None,
    ) -> Any:
        """GET ``{api_base}/<path>``. Refreshes token once on 401."""
        return await self._request_json("GET", path, query=query, attempt=0)

    async def list_locations(self) -> list[dict[str, Any]]:
        """Convenience wrapper for ``GET /api/v1.0/locations``.

        CareStack returns a JSON array directly. This method asserts
        the shape so the caller never has to defend against a single
        object or a wrapped envelope.
        """
        body = await self.get("api/v1.0/locations")
        if not isinstance(body, list):
            raise CareStackApiError(
                "carestack /locations returned non-array body",
                details={"type": type(body).__name__},
            )
        return body

    async def get_procedure_code(self, code_id: int | str) -> dict[str, Any]:
        """``GET /api/v1.0/procedure-codes/{id}`` — one procedure-code entry.

        ENG-538: the flat ``GET /api/v1.0/procedure-codes`` LIST endpoint is
        broken on the real account (it returns only a handful of junk "Other"
        codes and never the CDT codes that treatment procedures reference).
        The by-id endpoint, however, resolves every real entry — so the
        catalog is populated by resolving each needed ``procedureCodeId``
        individually through this method instead of trusting the list pull.

        Returns the CareStack Procedure Code object verbatim
        (``id`` / ``code`` / ``description`` / ``codeTypeId`` /
        ``cdtCategoryId``). Read-only; same auth / 401-retry behaviour as
        :meth:`get`. No PHI — procedure codes are reference data.
        """
        body = await self.get(f"api/v1.0/procedure-codes/{code_id}")
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /procedure-codes/{id} returned non-object body",
                details={"type": type(body).__name__, "code_id": str(code_id)},
            )
        return body

    async def list_providers(self) -> list[dict[str, Any]]:
        """Convenience wrapper for ``GET /api/v1.0/providers`` (ENG-308).

        Per ``docs/integrations/carestack/resources/providers.md`` the
        endpoint returns a flat unpaginated JSON array of provider
        records (clinician name, type, active flag, etc.). Same auth /
        retry behaviour as :meth:`list_locations`.
        """
        body = await self.get("api/v1.0/providers")
        if not isinstance(body, list):
            raise CareStackApiError(
                "carestack /providers returned non-array body",
                details={"type": type(body).__name__},
            )
        return body

    async def list_patients_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        """``GET /api/v1.0/sync/patients`` — patient feed modified after.

        Per ``docs/integrations/carestack/sync/patients.md``. Returns the
        CareStack envelope verbatim — typically
        ``{"patients": [...], "continueToken": "..."}`` (key names vary by
        endpoint version; the route layer is responsible for the operator
        UI shape). ``modified_since`` must be timezone-aware UTC.
        """
        query: dict[str, str | int] = {"pageSize": page_size}
        if continue_token is not None:
            query["continueToken"] = continue_token
        else:
            query["modifiedSince"] = _iso_utc(modified_since)
        body = await self.get("api/v1.0/sync/patients", query=query)
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /sync/patients returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def list_appointments_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        """``GET /api/v1.0/sync/appointments`` — appointment feed modified after.

        Per ``docs/integrations/carestack/sync/appointments.md``. Same
        contract as :meth:`list_patients_modified_since`.
        """
        query: dict[str, str | int] = {"pageSize": page_size}
        if continue_token is not None:
            query["continueToken"] = continue_token
        else:
            query["modifiedSince"] = _iso_utc(modified_since)
        body = await self.get("api/v1.0/sync/appointments", query=query)
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /sync/appointments returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def list_treatment_procedures_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        """``GET /api/v1.0/sync/treatment-procedures`` — treatment procedure feed.

        Per ``docs/integrations/carestack/sync/treatment-procedures.md``.
        Returns the CareStack envelope verbatim — typically
        ``{"results": [...], "continueToken": "..."}`` (key names vary by
        endpoint version). ``modified_since`` must be timezone-aware UTC.
        """
        query: dict[str, str | int] = {"pageSize": page_size}
        if continue_token is not None:
            query["continueToken"] = continue_token
        else:
            query["modifiedSince"] = _iso_utc(modified_since)
        body = await self.get("api/v1.0/sync/treatment-procedures", query=query)
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /sync/treatment-procedures returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def list_invoices_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        """``GET /api/v1.0/sync/invoices`` — invoice feed modified after.

        Per ``docs/integrations/carestack/sync/invoices.md``. Returns
        the CareStack envelope verbatim — typically
        ``{"results": [...], "continueToken": "..."}`` (key names vary by
        endpoint version). ``modified_since`` must be timezone-aware UTC.
        """
        query: dict[str, str | int] = {"pageSize": page_size}
        if continue_token is not None:
            query["continueToken"] = continue_token
        else:
            query["modifiedSince"] = _iso_utc(modified_since)
        body = await self.get("api/v1.0/sync/invoices", query=query)
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /sync/invoices returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def list_accounting_transactions_modified_since(
        self,
        modified_since: datetime,
        *,
        page_size: int = 100,
        continue_token: str | None = None,
    ) -> dict[str, Any]:
        """``GET /api/v1.0/sync/accounting-transactions`` — partial-payment ledger.

        Per ``docs/integrations/carestack/sync/accounting-transactions.md``.
        The CareStack spec emits next-page URLs prefixed with ``billing/``
        (``/api/v1.0/sync/billing/accounting-transactions?continueToken=...``)
        — that is the same endpoint as the base path. This client always
        issues the request against the canonical
        ``api/v1.0/sync/accounting-transactions`` path and just forwards
        ``continueToken`` as a query parameter, which CareStack accepts
        identically.

        Returns the CareStack envelope verbatim — typically
        ``{"accountingTransactions": [...], "continueToken": "..."}`` (key
        names vary by endpoint version). ``modified_since`` must be
        timezone-aware UTC.
        """
        query: dict[str, str | int] = {"pageSize": page_size}
        if continue_token is not None:
            query["continueToken"] = continue_token
        else:
            query["modifiedSince"] = _iso_utc(modified_since)
        body = await self.get(
            "api/v1.0/sync/accounting-transactions", query=query
        )
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /sync/accounting-transactions returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def get_payment_summary(self, patient_id: int | str) -> dict[str, Any]:
        """``GET /api/v1.0/billing/payment-summary/{patientId}`` — patient balances.

        Per ``docs/integrations/carestack/resources/payment-summary.md``.
        Returns the CareStack PaymentSummary object verbatim — financial
        balances (applied payments, outstanding balances, unapplied
        credits) keyed by ``patientId``. There is no bulk feed; callers
        iterate over linked CareStack patients.
        """
        body = await self.get(
            f"api/v1.0/billing/payment-summary/{patient_id}"
        )
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /billing/payment-summary/{id} returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def get_treatment_plans(
        self, patient_id: int | str
    ) -> list[dict[str, Any]]:
        """``GET /api/v1.0/patients/{patientId}/treatment-plans`` — patient plans.

        Per ``docs/integrations/carestack/resources/treatment-plans.md``. There
        is no bulk/sync feed — treatment plans are read per patient. CareStack's
        spec wording is ambiguous (object vs array); this method normalises both
        shapes to a list of plan dicts:

        * a bare JSON array -> returned as-is;
        * an envelope ``{"treatmentPlans"/"results"/"items"/...: [...]}`` ->
          the embedded list;
        * a single plan object (carries a ``TreatmentPlanId``) -> wrapped in a
          one-element list.

        The caller captures each plan verbatim to ``ingest.raw_event`` — no
        field filter (full-fidelity, invariant #11).
        """
        body = await self.get(f"api/v1.0/patients/{patient_id}/treatment-plans")
        if isinstance(body, list):
            return [row for row in body if isinstance(row, dict)]
        if isinstance(body, dict):
            for key in ("treatmentPlans", "results", "items", "records", "data"):
                value = body.get(key)
                if isinstance(value, list):
                    return [row for row in value if isinstance(row, dict)]
            # A single plan object returned directly.
            if any(
                k in body
                for k in ("TreatmentPlanId", "treatmentPlanId", "id")
            ):
                return [body]
            return []
        raise CareStackApiError(
            "carestack /patients/{id}/treatment-plans returned unexpected body",
            details={"type": type(body).__name__},
        )

    async def get_patient(self, patient_id: int | str) -> dict[str, Any]:
        """``GET /api/v1.0/patients/{patientId}`` — full Patient record.

        Returns the CareStack response as-is — every readable field for
        the patient including PHI. Used by the operator inspector "view
        full payload" path; never persisted. The route layer surfaces it
        verbatim under the local-dev inspector carve-out.
        """
        body = await self.get(f"api/v1.0/patients/{patient_id}")
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /patients/{id} returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def get_appointment(
        self, appointment_id: int | str
    ) -> dict[str, Any]:
        """``GET /api/v1.0/appointments/{AppointmentId}`` — full Appointment record."""
        body = await self.get(f"api/v1.0/appointments/{appointment_id}")
        if not isinstance(body, dict):
            raise CareStackApiError(
                "carestack /appointments/{id} returned non-object body",
                details={"type": type(body).__name__},
            )
        return body

    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> CareStackClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ private

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str | int] | None = None,
        attempt: int,
    ) -> Any:
        trimmed = path.lstrip("/")
        url = f"{self._api_base_url}/{trimmed}"

        tokens = await self._ensure_token()
        headers = self._auth_headers(tokens.access_token)
        params = {k: str(v) for k, v in (query or {}).items()}

        response = await self._http.request(method, url, headers=headers, params=params)

        if response.status_code == 401 and attempt == 0:
            log.info("carestack.401_regranting", path=trimmed)
            self._tokens = None  # force re-grant
            return await self._request_json(method, path, query=query, attempt=attempt + 1)

        if response.status_code == 401:
            raise CareStackNotConnectedError(
                "carestack 401 after token re-grant",
                details={"status": 401, "path": trimmed},
            )

        if response.status_code >= 400:
            raise CareStackApiError(
                f"carestack {method} {trimmed} failed: {response.status_code}",
                details={
                    "status": response.status_code,
                    "path": trimmed,
                    "body": response.text[:500],
                },
            )

        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover — malformed JSON is rare
            raise CareStackApiError(
                "carestack returned non-JSON body",
                details={"status": response.status_code, "path": trimmed},
            ) from exc

    async def _ensure_token(self) -> CareStackTokens:
        cached = self._tokens
        if cached is not None:
            cutoff = datetime.now(UTC) + timedelta(seconds=_TOKEN_REFRESH_SKEW_SECONDS)
            if cached.expires_at > cutoff:
                return cached
        return await self._issue_token()

    async def _issue_token(self) -> CareStackTokens:
        url = f"{self._idp_base_url}/connect/token"
        data = {
            "grant_type": "password",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "username": self._vendor_key,
            "password": self._account_key,
            "scope": "",
        }
        response = await self._http.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            raise CareStackNotConnectedError(
                f"carestack token issue failed: {response.status_code}",
                details={"status": response.status_code, "body": response.text[:500]},
            )

        body = response.json()
        access = body.get("access_token")
        token_type = body.get("token_type", "Bearer")
        expires_in = body.get("expires_in")
        if not access or not isinstance(expires_in, int):
            raise CareStackNotConnectedError(
                "carestack token response missing required fields",
                details={"keys": list(body.keys()) if isinstance(body, dict) else None},
            )

        tokens = CareStackTokens(
            access_token=access,
            token_type=token_type,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            account_id=self._account_id,
        )
        self._tokens = tokens
        log.info("carestack.token.issued", expires_in=expires_in)
        return tokens

    def _auth_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "VendorKey": self._vendor_key,
            "AccountKey": self._account_key,
            "AccountId": self._account_id,
            "Accept": "application/json",
        }
