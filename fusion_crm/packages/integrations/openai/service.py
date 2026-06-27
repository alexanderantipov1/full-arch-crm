"""Service layer for OpenAI tenant integrations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.exceptions import ValidationError
from packages.core.types import TenantId
from packages.tenant.credential_service import IntegrationCredentialService

from .client import (
    OpenAIAgentHealthClient,
    OpenAIAgentPlanningClient,
    OpenAIManagerAnswerClient,
)
from .schemas import (
    OpenAIAgentPlanIn,
    OpenAIAgentPlanOut,
    OpenAIConnectionCheckOut,
    OpenAIManagerAnswerIn,
    OpenAIManagerAnswerOut,
)


class OpenAIIntegrationService:
    """Tenant-scoped OpenAI integration operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._credentials = IntegrationCredentialService(session)

    async def test_connection(self, tenant_id: TenantId) -> OpenAIConnectionCheckOut:
        """Read the tenant OpenAI API key and run a minimal agent check."""

        api_key = await self._read_api_key(tenant_id)
        return await OpenAIAgentHealthClient(api_key=api_key).test_connection()

    async def generate_agent_plan(
        self,
        tenant_id: TenantId,
        payload: OpenAIAgentPlanIn,
    ) -> OpenAIAgentPlanOut:
        """Read the tenant OpenAI API key and run a constrained planning turn."""

        api_key = await self._read_api_key(tenant_id)
        return await OpenAIAgentPlanningClient(api_key=api_key).generate_plan(payload)

    async def generate_manager_answer(
        self,
        tenant_id: TenantId,
        payload: OpenAIManagerAnswerIn,
    ) -> OpenAIManagerAnswerOut:
        """Read the tenant OpenAI API key and generate a safe manager answer."""

        api_key = await self._read_api_key(tenant_id)
        return await OpenAIManagerAnswerClient(api_key=api_key).generate_answer(payload)

    async def _read_api_key(self, tenant_id: TenantId) -> str:
        """Return the tenant OpenAI API key without exposing it to callers."""

        payload = await self._credentials.read_for(tenant_id, "openai", "api_key")
        api_key = payload.get("api_key")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValidationError(
                "OpenAI credential payload is missing api_key",
                details={"provider_kind": "openai", "credential_kind": "api_key"},
            )
        return api_key
