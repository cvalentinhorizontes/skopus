"""skopus_record_drift — append a drift entry to the approval queue.

Drift entries do NOT modify live memory. They land in
~/.skopus/queue/drift/ as JSON files for /charter-evolve to review,
approve, and promote into a real feedback file (or reject)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

VALID_SOURCE = {
    "explicit-correction",
    "charter-evolve",
    "imported",
    "inferred",
}
VALID_CONFIDENCE = {"confirmed", "probable", "weak"}
VALID_SCOPE = {"user", "project", "team"}


async def skopus_record_drift(
    summary: str,
    source: str,
    confidence: str,
    scope: str = "user",
) -> dict:
    """Queue a drift record for /charter-evolve review.

    Validates source / confidence / scope before writing. Returns a
    `recorded` boolean and (on rejection) the valid value sets so the
    agent can retry.

    Returns:
        {"recorded": True, "id": <hex>, "queued_at": <path>}
        or {"recorded": False, "valid_source": [...]}
        or {"recorded": False, "valid_confidence": [...]}
        or {"recorded": False, "valid_scope": [...]}
    """
    if source not in VALID_SOURCE:
        return {"recorded": False, "valid_source": sorted(VALID_SOURCE)}
    if confidence not in VALID_CONFIDENCE:
        return {
            "recorded": False,
            "valid_confidence": sorted(VALID_CONFIDENCE),
        }
    if scope not in VALID_SCOPE:
        return {"recorded": False, "valid_scope": sorted(VALID_SCOPE)}

    skopus_dir = Path.home() / ".skopus"
    queue_dir = skopus_dir / "queue" / "drift"
    queue_dir.mkdir(parents=True, exist_ok=True)

    entry_id = uuid.uuid4().hex[:12]
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "id": entry_id,
        "summary": summary,
        "source": source,
        "confidence": confidence,
        "scope": scope,
        "captured_at": captured_at,
    }

    out = queue_dir / f"{captured_at[:10]}-{entry_id}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return {"recorded": True, "id": entry_id, "queued_at": str(out)}
