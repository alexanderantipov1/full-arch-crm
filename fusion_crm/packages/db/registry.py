"""Single import point that registers every domain model with ``Base.metadata``.

Alembic's ``env.py`` imports this module so that autogenerate sees ALL tables
across every domain. Add new domains here.
"""

from __future__ import annotations

# The imports have side effects (model class creation registers with metadata).
# noqa: F401 — intentional re-exports, do not remove.
from packages.actor import models as _actor_models  # noqa: F401
from packages.agent_runtime import models as _agent_runtime_models  # noqa: F401
from packages.analytics import models as _analytics_models  # noqa: F401
from packages.attribution import models as _attribution_models  # noqa: F401
from packages.audit import models as _audit_models  # noqa: F401
from packages.auth import models as _auth_models  # noqa: F401
from packages.catalog import models as _catalog_models  # noqa: F401
from packages.enrichment import models as _enrichment_models  # noqa: F401
from packages.identity import models as _identity_models  # noqa: F401
from packages.ingest import models as _ingest_models  # noqa: F401
from packages.insight import models as _insight_models  # noqa: F401
from packages.integrations import models as _integrations_models  # noqa: F401
from packages.interaction import models as _interaction_models  # noqa: F401
from packages.marketing import models as _marketing_models  # noqa: F401
from packages.ops import models as _ops_models  # noqa: F401
from packages.outreach import models as _outreach_models  # noqa: F401
from packages.phi import models as _phi_models  # noqa: F401
from packages.tenant import models as _tenant_models  # noqa: F401
