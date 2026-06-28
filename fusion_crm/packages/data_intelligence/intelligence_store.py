"""
fusion_crm — Intelligence Store

Local storage for anonymized patterns pushed by full-arch-crm's Karpathy wiki.
This is NOT the wiki — it is the persistence layer that stores patterns received
via the /api/v1/intelligence/* endpoints.

The Karpathy wiki and WikiService live in full-arch-crm.
fusion_crm simply stores patterns here so local agents (InsuranceCallAgent,
claim submission flow) can query them without calling back to full-arch-crm.

Architecture:
  full-arch-crm wiki  ──push──►  /api/v1/intelligence/ingest  ──►  IntelligenceStore (here)
  local InsuranceCallAgent  ──query──►  IntelligenceStore  (fast, local, no network hop)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Stored in wiki/ directory — JSON files per category
STORE_ROOT = Path(__file__).parent.parent.parent / "wiki"


class IntelligenceStore:
    """
    File-based local store for anonymized patterns received from full-arch-crm.
    In production, replace with DB table: intelligence_patterns.
    """

    def __init__(self, store_root: Optional[Path] = None):
        self.root = store_root or STORE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "insurance").mkdir(exist_ok=True)
        (self.root / "clinical").mkdir(exist_ok=True)
        (self.root / "appeals").mkdir(exist_ok=True)

    def _path(self, category: str, key: str) -> Path:
        safe_key = key.replace("/", "-").replace(" ", "_").lower()
        return self.root / category / f"{safe_key}.json"

    def _load(self, path: Path) -> dict:
        if path.exists():
            return json.loads(path.read_text())
        return {"patterns": [], "last_updated": None, "source_count": 0}

    def _save(self, path: Path, data: dict) -> None:
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(data, indent=2))

    # ── Insurance Patterns ─────────────────────────────────────────────────────

    def store_insurance_pattern(self, pattern: dict[str, Any]) -> None:
        """Store an anonymized insurance pattern (payer + CDT code approval rate)."""
        cdt = pattern.get("cdt_code", "unknown")
        payer = pattern.get("payer_type", "general")
        key = f"{payer}-{cdt}"
        path = self._path("insurance", key)
        data = self._load(path)

        # Keep the highest-sample-count version; append if new
        existing = next(
            (p for p in data["patterns"] if p.get("cdt_code") == cdt and p.get("payer_type") == payer),
            None,
        )
        if existing:
            if pattern.get("sample_count", 0) > existing.get("sample_count", 0):
                data["patterns"].remove(existing)
                data["patterns"].append(pattern)
                logger.info("INTELLIGENCE_STORE updated insurance pattern %s (n=%d)", key, pattern.get("sample_count"))
        else:
            data["patterns"].append(pattern)
            data["source_count"] = data.get("source_count", 0) + 1
            logger.info("INTELLIGENCE_STORE new insurance pattern %s (n=%d)", key, pattern.get("sample_count"))

        self._save(path, data)

    def query_insurance_patterns(
        self,
        cdt_code: Optional[str] = None,
        payer_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Query stored insurance patterns, optionally filtered by CDT code and payer."""
        results: list[dict] = []
        insurance_dir = self.root / "insurance"
        if not insurance_dir.exists():
            return results

        for f in insurance_dir.glob("*.json"):
            data = json.loads(f.read_text())
            for p in data.get("patterns", []):
                if cdt_code and p.get("cdt_code") != cdt_code:
                    continue
                if payer_type and p.get("payer_type") != payer_type:
                    continue
                results.append(p)

        return results

    # ── Documentation Tips ─────────────────────────────────────────────────────

    def store_documentation_tip(self, tip: dict[str, Any]) -> None:
        """Store a documentation tip for a CDT code."""
        cdt = tip.get("cdt_code", "unknown")
        path = self._path("clinical", f"doc-tips-{cdt}")
        data = self._load(path)
        data["patterns"].append(tip)
        data["source_count"] = data.get("source_count", 0) + 1
        self._save(path, data)
        logger.info("INTELLIGENCE_STORE doc tip for %s stored", cdt)

    def get_documentation_tips(self, cdt_code: str) -> list[dict[str, Any]]:
        path = self._path("clinical", f"doc-tips-{cdt_code}")
        if not path.exists():
            return []
        return json.loads(path.read_text()).get("patterns", [])

    # ── Appeal Templates ───────────────────────────────────────────────────────

    def store_appeal_template(self, template: dict[str, Any]) -> None:
        """Store a validated appeal letter template."""
        payer = template.get("payer_slug", "unknown")
        cdt = template.get("cdt_code", "unknown")
        key = f"{payer}-{cdt}"
        path = self._path("appeals", key)
        data = self._load(path)

        existing = next(
            (t for t in data["patterns"] if t.get("payer_slug") == payer and t.get("cdt_code") == cdt),
            None,
        )
        if existing:
            if template.get("success_rate", 0) > existing.get("success_rate", 0):
                data["patterns"].remove(existing)
                data["patterns"].append(template)
        else:
            data["patterns"].append(template)
            data["source_count"] = data.get("source_count", 0) + 1

        self._save(path, data)
        logger.info("INTELLIGENCE_STORE appeal template %s stored (success_rate=%.2f)", key, template.get("success_rate", 0))

    def get_appeal_template(
        self, payer_slug: str, cdt_code: str
    ) -> Optional[dict[str, Any]]:
        path = self._path("appeals", f"{payer_slug}-{cdt_code}")
        if not path.exists():
            return None
        patterns = json.loads(path.read_text()).get("patterns", [])
        # Return highest success rate template
        return max(patterns, key=lambda t: t.get("success_rate", 0)) if patterns else None

    # ── General Query ──────────────────────────────────────────────────────────

    def query(
        self,
        category: str,
        cdt_code: Optional[str] = None,
        payer_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """General query interface used by the API intelligence/query endpoint."""
        if category == "insurance":
            patterns = self.query_insurance_patterns(cdt_code=cdt_code, payer_type=payer_type)
        elif category == "clinical":
            patterns = self.get_documentation_tips(cdt_code) if cdt_code else []
        elif category == "appeal":
            if payer_type and cdt_code:
                t = self.get_appeal_template(payer_type, cdt_code)
                patterns = [t] if t else []
            else:
                patterns = []
        else:
            patterns = []

        # Derive confidence from sample counts
        max_n = max((p.get("sample_count", 0) for p in patterns), default=0)
        confidence = "low" if max_n < 4 else ("medium" if max_n < 10 else "high")

        return {
            "category": category,
            "patterns": patterns,
            "confidence": confidence,
            "source_count": len(patterns),
        }


# Module-level singleton
intelligence_store = IntelligenceStore()
